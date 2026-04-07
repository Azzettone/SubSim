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


@dataclass
class HornSection:
    """Rappresenta una singola sezione della tromba."""
    position: float     # posizione normalizzata (0.0 - 1.0)
    x_m: float          # distanza dalla gola in metri
    area_m2: float      # area della sezione in m²
    radius_m: float     # raggio equivalente in metri
    width_m: float      # larghezza (se rettangolare)
    height_m: float     # altezza (se rettangolare)


@dataclass
class HornGeometry:
    """Risultato del calcolo della geometria di una tromba."""
    throat_area_m2: float
    mouth_area_m2: float
    horn_length_m: float
    flare_rate_m: float             # m⁻¹
    cutoff_frequency_hz: float
    throat_impedance: float         # Ω acustici
    coupling_volume_m3: float       # volume di accoppiamento
    expansion_type: str
    sections: List[HornSection] = field(default_factory=list)

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
    expansion_type: str = EXPANSION_EXPONENTIAL
) -> float:
    """
    Calcola il tasso di svasatura (flare rate) m in m⁻¹.

    Per tromba esponenziale: S(x) = S0 * exp(m * x)
    dove m = 2 * pi * fc / c * sqrt(2) per espansione esponenziale

    Riferimento: Olson, "Acoustical Engineering" (1957)

    Args:
        cutoff_freq_hz: Frequenza di taglio in Hz
        c: Velocità del suono in m/s
        expansion_type: Tipo di espansione

    Returns:
        Flare rate in m⁻¹
    """
    if expansion_type == EXPANSION_EXPONENTIAL:
        # Formula dal foglio di calcolo originale
        return (4 * np.pi * cutoff_freq_hz) / c
    elif expansion_type == EXPANSION_CONICAL:
        # Per tromba conica, m non è costante; restituiamo valore approssimato
        return (2 * np.pi * cutoff_freq_hz) / c
    elif expansion_type == EXPANSION_TRACTRIX:
        return (2 * np.pi * cutoff_freq_hz) / c
    elif expansion_type == EXPANSION_HYPEX:
        return (3 * np.pi * cutoff_freq_hz) / c
    else:
        return (4 * np.pi * cutoff_freq_hz) / c


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
    expansion_type: str = EXPANSION_EXPONENTIAL
) -> float:
    """
    Calcola la lunghezza della tromba dall'area gola e bocca.

    Per espansione esponenziale: L = ln(Smouth/Sthroat) / m

    Args:
        throat_area_m2: Area della gola in m²
        mouth_area_m2: Area della bocca in m²
        flare_rate_m: Tasso di svasatura m⁻¹
        expansion_type: Tipo di espansione

    Returns:
        Lunghezza in metri
    """
    if flare_rate_m < EPSILON:
        raise ValueError("Il flare rate deve essere maggiore di zero")

    ratio = mouth_area_m2 / throat_area_m2

    if expansion_type == EXPANSION_EXPONENTIAL:
        return np.log(ratio) / flare_rate_m
    elif expansion_type == EXPANSION_CONICAL:
        # Per tromba conica: L = r_throat * (sqrt(ratio) - 1)
        r_throat = np.sqrt(throat_area_m2 / np.pi)
        return r_throat * (np.sqrt(ratio) - 1)
    else:
        return np.log(ratio) / flare_rate_m


def area_at_position(
    x_m: float,
    throat_area_m2: float,
    flare_rate_m: float,
    expansion_type: str = EXPANSION_EXPONENTIAL
) -> float:
    """
    Calcola l'area della tromba in una data posizione lungo l'asse.

    Args:
        x_m: Posizione dalla gola in metri
        throat_area_m2: Area della gola in m²
        flare_rate_m: Tasso di svasatura m⁻¹
        expansion_type: Tipo di espansione

    Returns:
        Area della sezione in m²
    """
    if expansion_type == EXPANSION_EXPONENTIAL:
        # Formula principale: S(x) = S0 * exp(m * x)
        return throat_area_m2 * np.exp(flare_rate_m * x_m)

    elif expansion_type == EXPANSION_CONICAL:
        # S(x) = S0 * (1 + x/r0)²
        r0 = np.sqrt(throat_area_m2 / np.pi)
        r = r0 + x_m
        return np.pi * r ** 2

    elif expansion_type == EXPANSION_TRACTRIX:
        # Profilo tractrix: curva che parte perpendicolare all'asse
        # Approssimazione numerica
        r_mouth = np.sqrt(throat_area_m2 * 10 / np.pi)  # stima bocca
        t = x_m / (r_mouth * 1.2)
        r = r_mouth * np.sin(t * np.pi / 2) if t < 1 else r_mouth
        r = max(r, np.sqrt(throat_area_m2 / np.pi))
        return np.pi * r ** 2

    elif expansion_type == EXPANSION_HYPEX:
        # Profilo hypex (ibrido tractrix-esponenziale)
        # Usa approssimazione semplificata
        t = x_m * flare_rate_m
        r0 = np.sqrt(throat_area_m2 / np.pi)
        r = r0 * np.cosh(t * 0.5) * np.exp(t * 0.3)
        return np.pi * r ** 2

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
    expansion_type: str = EXPANSION_EXPONENTIAL
) -> float:
    """
    Calcola il volume di accoppiamento della tromba (volume equivalente).

    Per espansione esponenziale: V = S0 / m * (exp(m*L) - 1)

    Args:
        throat_area_m2: Area della gola in m²
        horn_length_m: Lunghezza tromba in m
        flare_rate_m: Tasso di svasatura m⁻¹
        expansion_type: Tipo di espansione

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
        areas = np.array([area_at_position(xi, throat_area_m2, flare_rate_m, expansion_type)
                          for xi in x])
        _trapz = getattr(np, "trapezoid", np.trapz)  # NumPy ≥2.0 / <2.0 compat
        return _trapz(areas, x)


def calculate_horn_sections(
    throat_area_m2: float,
    horn_length_m: float,
    flare_rate_m: float,
    expansion_type: str = EXPANSION_EXPONENTIAL,
    n_sections: int = NUM_HORN_SECTIONS
) -> List[HornSection]:
    """
    Calcola le sezioni della tromba per costruzione e visualizzazione.

    Args:
        throat_area_m2: Area della gola in m²
        horn_length_m: Lunghezza tromba in m
        flare_rate_m: Tasso di svasatura m⁻¹
        expansion_type: Tipo di espansione
        n_sections: Numero di sezioni da calcolare

    Returns:
        Lista di oggetti HornSection
    """
    sections = []
    positions = np.linspace(0, 1, n_sections + 1)[1:]  # esclude posizione 0

    for i, pos in enumerate(positions):
        x = pos * horn_length_m
        area = area_at_position(x, throat_area_m2, flare_rate_m, expansion_type)
        radius = np.sqrt(area / np.pi)

        sections.append(HornSection(
            position=pos,
            x_m=x,
            area_m2=area,
            radius_m=radius,
            width_m=2 * radius,   # profilo circolare -> larghezza = diametro
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
    n_sections: int = NUM_HORN_SECTIONS
) -> HornGeometry:
    """
    Progetta una tromba acustica a partire dai parametri fondamentali.

    Questa è la funzione principale che replica i calcoli del foglio
    di calcolo Horn Calculator originale.

    Args:
        cutoff_freq_hz: Frequenza di taglio in Hz
        driver_sd_m2: Area del diaframma del driver in m²
        smouth_sthroat_ratio: Rapporto area bocca/gola
        throat_compression_ratio: Rapporto di compressione alla gola
        expansion_type: Tipo di espansione
        c: Velocità del suono in m/s
        rho: Densità dell'aria in kg/m³
        n_sections: Numero di sezioni da calcolare

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
    # 1. Flare rate
    m = calculate_flare_rate(cutoff_freq_hz, c, expansion_type)

    # 2. Area gola
    s_throat = calculate_throat_area(driver_sd_m2, throat_compression_ratio)

    # 3. Area bocca
    s_mouth = calculate_mouth_area(s_throat, smouth_sthroat_ratio)

    # 4. Lunghezza tromba
    horn_length = calculate_horn_length(s_throat, s_mouth, m, expansion_type)

    # 5. Impedenza alla gola
    z_throat = calculate_throat_impedance(s_throat, c, rho)

    # 6. Volume di accoppiamento
    v_coupling = calculate_coupling_volume(s_throat, horn_length, m, expansion_type)

    # 7. Sezioni progressive
    sections = calculate_horn_sections(
        s_throat, horn_length, m, expansion_type, n_sections
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
    Calcola il fattore di direttività della tromba in funzione della frequenza.

    Args:
        frequencies: Array di frequenze in Hz
        mouth_radius_m: Raggio della bocca in metri
        c: Velocità del suono in m/s

    Returns:
        Array di angolo a -6dB in gradi
    """
    # Angolo a -6dB approssimato per pistone circolare
    ka = 2 * np.pi * frequencies * mouth_radius_m / c
    # Angolo di copertura a -6dB (approssimazione)
    angle_rad = np.arcsin(np.minimum(1.08 / np.maximum(ka, 0.1), 1.0))
    return np.degrees(angle_rad)
