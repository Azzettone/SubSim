"""
Calcolo delle geometrie per trombe acustiche.
Supporta configurazioni Straight, Folded e 2-Folded.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from .constants import (
    GEOMETRY_STRAIGHT, GEOMETRY_FOLDED, GEOMETRY_2FOLDED,
    DEFAULT_WOOD_PRICE_PER_M2
)
from .horn_calculator import HornGeometry, HornSection


@dataclass
class FoldPoint:
    """Rappresenta un punto di piega nella tromba."""
    x_m: float              # posizione lungo l'asse in m
    direction: str          # 'up', 'down', 'left', 'right'
    width_m: float          # larghezza della sezione alla piega
    height_m: float         # altezza della sezione alla piega


@dataclass
class Panel:
    """Pannello costruttivo della cassa."""
    name: str               # es. 'base', 'laterale sinistro', etc.
    width_m: float          # larghezza in m
    height_m: float         # altezza/profondità in m
    thickness_m: float      # spessore in m
    quantity: int = 1
    material: str = "mdf_18mm"
    notes: str = ""

    @property
    def area_m2(self) -> float:
        return self.width_m * self.height_m

    @property
    def width_mm(self) -> float:
        return self.width_m * 1000

    @property
    def height_mm(self) -> float:
        return self.height_m * 1000

    @property
    def thickness_mm(self) -> float:
        return self.thickness_m * 1000

    def cost(self, price_per_m2: float = DEFAULT_WOOD_PRICE_PER_M2) -> float:
        return self.area_m2 * self.quantity * price_per_m2


@dataclass
class CabinetGeometry:
    """
    Geometria completa del cabinet con la tromba.
    Include dimensioni esterne, pannelli e configurazione dei fold.
    """
    geometry_type: str          # GEOMETRY_STRAIGHT, GEOMETRY_FOLDED, GEOMETRY_2FOLDED
    horn_geometry: HornGeometry

    # Dimensioni esterne totali del cabinet
    total_width_m: float = 0.0
    total_height_m: float = 0.0
    total_depth_m: float = 0.0

    # Punti di piega (se folded)
    fold_points: List[FoldPoint] = field(default_factory=list)

    # Pannelli costruttivi
    panels: List[Panel] = field(default_factory=list)

    # Spessore pannelli (default 18mm MDF)
    panel_thickness_m: float = 0.018

    @property
    def total_width_mm(self) -> float:
        return self.total_width_m * 1000

    @property
    def total_height_mm(self) -> float:
        return self.total_height_m * 1000

    @property
    def total_depth_mm(self) -> float:
        return self.total_depth_m * 1000

    @property
    def volume_m3(self) -> float:
        return self.total_width_m * self.total_height_m * self.total_depth_m

    def total_panel_area_m2(self) -> float:
        return sum(p.area_m2 * p.quantity for p in self.panels)

    def total_cost(self, price_per_m2: float = DEFAULT_WOOD_PRICE_PER_M2) -> float:
        return sum(p.cost(price_per_m2) for p in self.panels)

    def get_panel_cutlist(self) -> List[dict]:
        """Restituisce la lista di taglio dei pannelli."""
        return [
            {
                "nome": p.name,
                "larghezza_mm": round(p.width_mm, 1),
                "altezza_mm": round(p.height_mm, 1),
                "spessore_mm": round(p.thickness_mm, 1),
                "quantità": p.quantity,
                "materiale": p.material,
                "area_m2": round(p.area_m2, 4),
                "note": p.notes,
            }
            for p in self.panels
        ]


def design_straight_horn(
    horn_geometry: HornGeometry,
    panel_thickness_m: float = 0.018,
    aspect_ratio: float = 1.0,
    wood_price: float = DEFAULT_WOOD_PRICE_PER_M2
) -> CabinetGeometry:
    """
    Progetta la geometria per una tromba dritta (straight).

    La tromba si espande direttamente lungo l'asse, senza pieghe.
    Sezione trasversale rettangolare con aspect ratio configurabile.

    Args:
        horn_geometry: Parametri della tromba calcolati
        panel_thickness_m: Spessore pannelli in m
        aspect_ratio: Rapporto larghezza/altezza (1.0 = quadrato)
        wood_price: Prezzo del legno in €/m²

    Returns:
        CabinetGeometry con tutti i pannelli calcolati
    """
    t = panel_thickness_m
    horn_length = horn_geometry.horn_length_m
    mouth_area = horn_geometry.mouth_area_m2

    # Calcola dimensioni bocca rettangolare
    mouth_height = np.sqrt(mouth_area / aspect_ratio)
    mouth_width = mouth_area / mouth_height

    # Dimensioni gola rettangolare
    throat_area = horn_geometry.throat_area_m2
    throat_height = np.sqrt(throat_area / aspect_ratio)
    throat_width = throat_area / throat_height

    # Dimensioni esterne del cabinet
    total_width = mouth_width + 2 * t
    total_height = mouth_height + 2 * t
    total_depth = horn_length + 2 * t  # lunghezza tromba + pannelli

    # Calcolo pannelli
    panels = [
        Panel("Base superiore",    total_width, total_depth, t, 1, notes="Pannello copertura superiore"),
        Panel("Base inferiore",    total_width, total_depth, t, 1, notes="Pannello base inferiore"),
        Panel("Laterale sinistro", total_height - 2*t, total_depth, t, 1),
        Panel("Laterale destro",   total_height - 2*t, total_depth, t, 1),
        Panel("Bocca tromba",      mouth_width, mouth_height, t, 1, notes="Pannello bocca/apertura"),
        Panel("Retro cabinet",     total_width - 2*t, total_height - 2*t, t, 1, notes="Pannello retro"),
    ]

    # Pannelli di espansione interni (sezioni progressive)
    for i, section in enumerate(horn_geometry.sections):
        if i > 0 and i < len(horn_geometry.sections) - 1:
            sec_height = np.sqrt(section.area_m2 / aspect_ratio)
            sec_width = section.area_m2 / sec_height
            panels.append(Panel(
                f"Sezione interna {i+1}",
                sec_width, sec_height, t * 0.5,  # pannelli interni più sottili
                1, notes=f"x={section.x_m*100:.1f}cm"
            ))

    cabinet = CabinetGeometry(
        geometry_type=GEOMETRY_STRAIGHT,
        horn_geometry=horn_geometry,
        total_width_m=total_width,
        total_height_m=total_height,
        total_depth_m=total_depth,
        panels=panels,
        panel_thickness_m=t,
    )
    return cabinet


def design_folded_horn(
    horn_geometry: HornGeometry,
    max_depth_m: float = None,
    panel_thickness_m: float = 0.018,
    aspect_ratio: float = 1.0,
    wood_price: float = DEFAULT_WOOD_PRICE_PER_M2
) -> CabinetGeometry:
    """
    Progetta la geometria per una tromba piegata 1 volta (folded).

    La tromba si piega a U per ridurre la profondità del cabinet.
    Usata quando la tromba dritta supera la profondità massima ammessa.

    Args:
        horn_geometry: Parametri della tromba calcolati
        max_depth_m: Profondità massima del cabinet in m
        panel_thickness_m: Spessore pannelli in m
        aspect_ratio: Rapporto larghezza/altezza bocca
        wood_price: Prezzo del legno in €/m²

    Returns:
        CabinetGeometry con pannelli e punto di piega calcolati
    """
    t = panel_thickness_m
    if max_depth_m is None:
        max_depth_m = horn_geometry.horn_length_m / 2
    horn_length = horn_geometry.horn_length_m
    mouth_area = horn_geometry.mouth_area_m2
    throat_area = horn_geometry.throat_area_m2

    # Dimensioni bocca rettangolare
    mouth_height = np.sqrt(mouth_area / aspect_ratio)
    mouth_width = mouth_area / mouth_height

    # Dimensioni gola
    throat_height = np.sqrt(throat_area / aspect_ratio)
    throat_width = throat_area / throat_height

    # Posizione piega: metà della lunghezza tromba
    fold_position = horn_length / 2

    # Area alla piega
    from .horn_calculator import area_at_position
    area_at_fold = area_at_position(
        fold_position,
        throat_area,
        horn_geometry.flare_rate_m,
        horn_geometry.expansion_type
    )
    fold_height = np.sqrt(area_at_fold / aspect_ratio)
    fold_width = area_at_fold / fold_height

    # Dimensioni cabinet: profondità ridotta, altezza aumentata
    total_depth = max_depth_m + 2 * t
    total_width = max(mouth_width, fold_width) + 2 * t
    total_height = 2 * (horn_length / 2) + mouth_height + 4 * t

    # Punto di piega
    fold_pts = [FoldPoint(
        x_m=fold_position,
        direction="up",
        width_m=fold_width,
        height_m=fold_height
    )]

    # Pannelli
    panels = [
        Panel("Base",            total_width, total_depth, t, 1),
        Panel("Copertura",       total_width, total_depth, t, 1),
        Panel("Laterale",        total_height - 2*t, total_depth, t, 2),
        Panel("Retro",           total_width - 2*t, total_height - 2*t, t, 1),
        Panel("Pannello piega",  total_width - 2*t, fold_height + 2*t, t, 1,
              notes="Pannello di inversione del percorso"),
        Panel("Apertura bocca",  mouth_width, mouth_height, t, 1),
    ]

    cabinet = CabinetGeometry(
        geometry_type=GEOMETRY_FOLDED,
        horn_geometry=horn_geometry,
        total_width_m=total_width,
        total_height_m=total_height,
        total_depth_m=total_depth,
        fold_points=fold_pts,
        panels=panels,
        panel_thickness_m=t,
    )
    return cabinet


def design_2folded_horn(
    horn_geometry: HornGeometry,
    max_depth_m: float = None,
    max_height_m: float = None,
    panel_thickness_m: float = 0.018,
    aspect_ratio: float = 1.0,
    wood_price: float = DEFAULT_WOOD_PRICE_PER_M2
) -> CabinetGeometry:
    """
    Progetta la geometria per una tromba con 2 pieghe (2-folded).

    Configurazione compatta per massimizzare le performance in spazio ridotto.

    Args:
        horn_geometry: Parametri della tromba calcolati
        max_depth_m: Profondità massima del cabinet in m
        max_height_m: Altezza massima del cabinet in m
        panel_thickness_m: Spessore pannelli in m
        aspect_ratio: Rapporto larghezza/altezza bocca
        wood_price: Prezzo del legno in €/m²

    Returns:
        CabinetGeometry con pannelli e 2 punti di piega calcolati
    """
    t = panel_thickness_m
    if max_depth_m is None:
        max_depth_m = horn_geometry.horn_length_m / 3
    if max_height_m is None:
        max_height_m = horn_geometry.mouth_diameter_m * 3.5
    horn_length = horn_geometry.horn_length_m
    mouth_area = horn_geometry.mouth_area_m2
    throat_area = horn_geometry.throat_area_m2

    # Dimensioni bocca
    mouth_height = np.sqrt(mouth_area / aspect_ratio)
    mouth_width = mouth_area / mouth_height

    # Posizione delle 2 pieghe (divide la tromba in 3 sezioni uguali)
    fold1_position = horn_length / 3
    fold2_position = 2 * horn_length / 3

    from .horn_calculator import area_at_position

    area_fold1 = area_at_position(
        fold1_position, throat_area,
        horn_geometry.flare_rate_m, horn_geometry.expansion_type
    )
    area_fold2 = area_at_position(
        fold2_position, throat_area,
        horn_geometry.flare_rate_m, horn_geometry.expansion_type
    )

    fold1_h = np.sqrt(area_fold1 / aspect_ratio)
    fold1_w = area_fold1 / fold1_h
    fold2_h = np.sqrt(area_fold2 / aspect_ratio)
    fold2_w = area_fold2 / fold2_h

    # Dimensioni esterne ottimizzate per i vincoli
    segment_length = horn_length / 3
    total_depth = min(segment_length + 2 * t, max_depth_m)
    total_height = min(3 * segment_length + mouth_height + 6 * t, max_height_m)
    total_width = max(mouth_width, fold2_w) + 2 * t

    fold_pts = [
        FoldPoint(fold1_position, "down", fold1_w, fold1_h),
        FoldPoint(fold2_position, "up",   fold2_w, fold2_h),
    ]

    panels = [
        Panel("Base",             total_width, total_depth, t, 1),
        Panel("Copertura",        total_width, total_depth, t, 1),
        Panel("Laterale",         total_height - 2*t, total_depth, t, 2),
        Panel("Retro",            total_width - 2*t, total_height - 2*t, t, 1),
        Panel("Pannello piega 1", total_width - 2*t, fold1_h + 2*t, t, 1,
              notes="Prima inversione percorso"),
        Panel("Pannello piega 2", total_width - 2*t, fold2_h + 2*t, t, 1,
              notes="Seconda inversione percorso"),
        Panel("Apertura bocca",   mouth_width, mouth_height, t, 1),
    ]

    cabinet = CabinetGeometry(
        geometry_type=GEOMETRY_2FOLDED,
        horn_geometry=horn_geometry,
        total_width_m=total_width,
        total_height_m=total_height,
        total_depth_m=total_depth,
        fold_points=fold_pts,
        panels=panels,
        panel_thickness_m=t,
    )
    return cabinet


def auto_select_geometry(
    horn_geometry: HornGeometry,
    max_width_m: Optional[float] = None,
    max_height_m: Optional[float] = None,
    max_depth_m: Optional[float] = None,
    panel_thickness_m: float = 0.018
) -> CabinetGeometry:
    """
    Seleziona automaticamente la geometria ottimale in base ai vincoli.

    Args:
        horn_geometry: Parametri della tromba
        max_width_m: Larghezza massima in m (None = nessun limite)
        max_height_m: Altezza massima in m
        max_depth_m: Profondità massima in m
        panel_thickness_m: Spessore pannelli in m

    Returns:
        CabinetGeometry ottimale
    """
    horn_length = horn_geometry.horn_length_m
    t = panel_thickness_m

    # Stima profondità richiesta per tromba dritta
    straight_depth = horn_length + 2 * t

    if max_depth_m is None or straight_depth <= max_depth_m:
        # La tromba dritta entra nei vincoli
        return design_straight_horn(horn_geometry, t)

    elif straight_depth <= 2 * (max_depth_m or float('inf')):
        # Una piega è sufficiente
        depth = max_depth_m or horn_length / 2
        return design_folded_horn(horn_geometry, depth, t)

    else:
        # Servono 2 pieghe
        depth = max_depth_m or horn_length / 3
        height = max_height_m or horn_length + 0.5
        return design_2folded_horn(horn_geometry, depth, height, t)
