"""
Fluidodinamica applicata al design acustico.

Modulo condiviso tra SubSim e BTK Speaker Designer.

Contiene:
- Analisi regime di flusso (Reynolds, turbolenza)
- Perdite strato limite termoviscoso (Kirchhoff 1868)
- Acustica non-lineare: formazione shock, THD (Burgers / Goldberg)
- Distacco vortici (Strouhal)
- Analisi sezione di tromba o porta bass-reflex

IMPORTANTE — errori comuni da evitare
--------------------------------------
1. La formula `α = (δ_v + δ_t) / (2r²)` ha dimensioni ERRATE.
   La formula corretta (Kirchhoff 1868) è:
       α [Np/m] = (1/r) · √(ωρ/(2μ)) · (1 + (γ-1)/√Pr)

2. `r(x) = a/cosh(...)` descrive una CATENARIA, NON la tractrix.
   La tractrix vera richiede inversione parametrica (arccosh — vedi horn_calculator.py).

Riferimenti primari
-------------------
- Kirchhoff G. (1868) Ann.Phys. 134:177  — strato limite termoviscoso
- Beranek L.L. (1954) "Acoustics" cap.3  — perdite in tubi
- Reynolds O. (1883) Phil.Trans.R.Soc. 174:935 — transizione laminare→turbolento
- Lighthill M.J. (1952) Proc.R.Soc.A 211:564 — analogia aerodinamica (vortici)
- Hamilton & Blackstock (1998) "Nonlinear Acoustics" (ASA) — Burgers, Goldberg
- Goldberg Z.A. (1957) Sov.Phys.Acoust. 3:340 — numero di Goldberg
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Union

import numpy as np

# ── Costanti fisiche aria standard (20 °C, 101325 Pa) ───────────────────────
RHO_AIR   = 1.225       # kg/m³
C_AIR     = 342.016     # m/s
MU_AIR    = 1.81e-5     # Pa·s (viscosità dinamica)
NU_AIR    = 1.48e-5     # m²/s (viscosità cinematica = μ/ρ)
GAMMA_AIR = 1.4         # rapporto calori specifici
PR_AIR    = 0.707       # numero di Prandtl
KAPPA_AIR = 0.0257      # W/(m·K) conducibilità termica
CP_AIR    = 1005.0      # J/(kg·K) calore specifico a pressione costante
P_REF     = 20e-6       # Pa (soglia di udibilità)
BETA_AIR  = 1.2         # coefficiente di non-linearità aria (β = 1 + B/2A)


# ─────────────────────────────────────────────────────────────────────────────
# 1. FUNZIONI BASE
# ─────────────────────────────────────────────────────────────────────────────

def particle_velocity(
    spl_db: Union[float, np.ndarray],
    rho: float = RHO_AIR,
    c: float = C_AIR,
) -> Union[float, np.ndarray]:
    """
    Velocità picco delle particelle d'aria da SPL.

        v = p / (ρ · c)     con p = p_ref · 10^(SPL/20)

    Args:
        spl_db: Livello di pressione sonora (dB SPL)
        rho:    Densità aria (kg/m³)
        c:      Velocità del suono (m/s)

    Returns:
        Velocità delle particelle [m/s]

    Note:
        A 120 dB SPL → v ≈ 0.082 m/s (regime lineare, v << c).
        A 140 dB SPL → v ≈ 8.2 m/s → Mach acustico ≈ 0.024 (non-lineare).

    Rif: Beranek (1954) cap.2
    """
    p_peak = P_REF * 10.0 ** (np.asarray(spl_db, dtype=float) / 20.0)
    return p_peak / (rho * c)


def acoustic_mach(
    spl_db: Union[float, np.ndarray],
    rho: float = RHO_AIR,
    c: float = C_AIR,
) -> Union[float, np.ndarray]:
    """
    Numero di Mach acustico (v/c).

    Mach < 0.001 → regime lineare (< ~124 dB).
    Mach > 0.01  → effetti non-lineari significativi (> ~144 dB).
    """
    return particle_velocity(spl_db, rho, c) / c


# ─────────────────────────────────────────────────────────────────────────────
# 2. ANALISI REGIME DI FLUSSO (Reynolds)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FlowAnalysis:
    """Risultato analisi flusso in una sezione."""
    velocity_ms: float
    diameter_m: float
    reynolds: float
    regime: str           # "laminar" | "transitional" | "turbulent"
    vortex_freq_hz: float
    vortex_spl_db: float  # SPL aggiuntivo da rumore di vortici (Lighthill)
    warning: str = ""


def reynolds_number(
    velocity_ms: float,
    diameter_m: float,
    rho: float = RHO_AIR,
    mu: float = MU_AIR,
) -> float:
    """
    Re = ρ · v · D / μ

    Soglie:
      Re < 2300  → laminare
      2300–4000  → transizione
      Re > 4000  → turbolento (rischio chuffing/rumore)

    Rif: Reynolds O. (1883) Phil.Trans.R.Soc. 174:935
    """
    return rho * velocity_ms * diameter_m / mu


def flow_regime(re: float) -> str:
    if re < 2300:
        return "laminar"
    if re < 4000:
        return "transitional"
    return "turbulent"


def vortex_shedding_frequency(
    velocity_ms: float,
    diameter_m: float,
    strouhal: float = 0.21,
) -> float:
    """
    Frequenza di distacco vortici: f_v = St · v / D

    St ≈ 0.21 per geometrie cilindriche (Strouhal 1878).
    Rilevante per porte bass-reflex e gole di compression driver.

    Rif: Lighthill M.J. (1952) Proc.R.Soc.A 211:564
    """
    if velocity_ms < 1e-12:
        return 0.0
    return strouhal * velocity_ms / diameter_m


def vortex_sound_power_watts(
    velocity_ms: float,
    diameter_m: float,
    rho: float = RHO_AIR,
    c: float = C_AIR,
) -> float:
    """
    Potenza acustica irradiata dai vortici (analogia di Lighthill).

        P ∝ ρ · v⁶ · D² / c⁵

    Scala con la sesta potenza della velocità: a bassi SPL trascurabile,
    rilevante per porte ad alta escursione (> 10 m/s) o gole CD ad alto SPL.

    Rif: Lighthill (1952), Powell A. (1964) JASA 36:177
    """
    return 1e-5 * rho * velocity_ms ** 6 * diameter_m ** 2 / c ** 5


def analyze_cross_section(
    diameter_m: float,
    spl_db: float,
    frequency: float = 100.0,
    rho: float = RHO_AIR,
    mu: float = MU_AIR,
    c: float = C_AIR,
) -> FlowAnalysis:
    """
    Analisi fluidodinamica completa di una sezione (porta o gola tromba).

    Args:
        diameter_m:  Diametro idraulico della sezione [m]
        spl_db:      SPL stimato in quella sezione [dB]
        frequency:   Frequenza di lavoro [Hz]

    Returns:
        FlowAnalysis con velocità, Reynolds, regime, vortici.

    Uso tipico:
        - Porta bass-reflex: diameter_m = diametro porta
        - Gola tromba: diameter_m = diametro gola
        - Gola CD: diameter_m = diametro gola (es. 0.0254 m per 1")
    """
    v = particle_velocity(spl_db, rho, c)
    re = reynolds_number(v, diameter_m, rho, mu)
    regime = flow_regime(re)
    f_v = vortex_shedding_frequency(v, diameter_m)
    p_v = vortex_sound_power_watts(v, diameter_m, rho, c)
    spl_v = 10.0 * math.log10(p_v / 1e-12) if p_v > 1e-30 else -999.0

    warning = ""
    if regime == "turbulent":
        warning = (
            f"⚠ Flusso TURBOLENTO (Re={re:.0f}): rischio chuffing/rumore. "
            f"Vortici a {f_v:.0f} Hz (+{spl_v:.1f} dB)."
        )
    elif regime == "transitional":
        warning = f"⚠ Flusso in TRANSIZIONE (Re={re:.0f}): monitorare."

    return FlowAnalysis(
        velocity_ms=v,
        diameter_m=diameter_m,
        reynolds=re,
        regime=regime,
        vortex_freq_hz=f_v,
        vortex_spl_db=spl_v,
        warning=warning,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. PERDITE STRATO LIMITE TERMOVISCOSO (Kirchhoff 1868)
# ─────────────────────────────────────────────────────────────────────────────

def boundary_layer_attenuation(
    frequency: Union[float, np.ndarray],
    tube_radius_m: float,
    rho: float = RHO_AIR,
    mu: float = MU_AIR,
    gamma: float = GAMMA_AIR,
    pr: float = PR_AIR,
) -> Union[float, np.ndarray]:
    """
    Coefficiente di attenuazione per perdite termoviscose in tubo circolare [Np/m].

        α = (1/r) · √(ω·ρ/(2·μ)) · (1 + (γ-1)/√Pr)

    Valida per ka << 1 (regime sub-wavelength).
    Significativa solo per raggi piccoli (< ~5 mm a frequenze audio).

    Args:
        frequency:    Frequenza [Hz] (scalare o array)
        tube_radius_m: Raggio interno tubo [m]
        rho:          Densità aria [kg/m³]
        mu:           Viscosità dinamica [Pa·s]
        gamma:        Rapporto calori specifici (1.4 per aria)
        pr:           Numero di Prandtl (0.707 per aria)

    Returns:
        α [Np/m]  —  moltiplicare per 8.686 per avere dB/m

    Esempio:
        Gola CD 1" (r=0.0127 m) a 2 kHz → α ≈ 0.08 Np/m = 0.7 dB/m

    Rif: Kirchhoff G. (1868) Ann.Phys. 134:177
         Beranek L.L. (1954) "Acoustics" cap.3
    """
    freq = np.asarray(frequency, dtype=float)
    omega = 2.0 * np.pi * freq
    visc_term = np.sqrt(omega * rho / (2.0 * mu))
    therm_term = (gamma - 1.0) / math.sqrt(pr)
    return (1.0 / tube_radius_m) * visc_term * (1.0 + therm_term)


def boundary_layer_attenuation_db_per_m(
    frequency: Union[float, np.ndarray],
    tube_radius_m: float,
    **kwargs,
) -> Union[float, np.ndarray]:
    """Come boundary_layer_attenuation() ma restituisce dB/m."""
    return 8.686 * boundary_layer_attenuation(frequency, tube_radius_m, **kwargs)


def total_horn_boundary_loss_db(
    frequencies: np.ndarray,
    throat_radius_m: float,
    mouth_radius_m: float,
    horn_length_m: float,
    n_segments: int = 100,
    **kwargs,
) -> np.ndarray:
    """
    Perdita totale strato limite lungo una tromba [dB], integrata numericamente.

    Il raggio varia in modo approssimato come potenza tra gola e bocca.
    Per risultati esatti passare il profilo reale con `radii_at_positions`.

    Args:
        frequencies:    Array frequenze [Hz]
        throat_radius_m: Raggio gola [m]
        mouth_radius_m:  Raggio bocca [m]
        horn_length_m:   Lunghezza tromba [m]
        n_segments:      Numero segmenti per integrazione

    Returns:
        Array perdite [dB] per ogni frequenza
    """
    # Profilo raggio lineare in log (esponenziale è il caso più comune)
    positions = np.linspace(0.0, horn_length_m, n_segments + 1)
    t = positions / horn_length_m
    radii = throat_radius_m * (mouth_radius_m / throat_radius_m) ** t
    dx = horn_length_m / n_segments

    losses = np.zeros_like(frequencies, dtype=float)
    for i, r in enumerate(radii[:-1]):
        r_mid = 0.5 * (r + radii[i + 1])
        losses += 8.686 * boundary_layer_attenuation(frequencies, r_mid, **kwargs) * dx

    return losses


# ─────────────────────────────────────────────────────────────────────────────
# 4. ACUSTICA NON-LINEARE (Burgers / Goldberg)
# ─────────────────────────────────────────────────────────────────────────────

def shock_formation_distance(
    spl_db: float,
    frequency: float,
    beta: float = BETA_AIR,
    rho: float = RHO_AIR,
    c: float = C_AIR,
) -> float:
    """
    Distanza di formazione shock acustico [m].

        x_shock = 1 / (β · k · M)

    Oltre questa distanza l'equazione di Webster lineare non è più valida:
    serve la soluzione dell'equazione di Burgers.

    Args:
        spl_db:    SPL [dB] alla sorgente
        frequency: Frequenza [Hz]
        beta:      Coefficiente di non-linearità (1.2 per aria)

    Returns:
        Distanza shock [m] — inf se regime lineare

    Rif: Hamilton & Blackstock (1998) "Nonlinear Acoustics" cap.2
    """
    M = acoustic_mach(spl_db, rho, c)
    if M < 1e-12:
        return math.inf
    k = 2.0 * math.pi * frequency / c
    return 1.0 / (beta * k * M)


def goldberg_number(
    spl_db: float,
    frequency: float,
    path_length_m: float,
    beta: float = BETA_AIR,
    rho: float = RHO_AIR,
    c: float = C_AIR,
    mu: float = MU_AIR,
) -> float:
    """
    Numero di Goldberg Γ — rapporto tra non-linearità e dissipazione viscosa.

        Γ = β · k · u₀ · x · ρ · c / μ

    Γ >> 1 → non-linearità domina → generazione armoniche rilevante.
    Γ << 1 → viscosità domina → propagazione quasi-lineare.

    Tipicamente Γ > 1 solo per SPL > 130 dB in trombe CD.

    Rif: Goldberg Z.A. (1957) Sov.Phys.Acoust. 3:340
         Hamilton & Blackstock (1998) cap.2
    """
    u0 = particle_velocity(spl_db, rho, c)
    k = 2.0 * math.pi * frequency / c
    return beta * k * u0 * path_length_m * rho * c / mu


def thd_nonlinear_ratio(
    spl_db: float,
    frequency: float,
    path_length_m: float,
    beta: float = BETA_AIR,
    rho: float = RHO_AIR,
    c: float = C_AIR,
) -> float:
    """
    THD stimato per effetti non-lineari dell'aria lungo un cammino [ratio, non %].

    Approssimazione di primo ordine valida per A₂/A₁ << 1:

        A₂/A₁ ≈ (β · k · u₀ · x) / 2

    Moltiplicare per 100 per ottenere %.

    Nota: Questa formula stima SOLO la distorsione dell'aria come mezzo.
    La distorsione totale del sistema include anche la distorsione meccanica
    del driver (molto maggiore a basse frequenze).

    Rif: Hamilton & Blackstock (1998) cap.2
    """
    u0 = particle_velocity(spl_db, rho, c)
    k = 2.0 * math.pi * frequency / c
    return (beta * k * u0 * path_length_m) / 2.0


# ─────────────────────────────────────────────────────────────────────────────
# 5. DIRETTIVITÀ E DIFFRAZIONE GRIGLIA (per controllo del pattern)
# ─────────────────────────────────────────────────────────────────────────────

def grille_diffraction_db(
    frequency: Union[float, np.ndarray],
    hole_diameter_m: float,
    open_ratio: float,
    angle_deg: Union[float, np.ndarray] = 0.0,
    c: float = C_AIR,
) -> Union[float, np.ndarray]:
    """
    Pattern di diffrazione per griglia con fori circolari (Fraunhofer + Bessel J1).

    Il pattern è basato sulla diffrazione Fraunhofer da apertura circolare:

        D(θ) = 2 J₁(ka sinθ) / (ka sinθ)    [pistone circolare]

    Trasmissione effettiva:

        T(θ) = open_ratio + (1 - open_ratio) · D(θ)²

    Significativa solo ad alta frequenza (ka > 1, cioè d > λ/π).
    A basse frequenze (<400 Hz per fori da 5 mm) T≈open_ratio (pass-through lineare).

    Args:
        frequency:      Frequenza [Hz]
        hole_diameter_m: Diametro di un singolo foro [m]
        open_ratio:     Rapporto area aperta / area totale [0–1]
        angle_deg:      Angolo di osservazione dal centro [°]
        c:              Velocità del suono [m/s]

    Returns:
        Attenuazione/modifica direttività [dB] (< 0 = attenuazione)

    Rif: Fraunhofer diffraction — Born & Wolf (1999) "Principles of Optics" cap.8
         Beranek (1954) "Acoustics" — pistone circolare (stessa funzione J1)
    """
    try:
        from scipy.special import j1 as _j1
        _has_scipy = True
    except ImportError:
        _has_scipy = False

    freq = np.asarray(frequency, dtype=float)
    theta = np.deg2rad(np.asarray(angle_deg, dtype=float))
    k = 2.0 * np.pi * freq / c
    a = hole_diameter_m / 2.0
    u = k * a * np.sin(theta)

    if _has_scipy:
        # Forma esatta con Bessel J1
        with np.errstate(divide="ignore", invalid="ignore"):
            form_factor = np.where(
                np.abs(u) < 1e-9,
                1.0,
                2.0 * _j1(u) / u,
            )
    else:
        # Approssimazione polinomiale (Abramowitz & Stegun 9.4)
        # Valida per ka·sinθ < 3.8 (primo minimo)
        form_factor = np.where(
            np.abs(u) < 1e-9,
            1.0,
            np.sinc(u / np.pi),  # sinc è J0 approximation, meno preciso
        )

    transmission = open_ratio + (1.0 - open_ratio) * form_factor ** 2
    return 10.0 * np.log10(np.maximum(transmission, 1e-12))


def grille_directivity_pattern(
    frequencies: np.ndarray,
    angles_deg: np.ndarray,
    hole_diameter_m: float,
    open_ratio: float,
    c: float = C_AIR,
) -> np.ndarray:
    """
    Matrice (n_freq × n_angles) del pattern di direttività modificato dalla griglia [dB].

    Usa grille_diffraction_db() su ogni combinazione (frequenza, angolo).

    Args:
        frequencies:    Array frequenze [Hz]   — shape (F,)
        angles_deg:     Array angoli [°]        — shape (A,)
        hole_diameter_m: Diametro fori [m]
        open_ratio:     Rapporto area aperta [0–1]

    Returns:
        Matrice [dB] di shape (F, A)

    Uso tipico in BTK Speaker Designer:
        - Calcola pattern driver puro D_driver(F, A)
        - Aggiungi grille_directivity_pattern() per ottenere pattern modificato
        - Ottimizza hole_diameter_m e open_ratio per target coverage
    """
    F = len(frequencies)
    A = len(angles_deg)
    out = np.zeros((F, A))
    for i, f in enumerate(frequencies):
        out[i, :] = grille_diffraction_db(f, hole_diameter_m, open_ratio, angles_deg, c)
    return out


def optimize_grille_for_coverage(
    target_coverage_deg: float,
    target_frequency_hz: float,
    driver_mouth_radius_m: float,
    hole_diameter_range_m: tuple = (0.002, 0.015),
    open_ratio_range: tuple = (0.3, 0.8),
    c: float = C_AIR,
) -> dict:
    """
    Trova i parametri di griglia che avvicinano la copertura al target a -6 dB.

    Strategia: scansione grid search su (hole_diameter, open_ratio).
    La copertura è l'angolo a cui la griglia porta il guadagno a -3 dB
    rispetto all'asse (non è -6 dB totale del sistema, solo contributo griglia).

    Args:
        target_coverage_deg:  Copertura desiderata full-angle [°]
        target_frequency_hz:  Frequenza di ottimizzazione [Hz]
        driver_mouth_radius_m: Raggio bocca driver (usato come vincolo fisico)

    Returns:
        dict con {hole_diameter_m, open_ratio, achieved_coverage_deg, error_deg}
    """
    angles = np.linspace(0, 90, 181)
    best = {"error_deg": 1e9}

    for d_hole in np.linspace(*hole_diameter_range_m, 20):
        for oa in np.linspace(*open_ratio_range, 15):
            pattern = grille_diffraction_db(
                target_frequency_hz, d_hole, oa, angles, c
            )
            # Trova angolo a -3 dB rispetto all'asse (angolo=0°)
            on_axis = float(grille_diffraction_db(target_frequency_hz, d_hole, oa, 0.0, c))
            mask = pattern <= on_axis - 3.0
            if mask.any():
                half_angle = float(angles[np.argmax(mask)])
            else:
                half_angle = 90.0
            full_coverage = 2.0 * half_angle
            error = abs(full_coverage - target_coverage_deg)
            if error < best["error_deg"]:
                best = {
                    "hole_diameter_m": d_hole,
                    "open_ratio": oa,
                    "achieved_coverage_deg": full_coverage,
                    "error_deg": error,
                }

    return best
