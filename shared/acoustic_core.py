"""
Modulo core per calcoli acustici condivisi tra SubSim e BTK Speaker Designer.
Contiene formule fisiche fondamentali per l'acustica.
"""

import numpy as np
from typing import Union


# Costanti fisiche standard
SPEED_OF_SOUND_0C = 331.3  # m/s a 0°C
AIR_DENSITY_0C = 1.293      # kg/m³ a 0°C, 1 atm
REFERENCE_PRESSURE = 20e-6  # Pa (soglia di udibilità)


def speed_of_sound(temperature_c: float = 20.0) -> float:
    """
    Calcola la velocità del suono in aria in funzione della temperatura.

    Args:
        temperature_c: Temperatura in gradi Celsius (default 20°C)

    Returns:
        Velocità del suono in m/s

    Riferimento: ISO 9613-1:1993
    """
    return 331.3 * np.sqrt(1 + temperature_c / 273.15)


def air_density(temperature_c: float = 20.0, pressure_pa: float = 101325.0) -> float:
    """
    Calcola la densità dell'aria in funzione di temperatura e pressione.

    Args:
        temperature_c: Temperatura in gradi Celsius
        pressure_pa: Pressione atmosferica in Pascal

    Returns:
        Densità dell'aria in kg/m³
    """
    temperature_k = temperature_c + 273.15
    R_air = 287.05  # costante gas secco J/(kg·K)
    return pressure_pa / (R_air * temperature_k)


def spl_from_pressure(pressure_pa: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """
    Calcola il livello di pressione sonora (SPL) da pressione in Pascal.

    Args:
        pressure_pa: Pressione sonora in Pascal

    Returns:
        SPL in dB re 20μPa
    """
    return 20 * np.log10(np.abs(pressure_pa) / REFERENCE_PRESSURE)


def pressure_from_spl(spl_db: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """
    Calcola la pressione sonora in Pascal da SPL in dB.

    Args:
        spl_db: Livello SPL in dB re 20μPa

    Returns:
        Pressione sonora in Pascal
    """
    return REFERENCE_PRESSURE * 10 ** (spl_db / 20)


def wavelength(frequency: Union[float, np.ndarray], c: float = 343.0) -> Union[float, np.ndarray]:
    """
    Calcola la lunghezza d'onda a una data frequenza.

    Args:
        frequency: Frequenza in Hz
        c: Velocità del suono in m/s

    Returns:
        Lunghezza d'onda in metri
    """
    return c / frequency


def ka_number(frequency: float, radius_m: float, c: float = 343.0) -> float:
    """
    Calcola il numero ka (prodotto numero d'onda per raggio).
    Usato per determinare regime di radiazione di un trasduttore.

    Args:
        frequency: Frequenza in Hz
        radius_m: Raggio in metri
        c: Velocità del suono in m/s

    Returns:
        Numero ka adimensionale
    """
    k = 2 * np.pi * frequency / c
    return k * radius_m


def acoustic_impedance(medium_density: float, sound_speed: float) -> float:
    """
    Calcola l'impedenza acustica caratteristica di un mezzo.

    Args:
        medium_density: Densità del mezzo in kg/m³
        sound_speed: Velocità del suono nel mezzo in m/s

    Returns:
        Impedenza acustica caratteristica in Pa·s/m (Rayl)
    """
    return medium_density * sound_speed


def boundary_gain_db(position: str) -> float:
    """
    Calcola il guadagno di boundary (carico acustico) per diverse configurazioni.

    Args:
        position: Posizione del subwoofer:
                  'free'   - campo libero (4π): 0 dB
                  'wall'   - mezzo spazio (1 parete): +6 dB
                  'edge'   - quarto spazio (2 pareti): +12 dB
                  'corner' - ottavo spazio (3 pareti): +18 dB

    Returns:
        Guadagno in dB

    Riferimento: Beranek, "Acoustics" (1954)
    """
    gains = {
        'free': 0.0,
        'wall': 6.0,
        'edge': 12.0,
        'corner': 18.0,
    }
    return gains.get(position.lower(), 0.0)


def transmission_loss(
    frequency: Union[float, np.ndarray],
    mass_surface_density: float
) -> Union[float, np.ndarray]:
    """
    Calcola la perdita di trasmissione (TL) secondo la Mass Law.

    Args:
        frequency: Frequenza in Hz
        mass_surface_density: Densità superficiale di massa in kg/m²
                              (densità × spessore)

    Returns:
        TL in dB

    Riferimento: Bies & Hansen, "Engineering Noise Control" (4th ed.)
    """
    return 20 * np.log10(mass_surface_density * frequency) - 42


def octave_band_frequencies(f_low: float = 20.0, f_high: float = 20000.0) -> np.ndarray:
    """
    Genera le frequenze delle bande di terzo di ottava standard.

    Args:
        f_low: Frequenza minima in Hz
        f_high: Frequenza massima in Hz

    Returns:
        Array di frequenze in Hz
    """
    # Frequenze nominali di terzo di ottava (ISO 266)
    nominal = np.array([
        20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160,
        200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600,
        2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000
    ])
    return nominal[(nominal >= f_low) & (nominal <= f_high)]
