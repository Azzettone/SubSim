"""
PortBlock — porta di accordo reflex (tubo o slot).

Calcola dimensioni di un port Helmholtz dato l'accordo Fb desiderato e
il volume della camera, oppure direttamente dato area + lunghezza.

Formula Helmholtz (con correzione end):
    Fb = (c / 2π) · sqrt(A_p / (V · L_eff))
    L_eff = L_geom + correction
    correction = k · sqrt(A_p / π)         (k≈1.46 per flangia su un lato,
                                             ≈0.85 senza flangia, default 1.46)

Rif: Beranek (1954), Small (1973), Thiele (1971)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..core.constants import SPEED_OF_SOUND
from .base_block import (
    Block, Panel, ConnectionPort, ValidationWarning, Severity,
    DEFAULT_PANEL_THICKNESS, DEFAULT_PANEL_MATERIAL,
)


# Coefficienti correzione di estremità (end correction)
# k tale che L_eff = L_geom + k·r dove r=sqrt(A/π).
# Ports su una flangia (cabinet wall) su entrambi i lati → ~1.7 r totale.
# Tipicamente 0.85·r per ogni lato flangiato; 0.61·r per lato libero.
END_CORRECTION_FLANGED_BOTH = 1.70  # entrambi i lati su flangia (interno + esterno)
END_CORRECTION_FLANGED_ONE = 1.46   # un lato flangiato + uno libero
END_CORRECTION_FREE_BOTH = 1.22     # nessuna flangia (raro)


@dataclass
class PortBlock(Block):
    """
    Porta reflex (tubo circolare o slot rettangolare).

    Args:
        area: area sezione (m²)
        length: lunghezza geometrica (m) — quella fisica del condotto
        shape: "circular" o "rectangular"
        width, height: dimensioni esterne (per shape="rectangular");
                       per "circular" entrambi = diametro
        end_correction_factor: k della formula L_eff = L + k·sqrt(A/π)
        position: punto centrale ingresso porta nello spazio globale
        normal: versore direzione asse porta (uscita verso esterno)
        c: velocità del suono (m/s)
    """
    area: float
    length: float
    shape: str = "circular"
    width: float = 0.0
    height: float = 0.0
    end_correction_factor: float = END_CORRECTION_FLANGED_ONE
    position: np.ndarray = None  # type: ignore[assignment]
    normal: np.ndarray = None    # type: ignore[assignment]
    panel_thickness: float = DEFAULT_PANEL_THICKNESS
    panel_material: str = DEFAULT_PANEL_MATERIAL
    c: float = SPEED_OF_SOUND

    block_type = "port"

    def __post_init__(self) -> None:
        if self.shape not in ("circular", "rectangular"):
            raise ValueError(
                f"shape deve essere 'circular' o 'rectangular', "
                f"ricevuto: {self.shape!r}"
            )
        if self.area <= 0 or self.length <= 0:
            raise ValueError("area e length devono essere > 0")
        # Dimensioni coerenti con area
        if self.shape == "circular":
            d = 2.0 * float(np.sqrt(self.area / np.pi))
            self.width = d
            self.height = d
        else:
            if self.width <= 0 and self.height <= 0:
                # Default: slot 4:1
                self.height = float(np.sqrt(self.area / 4.0))
                self.width = 4.0 * self.height
            elif self.width <= 0:
                self.width = self.area / self.height
            elif self.height <= 0:
                self.height = self.area / self.width
            else:
                # Verifica coerenza
                expected = self.width * self.height
                if abs(expected - self.area) / self.area > 0.01:
                    self.area = expected  # adegua area
        if self.position is None:
            self.position = np.zeros(3)
        self.position = np.asarray(self.position, dtype=float).reshape(3)
        if self.normal is None:
            self.normal = np.array([0.0, 0.0, 1.0])
        n = np.asarray(self.normal, dtype=float).reshape(3)
        nn = np.linalg.norm(n)
        if nn < 1e-12:
            raise ValueError("PortBlock: normal non può essere nullo")
        self.normal = n / nn

    # ── Costruttori alternativi ──────────────────────────────────────────────

    @classmethod
    def from_dimensions(
        cls, *,
        area: Optional[float] = None,
        length: float,
        shape: str = "circular",
        width: float = 0.0,
        height: float = 0.0,
        diameter: Optional[float] = None,
        position: Optional[np.ndarray] = None,
        normal: Optional[np.ndarray] = None,
        end_correction_factor: float = END_CORRECTION_FLANGED_ONE,
        c: float = SPEED_OF_SOUND,
    ) -> "PortBlock":
        """Costruisce porta da dimensioni dirette."""
        if diameter is not None:
            shape = "circular"
            area = float(np.pi * (diameter / 2.0) ** 2)
        if area is None:
            if width > 0 and height > 0:
                area = width * height
            else:
                raise ValueError(
                    "Specifica area, oppure diameter, oppure width+height"
                )
        return cls(
            area=area, length=length, shape=shape,
            width=width, height=height,
            end_correction_factor=end_correction_factor,
            position=position if position is not None else np.zeros(3),
            normal=normal if normal is not None else np.array([0,0,1.0]),
            c=c,
        )

    @classmethod
    def from_tuning(
        cls, *,
        Fb: float,
        chamber_volume: float,
        shape: str = "circular",
        diameter: Optional[float] = None,
        width: Optional[float] = None,
        height: Optional[float] = None,
        area: Optional[float] = None,
        end_correction_factor: float = END_CORRECTION_FLANGED_ONE,
        position: Optional[np.ndarray] = None,
        normal: Optional[np.ndarray] = None,
        c: float = SPEED_OF_SOUND,
    ) -> "PortBlock":
        """
        Calcola lunghezza porta richiesta per accordare Helmholtz a Fb.

        Necessita area (o diameter o width+height) + chamber_volume.
        Formula con correzione end:
            L_eff = (c² · A) / ((2π·Fb)² · V)
            L_geom = L_eff - k · sqrt(A/π)

        Se L_geom risulta negativo → porta troppo grande per quella Fb;
        rilancia ValueError suggerendo riduzione area.
        """
        if Fb <= 0 or chamber_volume <= 0:
            raise ValueError("Fb e chamber_volume devono essere > 0")
        # Calcola area
        if diameter is not None:
            shape = "circular"
            area_eff = float(np.pi * (diameter / 2.0) ** 2)
        elif area is not None:
            area_eff = area
        elif width and height:
            area_eff = width * height
        else:
            raise ValueError(
                "Specifica area, diameter, oppure width+height"
            )

        omega_b = 2.0 * np.pi * Fb
        L_eff = (c ** 2 * area_eff) / (omega_b ** 2 * chamber_volume)
        end_corr = end_correction_factor * float(np.sqrt(area_eff / np.pi))
        L_geom = L_eff - end_corr
        if L_geom <= 0:
            min_L_eff = end_corr * 1.001
            max_area = (omega_b ** 2 * chamber_volume * min_L_eff) / c ** 2
            raise ValueError(
                f"Porta troppo grande: area {area_eff*1e4:.1f} cm² richiede "
                f"lunghezza geometrica negativa per Fb={Fb} Hz, V={chamber_volume*1000:.1f} L. "
                f"Riduci area a max {max_area*1e4:.1f} cm² o aumenta Fb/Volume."
            )
        return cls.from_dimensions(
            area=area_eff, length=L_geom, shape=shape,
            width=width or 0.0, height=height or 0.0, diameter=diameter,
            position=position, normal=normal,
            end_correction_factor=end_correction_factor, c=c,
        )

    # ── Calcoli acustici ─────────────────────────────────────────────────────

    def effective_length(self) -> float:
        """Lunghezza effettiva (geometrica + correzione end)."""
        return self.length + self.end_correction_factor * float(
            np.sqrt(self.area / np.pi)
        )

    def helmholtz_frequency(self, chamber_volume: float) -> float:
        """Calcola Fb dato il volume di camera connesso."""
        if chamber_volume <= 0:
            raise ValueError("chamber_volume deve essere > 0")
        L_eff = self.effective_length()
        return float(
            (self.c / (2.0 * np.pi))
            * np.sqrt(self.area / (chamber_volume * L_eff))
        )

    def air_velocity(self, spl_db: float, chamber_volume: float) -> float:
        """
        Velocità aria di picco nella porta a Fb (per check turbolenza).

        Approssimazione: v_p ≈ (V/A) · ω · x_eq dove x_eq è l'escursione
        equivalente del volume d'aria mobile nella porta. Per scopi di
        warning (non simulazione) usiamo: v_p ≈ p / (ρc) · (Sd/A) — ma
        semplifichiamo a v_p ≈ p_peak / (ρ·c) come stima conservativa.
        """
        rho = 1.225
        p_ref = 20e-6
        p_peak = p_ref * 10 ** (spl_db / 20.0)
        # stima velocità aria nella porta — usata solo come segnale qualitativo
        return float(p_peak / (rho * self.c))

    # ── Geometria pannelli (slot rectangolare) ───────────────────────────────

    def _build_panels(self) -> List[Panel]:
        """
        Per slot rettangolari: 4 pannelli (top/bottom/left/right del condotto).
        Per circolari: nessun pannello piano (tubo cilindrico — è un solido a
        sé, generato dal panel_generator nel Layer 3 successivo).
        """
        if self.shape == "circular":
            return []
        # Slot rettangolare allineato lungo `normal`
        # Costruiamo 4 pareti del condotto
        n = self.normal
        # Basi ortonormali
        if abs(n[1]) < 0.9:
            ref = np.array([0.0, 1.0, 0.0])
        else:
            ref = np.array([1.0, 0.0, 0.0])
        x_loc = np.cross(ref, n); x_loc /= np.linalg.norm(x_loc)
        y_loc = np.cross(n, x_loc); y_loc /= np.linalg.norm(y_loc)
        hw, hh = self.width / 2.0, self.height / 2.0
        L = self.length
        # Quattro angoli ingresso (z=0, dietro la porta)
        p_in = self.position
        p_out = self.position + n * L
        # Pannello bottom: da z=0 a z=L, y=-hh, x ∈ [-hw, +hw]
        def quad(p1, p2, p3, p4):
            return Panel(
                name="port_wall",
                vertices=np.array([p1, p2, p3, p4]),
                thickness=self.panel_thickness,
                material=self.panel_material,
                is_internal=True,
            )
        bottom_in_l  = p_in  - hw * x_loc - hh * y_loc
        bottom_in_r  = p_in  + hw * x_loc - hh * y_loc
        bottom_out_r = p_out + hw * x_loc - hh * y_loc
        bottom_out_l = p_out - hw * x_loc - hh * y_loc
        top_in_l     = p_in  - hw * x_loc + hh * y_loc
        top_in_r     = p_in  + hw * x_loc + hh * y_loc
        top_out_r    = p_out + hw * x_loc + hh * y_loc
        top_out_l    = p_out - hw * x_loc + hh * y_loc
        panels = [
            Panel(name="port_bottom", vertices=np.array(
                [bottom_in_l, bottom_in_r, bottom_out_r, bottom_out_l]),
                thickness=self.panel_thickness, material=self.panel_material, is_internal=True),
            Panel(name="port_top", vertices=np.array(
                [top_out_l, top_out_r, top_in_r, top_in_l]),
                thickness=self.panel_thickness, material=self.panel_material, is_internal=True),
            Panel(name="port_left", vertices=np.array(
                [bottom_in_l, bottom_out_l, top_out_l, top_in_l]),
                thickness=self.panel_thickness, material=self.panel_material, is_internal=True),
            Panel(name="port_right", vertices=np.array(
                [bottom_in_r, top_in_r, top_out_r, bottom_out_r]),
                thickness=self.panel_thickness, material=self.panel_material, is_internal=True),
        ]
        return panels

    # ── Block API ────────────────────────────────────────────────────────────

    @property
    def panels(self) -> List[Panel]:
        return self._build_panels()

    @property
    def connection_ports(self) -> Dict[str, ConnectionPort]:
        return {
            "inner": ConnectionPort(
                name="inner",
                position=self.position.copy(),
                normal=-self.normal,           # uscente verso camera
                area=self.area,
                shape=self.shape,
                width=self.width, height=self.height,
            ),
            "outer": ConnectionPort(
                name="outer",
                position=self.position + self.normal * self.length,
                normal=self.normal,
                area=self.area,
                shape=self.shape,
                width=self.width, height=self.height,
            ),
        }

    @property
    def bounding_box(self) -> Tuple[float, float, float]:
        n = np.abs(self.normal)
        # length lungo n, width/height sugli altri assi
        ext = np.zeros(3)
        # Per circolare: extent uguale a diameter sugli assi non-n
        cross_dim = max(self.width, self.height)
        ext = cross_dim * (1.0 - n) + self.length * n
        return (float(ext[0]), float(ext[1]), float(ext[2]))

    @property
    def internal_volume(self) -> float:
        return float(self.area * self.length)

    def validate(self) -> List[ValidationWarning]:
        warnings: List[ValidationWarning] = []
        # Lunghezza > diametro → port "lungo" (più stabile)
        d_eq = 2.0 * float(np.sqrt(self.area / np.pi))
        if self.length < 0.5 * d_eq:
            warnings.append(ValidationWarning(
                Severity.WARNING, "PORT_TOO_SHORT",
                f"Lunghezza porta {self.length*1000:.0f} mm < "
                f"0.5×diametro_eq ({0.5*d_eq*1000:.0f} mm). End correction "
                f"dominante: tuning effettivo difficile da prevedere.",
            ))
        if self.length > 8.0 * d_eq:
            warnings.append(ValidationWarning(
                Severity.INFO, "PORT_VERY_LONG",
                f"Porta molto lunga ({self.length:.2f} m): considera slot "
                f"o multiple porte parallele per ridurre velocità aria.",
            ))
        # Slot estremo
        if self.shape == "rectangular":
            ar = max(self.width, self.height) / min(self.width, self.height)
            if ar > 20:
                warnings.append(ValidationWarning(
                    Severity.WARNING, "SLOT_ASPECT_EXTREME",
                    f"Aspect ratio slot {ar:.1f} eccessivo: perdite viscose "
                    f"importanti.",
                ))
        return warnings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_type": self.block_type,
            "area": self.area,
            "length": self.length,
            "shape": self.shape,
            "width": self.width,
            "height": self.height,
            "end_correction_factor": self.end_correction_factor,
            "position": self.position.tolist(),
            "normal": self.normal.tolist(),
            "panel_thickness": self.panel_thickness,
            "panel_material": self.panel_material,
            "c": self.c,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PortBlock":
        return cls(
            area=data["area"], length=data["length"],
            shape=data.get("shape", "circular"),
            width=data.get("width", 0.0), height=data.get("height", 0.0),
            end_correction_factor=data.get(
                "end_correction_factor", END_CORRECTION_FLANGED_ONE),
            position=np.asarray(data.get("position", [0,0,0])),
            normal=np.asarray(data.get("normal", [0,0,1.0])),
            panel_thickness=data.get("panel_thickness", DEFAULT_PANEL_THICKNESS),
            panel_material=data.get("panel_material", DEFAULT_PANEL_MATERIAL),
            c=data.get("c", SPEED_OF_SOUND),
        )
