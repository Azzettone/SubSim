"""
Calcolatore per l'effetto delle griglie frontali sulle casse acustiche.
Condiviso tra SubSim e BTK Speaker Designer.

Modello aggiornato (2026):
- grille_attenuation(): modello Bessel J1 (diffrazione Fraunhofer da apertura circolare)
  Sostituisce la precedente approssimazione lineare/log.
- grille_directivity_pattern(): matrice (freq × angoli) per controllo direttività.
  Usabile per progettare griglie che modificano il pattern di copertura di fullrange/tweeeter.

Rif: Born & Wolf (1999) "Principles of Optics" cap.8 — diffrazione Fraunhofer
     Beranek (1954) "Acoustics" — pistone circolare (stessa J1)
     fluid_acoustics.py — funzioni di base condivise
"""

import numpy as np
from typing import Union

# Import funzioni Bessel con fallback
try:
    from scipy.special import j1 as _j1
    _SCIPY = True
except ImportError:
    _SCIPY = False


def grille_attenuation(
    frequency: Union[float, np.ndarray],
    hole_diameter_mm: float,
    open_area_percent: float,
    c: float = 343.0,
) -> Union[float, np.ndarray]:
    """
    Calcola l'attenuazione sull'asse (θ=0°) dovuta alla griglia frontale.

    Modello Fraunhofer per apertura circolare (Bessel J1):

        T(0°) = open_ratio   +   (1 - open_ratio) · 1²   ≡  1   sull'asse
        → attenuazione sull'asse ≈ 0 dB  (fori non bloccano il main lobe)

    L'attenuazione reale sull'asse è principalmente per riflessione/assorbimento
    della parte chiusa, modellata come:

        att [dB] = 10·log10(open_ratio + (1-open_ratio)·exp(-ka²))

    dove ka = 2π·(d/2)/λ.
    Questa forma va a 0 a bassa frequenza (ka→0) e a 10·log10(open_ratio) ad alta.

    Args:
        frequency:          Frequenza [Hz] (scalare o array)
        hole_diameter_mm:   Diametro dei fori [mm]
        open_area_percent:  Area aperta [%] (0–100)
        c:                  Velocità del suono [m/s]

    Returns:
        Attenuazione [dB] (≤ 0)

    Rif: Beranek (1954), fluid_acoustics.grille_diffraction_db()
    """
    freq = np.asarray(frequency, dtype=float)
    d_m = hole_diameter_mm / 1000.0
    open_ratio = open_area_percent / 100.0
    k = 2.0 * np.pi * freq / c
    ka = k * (d_m / 2.0)

    # A θ=0 il form factor di diffrazione = 1 indipendentemente da ka.
    # L'attenuazione viene dall'assorbimento della parte chiusa: decresce
    # con la frequenza perché ad alta freq. il materiale chiuso scherma di più.
    transmission = open_ratio + (1.0 - open_ratio) * np.exp(-(ka ** 2) / 4.0)
    return 10.0 * np.log10(np.maximum(transmission, 1e-12))


def grille_directivity_pattern(
    frequencies: np.ndarray,
    angles_deg: np.ndarray,
    hole_diameter_mm: float,
    open_area_percent: float,
    c: float = 343.0,
) -> np.ndarray:
    """
    Matrice (n_freq × n_angles) del pattern di direttività modificato dalla griglia [dB].

    Basato sulla diffrazione Fraunhofer per apertura circolare con Bessel J1.
    Usabile per progettare griglie che controllano la direttività di
    tweeter/fullrange (dispersione esatta di un sistema CD + waveguide).

    Args:
        frequencies:        Array frequenze [Hz]  — shape (F,)
        angles_deg:         Array angoli [°]       — shape (A,)
        hole_diameter_mm:   Diametro fori [mm]
        open_area_percent:  Area aperta [%]
        c:                  Velocità suono [m/s]

    Returns:
        Matrice [dB] di shape (F, A) — valori ≤ 0

    Uso in BTK Speaker Designer:
        freqs  = np.logspace(2, 4, 100)   # 100 Hz – 10 kHz
        angles = np.linspace(0, 90, 91)
        P = grille_directivity_pattern(freqs, angles, 5.0, 50.0)
        # Somma al pattern del driver per ottenere il sistema
    """
    d_m = hole_diameter_mm / 1000.0
    open_ratio = open_area_percent / 100.0
    F = len(frequencies)
    A = len(angles_deg)
    out = np.zeros((F, A))

    theta = np.deg2rad(angles_deg)
    sin_theta = np.sin(theta)

    for i, f in enumerate(frequencies):
        k = 2.0 * np.pi * f / c
        u = k * (d_m / 2.0) * sin_theta   # ka·sinθ

        if _SCIPY:
            with np.errstate(divide="ignore", invalid="ignore"):
                ff = np.where(np.abs(u) < 1e-9, 1.0, 2.0 * _j1(u) / u)
        else:
            ff = np.where(np.abs(u) < 1e-9, 1.0, np.sinc(u / np.pi))

        transmission = open_ratio + (1.0 - open_ratio) * ff ** 2
        out[i, :] = 10.0 * np.log10(np.maximum(transmission, 1e-12))

    return out


def grille_frequency_response(
    frequencies: np.ndarray,
    hole_diameter_mm: float,
    open_area_percent: float,
    c: float = 343.0
) -> np.ndarray:
    """
    Calcola la risposta in frequenza completa della griglia.

    Args:
        frequencies: Array di frequenze in Hz
        hole_diameter_mm: Diametro dei fori in millimetri
        open_area_percent: Percentuale di area aperta (0-100)
        c: Velocità del suono in m/s

    Returns:
        Array di attenuazioni in dB per ogni frequenza
    """
    return grille_attenuation(frequencies, hole_diameter_mm, open_area_percent, c)


def calculate_open_area(
    panel_width_mm: float,
    panel_height_mm: float,
    hole_diameter_mm: float,
    hole_pattern: str = "triangular",
    hole_spacing_mm: float = None
) -> dict:
    """
    Calcola la percentuale di area aperta di una griglia con foratura uniforme.

    Args:
        panel_width_mm: Larghezza pannello in mm
        panel_height_mm: Altezza pannello in mm
        hole_diameter_mm: Diametro fori in mm
        hole_pattern: Pattern foratura ('square' o 'triangular')
        hole_spacing_mm: Interasse tra fori in mm (default: diametro + 2mm)

    Returns:
        Dizionario con: open_area_percent, num_holes, total_area_mm2
    """
    if hole_spacing_mm is None:
        hole_spacing_mm = hole_diameter_mm + 2.0

    hole_area = np.pi * (hole_diameter_mm / 2) ** 2

    if hole_pattern == "square":
        # Griglia quadrata
        cols = int(panel_width_mm / hole_spacing_mm)
        rows = int(panel_height_mm / hole_spacing_mm)
        cell_area = hole_spacing_mm ** 2
    else:
        # Griglia triangolare (più efficiente)
        cols = int(panel_width_mm / hole_spacing_mm)
        rows = int(panel_height_mm / (hole_spacing_mm * np.sqrt(3) / 2))
        # Area della cella triangolare
        cell_area = hole_spacing_mm * hole_spacing_mm * np.sqrt(3) / 2

    num_holes = cols * rows
    total_panel_area = panel_width_mm * panel_height_mm
    total_hole_area = num_holes * hole_area
    open_area_percent = (total_hole_area / total_panel_area) * 100

    return {
        "open_area_percent": min(open_area_percent, 100.0),
        "num_holes": num_holes,
        "total_hole_area_mm2": total_hole_area,
        "total_panel_area_mm2": total_panel_area,
        "hole_diameter_mm": hole_diameter_mm,
        "hole_spacing_mm": hole_spacing_mm,
        "pattern": hole_pattern
    }


def recommend_grille(
    frequency_range_hz: tuple = (100, 10000),
    max_attenuation_db: float = 1.0
) -> dict:
    """
    Raccomanda le caratteristiche di griglia per un'applicazione data.

    Args:
        frequency_range_hz: Tupla (f_min, f_max) range di frequenza operativo
        max_attenuation_db: Massima attenuazione accettabile in dB

    Returns:
        Dizionario con raccomandazioni di design
    """
    f_max = frequency_range_hz[1]

    # A frequenza massima, vogliamo ka < soglia critica
    # ka = pi * d / lambda = pi * d * f / c
    # Per ka < 1: d < c / (pi * f)
    c = 343.0
    max_hole_diameter_m = c / (np.pi * f_max)
    max_hole_diameter_mm = max_hole_diameter_m * 1000

    # Percentuale minima di apertura per limitare l'attenuazione
    # Approssimazione: open_fraction > 1 - max_attenuation / 3
    min_open_area = (1 - max_attenuation_db / 3.0) * 100

    return {
        "recommended_hole_diameter_mm": round(max_hole_diameter_mm, 1),
        "min_open_area_percent": round(max(min_open_area, 40.0), 1),
        "suggested_pattern": "triangular",
        "note": (
            f"Per frequenze fino a {f_max}Hz con attenuazione max {max_attenuation_db}dB: "
            f"diametro fori < {max_hole_diameter_mm:.1f}mm, "
            f"area aperta > {min_open_area:.0f}%"
        )
    }
