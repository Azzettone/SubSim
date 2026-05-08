"""
ChamberBlock — camera (volume) acustica rettangolare o trapezoidale.

Usato per:
- Camere reflex (volume Vb) in cabinet bass-reflex
- Camera posteriore di sub a tromba (back-loaded)
- Camera frontale di bandpass
- Camera generica per coupling acustico

Genera 6 pannelli (front/back/top/bottom/left/right) e 6 ConnectionPort
(uno per faccia) usabili come punti di connessione ad altri blocchi.

NOTA: per "trapezoidal" si intende cabinet con front e back paralleli ma
larghezze diverse (taper laterale). top/bottom restano paralleli.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .base_block import (
    Block, Panel, ConnectionPort, ValidationWarning, Severity,
    DEFAULT_PANEL_THICKNESS, DEFAULT_PANEL_MATERIAL,
)


# Facce della camera (sistema locale: front=+Z, back=-Z, up=+Y, ...)
FACE_NAMES = ("front", "back", "top", "bottom", "left", "right")


@dataclass
class ChamberBlock(Block):
    """
    Camera parallelepipeda o trapezoidale (taper laterale).

    Args:
        width: larghezza max (m) — per trapezoidal è la larghezza alla front
        height: altezza (m)
        depth: profondità (m, asse Z)
        rear_width: solo per trapezoidal, larghezza al back
        shape: "rectangular" (default) o "trapezoidal"
        origin: posizione angolo "back-bottom-left" nello spazio globale (3,)
        panel_thickness, panel_material: come Panel
    """
    width: float
    height: float
    depth: float
    rear_width: Optional[float] = None
    shape: str = "rectangular"
    origin: np.ndarray = None  # type: ignore[assignment]
    panel_thickness: float = DEFAULT_PANEL_THICKNESS
    panel_material: str = DEFAULT_PANEL_MATERIAL

    block_type = "chamber"

    def __post_init__(self) -> None:
        if self.shape not in ("rectangular", "trapezoidal"):
            raise ValueError(
                f"shape deve essere 'rectangular' o 'trapezoidal', "
                f"ricevuto: {self.shape!r}"
            )
        if any(v <= 0 for v in (self.width, self.height, self.depth)):
            raise ValueError("width, height, depth devono essere > 0")
        if self.shape == "rectangular":
            self.rear_width = self.width
        else:
            if self.rear_width is None or self.rear_width <= 0:
                raise ValueError(
                    "shape='trapezoidal' richiede rear_width > 0"
                )
        if self.origin is None:
            self.origin = np.zeros(3)
        self.origin = np.asarray(self.origin, dtype=float).reshape(3)

        self._panels = self._build_panels()
        self._ports = self._build_ports()

    # ── Costruttori alternativi ──────────────────────────────────────────────

    @classmethod
    def from_dimensions(
        cls, *,
        width: float, height: float, depth: float,
        rear_width: Optional[float] = None,
        shape: str = "rectangular",
        origin: Optional[np.ndarray] = None,
        panel_thickness: float = DEFAULT_PANEL_THICKNESS,
        panel_material: str = DEFAULT_PANEL_MATERIAL,
    ) -> "ChamberBlock":
        """Costruisce camera dalle dimensioni esterne."""
        return cls(
            width=width, height=height, depth=depth,
            rear_width=rear_width, shape=shape,
            origin=origin if origin is not None else np.zeros(3),
            panel_thickness=panel_thickness, panel_material=panel_material,
        )

    @classmethod
    def from_volume(
        cls, *,
        volume_m3: float,
        width: Optional[float] = None,
        height: Optional[float] = None,
        depth: Optional[float] = None,
        shape: str = "rectangular",
        origin: Optional[np.ndarray] = None,
        panel_thickness: float = DEFAULT_PANEL_THICKNESS,
        panel_material: str = DEFAULT_PANEL_MATERIAL,
    ) -> "ChamberBlock":
        """
        Costruisce camera dato il volume target + 2 delle 3 dimensioni.

        Solo "rectangular" supportato (per trapezoidal il volume target +
        forma sono ambigui: usa from_dimensions).
        """
        if shape != "rectangular":
            raise ValueError(
                "from_volume supporta solo shape='rectangular'. "
                "Per trapezoidal usa from_dimensions."
            )
        if volume_m3 <= 0:
            raise ValueError("volume_m3 deve essere > 0")
        given = sum(v is not None for v in (width, height, depth))
        if given < 2:
            raise ValueError(
                "from_volume richiede almeno 2 di (width, height, depth)."
            )
        if width is None:
            assert height is not None and depth is not None
            width = volume_m3 / (height * depth)
        elif height is None:
            assert width is not None and depth is not None
            height = volume_m3 / (width * depth)
        elif depth is None:
            assert width is not None and height is not None
            depth = volume_m3 / (width * height)
        return cls(
            width=width, height=height, depth=depth,
            shape="rectangular",
            origin=origin if origin is not None else np.zeros(3),
            panel_thickness=panel_thickness, panel_material=panel_material,
        )

    # ── Geometria ────────────────────────────────────────────────────────────

    def _corners(self) -> Dict[str, np.ndarray]:
        """
        Ritorna gli 8 vertici della camera nel sistema globale.

        Convenzione: origin = corner "back-bottom-left".
        Asse Z = profondità (back → front), Y = altezza, X = larghezza.

        Per trapezoidal: front_width = self.width, back_width = self.rear_width.
        Le pareti laterali divergono linearmente. La camera è centrata in X.
        """
        ox, oy, oz = self.origin
        H = self.height
        D = self.depth
        wf = self.width  # front
        wb = self.rear_width if self.rear_width is not None else self.width  # back

        # Centra in X
        # Back face: x ∈ [-wb/2, +wb/2] @ z = oz
        # Front face: x ∈ [-wf/2, +wf/2] @ z = oz + D
        cx = ox  # consideriamo origin.x come asse di simmetria della camera
        # Vertici: (b=back, f=front, l=left, r=right, b=bottom, t=top)
        return {
            "bbl": np.array([cx - wb/2, oy,     oz]),
            "bbr": np.array([cx + wb/2, oy,     oz]),
            "btr": np.array([cx + wb/2, oy + H, oz]),
            "btl": np.array([cx - wb/2, oy + H, oz]),
            "fbl": np.array([cx - wf/2, oy,     oz + D]),
            "fbr": np.array([cx + wf/2, oy,     oz + D]),
            "ftr": np.array([cx + wf/2, oy + H, oz + D]),
            "ftl": np.array([cx - wf/2, oy + H, oz + D]),
        }

    def _build_panels(self) -> List[Panel]:
        c = self._corners()
        # Convenzione vertici: ordine antiorario visto dall'esterno
        # → normale uscente dal cabinet.
        defs = {
            # name:        (v0,    v1,    v2,    v3)
            "front":  ("fbl", "fbr", "ftr", "ftl"),
            "back":   ("bbr", "bbl", "btl", "btr"),
            "top":    ("ftl", "ftr", "btr", "btl"),
            "bottom": ("bbl", "bbr", "fbr", "fbl"),
            "left":   ("bbl", "fbl", "ftl", "btl"),
            "right":  ("fbr", "bbr", "btr", "ftr"),
        }
        panels: List[Panel] = []
        for name, keys in defs.items():
            verts = np.array([c[k] for k in keys])
            panels.append(Panel(
                name=name,
                vertices=verts,
                thickness=self.panel_thickness,
                material=self.panel_material,
                is_internal=False,
            ))
        return panels

    def _build_ports(self) -> Dict[str, ConnectionPort]:
        c = self._corners()
        ports: Dict[str, ConnectionPort] = {}
        # Per ogni faccia: centro + normale + area + dim
        face_specs = {
            "front":  (("fbl", "fbr", "ftr", "ftl"),  np.array([0,0,1.])),
            "back":   (("bbr", "bbl", "btl", "btr"),  np.array([0,0,-1.])),
            "top":    (("ftl", "ftr", "btr", "btl"),  np.array([0,1.,0])),
            "bottom": (("bbl", "bbr", "fbr", "fbl"),  np.array([0,-1.,0])),
            "left":   (("bbl", "fbl", "ftl", "btl"),  np.array([-1.,0,0])),
            "right":  (("fbr", "bbr", "btr", "ftr"),  np.array([1.,0,0])),
        }
        for name, (keys, normal) in face_specs.items():
            verts = np.array([c[k] for k in keys])
            center = verts.mean(axis=0)
            # Calcolo area come quadrilatero
            a = np.linalg.norm(np.cross(verts[1]-verts[0], verts[2]-verts[0])) * 0.5
            b = np.linalg.norm(np.cross(verts[2]-verts[0], verts[3]-verts[0])) * 0.5
            area = float(a + b)
            # Dimensioni: max extent X e Y/Z per faccia
            ext = verts.max(axis=0) - verts.min(axis=0)
            if name in ("front", "back"):
                w, h = float(ext[0]), float(ext[1])
            elif name in ("top", "bottom"):
                w, h = float(ext[0]), float(ext[2])
            else:  # left, right
                w, h = float(ext[2]), float(ext[1])
            ports[name] = ConnectionPort(
                name=name, position=center, normal=normal,
                area=area, shape="rectangular", width=w, height=h,
            )
        return ports

    # ── Block API ────────────────────────────────────────────────────────────

    @property
    def panels(self) -> List[Panel]:
        return self._panels

    @property
    def connection_ports(self) -> Dict[str, ConnectionPort]:
        return self._ports

    @property
    def bounding_box(self) -> Tuple[float, float, float]:
        all_verts = np.concatenate([p.vertices for p in self._panels], axis=0)
        ext = all_verts.max(axis=0) - all_verts.min(axis=0)
        return (float(ext[0]), float(ext[1]), float(ext[2]))

    @property
    def internal_volume(self) -> float:
        """Volume aria interno (sottrae spessore pannelli? No: volume esterno
        in questo Layer; correzioni di volume utile vanno applicate
        dall'Assembly conoscendo le porte aperte e i blocchi connessi)."""
        # Volume del solido tra back-face e front-face
        # Tronco di prisma: V = h × (A_back + A_front) / 2  — geometria nota
        if self.shape == "rectangular":
            return float(self.width * self.height * self.depth)
        # trapezoidal: media delle larghezze × altezza × profondità
        avg_w = 0.5 * (self.width + (self.rear_width or self.width))
        return float(avg_w * self.height * self.depth)

    def validate(self) -> List[ValidationWarning]:
        warnings: List[ValidationWarning] = []
        if self.shape == "trapezoidal":
            assert self.rear_width is not None
            ratio = max(self.width, self.rear_width) / min(self.width, self.rear_width)
            if ratio > 3.0:
                warnings.append(ValidationWarning(
                    Severity.WARNING, "TRAPEZOID_RATIO_HIGH",
                    f"Rapporto larghezze {ratio:.2f} > 3 può creare modi "
                    "interni anomali e difficoltà costruttive.",
                ))
        # Aspect-ratio cubico → modi degenerati
        dims = sorted([self.width, self.height, self.depth])
        if dims[0] > 0 and abs(dims[0] - dims[2]) / dims[0] < 0.05:
            warnings.append(ValidationWarning(
                Severity.WARNING, "CUBIC_CHAMBER",
                "Camera quasi cubica: modi assiali degenerano alla stessa "
                "frequenza causando picchi netti. Varia almeno una dimensione.",
            ))
        return warnings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_type": self.block_type,
            "width": self.width,
            "height": self.height,
            "depth": self.depth,
            "rear_width": self.rear_width,
            "shape": self.shape,
            "origin": self.origin.tolist(),
            "panel_thickness": self.panel_thickness,
            "panel_material": self.panel_material,
            "internal_volume": self.internal_volume,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChamberBlock":
        return cls(
            width=data["width"], height=data["height"], depth=data["depth"],
            rear_width=data.get("rear_width"),
            shape=data.get("shape", "rectangular"),
            origin=np.asarray(data.get("origin", [0,0,0])),
            panel_thickness=data.get("panel_thickness", DEFAULT_PANEL_THICKNESS),
            panel_material=data.get("panel_material", DEFAULT_PANEL_MATERIAL),
        )
