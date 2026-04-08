"""
Calcolatore principale per trombe acustiche.
Implementa le formule dal foglio di calcolo Horn Calculator originale.

Supporta espansione esponenziale, conica, tractrix e hypex.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .constants import (
    SPEED_OF_SOUND, AIR_DENSITY,
    EXPANSION_EXPONENTIAL, EXPANSION_CONICAL, EXPANSION_TRACTRIX, EXPANSION_HYPEX,
    NUM_HORN_SECTIONS, EPSILON
)

try:
    from scipy.optimize import brentq as _brentq
    from scipy.special import j1   as _j1
    _SCIPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SCIPY_AVAILABLE = False

# ─── Costante Bessel per direttività a -6 dB ──────────────────────────────────
# Soluzione di  2·J₁(u)/u = 0.5  (equivale a JBL/Keele 1975 AES Conv.46)
# Beranek "Acoustics" (1954) cap. 4 — pattern pistone circolare puro
if _SCIPY_AVAILABLE:
    _U_6DB = _brentq(lambda u: 2.0 * _j1(u) / u - 0.5, 0.5, 3.8)
else:
    _U_6DB = 2.2313   # valore precomputed


@dataclass
class HornSection:
    """Rappresenta una singola sezione della tromba."""
    position: float     # posizione normalizzata (0.0 - 1.0)
    x_m: float          # distanza dalla gola in metri
    area_m2: float      # area della sezione in m²
    radius_m: float     # raggio equivalente in metri
    width_m: float      # larghezza (se rettangolare)
    height_m: float     # altezza (se rettangolare)


# ─── Helper interni tractrix ─────────────────────────────────────────────────

def _tractrix_x_from_mouth(r: float, R_m: float) -> float:
    """
    Distanza geometrica dalla bocca per tromba tractrix di raggio bocca R_m.

    Formula (chiusa): x = R_m · [arccosh(R_m/r) − √(1 − (r/R_m)²)]

    Proprietà: la lunghezza della tangente da ogni punto della curva
    all'asse è costante e uguale a R_m.

    Rif: Klipsch P.W. (1941) JASA 13:137
         Salmon V. (1946) JASA 17:212
    """
    if r <= EPSILON:
        return float('inf')
    u = R_m / r
    if u < 1.0:
        return 0.0
    return R_m * (np.arccosh(u) - np.sqrt(1.0 - 1.0 / (u * u)))


def _tractrix_r_at_position(x_m: float, r_throat: float, R_m: float) -> float:
    """
    Raggio alla posizione x_m dalla gola per tromba tractrix.

    Inversione numerica con scipy.optimize.brentq.
    Fallback polinomiale se scipy non disponibile (accuratezza ~1%).

    Rif: Klipsch (1941), Salmon (1946)
    """
    if r_throat >= R_m:
        return r_throat
    L = _tractrix_x_from_mouth(r_throat, R_m)
    if x_m <= 0.0:
        return r_throat
    if x_m >= L:
        return R_m
    x_from_mouth = L - x_m
    if not _SCIPY_AVAILABLE:  # pragma: no cover
        # Approssimazione monotonica senza scipy
        t = x_m / L
        return r_throat + (R_m - r_throat) * (t ** 0.6)
    return _brentq(
        lambda r: _tractrix_x_from_mouth(r, R_m) - x_from_mouth,
        r_throat * (1.0 + EPSILON),
        R_m   * (1.0 - EPSILON),
        xtol=1e-10, rtol=1e-10,
    )


@dataclass
class HornGeometry:
    """Risultato del calcolo della geometria di una tromba."""
    throat_area_m2: float
    mouth_area_m2: float
    horn_length_m: float
    flare_rate_m: float             # σ o m, specifico per tipo espansione
    cutoff_frequency_hz: float
    throat_impedance: float         # Ω acustici
    coupling_volume_m3: float       # volume di accoppiamento
    expansion_type: str
    sections: List[HornSection] = field(default_factory=list)
    hypex_T: float = 0.5            # Parametro T di Salmon (solo per HYPEX)

    @property
    def throat_radius_m(self) -> float:
        return np.sqrt(self.throat_area_m2 / np.pi)

    @property
    def mouth_radius_m(self) -> float:
        return np.sqrt(self.mouth_area_m2 / np.pi)

    @property
    def throat_diameter_m(self) -> float:
        return 2 * self.throat_radius_m

    @property
    def mouth_diameter_m(self) -> float:
        return 2 * self.mouth_radius_m

    @property
    def expansion_ratio(self) -> float:
        return self.mouth_area_m2 / self.throat_area_m2


def calculate_flare_rate(
    cutoff_freq_hz: float,
    c: float = SPEED_OF_SOUND,
    expansion_type: str = EXPANSION_EXPONENTIAL,
    hypex_T: float = 0.5,
) -> float:
    """
    Calcola il tasso di svasatura σ (flare rate) in m⁻¹.

    Esponenziale : m = 4π·fc/c          S(x) = S₀·eˢˣ
    Tractrix     : σ = 2π·fc/c = 1/R_m  R_m = bocca (Klipsch 1941)
    Hypex        : σ = 2π·fc/(c·√(1−T²)) (Salmon 1946, JASA 17:212)
    Conico       : valore equivalente approssimato

    Nota: il docstring precedente riportava m=2π/c·√2 — ERRATO.
    La forma corretta per esponenziale è m = 4π·fc/c.
    Rif: Webster A.G. (1919) PNAS 5:275; Olson H.F. (1957) cap.6;
         Salmon V. (1946) JASA 17:212.

    Args:
        cutoff_freq_hz: Frequenza di taglio in Hz
        c: Velocità del suono in m/s
        expansion_type: Tipo di espansione
        hypex_T: Parametro di forma T per Hypex [0, 1)

    Returns:
        Flare rate σ in m⁻¹
    """
    if expansion_type == EXPANSION_EXPONENTIAL:
        # Webster (1919); Olson "Acoustical Engineering" (1957) cap. 6
        return (4.0 * np.pi * cutoff_freq_hz) / c
    elif expansion_type == EXPANSION_CONICAL:
        return (2.0 * np.pi * cutoff_freq_hz) / c
    elif expansion_type == EXPANSION_TRACTRIX:
        # σ = 1/R_m = 2π·fc/c  (Klipsch 1941, JASA 13:137)
        return (2.0 * np.pi * cutoff_freq_hz) / c
    elif expansion_type == EXPANSION_HYPEX:
        # σ = 2π·fc / (c·√(1−T²))  (Salmon 1946, JASA 17:212)
        if not (0.0 <= hypex_T < 1.0):
            raise ValueError(
                f"Hypex T deve essere in [0, 1), ricevuto: {hypex_T:.3f}"
            )
        return (2.0 * np.pi * cutoff_freq_hz) / (c * np.sqrt(1.0 - hypex_T ** 2))
    else:
        return (4.0 * np.pi * cutoff_freq_hz) / c


def calculate_throat_area(
    driver_sd_m2: float,
    compression_ratio: float = 1.0,
    throat_compression_ratio: Optional[float] = None,
) -> float:
    """
    Calcola l'area della gola della tromba.

    Args:
        driver_sd_m2: Area del diaframma del driver in m²
        compression_ratio: Rapporto di compressione (Sd/Sthroat)
                           1.0 = nessuna compressione (subwoofer)
                           >1 = compressione (compression driver)
        throat_compression_ratio: Alias per compression_ratio (deprecato)

    Returns:
        Area della gola in m²
    """
    ratio = throat_compression_ratio if throat_compression_ratio is not None else compression_ratio
    return driver_sd_m2 / ratio


def calculate_mouth_area(
    throat_area_m2: float,
    smouth_sthroat_ratio: float = 2.0
) -> float:
    """
    Calcola l'area della bocca della tromba.

    Args:
        throat_area_m2: Area della gola in m²
        smouth_sthroat_ratio: Rapporto Sbocca/Sgola

    Returns:
        Area della bocca in m²
    """
    return throat_area_m2 * smouth_sthroat_ratio


def calculate_horn_length(
    throat_area_m2: float,
    mouth_area_m2: float,
    flare_rate_m: float,
    expansion_type: str = EXPANSION_EXPONENTIAL,
    hypex_T: float = 0.5,
) -> float:
    """
    Calcola la lunghezza della tromba dall'area gola e bocca.

    Esponenziale : L = ln(S_m/S₀) / m
    Conico       : L = r₀ · (√ratio − 1)
    Tractrix     : L = R_m · [arccosh(R_m/r₀) − √(1−(r₀/R_m)²)]  (chiusa)
    Hypex        : L = ln(u) / σ  con u = [R + √(R²−(1−T²))] / (1+T) (chiusa)

    Args:
        throat_area_m2: Area della gola in m²
        mouth_area_m2: Area della bocca in m²
        flare_rate_m: Tasso di svasatura σ in m⁻¹
        expansion_type: Tipo di espansione
        hypex_T: Parametro di forma T per Hypex [0, 1)

    Returns:
        Lunghezza in metri
    """
    if flare_rate_m < EPSILON:
        raise ValueError("Il flare rate deve essere maggiore di zero")

    ratio = mouth_area_m2 / throat_area_m2

    if expansion_type == EXPANSION_EXPONENTIAL:
        # L = ln(S_m/S₀) / m  — Olson (1957) cap. 6
        return np.log(ratio) / flare_rate_m
    elif expansion_type == EXPANSION_CONICAL:
        # L = r₀ · (√ratio − 1)
        r_throat = np.sqrt(throat_area_m2 / np.pi)
        return r_throat * (np.sqrt(ratio) - 1.0)
    elif expansion_type == EXPANSION_TRACTRIX:
        # Lunghezza tramite formula chiusa della tractrix
        # L = R_m · [arccosh(R_m/r₀) − √(1 − (r₀/R_m)²)]
        # Rif: Klipsch (1941) JASA 13:137
        r_throat = np.sqrt(throat_area_m2 / np.pi)
        R_m = np.sqrt(mouth_area_m2 / np.pi)
        if R_m <= r_throat:
            raise ValueError(
                "Tractrix: raggio bocca deve essere maggiore del raggio gola. "
                "Aumenta Fc o riduci la compressione alla gola."
            )
        return _tractrix_x_from_mouth(r_throat, R_m)
    elif expansion_type == EXPANSION_HYPEX:
        # [cosh(σL) + T·sinh(σL)] = √(S_m/S₀)  → soluzione chiusa
        # u²·(1+T) − 2R·u + (1−T) = 0  dove u = e^(σL), R = √ratio
        # u = [R + √(R²−(1−T²))] / (1+T)
        # Rif: Salmon (1946) JASA 17:212
        R = np.sqrt(ratio)
        T = hypex_T
        discriminant = R ** 2 - (1.0 - T ** 2)
        if discriminant < 0.0:
            raise ValueError(
                f"Hypex (T={T:.2f}): rapporto bocca/gola {ratio:.2f} troppo piccolo. "
                f"Valore minimo richiesto: {1.0 - T**2:.3f}."
            )
        u = (R + np.sqrt(discriminant)) / (1.0 + T)
        if u <= 1.0:
            raise ValueError("Hypex: soluzione non valida — u <= 1.")
        return np.log(u) / flare_rate_m
    else:
        return np.log(ratio) / flare_rate_m


def area_at_position(
    x_m: float,
    throat_area_m2: float,
    flare_rate_m: float,
    expansion_type: str = EXPANSION_EXPONENTIAL,
    hypex_T: float = 0.5,
) -> float:
    """
    Calcola l'area della tromba in una data posizione lungo l'asse.

    Esponenziale : S(x) = S₀·exp(m·x)
                  Webster (1919); Olson (1957)
    Conico       : S(x) = π·(r₀ + x)²
                  (profile lineare)
    Tractrix     : inversione numerica della curva parametrica
                  Klipsch (1941) JASA 13:137; Salmon (1946) JASA 17:212
                  R_m = c/(2π·fc) = 1/flare_rate_m
    Hypex        : S(x) = S₀·[cosh(σx) + T·sinh(σx)]²
                  Salmon (1946) JASA 17:212
                  σ memorizzato in flare_rate_m

    Args:
        x_m: Posizione dalla gola in metri
        throat_area_m2: Area della gola in m²
        flare_rate_m: Tasso di svasatura σ in m⁻¹
        expansion_type: Tipo di espansione
        hypex_T: Parametro T di Salmon per Hypex [0, 1)

    Returns:
        Area della sezione in m²
    """
    if expansion_type == EXPANSION_EXPONENTIAL:
        # S(x) = S₀ · eˢˣ  — Webster (1919), Olson (1957) cap. 6
        return throat_area_m2 * np.exp(flare_rate_m * x_m)

    elif expansion_type == EXPANSION_CONICAL:
        # S(x) = π · (r₀ + x)²
        r0 = np.sqrt(throat_area_m2 / np.pi)
        return np.pi * (r0 + x_m) ** 2

    elif expansion_type == EXPANSION_TRACTRIX:
        # Inversione numerica del profilo tractrix
        # R_m = c/(2π·fc) = 1/σ = 1/flare_rate_m  (Klipsch 1941)
        R_m = 1.0 / max(flare_rate_m, EPSILON)
        r_throat = np.sqrt(throat_area_m2 / np.pi)
        if R_m < r_throat:
            R_m = r_throat * (1.0 + EPSILON)  # geometria degenere: clippa
        r = _tractrix_r_at_position(x_m, r_throat, R_m)
        return np.pi * r ** 2

    elif expansion_type == EXPANSION_HYPEX:
        # S(x) = S₀ · [cosh(σx) + T·sinh(σx)]²
        # Salmon (1946) JASA 17:212 — "Generalized Plane Wave Horn Theory"
        # T=0 → cosh²; T→1 → esponenziale
        s = flare_rate_m * x_m
        return throat_area_m2 * (np.cosh(s) + hypex_T * np.sinh(s)) ** 2

    else:
        return throat_area_m2 * np.exp(flare_rate_m * x_m)


def calculate_throat_impedance(
    throat_area_m2: float,
    c: float = SPEED_OF_SOUND,
    rho: float = AIR_DENSITY
) -> float:
    """
    Calcola l'impedenza acustica alla gola della tromba.

    Z_throat = rho * c / S_throat

    Args:
        throat_area_m2: Area della gola in m²
        c: Velocità del suono in m/s
        rho: Densità dell'aria in kg/m³

    Returns:
        Impedenza acustica in Pa·s/m³ (mkh nel foglio originale)
    """
    if throat_area_m2 < EPSILON:
        raise ValueError("L'area della gola deve essere maggiore di zero")
    return (rho * c) / throat_area_m2


def calculate_coupling_volume(
    throat_area_m2: float,
    horn_length_m: float,
    flare_rate_m: float,
    expansion_type: str = EXPANSION_EXPONENTIAL,
    hypex_T: float = 0.5,
) -> float:
    """
    Calcola il volume di accoppiamento della tromba (volume equivalente).

    Esponenziale: V = S₀/m · (e^(mL) − 1)  (formula chiusa, Olson 1957)
    Altri tipi  : integrazione numerica (Simpson)

    Args:
        throat_area_m2: Area della gola in m²
        horn_length_m: Lunghezza tromba in m
        flare_rate_m: Tasso di svasatura σ in m⁻¹
        expansion_type: Tipo di espansione
        hypex_T: Parametro di forma T per Hypex [0, 1)

    Returns:
        Volume di accoppiamento in m³
    """
    if expansion_type == EXPANSION_EXPONENTIAL:
        if flare_rate_m < EPSILON:
            return throat_area_m2 * horn_length_m
        return (throat_area_m2 / flare_rate_m) * (np.exp(flare_rate_m * horn_length_m) - 1)
    else:
        # Integrazione numerica per altri profili
        x = np.linspace(0, horn_length_m, 200)
        areas = np.array([
            area_at_position(xi, throat_area_m2, flare_rate_m, expansion_type, hypex_T)
            for xi in x
        ])
        _trapz = getattr(np, "trapezoid", np.trapz)  # NumPy ≥2.0 / <2.0 compat
        return _trapz(areas, x)


def calculate_horn_sections(
    throat_area_m2: float,
    horn_length_m: float,
    flare_rate_m: float,
    expansion_type: str = EXPANSION_EXPONENTIAL,
    n_sections: int = NUM_HORN_SECTIONS,
    hypex_T: float = 0.5,
) -> List[HornSection]:
    """
    Calcola le sezioni della tromba per costruzione e visualizzazione.

    Args:
        throat_area_m2: Area della gola in m²
        horn_length_m: Lunghezza tromba in m
        flare_rate_m: Tasso di svasatura σ in m⁻¹
        expansion_type: Tipo di espansione
        n_sections: Numero di sezioni da calcolare
        hypex_T: Parametro di forma T per Hypex [0, 1)

    Returns:
        Lista di oggetti HornSection
    """
    sections = []
    positions = np.linspace(0, 1, n_sections + 1)[1:]  # esclude posizione 0

    for i, pos in enumerate(positions):
        x = pos * horn_length_m
        area = area_at_position(x, throat_area_m2, flare_rate_m, expansion_type, hypex_T)
        radius = np.sqrt(area / np.pi)

        sections.append(HornSection(
            position=pos,
            x_m=x,
            area_m2=area,
            radius_m=radius,
            width_m=2 * radius,
            height_m=2 * radius,
        ))

    return sections


def design_horn(
    cutoff_freq_hz: float,
    driver_sd_m2: float,
    smouth_sthroat_ratio: float = 2.0,
    throat_compression_ratio: float = 1.0,
    expansion_type: str = EXPANSION_EXPONENTIAL,
    c: float = SPEED_OF_SOUND,
    rho: float = AIR_DENSITY,
    n_sections: int = NUM_HORN_SECTIONS,
    hypex_T: float = 0.5,
) -> HornGeometry:
    """
    Progetta una tromba acustica a partire dai parametri fondamentali.

    Args:
        cutoff_freq_hz: Frequenza di taglio in Hz
        driver_sd_m2: Area del diaframma del driver in m²
        smouth_sthroat_ratio: Rapporto area bocca/gola
                              (ignorato per Tractrix: bocca determinata da fc)
        throat_compression_ratio: Rapporto di compressione alla gola
        expansion_type: Tipo di espansione
        c: Velocità del suono in m/s
        rho: Densità dell'aria in kg/m³
        n_sections: Numero di sezioni da calcolare
        hypex_T: Parametro T di Salmon per Hypex [0, 1)
                 0.0=cosh², 0.5=Hypex classico, →1=esponenziale

    Returns:
        Oggetto HornGeometry con tutti i parametri calcolati

    Esempio:
        >>> geom = design_horn(
        ...     cutoff_freq_hz=70.0,
        ...     driver_sd_m2=0.091,    # 18" woofer
        ...     smouth_sthroat_ratio=2.0
        ... )
        >>> print(f"Lunghezza: {geom.horn_length_m:.4f} m")
        Lunghezza: 0.2696 m
    """
    # 1. Flare rate (include hypex_T per Hypex)
    m = calculate_flare_rate(cutoff_freq_hz, c, expansion_type, hypex_T)

    # 2. Area gola
    s_throat = calculate_throat_area(driver_sd_m2, throat_compression_ratio)

    # 3. Area bocca
    # Per Tractrix la bocca è fisica: R_m = c/(2π·fc) = 1/σ  (Klipsch 1941)
    # Non dipende dal ratio bocca/gola (che è un param di progetto libero
    # solo per esponenziale / iperbolico / conico).
    if expansion_type == EXPANSION_TRACTRIX:
        R_m = 1.0 / m  # R_m = c/(2π·fc)
        s_mouth = np.pi * R_m ** 2
        if s_mouth < s_throat:
            raise ValueError(
                f"Tractrix: area bocca ({s_mouth * 1e4:.1f} cm²) < area gola "
                f"({s_throat * 1e4:.1f} cm²). "
                "Aumenta Fc oppure riduci la compressione alla gola."
            )
    else:
        s_mouth = calculate_mouth_area(s_throat, smouth_sthroat_ratio)

    # 4. Lunghezza tromba
    horn_length = calculate_horn_length(s_throat, s_mouth, m, expansion_type, hypex_T)

    # 5. Impedenza alla gola
    z_throat = calculate_throat_impedance(s_throat, c, rho)

    # 6. Volume di accoppiamento
    v_coupling = calculate_coupling_volume(s_throat, horn_length, m, expansion_type, hypex_T)

    # 7. Sezioni progressive
    sections = calculate_horn_sections(
        s_throat, horn_length, m, expansion_type, n_sections, hypex_T
    )

    return HornGeometry(
        throat_area_m2=s_throat,
        mouth_area_m2=s_mouth,
        horn_length_m=horn_length,
        flare_rate_m=m,
        cutoff_frequency_hz=cutoff_freq_hz,
        throat_impedance=z_throat,
        coupling_volume_m3=v_coupling,
        expansion_type=expansion_type,
        sections=sections,
        hypex_T=hypex_T,
    )


def horn_frequency_response(
    frequencies: np.ndarray,
    horn_geometry: HornGeometry,
    c: float = SPEED_OF_SOUND
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calcola la risposta in ampiezza e fase della tromba.

    Args:
        frequencies: Array di frequenze in Hz
        horn_geometry: Geometria della tromba calcolata
        c: Velocità del suono in m/s

    Returns:
        Tupla (ampiezza_db, fase_rad) entrambi array numpy
    """
    fc = horn_geometry.cutoff_frequency_hz
    m = horn_geometry.flare_rate_m

    # Risposta in ampiezza: passa-alto del secondo ordine
    # Sopra fc: guadagno dipende dall'espansione
    # np.maximum evita log10(valore<=0) per freq vicine a fc
    ratio_sq = np.where(frequencies > 0, (fc / frequencies) ** 2, 1.0)
    amplitude_db = np.where(
        frequencies > fc,
        10 * np.log10(np.maximum(1e-10, 1.0 - ratio_sq)),
        -60.0  # sotto fc: forte attenuazione
    )

    # Risposta in fase
    k = 2 * np.pi * frequencies / c
    phase_rad = np.where(
        frequencies > fc,
        np.arctan2(m, 2 * k),
        np.pi / 2
    )

    return amplitude_db, phase_rad


def calculate_horn_directivity(
    frequencies: np.ndarray,
    mouth_radius_m: float,
    c: float = SPEED_OF_SOUND
) -> np.ndarray:
    """
    Angolo di copertura a -6 dB (full angle, ambo i lati) per pistone circolare.

    Formula esatta: D(θ) = 2·J₁(ka·sinθ) / (ka·sinθ) = 0.5
    → sinθ = _U_6DB / ka  con _U_6DB ≈ 2.2313 (risolto con Bessel)
    → angolo full = 2 · arcsin(_U_6DB / ka)

    Rif: Beranek L.L. "Acoustics" (1954) cap. 4
         Keele D.B. Jr. (1975) AES Conv. 46, preprint 950

    Args:
        frequencies: Array di frequenze in Hz
        mouth_radius_m: Raggio della bocca in metri
        c: Velocità del suono in m/s

    Returns:
        Array di angolo di copertura full a -6 dB in gradi
    """
    ka = 2.0 * np.pi * frequencies * mouth_radius_m / c
    sin_theta = np.minimum(_U_6DB / np.maximum(ka, EPSILON), 1.0)
    half_angle_deg = np.degrees(np.arcsin(sin_theta))
    return 2.0 * half_angle_deg  # angolo totale (full coverage angle)
