"""
Tipi base condivisi tra tutti i blocchi del Block Assembler.

Definisce:
- Block: classe astratta base
- Panel: pannello costruttivo (quadrilatero planare nello spazio)
- ConnectionPort: punto di connessione tra blocchi
- ValidationWarning + Severity: avvisi di validazione fisica
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np


# ─── Costanti globali del sistema (modificabili a runtime) ───────────────────

DEFAULT_PANEL_THICKNESS = 0.018   # m (18 mm multistrato)
DEFAULT_PANEL_MATERIAL = "birch_plywood_18mm"


# ─── Severity ────────────────────────────────────────────────────────────────

class Severity(str, Enum):
    """Livelli di severità per avvisi di validazione."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# ─── Validation Warning ──────────────────────────────────────────────────────

@dataclass
class ValidationWarning:
    """
    Avviso di validazione fisica/geometrica emesso da un blocco.

    Attributi:
        severity: livello (info | warning | error)
        code: codice macchina-leggibile (es. "AREA_RATIO_TOO_HIGH")
        message: descrizione umana del problema
        location: identificativo della parte interessata (es. "section[12]")
    """
    severity: Severity
    code: str
    message: str
    location: Optional[str] = None

    def __str__(self) -> str:
        loc = f" @ {self.location}" if self.location else ""
        return f"[{self.severity.value.upper()}] {self.code}{loc}: {self.message}"


# ─── Panel ───────────────────────────────────────────────────────────────────

@dataclass
class Panel:
    """
    Pannello costruttivo del cabinet.

    Rappresentato come quadrilatero planare (4 vertici 3D) nel sistema di
    riferimento globale dell'assembly. Per profili curvi, le pareti vengono
    discretizzate in N pannelli adiacenti (ogni segmento = trapezio piatto
    tra due sezioni consecutive del profilo della tromba).

    Attributi:
        name: identificativo logico (es. "side_L", "top", "throat_baffle")
        vertices: array (4, 3) in ordine antiorario visto dal fronte
        thickness: spessore pannello in metri
        material: stringa identificativa materiale (lookup in DB materiali)
        is_internal: True se è una paratia interna (es. setto di piegatura)
        cutouts: lista opzionale di fori (es. driver mount, port slot)
    """
    name: str
    vertices: np.ndarray  # shape (4, 3)
    thickness: float = DEFAULT_PANEL_THICKNESS
    material: str = DEFAULT_PANEL_MATERIAL
    is_internal: bool = False
    cutouts: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        v = np.asarray(self.vertices, dtype=float)
        if v.shape != (4, 3):
            raise ValueError(
                f"Panel '{self.name}': vertices deve avere shape (4, 3), "
                f"ricevuto {v.shape}"
            )
        self.vertices = v

    @property
    def area_m2(self) -> float:
        """Area del quadrilatero (somma dei due triangoli)."""
        v = self.vertices
        a = np.linalg.norm(np.cross(v[1] - v[0], v[2] - v[0])) * 0.5
        b = np.linalg.norm(np.cross(v[2] - v[0], v[3] - v[0])) * 0.5
        return float(a + b)

    @property
    def normal(self) -> np.ndarray:
        """Versore normale al pannello (da v0,v1,v2)."""
        v = self.vertices
        n = np.cross(v[1] - v[0], v[2] - v[0])
        norm = np.linalg.norm(n)
        if norm < 1e-12:
            return np.array([0.0, 0.0, 1.0])
        return n / norm

    @property
    def centroid(self) -> np.ndarray:
        """Centroide geometrico del quadrilatero."""
        return self.vertices.mean(axis=0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "vertices": self.vertices.tolist(),
            "thickness": self.thickness,
            "material": self.material,
            "is_internal": self.is_internal,
            "cutouts": self.cutouts,
            "area_m2": self.area_m2,
        }


# ─── ConnectionPort ──────────────────────────────────────────────────────────

@dataclass
class ConnectionPort:
    """
    Punto di connessione tra due blocchi nell'Assembly.

    Esempi: l'output "mouth" di un HornBlock può connettersi all'input
    "front" di una ChamberBlock; "throat" del HornBlock connette al
    DriverBlock.

    Attributi:
        name: identificativo logico (es. "throat", "mouth")
        position: punto centrale (3,) nel sistema globale
        normal: versore normale uscente (3,)
        area: area del passaggio in m²
        shape: "rectangular" | "circular"
        width, height: dimensioni rettangolari (m); per circolari, width=height=2r
    """
    name: str
    position: np.ndarray
    normal: np.ndarray
    area: float
    shape: str = "rectangular"
    width: float = 0.0
    height: float = 0.0

    def __post_init__(self) -> None:
        self.position = np.asarray(self.position, dtype=float).reshape(3)
        n = np.asarray(self.normal, dtype=float).reshape(3)
        norm = np.linalg.norm(n)
        if norm < 1e-12:
            raise ValueError(f"ConnectionPort '{self.name}': normale nulla")
        self.normal = n / norm

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "position": self.position.tolist(),
            "normal": self.normal.tolist(),
            "area": self.area,
            "shape": self.shape,
            "width": self.width,
            "height": self.height,
        }


# ─── Block (classe astratta) ─────────────────────────────────────────────────

class Block(ABC):
    """
    Classe base astratta per ogni blocco del Block Assembler.

    Sottoclassi (HornBlock, ChamberBlock, PortBlock, DriverBlock) devono
    implementare:
      - panels: lista pannelli costruttivi
      - connection_ports: dict di porte di connessione
      - bounding_box: dimensioni esterne
      - internal_volume: volume aria interno
      - validate(): lista warning fisici/geometrici
      - to_dict() / from_dict(): serializzazione

    Le sottoclassi forniscono anche due costruttori a livello di classe:
      - from_acoustics(...): partendo da parametri acustici
      - from_constraints(...): partendo da vincoli dimensionali (ottimizza)
    """

    block_type: str = "abstract"

    @property
    @abstractmethod
    def panels(self) -> List[Panel]:
        """Lista pannelli costruttivi (uso: cutlist, mesh, viz)."""

    @property
    @abstractmethod
    def connection_ports(self) -> Dict[str, ConnectionPort]:
        """Mappa nome → ConnectionPort."""

    @property
    @abstractmethod
    def bounding_box(self) -> tuple[float, float, float]:
        """(width, height, depth) in metri."""

    @property
    @abstractmethod
    def internal_volume(self) -> float:
        """Volume aria interno in m³."""

    @abstractmethod
    def validate(self) -> List[ValidationWarning]:
        """Esegue verifiche fisiche/geometriche."""

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serializzazione JSON-compatibile."""

    # Helpers di severità
    @staticmethod
    def has_errors(warnings: List[ValidationWarning]) -> bool:
        return any(w.severity == Severity.ERROR for w in warnings)
