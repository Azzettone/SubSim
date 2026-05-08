"""
Geometry layer — converte i blocchi acustici in solidi 3D B-rep.

Stack:
- build123d (>= 0.10) come kernel CAD parametrico (OCCT sotto).
- Output: Part / Compound (solidi) esportabili in STEP, STL, BREP.

Moduli:
- panel_generator: Block → solidi 3D (pannelli costruttivi + volumi cavità).
- viewport: visualizzazione pyvista standalone (Fase 2.2).
- mesh_generator: tetra/triangoli per FEM/BEM (Fase 4).

NOTE su unità:
build123d lavora in unità "raw" — usiamo coerentemente METRI in tutto
il progetto (come fanno i blocchi). Volume di una box 1×1×1m = 1.0.
Per export STEP a CAD esterni si scala a millimetri (vedi export_step).
"""

from .panel_generator import (
    panel_to_solid,
    chamber_shell,
    chamber_inner_volume,
    port_to_solid,
    driver_to_solid,
    horn_inner_volume,
    horn_wall_shell,
    export_step,
    export_stl,
    PanelGeometryError,
)
from .viewport import (
    show_solid,
    show_assembly,
    ViewportError,
)

__all__ = [
    "panel_to_solid",
    "chamber_shell",
    "chamber_inner_volume",
    "port_to_solid",
    "driver_to_solid",
    "horn_inner_volume",
    "horn_wall_shell",
    "export_step",
    "export_stl",
    "PanelGeometryError",
]
