"""
Combinatore per sistemi Fullrange (CD + SUB in unica cassa).
Gestisce il crossover, la somma acustica e l'ottimizzazione delle dimensioni.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple

from .driver_model import DriverModel
from .horn_model import HornModel
from .horn_calculator import HornGeometry, design_horn, horn_frequency_response
from .geometry import CabinetGeometry
from .constants import CROSSOVER_FREQ_DEFAULT, SPEED_OF_SOUND


@dataclass
class CrossoverSettings:
    """Impostazioni del crossover per sistema fullrange."""
    frequency_hz: float = CROSSOVER_FREQ_DEFAULT
    slope_db_octave: float = 24.0    # pendenza del crossover: 6, 12, 18, 24 dB/ottava
    alignment: str = "butterworth"   # 'butterworth', 'linkwitz_riley', 'bessel'
    time_alignment_ms: float = 0.0   # ritardo temporale per allineamento fase


@dataclass
class FullrangeSystem:
    """
    Sistema acustico fullrange con sezione HF (CD) e LF (SUB).

    Rappresenta una cassa a 2 vie con tromba per la sezione medi/alti
    e sezione di subwoofer con tromba per le basse frequenze.
    """
    # ─── Sezione HF (Compression Driver) ─────────────────────────────────────
    hf_driver: Optional[DriverModel] = None
    hf_horn: Optional[HornGeometry] = None       # geometria tromba HF calcolata
    hf_horn_model: Optional[HornModel] = None    # tromba HF da database (alternativa)

    # ─── Sezione LF (Subwoofer) ───────────────────────────────────────────────
    lf_driver: Optional[DriverModel] = None
    lf_horn: Optional[HornGeometry] = None       # geometria tromba LF calcolata
    lf_horn_model: Optional[HornModel] = None    # tromba LF da database (alternativa)

    # ─── Crossover ───────────────────────────────────────────────────────────
    crossover: CrossoverSettings = field(default_factory=CrossoverSettings)

    # ─── Disposizione fisica ─────────────────────────────────────────────────
    hf_position: str = "top"          # posizione CD: 'top', 'center', 'bottom'
    hf_offset_m: float = 0.0          # offset verticale del CD in m
    lf_offset_m: float = 0.0          # offset verticale del sub in m

    # ─── Risultati ───────────────────────────────────────────────────────────
    combined_cabinet: Optional[CabinetGeometry] = None

    def is_valid(self) -> bool:
        return (self.hf_driver is not None and
                self.lf_driver is not None and
                (self.hf_horn is not None or self.hf_horn_model is not None) and
                (self.lf_horn is not None or self.lf_horn_model is not None))

    def get_path_difference_m(self) -> float:
        """
        Calcola la differenza di cammino acustico tra le due sezioni.
        Usato per il calcolo del ritardo di fase al crossover.
        """
        hf_length = self.hf_horn.horn_length_m if self.hf_horn else 0.25
        lf_length = self.lf_horn.horn_length_m if self.lf_horn else 0.5
        # Differenza di percorso include l'offset fisico tra i driver
        return abs(hf_length - lf_length) + abs(self.hf_offset_m - self.lf_offset_m)


def butterworth_crossover(
    frequencies: np.ndarray,
    crossover_freq: float,
    order: int = 4
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calcola filtri Butterworth di ordine n per crossover.

    Args:
        frequencies: Array di frequenze in Hz
        crossover_freq: Frequenza di crossover in Hz
        order: Ordine del filtro (2=12dB/ott, 4=24dB/ott)

    Returns:
        Tupla (hpf_response, lpf_response) in dB
    """
    # Frequenza normalizzata
    omega = frequencies / crossover_freq

    # Butterworth HPF (passa-alto)
    hpf_linear = omega ** order / np.sqrt(1 + omega ** (2 * order))
    hpf_db = 20 * np.log10(np.maximum(hpf_linear, 1e-10))

    # Butterworth LPF (passa-basso): complementare al HPF
    lpf_linear = 1 / np.sqrt(1 + omega ** (2 * order))
    lpf_db = 20 * np.log10(np.maximum(lpf_linear, 1e-10))

    return hpf_db, lpf_db


def linkwitz_riley_crossover(
    frequencies: np.ndarray,
    crossover_freq: float,
    order: int = 4
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calcola filtri Linkwitz-Riley (Butterworth al quadrato) per crossover.
    Garantisce somma flat (0dB) alla frequenza di crossover.

    Args:
        frequencies: Array di frequenze in Hz
        crossover_freq: Frequenza di crossover in Hz
        order: Ordine del filtro (4=24dB/ott, 8=48dB/ott)

    Returns:
        Tupla (hpf_response, lpf_response) in dB
    """
    omega = frequencies / crossover_freq
    half_order = order // 2

    # LR = Butterworth al quadrato
    lpf_linear = 1 / (1 + omega ** (2 * half_order))
    hpf_linear = omega ** order / (1 + omega ** (2 * half_order)) ** 2

    # Normalizza a 0dB @ fc
    hpf_db = 20 * np.log10(np.maximum(hpf_linear, 1e-10))
    lpf_db = 20 * np.log10(np.maximum(lpf_linear, 1e-10))

    return hpf_db, lpf_db


def calculate_combined_response(
    system: FullrangeSystem,
    frequencies: np.ndarray,
    c: float = SPEED_OF_SOUND
) -> dict:
    """
    Calcola la risposta in frequenza combinata del sistema fullrange.

    Tiene conto di:
    - Risposta del driver HF + tromba HF filtrata dal HPF
    - Risposta del driver LF + tromba LF filtrata dal LPF
    - Differenza di fase tra le sezioni
    - Somma vettoriale all'uscita

    Args:
        system: Sistema fullrange configurato
        frequencies: Array di frequenze in Hz
        c: Velocità del suono in m/s

    Returns:
        Dizionario con risposte HF, LF e combinata in dB e fase
    """
    if not system.is_valid():
        raise ValueError("Il sistema fullrange non è configurato completamente")

    crossover_freq = system.crossover.frequency_hz
    slope = system.crossover.slope_db_octave
    order = max(2, int(slope / 6))  # da dB/ottava a ordine filtro

    # Filtri crossover
    if system.crossover.alignment == "linkwitz_riley":
        hpf_db, lpf_db = linkwitz_riley_crossover(frequencies, crossover_freq, order)
    else:
        hpf_db, lpf_db = butterworth_crossover(frequencies, crossover_freq, order)

    # Risposta HF (CD + tromba HF + HPF)
    hf_spl_base = system.hf_driver.spl_1w_1m
    if system.hf_horn:
        hf_horn_amp, hf_horn_phase = horn_frequency_response(frequencies, system.hf_horn, c)
    else:
        hf_horn_amp = np.zeros_like(frequencies)
        hf_horn_phase = np.zeros_like(frequencies)

    hf_total_db = hf_spl_base + hf_horn_amp + hpf_db

    # Risposta LF (Sub + tromba LF + LPF)
    lf_spl_base = system.lf_driver.spl_1w_1m
    if system.lf_horn:
        lf_horn_amp, lf_horn_phase = horn_frequency_response(frequencies, system.lf_horn, c)
    else:
        lf_horn_amp = np.zeros_like(frequencies)
        lf_horn_phase = np.zeros_like(frequencies)

    lf_total_db = lf_spl_base + lf_horn_amp + lpf_db

    # Ritardo di fase tra HF e LF (differenza di percorso fisico)
    path_diff = system.get_path_difference_m()
    phase_delay = 2 * np.pi * frequencies * path_diff / c

    # Converti in pressioni lineari
    hf_pressure = 10 ** (hf_total_db / 20)
    lf_pressure = 10 ** (lf_total_db / 20)

    # Fasor HF
    hf_phasor = hf_pressure * np.exp(1j * (hf_horn_phase + system.crossover.time_alignment_ms * 2 * np.pi * frequencies * 0.001))

    # Fasor LF (con ritardo di percorso)
    lf_phasor = lf_pressure * np.exp(1j * (lf_horn_phase + phase_delay))

    # Somma
    combined_phasor = hf_phasor + lf_phasor
    combined_spl = 20 * np.log10(np.maximum(np.abs(combined_phasor), 1e-10))
    combined_phase = np.angle(combined_phasor, deg=True)

    return {
        "frequencies": frequencies,
        "hf_spl_db": hf_total_db,
        "lf_spl_db": lf_total_db,
        "combined_spl_db": combined_spl,
        "combined_phase_deg": combined_phase,
        "hpf_db": hpf_db,
        "lpf_db": lpf_db,
        "crossover_freq_hz": crossover_freq,
        "path_difference_m": path_diff,
    }


def design_fullrange_system(
    hf_driver: DriverModel,
    lf_driver: DriverModel,
    crossover_freq: float = CROSSOVER_FREQ_DEFAULT,
    hf_cutoff_hz: float = 700.0,
    lf_cutoff_hz: float = 50.0,
    hf_smouth_ratio: float = 5.0,
    lf_smouth_ratio: float = 2.0,
    hf_compression_ratio: float = 10.0,
    lf_compression_ratio: float = 1.0,
    crossover_slope: float = 24.0,
    c: float = SPEED_OF_SOUND
) -> FullrangeSystem:
    """
    Progetta un sistema fullrange completo CD + SUB.

    Args:
        hf_driver: Driver per la sezione alti (compression driver)
        lf_driver: Driver per la sezione bassi (subwoofer)
        crossover_freq: Frequenza di crossover in Hz
        hf_cutoff_hz: Frequenza di taglio tromba HF in Hz
        lf_cutoff_hz: Frequenza di taglio tromba LF in Hz
        hf_smouth_ratio: Rapporto bocca/gola tromba HF
        lf_smouth_ratio: Rapporto bocca/gola tromba LF
        hf_compression_ratio: Rapporto di compressione alla gola HF
        lf_compression_ratio: Rapporto di compressione alla gola LF
        crossover_slope: Pendenza crossover in dB/ottava
        c: Velocità del suono in m/s

    Returns:
        FullrangeSystem configurato e pronto per i calcoli
    """
    # Progetta tromba HF
    hf_horn = design_horn(
        cutoff_freq_hz=hf_cutoff_hz,
        driver_sd_m2=hf_driver.sd,
        smouth_sthroat_ratio=hf_smouth_ratio,
        throat_compression_ratio=hf_compression_ratio,
        c=c
    )

    # Progetta tromba LF
    lf_horn = design_horn(
        cutoff_freq_hz=lf_cutoff_hz,
        driver_sd_m2=lf_driver.sd,
        smouth_sthroat_ratio=lf_smouth_ratio,
        throat_compression_ratio=lf_compression_ratio,
        c=c
    )

    crossover = CrossoverSettings(
        frequency_hz=crossover_freq,
        slope_db_octave=crossover_slope,
        alignment="linkwitz_riley"
    )

    return FullrangeSystem(
        hf_driver=hf_driver,
        hf_horn=hf_horn,
        lf_driver=lf_driver,
        lf_horn=lf_horn,
        crossover=crossover
    )
