"""
Calcolatore per l'effetto delle griglie frontali sulle casse acustiche.
Condiviso tra SubSim e BTK Speaker Designer.
"""

import numpy as np
from typing import Union


def grille_attenuation(
    frequency: Union[float, np.ndarray],
    hole_diameter_mm: float,
    open_area_percent: float,
    c: float = 343.0
) -> Union[float, np.ndarray]:
    """
    Calcola l'attenuazione acustica dovuta alla griglia frontale.

    L'effetto della griglia dipende dal rapporto tra la lunghezza d'onda
    e il diametro dei fori. A basse frequenze (lunghezza d'onda >> diametro),
    l'effetto è minimo. Ad alte frequenze l'attenuazione aumenta.

    Args:
        frequency: Frequenza in Hz (singola o array)
        hole_diameter_mm: Diametro dei fori in millimetri
        open_area_percent: Percentuale di area aperta (0-100)
        c: Velocità del suono in m/s

    Returns:
        Attenuazione in dB (valore negativo indica attenuazione)

    Riferimento: Beranek, "Noise and Vibration Control Engineering" (2006)
    """
    wavelength_mm = (c * 1000) / frequency  # lunghezza d'onda in mm
    ka = 2 * np.pi * (hole_diameter_mm / 2) / wavelength_mm

    # Coefficiente di apertura (0-1)
    open_fraction = open_area_percent / 100.0

    if np.isscalar(ka):
        if ka < 1.0:
            # Basse frequenze: effetto minimo, proporzionale alla chiusura
            attenuation = -0.1 * (1 - open_fraction)
        else:
            # Alte frequenze: effetto maggiore
            attenuation = -3.0 * (1 - open_fraction) * np.log10(ka)
    else:
        attenuation = np.where(
            ka < 1.0,
            -0.1 * (1 - open_fraction),
            -3.0 * (1 - open_fraction) * np.log10(np.maximum(ka, 1e-10))
        )

    return attenuation


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
