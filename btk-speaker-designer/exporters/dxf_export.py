"""
Esportatore DXF per BTK Speaker Designer.
Genera file DXF per CNC/laser cutter con le dimensioni della cassa.

Richiede: ezdxf (pip install ezdxf)
"""

import sys
from pathlib import Path
from typing import Optional

try:
    import ezdxf
    from ezdxf import units
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False

from ..core.geometry import CabinetGeometry, Panel
from ..core.horn_calculator import HornGeometry


def export_cabinet_dxf(
    cabinet: CabinetGeometry,
    output_path: str,
    scale_mm: bool = True
) -> bool:
    """
    Esporta la geometria del cabinet in formato DXF per CNC.

    Genera un disegno 2D con tutti i pannelli disposti in layout per taglio.

    Args:
        cabinet: Geometria del cabinet da esportare
        output_path: Percorso del file DXF di output
        scale_mm: True = unità millimetri, False = unità centimetri

    Returns:
        True se l'export ha avuto successo

    Raises:
        ImportError: se ezdxf non è installato
    """
    if not EZDXF_AVAILABLE:
        raise ImportError(
            "Il pacchetto 'ezdxf' non è installato.\n"
            "Installa con: pip install ezdxf"
        )

    doc = ezdxf.new(dxfversion="R2010")
    doc.units = units.MM if scale_mm else units.CM
    msp = doc.modelspace()

    # Layer per i pannelli
    doc.layers.add("PANNELLI", color=7)          # bianco
    doc.layers.add("DIMENSIONI", color=1)        # rosso
    doc.layers.add("TESTO", color=2)             # giallo
    doc.layers.add("ASSI", color=5)              # blu

    # Posizionamento automatico dei pannelli in griglia
    x_offset = 0.0
    y_offset = 0.0
    row_height = 0.0
    max_row_width = 2000.0  # mm - larghezza massima foglio
    padding = 20.0  # mm tra i pannelli

    scale = 1.0 if scale_mm else 0.1  # converti mm in cm se necessario

    for panel in cabinet.panels:
        w = panel.width_mm * scale
        h = panel.height_mm * scale

        # Vai a riga successiva se non c'è spazio
        if x_offset + w > max_row_width and x_offset > 0:
            y_offset -= row_height + padding
            x_offset = 0.0
            row_height = 0.0

        # Disegna rettangolo pannello
        pts = [
            (x_offset, y_offset),
            (x_offset + w, y_offset),
            (x_offset + w, y_offset - h),
            (x_offset, y_offset - h),
            (x_offset, y_offset),
        ]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "PANNELLI"})

        # Etichetta pannello
        center_x = x_offset + w / 2
        center_y = y_offset - h / 2
        msp.add_text(
            f"{panel.name}\n{panel.width_mm:.0f}x{panel.height_mm:.0f}mm (x{panel.quantity})",
            dxfattribs={
                "layer": "TESTO",
                "height": min(w, h) * 0.08,
                "insert": (center_x, center_y),
                "align_point": (center_x, center_y),
                "halign": 4,  # center
                "valign": 0,  # baseline
            }
        )

        # Aggiorna offsets
        x_offset += w + padding
        row_height = max(row_height, h)

    # Salva il file
    doc.saveas(output_path)
    return True


def export_horn_profile_dxf(
    horn_geometry: HornGeometry,
    output_path: str,
    include_centerline: bool = True
) -> bool:
    """
    Esporta il profilo 2D della tromba in DXF.

    Args:
        horn_geometry: Geometria della tromba calcolata
        output_path: Percorso del file DXF di output
        include_centerline: Se aggiungere la linea centrale

    Returns:
        True se l'export ha avuto successo
    """
    if not EZDXF_AVAILABLE:
        raise ImportError("Il pacchetto 'ezdxf' non è installato.")

    import numpy as np
    from ..core.horn_calculator import area_at_position

    doc = ezdxf.new(dxfversion="R2010")
    doc.units = units.MM
    msp = doc.modelspace()

    doc.layers.add("PROFILO", color=7)
    doc.layers.add("ASSI", color=5)

    # Genera punti profilo (in mm)
    n_points = 200
    x_vals = np.linspace(0, horn_geometry.horn_length_m, n_points)
    r_vals = np.array([
        np.sqrt(area_at_position(x, horn_geometry.throat_area_m2,
                                 horn_geometry.flare_rate_m, horn_geometry.expansion_type) / np.pi)
        for x in x_vals
    ]) * 1000  # converti in mm
    x_vals_mm = x_vals * 1000

    # Profilo superiore
    upper = list(zip(x_vals_mm, r_vals))
    msp.add_lwpolyline(upper, dxfattribs={"layer": "PROFILO"})

    # Profilo inferiore (simmetrico)
    lower = list(zip(x_vals_mm, -r_vals))
    msp.add_lwpolyline(lower, dxfattribs={"layer": "PROFILO"})

    # Chiusura gola e bocca
    msp.add_line((0, r_vals[0]), (0, -r_vals[0]), dxfattribs={"layer": "PROFILO"})
    msp.add_line(
        (x_vals_mm[-1], r_vals[-1]),
        (x_vals_mm[-1], -r_vals[-1]),
        dxfattribs={"layer": "PROFILO"}
    )

    # Linea centrale
    if include_centerline:
        msp.add_line((-20, 0), (x_vals_mm[-1] + 20, 0),
                     dxfattribs={"layer": "ASSI", "linetype": "CENTER"})

    doc.saveas(output_path)
    return True
