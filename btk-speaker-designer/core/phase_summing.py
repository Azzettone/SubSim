"""
Calcolo somma acustica in fase tra emissione frontale (tromba) e posteriore (back radiation).

Quando il retro del cono è a vista (back radiation), si genera:
- Un'onda che percorre il percorso della tromba verso l'ascoltatore
- Un'onda che si propaga direttamente all'indietro

La loro somma all'uscita della tromba determina la risposta in frequenza combinata.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class PhaseSummingResult:
    """Risultato del calcolo di somma in fase fronte/retro."""
    frequencies: np.ndarray
    front_spl: np.ndarray           # SPL emissione frontale (dB)
    back_spl: np.ndarray            # SPL emissione posteriore (dB)
    combined_spl: np.ndarray        # SPL somma combinata (dB)
    phase_difference: np.ndarray    # Differenza di fase (gradi)
    interference_type: np.ndarray   # +1 costruttiva, -1 distruttiva
    path_difference_m: float        # Differenza di cammino in m


def calculate_phase_delay(
    path_length_m: float,
    frequencies: np.ndarray,
    c: float = 343.0
) -> np.ndarray:
    """
    Calcola il ritardo di fase dovuto alla differenza di cammino acustico.

    Args:
        path_length_m: Lunghezza del percorso (differenza di cammino) in m
        frequencies: Array di frequenze in Hz
        c: Velocità del suono in m/s

    Returns:
        Array di sfasamenti in radianti
    """
    return 2 * np.pi * frequencies * path_length_m / c


def sum_front_back_radiation(
    frequencies: np.ndarray,
    front_spl: np.ndarray,
    back_spl: np.ndarray,
    path_difference_m: float,
    front_phase_offset: float = 0.0,
    back_phase_offset: float = np.pi,
    c: float = 343.0
) -> PhaseSummingResult:
    """
    Calcola la somma vettoriale delle emissioni frontale e posteriore del cono.

    L'emissione posteriore è per natura in opposizione di fase rispetto
    alla frontale (il cono si muove avanti/indietro). Tenendo conto del
    percorso acustico della tromba, si calcola l'interferenza risultante.

    Args:
        frequencies: Array di frequenze in Hz
        front_spl: SPL emissione frontale (dB) per ogni frequenza
        back_spl: SPL emissione posteriore (dB) per ogni frequenza
        path_difference_m: Differenza di cammino tra fronte e retro in m
                           (tipicamente = lunghezza tromba + distanza dal cono)
        front_phase_offset: Offset fase fronte in rad (default: 0)
        back_phase_offset: Offset fase retro in rad (default: π - opposta)
        c: Velocità del suono in m/s

    Returns:
        PhaseSummingResult con tutti i risultati del calcolo

    Esempio:
        >>> freqs = np.logspace(np.log10(50), np.log10(5000), 200)
        >>> front = np.full_like(freqs, 100.0)  # 100 dB costante
        >>> back = np.full_like(freqs, 94.0)    # 6 dB più basso
        >>> result = sum_front_back_radiation(freqs, front, back, 0.3)
    """
    # Converti SPL in pressione lineare (normalizzata a 1 per 0 dB)
    front_pressure = 10 ** (front_spl / 20)
    back_pressure = 10 ** (back_spl / 20)

    # Ritardo di fase dovuto alla differenza di percorso
    delta_phase = calculate_phase_delay(path_difference_m, frequencies, c)

    # Fasor fronte
    front_phasor = front_pressure * np.exp(1j * front_phase_offset)

    # Fasor retro (include ritardo del percorso e offset di fase naturale)
    back_phasor = back_pressure * np.exp(1j * (back_phase_offset + delta_phase))

    # Somma vettoriale
    total_phasor = front_phasor + back_phasor

    # Conversione in dB
    combined_spl = 20 * np.log10(np.maximum(np.abs(total_phasor), 1e-10))

    # Differenza di fase tra fronte e retro
    total_phase_diff = (back_phase_offset + delta_phase - front_phase_offset)
    phase_diff_degrees = np.degrees(total_phase_diff % (2 * np.pi))

    # Tipo di interferenza: costruttiva (<90° o >270°), distruttiva (90°-270°)
    phase_mod = phase_diff_degrees % 360
    interference = np.where(
        (phase_mod < 90) | (phase_mod > 270),
        1,   # costruttiva
        -1   # distruttiva
    )

    return PhaseSummingResult(
        frequencies=frequencies,
        front_spl=front_spl,
        back_spl=back_spl,
        combined_spl=combined_spl,
        phase_difference=phase_diff_degrees,
        interference_type=interference,
        path_difference_m=path_difference_m
    )


def calculate_back_radiation_spl(
    front_spl: np.ndarray,
    frequencies: np.ndarray,
    damping_factor: float = 0.5
) -> np.ndarray:
    """
    Stima il livello SPL dell'emissione posteriore del cono.

    L'emissione posteriore dipende dalla struttura del cabinet:
    - Cabinet aperto (back radiation a vista): ~6 dB sotto il fronte
    - Cabinet con apertura controllata: attenuazione variabile per frequenza
    - Cabinet chiuso: forte attenuazione, specialmente alle alte frequenze

    Args:
        front_spl: SPL frontale in dB
        frequencies: Array di frequenze in Hz
        damping_factor: Fattore di smorzamento dell'emissione posteriore
                        0.0 = nessuna attenuazione
                        0.5 = -6 dB (valore tipico per apertura a vista)
                        1.0 = -20 dB (forte smorzamento)

    Returns:
        Array di SPL posteriore in dB
    """
    # Attenuazione base
    attenuation_db = -20 * damping_factor

    # A frequenze alte, la direttività del cono riduce l'emissione posteriore
    # Approssimazione: -6dB per ottava sopra la frequenza di breakup
    freq_breakup = 1000.0
    high_freq_attenuation = np.where(
        frequencies > freq_breakup,
        -6 * np.log2(frequencies / freq_breakup),
        0.0
    )

    return front_spl + attenuation_db + high_freq_attenuation


def calculate_path_difference(
    horn_length_m: float,
    driver_depth_m: float = 0.05,
    baffle_to_driver_m: float = 0.0
) -> float:
    """
    Calcola la differenza di cammino tra emissione frontale e posteriore.

    La differenza di cammino è determinata da:
    - Lunghezza della tromba
    - Profondità del driver nel cabinet
    - Distanza tra il baffle e il driver

    Args:
        horn_length_m: Lunghezza della tromba in m
        driver_depth_m: Profondità del driver nel cabinet in m
        baffle_to_driver_m: Distanza baffle-driver in m

    Returns:
        Differenza di cammino in m
    """
    return horn_length_m + driver_depth_m + baffle_to_driver_m


def find_interference_frequencies(
    path_difference_m: float,
    c: float = 343.0,
    f_min: float = 20.0,
    f_max: float = 20000.0
) -> dict:
    """
    Trova le frequenze di interferenza costruttiva e distruttiva.

    Interferenza costruttiva: percorso = n * λ (pressioni in fase)
    Interferenza distruttiva: percorso = (n + 0.5) * λ (pressioni in opposizione)

    Args:
        path_difference_m: Differenza di cammino in m
        c: Velocità del suono in m/s
        f_min: Frequenza minima di interesse in Hz
        f_max: Frequenza massima di interesse in Hz

    Returns:
        Dizionario con liste di frequenze costruttive e distruttive
    """
    constructive = []
    destructive = []

    n = 1
    while True:
        # Interferenza costruttiva: f = n * c / path
        f_constr = n * c / path_difference_m
        if f_constr > f_max:
            break
        if f_constr >= f_min:
            constructive.append(round(f_constr, 1))

        # Interferenza distruttiva: f = (2n-1) * c / (2 * path)
        f_destr = (2 * n - 1) * c / (2 * path_difference_m)
        if f_destr >= f_min and f_destr <= f_max:
            destructive.append(round(f_destr, 1))

        n += 1

    return {
        "constructive_hz": constructive,
        "destructive_hz": destructive,
        "path_difference_m": path_difference_m,
        "fundamental_hz": c / path_difference_m
    }


def calculate_combined_response(
    frequencies: np.ndarray,
    driver_spl_1w: float,
    horn_gain_db: float,
    horn_length_m: float,
    driver_depth_m: float = 0.05,
    back_radiation_open: bool = True,
    damping_factor: float = 0.5,
    c: float = 343.0
) -> PhaseSummingResult:
    """
    Funzione di alto livello per calcolare la risposta combinata completa.

    Args:
        frequencies: Array di frequenze in Hz
        driver_spl_1w: Sensibilità del driver a 1W/1m in dB
        horn_gain_db: Guadagno della tromba in dB
        horn_length_m: Lunghezza della tromba in m
        driver_depth_m: Profondità del driver in m
        back_radiation_open: True se il retro del cono è a vista
        damping_factor: Fattore di smorzamento emissione posteriore (0-1)
        c: Velocità del suono in m/s

    Returns:
        PhaseSummingResult completo
    """
    # SPL frontale (driver + guadagno tromba)
    front_spl = np.full_like(frequencies, driver_spl_1w + horn_gain_db)

    # SPL posteriore
    if back_radiation_open:
        back_spl = calculate_back_radiation_spl(front_spl, frequencies, damping_factor)
    else:
        back_spl = np.full_like(frequencies, -60.0)  # praticamente nulla se chiuso

    # Differenza di cammino
    path_diff = calculate_path_difference(horn_length_m, driver_depth_m)

    return sum_front_back_radiation(
        frequencies=frequencies,
        front_spl=front_spl,
        back_spl=back_spl,
        path_difference_m=path_diff,
        c=c
    )
