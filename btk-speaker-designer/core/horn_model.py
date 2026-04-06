"""
Modello per trombe acustiche commerciali (dal database).
Permette di selezionare una tromba esistente invece di progettarne una custom.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class HornModel:
    """
    Rappresenta una tromba acustica commerciale con le sue caratteristiche.
    """

    # ─── Identificazione ──────────────────────────────────────────────────────
    manufacturer: str = ""
    model: str = ""
    horn_type: str = "constant_directivity"
    # Tipi: 'constant_directivity', 'exponential', 'tractrix', 'radial', 'sector'

    # ─── Specifiche geometriche ───────────────────────────────────────────────
    throat_diameter_inch: float = 1.0       # pollici
    mouth_width_cm: float = 30.0            # cm
    mouth_height_cm: float = 20.0           # cm
    length_cm: float = 25.0                 # cm
    flare_rate: float = 0.0                 # m⁻¹ (0 = non specificato)

    # ─── Pattern di direttività ───────────────────────────────────────────────
    coverage_h: float = 90.0    # gradi - copertura orizzontale (-6dB)
    coverage_v: float = 40.0    # gradi - copertura verticale (-6dB)

    # ─── Caratteristiche acustiche ────────────────────────────────────────────
    freq_range_low: float = 500.0    # Hz
    freq_range_high: float = 20000.0  # Hz
    cutoff_freq: float = 500.0       # Hz - frequenza di taglio
    avg_spl_boost: float = 0.0       # dB - incremento SPL medio rispetto a driver libero

    # ─── Dati fisici ──────────────────────────────────────────────────────────
    material: str = "plastic"
    # Materiali: 'plastic', 'aluminum', 'fiberglass', 'wood'
    weight_kg: float = 0.5
    mounting_pattern: str = ""     # es. "4x60mm", "2x76mm"

    # ─── Compatibilità ────────────────────────────────────────────────────────
    compatible_throat_diameters: List[float] = field(default_factory=list)
    # Lista di diametri gola compatibili in pollici

    # ─── Metadati ─────────────────────────────────────────────────────────────
    description: str = ""
    notes: str = ""

    def __post_init__(self):
        if not self.compatible_throat_diameters:
            self.compatible_throat_diameters = [self.throat_diameter_inch]

    @property
    def throat_diameter_m(self) -> float:
        return self.throat_diameter_inch * 0.0254

    @property
    def throat_area_m2(self) -> float:
        r = self.throat_diameter_m / 2
        return np.pi * r ** 2

    @property
    def mouth_area_cm2(self) -> float:
        return self.mouth_width_cm * self.mouth_height_cm

    @property
    def mouth_area_m2(self) -> float:
        return self.mouth_area_cm2 * 0.0001

    @property
    def coverage_pattern(self) -> str:
        return f"{self.coverage_h:.0f}°×{self.coverage_v:.0f}°"

    def is_compatible_with_driver(self, driver_throat_inch: float, tolerance: float = 0.1) -> bool:
        """
        Verifica se la tromba è compatibile con un driver dato.

        Args:
            driver_throat_inch: Diametro gola del driver in pollici
            tolerance: Tolleranza in pollici

        Returns:
            True se compatibile
        """
        for d in self.compatible_throat_diameters:
            if abs(d - driver_throat_inch) <= tolerance:
                return True
        return abs(self.throat_diameter_inch - driver_throat_inch) <= tolerance

    def get_frequency_response_correction(
        self, frequencies: np.ndarray
    ) -> np.ndarray:
        """
        Calcola la correzione della risposta in frequenza rispetto al driver libero.

        Args:
            frequencies: Array di frequenze in Hz

        Returns:
            Array di correzioni in dB
        """
        # Boost sotto la frequenza di taglio
        correction = np.zeros_like(frequencies, dtype=float)

        # Gain della tromba (guadagno per carico acustico)
        # Approx: 6dB per ogni raddoppio della direttività
        throat_area = self.throat_area_m2
        mouth_area = self.mouth_area_m2
        if mouth_area > 0 and throat_area > 0:
            gain_db = 10 * np.log10(mouth_area / throat_area)
        else:
            gain_db = 0.0

        # Sopra la frequenza di taglio: boost completo
        correction = np.where(
            frequencies >= self.cutoff_freq,
            self.avg_spl_boost,
            self.avg_spl_boost * (frequencies / self.cutoff_freq)
        )

        return correction

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manufacturer": self.manufacturer,
            "model": self.model,
            "horn_type": self.horn_type,
            "throat_diameter_inch": self.throat_diameter_inch,
            "mouth_width_cm": self.mouth_width_cm,
            "mouth_height_cm": self.mouth_height_cm,
            "length_cm": self.length_cm,
            "flare_rate": self.flare_rate,
            "coverage_h": self.coverage_h,
            "coverage_v": self.coverage_v,
            "freq_range_low": self.freq_range_low,
            "freq_range_high": self.freq_range_high,
            "cutoff_freq": self.cutoff_freq,
            "avg_spl_boost": self.avg_spl_boost,
            "material": self.material,
            "weight_kg": self.weight_kg,
            "mounting_pattern": self.mounting_pattern,
            "compatible_throat_diameters": self.compatible_throat_diameters,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HornModel":
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})

    def __str__(self) -> str:
        return f"{self.manufacturer} {self.model} ({self.coverage_pattern})"

    def __repr__(self) -> str:
        return (
            f"HornModel({self.manufacturer!r}, {self.model!r}, "
            f"throat={self.throat_diameter_inch}\", "
            f"coverage={self.coverage_pattern}, "
            f"fc={self.cutoff_freq}Hz)"
        )
