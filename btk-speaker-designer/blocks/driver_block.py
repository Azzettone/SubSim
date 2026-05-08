"""
DriverBlock — wrapper geometrico del driver da database.

Rappresenta il driver fisico installato nel cabinet. Non genera pannelli
propri (è "ospite" di un altro pannello tramite cutout) ma espone:
  - ConnectionPort "front": lato emissivo (verso tromba o aria)
  - ConnectionPort "back":  lato cono posteriore (verso camera)
  - cutout circolare per montaggio sul pannello ospite
  - volume occupato dal cestello (sottratto dal volume camera)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from ..core.driver_model import DriverModel
from .base_block import (
    Block, Panel, ConnectionPort, ValidationWarning, Severity,
)


_ORIENTATION_VECTORS: Dict[str, np.ndarray] = {
    "forward":  np.array([0.0, 0.0,  1.0]),
    "backward": np.array([0.0, 0.0, -1.0]),
    "up":       np.array([0.0,  1.0, 0.0]),
    "down":     np.array([0.0, -1.0, 0.0]),
    "right":    np.array([ 1.0, 0.0, 0.0]),
    "left":     np.array([-1.0, 0.0, 0.0]),
}


@dataclass
class DriverBlock(Block):
    """
    Driver fisico montato in un cabinet/tromba.

    Args:
        driver: DriverModel (T&S) dal database
        orientation: direzione di emissione del cono ("forward" = +Z)
        mounting_depth: profondità a cui sporge il cestello dal piano di
            montaggio (m). Usato per stimare il volume occupato.
        position: punto centrale di montaggio nello spazio globale (3,)
        basket_volume: volume occupato dal cestello (m³). Se None viene
            stimato come 0.6·Sd·mounting_depth (approssimazione conservativa).
    """
    driver: DriverModel
    orientation: str = "forward"
    mounting_depth: float = 0.0
    position: np.ndarray = None  # type: ignore[assignment]
    basket_volume: Optional[float] = None

    block_type = "driver"

    def __post_init__(self) -> None:
        if self.orientation not in _ORIENTATION_VECTORS:
            raise ValueError(
                f"orientation deve essere in {list(_ORIENTATION_VECTORS)}, "
                f"ricevuto: {self.orientation!r}"
            )
        if self.position is None:
            self.position = np.zeros(3)
        self.position = np.asarray(self.position, dtype=float).reshape(3)
        if self.driver.sd <= 0:
            raise ValueError("DriverBlock: driver.sd deve essere > 0")
        if self.basket_volume is None:
            # Stima: cestello = 0.6 × Sd × mounting_depth
            self.basket_volume = 0.6 * self.driver.sd * max(
                self.mounting_depth, 0.05
            )

    @property
    def front_normal(self) -> np.ndarray:
        return _ORIENTATION_VECTORS[self.orientation].copy()

    @property
    def back_normal(self) -> np.ndarray:
        return -_ORIENTATION_VECTORS[self.orientation]

    @property
    def diameter_emission(self) -> float:
        """Diametro equivalente dell'area emissiva Sd."""
        return 2.0 * float(np.sqrt(self.driver.sd / np.pi))

    # ── Block API ────────────────────────────────────────────────────────────

    @property
    def panels(self) -> List[Panel]:
        # Il driver non genera pannelli propri (montato su pannello ospite)
        return []

    @property
    def connection_ports(self) -> Dict[str, ConnectionPort]:
        diameter = self.diameter_emission
        return {
            "front": ConnectionPort(
                name="front",
                position=self.position.copy(),
                normal=self.front_normal,
                area=self.driver.sd,
                shape="circular",
                width=diameter,
                height=diameter,
            ),
            "back": ConnectionPort(
                name="back",
                position=self.position - self.front_normal * self.mounting_depth,
                normal=self.back_normal,
                area=self.driver.sd,
                shape="circular",
                width=diameter,
                height=diameter,
            ),
        }

    @property
    def bounding_box(self) -> tuple[float, float, float]:
        # Cilindro Sd × mounting_depth: bbox lungo orientation
        d = self.diameter_emission
        depth = self.mounting_depth
        # Restituisce dimensioni lungo X, Y, Z in valore assoluto
        n = np.abs(self.front_normal)
        # Il "tubo" del driver: depth lungo n, d sugli altri assi
        ext = d * (1.0 - n) + depth * n
        return (float(ext[0]), float(ext[1]), float(ext[2]))

    @property
    def internal_volume(self) -> float:
        # Il driver non racchiude volume aria proprio (è solido)
        # basket_volume è il volume *occupato*, non racchiuso.
        return 0.0

    @property
    def occupied_volume(self) -> float:
        """Volume sottratto dalla camera in cui il driver è montato."""
        return float(self.basket_volume or 0.0)

    def cutout_for_panel(self) -> Dict[str, Any]:
        """Genera il cutout circolare da applicare al pannello ospite."""
        return {
            "type": "circular",
            "diameter": self.diameter_emission,
            "center_local": [0.0, 0.0],
            "purpose": "driver_mount",
            "driver_model": self.driver.model,
            "driver_manufacturer": self.driver.manufacturer,
        }

    def validate(self) -> List[ValidationWarning]:
        warnings: List[ValidationWarning] = []
        if self.mounting_depth <= 0.0:
            warnings.append(ValidationWarning(
                Severity.INFO, "DRIVER_MOUNTING_DEPTH_ZERO",
                "mounting_depth=0: assumo flush mount (no rear protrusion).",
            ))
        if self.driver.xmax <= 0:
            warnings.append(ValidationWarning(
                Severity.WARNING, "DRIVER_XMAX_MISSING",
                "driver.xmax non specificato; alcuni check di non-linearità "
                "non saranno eseguiti.",
            ))
        return warnings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_type": self.block_type,
            "driver": {
                "manufacturer": self.driver.manufacturer,
                "model": self.driver.model,
                "sd": self.driver.sd,
            },
            "orientation": self.orientation,
            "mounting_depth": self.mounting_depth,
            "position": self.position.tolist(),
            "basket_volume": self.basket_volume,
        }
