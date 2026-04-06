"""
Modello driver acustico con parametri Thiele-Small.
Gestisce subwoofer, compression driver e woofer fullrange.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class DriverModel:
    """
    Modello completo di un driver acustico con parametri Thiele-Small.

    Riferimento: Thiele, "Loudspeakers in Vented Boxes" (1971)
                 Small, "Vented-Box Loudspeaker Systems" (1973)
    """

    # ─── Identificazione ──────────────────────────────────────────────────────
    manufacturer: str = ""
    model: str = ""
    driver_type: str = "subwoofer"  # 'subwoofer', 'woofer', 'compression_driver'

    # ─── Parametri Thiele-Small ───────────────────────────────────────────────
    fs: float = 50.0        # Hz - frequenza di risonanza fondamentale
    re: float = 8.0         # Ω  - resistenza DC bobina mobile
    qes: float = 0.5        # adim. - fattore di merito elettrico
    qms: float = 4.0        # adim. - fattore di merito meccanico
    qts: float = 0.0        # adim. - fattore di merito totale (calcolato)
    vas: float = 100.0      # litri - volume equivalente di complianza
    sd: float = 0.0         # m² - area efficace del diaframma
    xmax: float = 10.0      # mm - escursione massima lineare (picco)
    bl: float = 12.0        # T·m - prodotto forza motrice
    mms: float = 50.0       # g - massa totale mobile
    cms: float = 0.0        # m/N - complianza meccanica (calcolata)
    rms: float = 0.0        # kg/s - resistenza meccanica (calcolata)
    le: float = 0.5         # mH - induttanza bobina mobile

    # ─── Parametri elettro-acustici ───────────────────────────────────────────
    spl_1w_1m: float = 100.0    # dB - sensibilità a 1W/1m
    power_rms: float = 500.0    # W - potenza nominale RMS/AES
    power_program: float = 0.0  # W - potenza nominale programma
    power_peak: float = 0.0     # W - potenza nominale picco
    impedance_nominal: float = 8.0  # Ω - impedenza nominale

    # ─── Caratteristiche fisiche ──────────────────────────────────────────────
    diameter_inch: float = 15.0     # pollici - diametro nominale
    throat_diameter_inch: float = 0.0  # pollici - diametro gola (solo CD)
    weight_kg: float = 5.0          # kg - peso
    magnet_type: str = "ferrite"    # 'ferrite', 'neodymium', 'alnico'
    cone_material: str = "paper"    # 'paper', 'polypropylene', 'carbon', 'aluminum'
    voice_coil_material: str = "aluminum"  # 'aluminum', 'copper', 'ccaw'

    # ─── Range di frequenza ───────────────────────────────────────────────────
    freq_range_low: float = 0.0     # Hz - frequenza minima consigliata
    freq_range_high: float = 0.0    # Hz - frequenza massima consigliata

    # ─── Metadati ─────────────────────────────────────────────────────────────
    description: str = ""
    notes: str = ""

    def __post_init__(self):
        """Calcola parametri derivati dopo inizializzazione."""
        # Calcolo Qts se non fornito
        if self.qts == 0.0 and self.qes > 0 and self.qms > 0:
            self.qts = (self.qes * self.qms) / (self.qes + self.qms)

        # Potenza programma e picco se non fornite
        if self.power_program == 0.0:
            self.power_program = self.power_rms * 2
        if self.power_peak == 0.0:
            self.power_peak = self.power_rms * 4

        # Calcolo Cms se non fornito (Cms = Vas / (rho * c² * Sd²))
        if self.cms == 0.0 and self.vas > 0 and self.sd > 0:
            rho = 1.225
            c = 343.0
            vas_m3 = self.vas * 0.001
            self.cms = vas_m3 / (rho * c ** 2 * self.sd ** 2)

        # Calcolo Rms se non fornito (Rms = 1 / (2*pi*Fs*Qms*Cms))
        if self.rms == 0.0 and self.cms > 0 and self.qms > 0 and self.fs > 0:
            self.rms = 1.0 / (2 * np.pi * self.fs * self.qms * self.cms)

    @property
    def sd_cm2(self) -> float:
        """Area del diaframma in cm²."""
        return self.sd * 10000

    @property
    def vas_m3(self) -> float:
        """Volume equivalente in m³."""
        return self.vas * 0.001

    @property
    def xmax_m(self) -> float:
        """Escursione massima in metri."""
        return self.xmax * 0.001

    @property
    def mms_kg(self) -> float:
        """Massa mobile in kg."""
        return self.mms * 0.001

    @property
    def le_h(self) -> float:
        """Induttanza bobina in Henry."""
        return self.le * 0.001

    @property
    def diameter_m(self) -> float:
        """Diametro nominale in metri."""
        return self.diameter_inch * 0.0254

    @property
    def throat_diameter_m(self) -> float:
        """Diametro gola in metri (solo CD)."""
        return self.throat_diameter_inch * 0.0254

    def max_spl_1m(self, rms_power_w: Optional[float] = None) -> float:
        """
        Calcola il massimo SPL a 1 metro con potenza data.

        Args:
            rms_power_w: Potenza in W (default: potenza nominale)

        Returns:
            SPL massimo in dB
        """
        power = rms_power_w or self.power_rms
        return self.spl_1w_1m + 10 * np.log10(power)

    def calculate_impedance(
        self, frequencies: np.ndarray
    ) -> np.ndarray:
        """
        Calcola la risposta di impedenza elettrica in funzione della frequenza.

        Modello semplificato con picco di risonanza e effetto LE.

        Args:
            frequencies: Array di frequenze in Hz

        Returns:
            Array di impedenze in Ohm
        """
        omega = 2 * np.pi * np.asarray(frequencies, dtype=float)
        omega_s = 2 * np.pi * self.fs if self.fs > 0 else 1.0

        # Avoid division by zero: replace zero frequencies with a tiny positive value
        xs = np.where(omega > 0, omega / omega_s, 1e-12)  # frequenza normalizzata

        # Componente DC (resistenza voce)
        z_dc = self.re

        # Termine di risonanza meccanica: BL²/Zms = Re*Qms/Qes / (1 + j*Qms*(xs - 1/xs))
        # Derivato dalle relazioni T&S standard:
        #   BL² = Re * ωs * Mms / Qes,  Rms = ωs * Mms / Qms
        #   Peak a risonanza: Re * (1 + Qms/Qes)
        if self.qms > 0 and self.qes > 0:
            z_res = (self.re * self.qms / self.qes) / (
                1 + 1j * self.qms * (xs - 1.0 / xs)
            )
        else:
            z_res = np.zeros(len(omega), dtype=complex)

        # Effetto induttanza a frequenze alte
        z_le = 1j * omega * self.le_h

        z_total = z_dc + z_res + z_le

        return np.abs(z_total)

    def to_dict(self) -> Dict[str, Any]:
        """Serializza il driver in dizionario."""
        return {
            "manufacturer": self.manufacturer,
            "model": self.model,
            "driver_type": self.driver_type,
            "fs": self.fs,
            "re": self.re,
            "qes": self.qes,
            "qms": self.qms,
            "qts": self.qts,
            "vas": self.vas,
            "sd": self.sd,
            "xmax": self.xmax,
            "bl": self.bl,
            "mms": self.mms,
            "le": self.le,
            "spl_1w_1m": self.spl_1w_1m,
            "power_rms": self.power_rms,
            "impedance_nominal": self.impedance_nominal,
            "diameter_inch": self.diameter_inch,
            "throat_diameter_inch": self.throat_diameter_inch,
            "weight_kg": self.weight_kg,
            "magnet_type": self.magnet_type,
            "freq_range_low": self.freq_range_low,
            "freq_range_high": self.freq_range_high,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DriverModel":
        """Crea driver da dizionario (es. da JSON database)."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def __str__(self) -> str:
        return f"{self.manufacturer} {self.model} ({self.diameter_inch}\")"

    def __repr__(self) -> str:
        return (
            f"DriverModel({self.manufacturer!r}, {self.model!r}, "
            f"Fs={self.fs}Hz, Qts={self.qts:.3f}, "
            f"Sd={self.sd_cm2:.0f}cm², Vas={self.vas:.1f}L)"
        )


def calculate_driver_efficiency(driver: DriverModel, c: float = 343.0, rho: float = 1.225) -> float:
    """
    Calcola l'efficienza di riferimento (η₀) del driver.

    η₀ = (4π² / c³) * (Fs³ * Vas) / Qes

    Args:
        driver: Modello del driver
        c: Velocità del suono in m/s
        rho: Densità aria in kg/m³

    Returns:
        Efficienza di riferimento (adimensionale, tipicamente 0.0001 - 0.01)

    Riferimento: Thiele (1971)
    """
    if driver.qes <= 0 or driver.vas <= 0 or driver.fs <= 0:
        return 0.0
    vas_m3 = driver.vas_m3
    return (4 * np.pi ** 2 / c ** 3) * (driver.fs ** 3 * vas_m3) / driver.qes


def calculate_sensitivity_from_ts(driver: DriverModel, c: float = 343.0, rho: float = 1.225) -> float:
    """
    Calcola la sensibilità a 1W/1m a partire dai parametri T&S.

    SPL = 10 * log10(η₀) + 112 dB

    Args:
        driver: Modello del driver
        c: Velocità del suono in m/s
        rho: Densità aria in kg/m³

    Returns:
        Sensibilità in dB (1W/1m)
    """
    eta0 = calculate_driver_efficiency(driver, c, rho)
    if eta0 <= 0:
        return 0.0
    return 10 * np.log10(eta0) + 112.0
