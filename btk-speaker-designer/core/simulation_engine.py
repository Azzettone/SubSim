"""
Motore di simulazione acustica completo per BTK Speaker Designer.

Integra in un unico pipeline:
  1. Risposta del driver (circuito equivalente T&S completo)
  2. Trasformazione d'impedenza e guadagno della tromba (Webster + transfer matrix)
  3. Perdite fluidodinamiche integrate lungo il profilo (Kirchhoff 1868)
  4. Check aberrazioni fisiche: turbolenza (Reynolds), nonlinearità (Goldberg),
     distorsione vortici (Lighthill), shock di compressione (Burgers)
  5. Risposta combinata in SPL assoluto, fase e impedenza elettrica caricata

Pipeline di calcolo:
--------------------
    DriverModel  →  [Z_motional]  →  [P_throat]  →  [Horn gain]
                                                           ↓
                                              [BL losses (Kirchhoff)]
                                                           ↓
                                          SPL_mouth  +  Phase  +  Z_electrical

Physical foundations:
---------------------
- Webster A.G. (1919) PNAS 5:275          — equazione d'onda tromba
- Klipsch P.W. (1941) JASA 13:137         — tractrix, riflessioni
- Salmon V. (1946) JASA 17:212            — Hypex, espansione generalizzata
- Beranek L.L. (1954) "Acoustics"         — impedenza, pistone circolare
- Olson H.F. (1957) "Acoustical Eng."     — vincoli sezioni, perdite
- Kirchhoff G. (1868) Ann.Phys. 134:177   — strato limite termoviscoso
- Reynolds O. (1883)                      — transizione laminare→turbolento
- Lighthill M.J. (1952)                   — rumore aerodinamico da vortici
- Goldberg Z.A. (1957)                    — nonlinearità acustica
- Hamilton & Blackstock (1998)            — Burgers, THD
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ─── Import moduli locali ────────────────────────────────────────────────────
from .constants import (
    SPEED_OF_SOUND, AIR_DENSITY,
    EXPANSION_EXPONENTIAL, EXPANSION_CONICAL,
    EXPANSION_TRACTRIX, EXPANSION_HYPEX,
    EPSILON,
)
from .horn_calculator import HornGeometry, HornSection, area_at_position
from .driver_model import DriverModel

# ─── Fluidodinamica (shared) ─────────────────────────────────────────────────
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from shared.fluid_acoustics import (
        RHO_AIR, C_AIR, MU_AIR, GAMMA_AIR, PR_AIR, BETA_AIR, P_REF,
        boundary_layer_attenuation,
        analyze_cross_section,
        goldberg_number,
        thd_nonlinear_ratio,
        reynolds_number,
        flow_regime,
    )
    _FLUID_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FLUID_AVAILABLE = False
    RHO_AIR = 1.225
    C_AIR   = 342.016
    MU_AIR  = 1.81e-5
    GAMMA_AIR = 1.4
    PR_AIR    = 0.707
    BETA_AIR  = 1.2
    P_REF     = 20e-6


# ─────────────────────────────────────────────────────────────────────────────
# DATACLASS: Risultato della simulazione
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SimulationResult:
    """
    Risultato completo della simulazione acustica.

    Tutti gli array hanno la stessa lunghezza di `frequencies`.
    """
    frequencies: np.ndarray             # Hz — asse frequenze

    # ── Risposta acustica ────────────────────────────────────────────────────
    spl_db: np.ndarray                  # dB SPL assoluto alla bocca (1 m, 1 W)
    phase_deg: np.ndarray               # ° — fase totale sistema
    group_delay_ms: np.ndarray          # ms — ritardo di gruppo = -dφ/dω

    # ── Guadagno tromba ──────────────────────────────────────────────────────
    horn_gain_db: np.ndarray            # dB — guadagno tromba vs free piston
    horn_phase_rad: np.ndarray          # rad — fase della tromba

    # ── Perdite fluidodinamiche ──────────────────────────────────────────────
    bl_loss_db: np.ndarray              # dB — perdite strato limite (Kirchhoff 1868)
    # integrato lungo il profilo; dipende dall'area media del profilo

    # ── Impedenza ────────────────────────────────────────────────────────────
    z_electrical: np.ndarray            # Ω — impedenza elettrica totale (modulo)
    z_electrical_complex: np.ndarray    # Ω complex — inclusa bobina + risonanza
    z_acoustic_throat: np.ndarray       # Pa·s/m³ — impedenza acustica alla gola
    z_acoustic_mouth: np.ndarray        # Pa·s/m³ — impedenza acustica alla bocca

    # ── Check aberrazioni fisiche ────────────────────────────────────────────
    warnings: List[str] = field(default_factory=list)
    # Ogni warning ha prefisso: "[TURBOLENZA]", "[NONLINEARE]", "[SHOCK]", "[RATIO]", "[VORTICI]"

    # ── Parametri derivati scalari (utili per status bar) ───────────────────
    throat_spl_peak_db: float = 0.0     # SPL massimo stimato alla gola
    reynolds_throat: float = 0.0        # Re alla gola (per check turbolenza)
    goldberg_throat: float = 0.0        # Γ alla gola (check nonlinearità)
    boundary_layer_loss_avg_db: float = 0.0  # perdita media BL su tutta banda
    thdx100_throat: float = 0.0         # THD% stimato alla gola (nonlineare)


# ─────────────────────────────────────────────────────────────────────────────
# FUNZIONI CORE — DRIVER
# ─────────────────────────────────────────────────────────────────────────────

def _driver_electrical_impedance(
    freqs: np.ndarray,
    driver: DriverModel,
) -> np.ndarray:
    """
    Impedenza elettrica complessa Z(f) del driver isolato.

    Circuito equivalente T&S completo:
        Z(f) = Re + jωLe + BL² / Z_mec(f)

    dove:
        Z_mec = Rms + j(ω·Mms − 1/(ω·Cms))
        BL²/Z_mec = impedenza motrice (motional impedance)

    Unità: Ω (complex)

    Rif: Thiele A.N. (1971) "Loudspeakers in Vented Boxes", Parts I–II
         Small R.H. (1973) JAES 21:363
         Beranek (1954) cap. 7
    """
    omega = 2.0 * np.pi * freqs
    omega_s = 2.0 * np.pi * driver.fs

    # Complianza meccanica Cms [m/N]
    mms_kg = driver.mms * 1e-3
    if driver.vas > 0 and driver.sd > 0:
        rho, c = RHO_AIR, C_AIR
        cms = (driver.vas * 1e-3) / (rho * c**2 * driver.sd**2)
    else:
        # Stima da definizione: ωs² = 1/(Mms·Cms)
        cms = 1.0 / (mms_kg * omega_s**2 + EPSILON)

    # Resistenza meccanica Rms [kg/s]
    rms = (omega_s * mms_kg) / max(driver.qms, EPSILON)

    # Impedenza meccanica Z_mec [N·s/m]
    z_mec = rms + 1j * (omega * mms_kg - 1.0 / (omega * cms + 1e-30))

    # Impedenza motrice Z_mot = BL² / Z_mec [Ω]
    z_mot = (driver.bl ** 2) / z_mec

    # Impedenza della bobina: Re + jωLe [Ω]
    z_coil = driver.re + 1j * omega * (driver.le * 1e-3)

    return z_coil + z_mot


def _driver_volume_velocity(
    freqs: np.ndarray,
    driver: DriverModel,
    voltage_rms: float = 2.83,   # V → equivalente 1 W su 8 Ω
    c: float = C_AIR,
    rho: float = RHO_AIR,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Velocità volumetrica U(f) del pistone [m³/s] e corrente I(f) [A].

    A partire dalla tensione sul morsetto e dal circuito equivalente:
        I(f) = V / Z_electrical(f)
        F(f) = BL · I(f)
        U(f) = F(f) / (Z_mec + Sd²·rho·c/S_throat)  × Sd

    Per semplicità (carico della tromba trattato nella sezione horn):
        U(f) = Sd · v_diaphragm
        v_diaphragm = BL·I / Z_mec   (senza back-load)

    Il carico acustico della tromba viene aggiunto in pipeline.

    Rif: Small (1973), Beranek (1954) cap. 7
    """
    omega = 2.0 * np.pi * freqs
    omega_s = 2.0 * np.pi * driver.fs

    mms_kg = driver.mms * 1e-3
    if driver.vas > 0 and driver.sd > 0:
        cms = (driver.vas * 1e-3) / (RHO_AIR * C_AIR**2 * driver.sd**2)
    else:
        cms = 1.0 / (mms_kg * (omega_s**2) + EPSILON)
    rms = (omega_s * mms_kg) / max(driver.qms, EPSILON)

    z_mec = rms + 1j * (omega * mms_kg - 1.0 / (omega * cms + 1e-30))
    z_coil = driver.re + 1j * omega * (driver.le * 1e-3)
    z_mot  = (driver.bl ** 2) / z_mec
    z_total = z_coil + z_mot

    current = voltage_rms / z_total
    force   = driver.bl * current
    v_diaphragm = force / z_mec   # m/s (complessa)
    u_volume = v_diaphragm * driver.sd   # m³/s

    return u_volume, current


# ─────────────────────────────────────────────────────────────────────────────
# FUNZIONI CORE — TROMBA (Webster Transfer Matrix)
# ─────────────────────────────────────────────────────────────────────────────

def _horn_pressure_gain(
    freqs: np.ndarray,
    horn: HornGeometry,
    c: float = C_AIR,
    rho: float = RHO_AIR,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Guadagno di pressione e fase della tromba calcolato con
    il metodo della matrice di trasferimento (TMM) per sezioni discrete.

    Per ogni sezione i → i+1 si usa la matrice:
        [p₂]   [cos(kl)         j·ρc/S·sin(kl)] [p₁]
        [U₂] = [j·S/(ρc)·sin(kl)   cos(kl)    ] [U₁]

    dove l = lunghezza sezione, S = area media sezione, k = ω/c.

    Alla bocca: carico di radiazione di pistone circolare:
        Z_rad = ρc/S_mouth · [R₁(2ka) + j·X₁(2ka)]
    dove R₁, X₁ ≈ Bessel/Struve functions.
    Per ka << 1: Z_rad ≈ ρc/S · (ka)²/2 + j·8ka/(3π)

    Prodotto delle matrici di tutte le sezioni → rapporto p_mouth/p_throat.

    Rif: Webster (1919), Beranek (1954) cap. 5, Olson (1957) cap. 6
    """
    sections = horn.sections
    if not sections:
        # Fallback: filtro passa-alto 2° ordine
        fc = horn.cutoff_frequency_hz
        ratio_sq = (fc / np.maximum(freqs, EPSILON))**2
        gain_db = np.where(freqs > fc, 10*np.log10(np.maximum(1e-12, 1.0-ratio_sq)), -60.0)
        phase   = np.where(freqs > fc, np.arctan2(horn.flare_rate_m, 2*2*np.pi*freqs/c), np.pi/2)
        return gain_db, phase

    # Costruisce array di sezioni: (x, S) incluso gola (0, S_throat)
    xs = np.array([0.0] + [s.x_m for s in sections])
    Ss = np.array([horn.throat_area_m2] + [s.area_m2 for s in sections])

    omega = 2.0 * np.pi * freqs  # (F,)
    k_arr = omega / c             # (F,)

    # Inizializza matrice prodotto: shape (F, 2, 2)
    nf = len(freqs)
    M = np.zeros((nf, 2, 2), dtype=complex)
    M[:, 0, 0] = 1.0
    M[:, 1, 1] = 1.0

    n_seg = len(xs) - 1
    for i in range(n_seg):
        S_avg = 0.5 * (Ss[i] + Ss[i+1])
        if S_avg < EPSILON:
            S_avg = EPSILON
        l = xs[i+1] - xs[i]
        if l <= 0.0:
            continue

        kl  = k_arr * l               # (F,)
        Zc  = rho * c / S_avg         # impedenza caratteristica sezione (F-indip.)

        cos_kl = np.cos(kl)
        sin_kl = np.sin(kl)

        # Matrice TMM sezione i: shape (F, 2, 2)
        Mi = np.zeros((nf, 2, 2), dtype=complex)
        Mi[:, 0, 0] = cos_kl
        Mi[:, 0, 1] = 1j * Zc * sin_kl
        Mi[:, 1, 0] = 1j / Zc * sin_kl
        Mi[:, 1, 1] = cos_kl

        # M = Mi @ M  per ogni frequenza
        M = np.einsum('fij,fjk->fik', Mi, M)

    # Carico di radiazione alla bocca: pistone circolare
    # Per ka << 1: Z_rad ≈ ρc/S_m · [(ka)²/2 + j·8ka/(3π)]
    # Per ka → ∞: Z_rad → ρc/S_m (resistenza pura)
    ka_mouth = k_arr * horn.mouth_radius_m
    Zm_char = rho * c / horn.mouth_area_m2
    # Levine & Schwinger (1948) approssimazione
    R1 = ka_mouth**2 / (2.0 + ka_mouth**2)            # da 0 a 1
    X1 = 8.0 * ka_mouth / (3.0 * np.pi * (1.0 + 0.77*ka_mouth))
    Z_rad = Zm_char * (R1 + 1j * X1)

    # Rapporto di trasferimento p_mouth/p_throat:
    # Sistema: p_mouth = M[0,0]*p_t + M[0,1]*U_t
    #          U_mouth = M[1,0]*p_t + M[1,1]*U_t
    # Condizione di bordo bocca: p_mouth = Z_rad · U_mouth
    # → p_t/U_t = (M[0,1] - Z_rad·M[1,1]) / (Z_rad·M[1,0] - M[0,0])
    # Guadagno p_mouth/p_throat:
    #   H = Z_rad / (Z_rad·M[1,0] - M[0,0]) * ... (complessa)
    # Forma compatta (source = volume velocity U₀ all'ingresso):
    #   p_throat = M[0,0]·p_mouth/Z_rad·M[1,0] + M[0,1]·U_mouth ... si semplifica a:
    # Usiamo direttamente:
    #   Zin = (M[0,0]*Z_rad + M[0,1]) / (M[1,0]*Z_rad + M[1,1])
    #   Guadagno pressione alla bocca = Z_rad / (Z_rad·M[1,0] + M[1,1])
    # NOTE: il fattore di guadagno SPL della tromba rispetto al pistone libero è:
    #   G = 20·log10(|Z_rad·Sqrt(S_m)|/|Z_throat·Sqrt(S_t)|) + boundary gain

    denom = M[:, 1, 0] * Z_rad + M[:, 1, 1]
    # Pressione relativa alla bocca (normalizzata a 1 U₀ all'ingresso)
    H_transfer = Z_rad / denom  # (F,) complex

    # Guadagno in dB e fase
    gain_db = 20.0 * np.log10(np.maximum(np.abs(H_transfer), 1e-12))
    phase   = np.angle(H_transfer)

    return gain_db, phase


def _horn_input_impedance(
    freqs: np.ndarray,
    horn: HornGeometry,
    c: float = C_AIR,
    rho: float = RHO_AIR,
) -> np.ndarray:
    """
    Impedenza acustica all'ingresso della tromba (alla gola) Z_in(f) [Pa·s/m³].

    Usa lo stesso TMM di _horn_pressure_gain.

    La tromba modifica l'impedenza vista dal driver rispetto al pistone libero:
        Z_in_horn vs Z_in_piston = rho·c / S_t

    Rif: Beranek (1954) cap. 5, Olson (1957)
    """
    sections = horn.sections
    if not sections:
        return np.full(len(freqs), horn.throat_impedance, dtype=complex)

    xs = np.array([0.0] + [s.x_m for s in sections])
    Ss = np.array([horn.throat_area_m2] + [s.area_m2 for s in sections])

    omega = 2.0 * np.pi * freqs
    k_arr = omega / c
    nf    = len(freqs)

    M = np.zeros((nf, 2, 2), dtype=complex)
    M[:, 0, 0] = 1.0
    M[:, 1, 1] = 1.0

    for i in range(len(xs) - 1):
        S_avg = 0.5 * (Ss[i] + Ss[i+1])
        if S_avg < EPSILON:
            S_avg = EPSILON
        l = xs[i+1] - xs[i]
        if l <= 0.0:
            continue
        kl  = k_arr * l
        Zc  = rho * c / S_avg
        cos_kl = np.cos(kl)
        sin_kl = np.sin(kl)
        Mi = np.zeros((nf, 2, 2), dtype=complex)
        Mi[:, 0, 0] = cos_kl
        Mi[:, 0, 1] = 1j * Zc * sin_kl
        Mi[:, 1, 0] = 1j / Zc * sin_kl
        Mi[:, 1, 1] = cos_kl
        M = np.einsum('fij,fjk->fik', Mi, M)

    ka_mouth = k_arr * horn.mouth_radius_m
    Zm_char  = rho * c / horn.mouth_area_m2
    R1 = ka_mouth**2 / (2.0 + ka_mouth**2)
    X1 = 8.0 * ka_mouth / (3.0 * np.pi * (1.0 + 0.77*ka_mouth))
    Z_rad = Zm_char * (R1 + 1j * X1)

    # Z_in = (M[0,0]·Z_rad + M[0,1]) / (M[1,0]·Z_rad + M[1,1])
    Z_in = (M[:, 0, 0] * Z_rad + M[:, 0, 1]) / (M[:, 1, 0] * Z_rad + M[:, 1, 1])
    return Z_in


# ─────────────────────────────────────────────────────────────────────────────
# FUNZIONI CORE — PERDITE FLUIDODINAMICHE INTEGRATE
# ─────────────────────────────────────────────────────────────────────────────

def _integrated_boundary_layer_loss(
    freqs: np.ndarray,
    horn: HornGeometry,
    n_points: int = 40,
    c: float = C_AIR,
    rho: float = RHO_AIR,
    mu: float = MU_AIR,
    gamma: float = GAMMA_AIR,
    pr: float = PR_AIR,
) -> np.ndarray:
    """
    Perdite termoviscose integrate lungo il profilo della tromba [dB].

    Per ogni sezione del profilo calcola α(f, r) secondo Kirchhoff (1868):
        α(f, r) = (1/r) · √(ω·ρ/(2μ)) · (1 + (γ-1)/√Pr)    [Np/m]

    Poi integra numericamente:
        Loss(f) = 2 · ∫₀ᴸ α(f, r(x)) dx   [Np]   × 8.686 → [dB]

    Il fattore 2 è perché le perdite BL agiscono su entrambe le pareti del
    canale acustico (propagazione bidirezionale verso le pareti).

    Valida per ka << 1 (regime sub-wavelength in ogni sezione).
    Rilevante in gole strette di compression driver e porte bass-reflex.
    Trascurabile per grandi aperture (r > 5 cm a frequenze sub-200 Hz).

    Rif: Kirchhoff G. (1868) Ann.Phys. 134:177
         Beranek L.L. (1954) "Acoustics" cap.3
    """
    if not _FLUID_AVAILABLE:
        return np.zeros(len(freqs))

    # Costruisce profilo r(x) del horn
    if horn.sections:
        xs = np.array([0.0] + [s.x_m for s in horn.sections])
        rs = np.array([horn.throat_radius_m] + [s.radius_m for s in horn.sections])
    else:
        # Profilo sintetico con n_points
        xs = np.linspace(0.0, horn.horn_length_m, n_points)
        rs = np.array([
            np.sqrt(area_at_position(
                x, horn.throat_area_m2, horn.flare_rate_m,
                horn.expansion_type, horn.hypex_T
            ) / np.pi)
            for x in xs
        ])

    # Integrazione: per ogni frequenza, integra α lungo x
    omega = 2.0 * np.pi * freqs  # (F,)
    losses_nepers = np.zeros(len(freqs))

    for i in range(len(xs) - 1):
        r_avg = 0.5 * (rs[i] + rs[i+1])
        if r_avg < 1e-4:  # < 0.1 mm — evita singolarità
            r_avg = 1e-4
        dx = xs[i+1] - xs[i]
        if dx <= 0.0:
            continue

        # α(f) per questo segmento: vettorizzato su freq
        visc_term  = np.sqrt(omega * rho / (2.0 * mu + EPSILON))
        therm_term = (gamma - 1.0) / (pr ** 0.5)
        alpha = (1.0 / r_avg) * visc_term * (1.0 + therm_term)   # Np/m

        losses_nepers += alpha * dx

    # ×2 (parete) e converti Np→dB
    total_loss_db = losses_nepers * 2.0 * 8.686
    return total_loss_db   # shape (F,), sempre ≥ 0


# ─────────────────────────────────────────────────────────────────────────────
# FUNZIONI CORE — CHECK ABERRAZIONI FISICHE
# ─────────────────────────────────────────────────────────────────────────────

def _check_physical_aberrations(
    horn: HornGeometry,
    driver: DriverModel,
    input_power_w: float = 1.0,
) -> Tuple[float, float, float, float, List[str]]:
    """
    Controlla le possibili aberrazioni fisiche del design.

    Ritorna:
        (reynolds_throat, goldberg_throat, thd_pct, throat_spl_db, warnings)

    Warnings generati:
      [TURBOLENZA]   Re > 2300 alla gola o bocca
      [NONLINEARE]   Γ (Goldberg) > 0.1 alla gola
      [SHOCK]        Distanza formazione shock < lunghezza tromba
      [RATIO]        Rapporto area sezioni adiacenti > 4 (Olson 1957)
      [VORTICI]      Frequenza vortici nel range udibile (Lighthill 1952)
    """
    warnings_list: List[str] = []
    rho, c = RHO_AIR, C_AIR

    # SPL stimato alla gola per 1 W di ingresso
    # SPL_input = sensibilità + 10·log10(P) + guadagno_tromba_medio
    horn_boundary_gain = 6.0  # half-space default (parete)
    throat_spl_db = driver.spl_1w_1m + 10*np.log10(max(input_power_w, EPSILON)) + horn_boundary_gain

    re_t = 0.0
    gold_t = 0.0
    thd_pct = 0.0

    if _FLUID_AVAILABLE:
        # Reynolds alla gola
        p_throat = 20e-6 * 10**(throat_spl_db / 20.0)
        v_throat  = p_throat / (rho * c)
        re_t = reynolds_number(v_throat, horn.throat_diameter_m)
        regime = flow_regime(re_t)

        if regime == "turbulent":
            warnings_list.append(
                f"[TURBOLENZA] Gola: Re = {re_t:.0f} > 4000 — rischio chuffing. "
                f"Aumenta area gola o riduci potenza."
            )
        elif regime == "transitional":
            warnings_list.append(
                f"[TURBOLENZA] Gola: Re = {re_t:.0f} in transizione (2300–4000). "
                f"Monitorare con potenza piena."
            )

        # Reynolds alla bocca
        p_mouth = p_throat * (horn.throat_area_m2 / max(horn.mouth_area_m2, EPSILON))**0.5
        v_mouth  = p_mouth / (rho * c)
        re_m = reynolds_number(v_mouth, horn.mouth_radius_m * 2)
        if flow_regime(re_m) == "turbulent":
            warnings_list.append(
                f"[TURBOLENZA] Bocca: Re = {re_m:.0f} > 4000."
            )

        # Goldberg number (non-linearità) — path = lunghezza tromba
        gold_t = goldberg_number(throat_spl_db, 100.0, horn.horn_length_m)
        if gold_t > 1.0:
            warnings_list.append(
                f"[NONLINEARE] Γ = {gold_t:.2f} > 1 alla gola @ 100 Hz — "
                f"distorsione armonica significativa."
            )
        elif gold_t > 0.1:
            warnings_list.append(
                f"[NONLINEARE] Γ = {gold_t:.2f} > 0.1 — effetti non-lineari percepibili "
                f"ad alto volume."
            )

        # THD stimato
        thd = thd_nonlinear_ratio(throat_spl_db, 100.0, horn.horn_length_m)
        thd_pct = thd * 100.0
        if thd_pct > 3.0:
            warnings_list.append(
                f"[THD] Distorsione acustica stimata ~{thd_pct:.1f}% alla gola."
            )

        # Distanza formazione shock
        try:
            from shared.fluid_acoustics import shock_formation_distance
            d_shock = shock_formation_distance(throat_spl_db, 100.0)
            if d_shock < horn.horn_length_m:
                warnings_list.append(
                    f"[SHOCK] Formazione shock a {d_shock*100:.1f} cm < lunghezza tromba "
                    f"({horn.horn_length_m*100:.1f} cm). SPL troppo alto per questa geometria."
                )
        except Exception:
            pass

    # Controllo rapporto sezioni adiacenti (Olson 1957)
    if horn.sections and len(horn.sections) > 1:
        areas = [horn.throat_area_m2] + [s.area_m2 for s in horn.sections]
        for i in range(len(areas) - 1):
            if areas[i] > EPSILON:
                ratio = areas[i+1] / areas[i]
                if ratio > 4.0:
                    warnings_list.append(
                        f"[RATIO] Sezione {i+1}→{i+2}: rapporto area {ratio:.1f} > 4.0 "
                        f"(Olson 1957) — riflessioni interne."
                    )
                    break  # un solo warning per non spammare

    return re_t, gold_t, thd_pct, throat_spl_db, warnings_list


# ─────────────────────────────────────────────────────────────────────────────
# FUNZIONE PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

def simulate(
    horn: HornGeometry,
    driver: DriverModel,
    frequencies: Optional[np.ndarray] = None,
    input_power_w: float = 1.0,
    voltage_rms: Optional[float] = None,
    c: float = C_AIR,
    rho: float = RHO_AIR,
) -> SimulationResult:
    """
    Simula risposta completa del sistema driver + tromba.

    Pipeline:
        1. Calcola U(f) e I(f) del driver con circuito equivalente T&S
        2. Calcola guadagno di pressione H(f) della tromba (TMM)
        3. Calcola perdite di strato limite α(f) lungo il profilo (Kirchhoff)
        4. Calcola SPL assoluto alla bocca (riferimento 1 W / 1 m)
        5. Calcola impedenza elettrica con back-load della tromba
        6. Controlla aberrazioni fisiche e genera warnings

    Args:
        horn:           Geometria tromba (HornGeometry)
        driver:         Parametri driver (DriverModel)
        frequencies:    Array Hz (default: 40 punti/ottava 20–20000 Hz)
        input_power_w:  Potenza di ingresso in W (per check aberrazioni)
        voltage_rms:    Tensione RMS alternativa a input_power_w
        c:              Velocità del suono [m/s]
        rho:            Densità aria [kg/m³]

    Returns:
        SimulationResult con SPL, fase, impedenza e warnings fisici.
    """
    if frequencies is None:
        frequencies = np.logspace(np.log10(20), np.log10(20000), 400)

    # ── Tensione equivalente ──────────────────────────────────────────────
    if voltage_rms is None:
        # V = sqrt(P · Re) — riferimento 1 W sull'impedenza nominale
        voltage_rms = np.sqrt(input_power_w * max(driver.re, 1.0))

    # ── Step 1: Volume velocity e corrente del driver ─────────────────────
    U_volume, current = _driver_volume_velocity(frequencies, driver, voltage_rms, c, rho)

    # ── Step 2: Risposta e impedenza acustica della tromba (TMM) ──────────
    horn_gain_db, horn_phase_rad = _horn_pressure_gain(frequencies, horn, c, rho)
    Z_acoustic_in  = _horn_input_impedance(frequencies, horn, c, rho)
    Z_acoustic_mouth = np.full(len(frequencies), rho * c / horn.mouth_area_m2)

    # ── Step 3: Perdite strato limite integrate ───────────────────────────
    bl_loss_db = _integrated_boundary_layer_loss(frequencies, horn, c=c, rho=rho)

    # ── Step 4: SPL assoluto alla bocca ───────────────────────────────────
    # Pressione alla gola da U e Z_in:  p_throat = Z_in · U
    p_throat_complex = Z_acoustic_in * U_volume
    pressure_throat_pa = np.abs(p_throat_complex)

    # SPL alla gola
    spl_throat = 20.0 * np.log10(np.maximum(pressure_throat_pa, P_REF) / P_REF)

    # Guadagno tromba → SPL alla bocca
    # Correzione: il gain TMM è già riferito al volume velocity → pressione bocca
    # SPL_mouth = SPL_throat + horn_gain_db − bl_loss_db
    spl_mouth = spl_throat + horn_gain_db - bl_loss_db

    # Normalizzazione di riferimento:
    # La sensibilità del driver è già calibrata come 1W/1m in campo libero.
    # Il motore T&S produce pressioni assolute; normalizziamo sul valore
    # a 1 kHz per ancorarlo alla sensibilità dichiarata.
    ref_freq_idx = np.argmin(np.abs(frequencies - 1000.0))
    # Offset per ancorare SPL_1kHz al valore calibrato del driver
    # (include il guadagno della tromba medio intorno a 1 kHz)
    spl_cal_target = driver.spl_1w_1m + horn_gain_db[ref_freq_idx]
    spl_offset = spl_cal_target - spl_mouth[ref_freq_idx]
    spl_absolute = spl_mouth + spl_offset

    # ── Step 5: Fase totale ───────────────────────────────────────────────
    phase_total_rad = np.angle(p_throat_complex) + horn_phase_rad
    phase_total_deg = np.degrees(phase_total_rad)
    # Unwrap per visualizzazione
    phase_total_deg = np.degrees(np.unwrap(phase_total_rad))

    # ── Ritardo di gruppo ─────────────────────────────────────────────────
    # τ_g(f) = -dφ/dω   [s], converti in ms
    dphi_dof = np.gradient(np.unwrap(phase_total_rad), 2.0 * np.pi * frequencies)
    group_delay_ms = -dphi_dof * 1000.0

    # ── Step 6: Impedenza elettrica modificata dal carico tromba ──────────
    # Z_e(f) = Z_coil + Z_mot_loaded
    # Il carico acustico Z_in modifica la back-EMF equivalente:
    # Z_acoustic_load_electrical = BL² · Sd² / Z_acoustic_in  (referred to electrical)
    omega = 2.0 * np.pi * frequencies
    mms_kg = driver.mms * 1e-3
    omega_s = 2.0 * np.pi * driver.fs
    if driver.vas > 0 and driver.sd > 0:
        cms = (driver.vas * 1e-3) / (RHO_AIR * C_AIR**2 * driver.sd**2)
    else:
        cms = 1.0 / (mms_kg * omega_s**2 + EPSILON)
    rms = (omega_s * mms_kg) / max(driver.qms, EPSILON)

    z_mec = rms + 1j * (omega * mms_kg - 1.0 / (omega * cms + 1e-30))
    # Con carico tromba: Z_mec_loaded = Z_mec + Sd²·Z_acoustic_in
    z_mec_loaded = z_mec + driver.sd**2 * Z_acoustic_in
    z_mot_loaded = (driver.bl**2) / z_mec_loaded
    z_coil = driver.re + 1j * omega * (driver.le * 1e-3)
    z_electrical_complex = z_coil + z_mot_loaded
    z_electrical_mag = np.abs(z_electrical_complex)

    # ── Step 7: Check aberrazioni fisiche ─────────────────────────────────
    re_t, gold_t, thd_pct, throat_spl, aberr_warnings = _check_physical_aberrations(
        horn, driver, input_power_w
    )

    # ── BL loss media sulla banda passante ────────────────────────────────
    passband = frequencies > horn.cutoff_frequency_hz
    bl_loss_avg = float(np.mean(bl_loss_db[passband])) if np.any(passband) else float(np.mean(bl_loss_db))

    return SimulationResult(
        frequencies          = frequencies,
        spl_db               = spl_absolute,
        phase_deg            = phase_total_deg,
        group_delay_ms       = group_delay_ms,
        horn_gain_db         = horn_gain_db,
        horn_phase_rad       = horn_phase_rad,
        bl_loss_db           = bl_loss_db,
        z_electrical         = z_electrical_mag,
        z_electrical_complex = z_electrical_complex,
        z_acoustic_throat    = np.abs(Z_acoustic_in),
        z_acoustic_mouth     = Z_acoustic_mouth,
        warnings             = aberr_warnings,
        throat_spl_peak_db   = throat_spl,
        reynolds_throat      = re_t,
        goldberg_throat      = gold_t,
        boundary_layer_loss_avg_db = bl_loss_avg,
        thdx100_throat       = thd_pct,
    )


def simulate_from_custom_sections(
    horn: HornGeometry,
    driver: DriverModel,
    custom_sections: List[HornSection],
    frequencies: Optional[np.ndarray] = None,
    input_power_w: float = 1.0,
    c: float = C_AIR,
    rho: float = RHO_AIR,
) -> SimulationResult:
    """
    Simula con sezioni custom (da drag interattivo nel plot 2D).

    Crea una HornGeometry temporanea con le sezioni modificate,
    ricalcola la lunghezza e la frequenza di taglio effettiva
    dalla nuova geometria, poi chiama simulate().

    Questo è il bridge tra la modifica grafica dei punti di sezione
    e il motore di simulazione.
    """
    import copy
    horn_custom = copy.copy(horn)
    horn_custom.sections = list(custom_sections)

    # Aggiorna area bocca dalla ultima sezione custom
    if custom_sections:
        last = custom_sections[-1]
        horn_custom.mouth_area_m2 = last.area_m2
        horn_custom.horn_length_m = last.x_m

    return simulate(horn_custom, driver, frequencies, input_power_w, c=c, rho=rho)
