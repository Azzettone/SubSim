"""
Generatore di report PDF per BTK Speaker Designer.
Produce report completi con parametri, grafici e lista taglio.

Richiede: reportlab (pip install reportlab)
"""

from typing import Optional
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor, black, white, grey
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from ..core.horn_calculator import HornGeometry
from ..core.geometry import CabinetGeometry
from ..core.constants import DEFAULT_WOOD_PRICE_PER_M2


def generate_pdf_report(
    project_data: dict,
    horn_geometry: HornGeometry,
    cabinet: CabinetGeometry,
    output_path: str,
    wood_price: float = DEFAULT_WOOD_PRICE_PER_M2,
    include_graphs: bool = False
) -> bool:
    """
    Genera un report PDF completo del progetto.

    Args:
        project_data: Dati del progetto
        horn_geometry: Geometria della tromba
        cabinet: Geometria del cabinet
        output_path: Percorso del file PDF di output
        wood_price: Prezzo del legno in €/m²
        include_graphs: Se includere i grafici (richiede matplotlib)

    Returns:
        True se la generazione è avvenuta con successo

    Raises:
        ImportError: se reportlab non è installato
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError(
            "Il pacchetto 'reportlab' non è installato.\n"
            "Installa con: pip install reportlab"
        )

    # Colori tema
    COLOR_PRIMARY = HexColor("#7C9EF0")
    COLOR_BG = HexColor("#1E1E2E")
    COLOR_ACCENT = HexColor("#F0A040")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=20*mm,
        bottomMargin=20*mm,
    )

    styles = getSampleStyleSheet()

    # Stili personalizzati
    title_style = ParagraphStyle(
        "BTKTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=HexColor("#7C9EF0"),
        spaceAfter=6*mm,
    )
    heading_style = ParagraphStyle(
        "BTKHeading",
        parent=styles["Heading1"],
        fontSize=14,
        textColor=HexColor("#7C9EF0"),
        spaceBefore=6*mm,
        spaceAfter=3*mm,
    )
    body_style = ParagraphStyle(
        "BTKBody",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=2*mm,
    )

    # Costruisce contenuto
    content = []

    # Intestazione
    content.append(Paragraph("BTK Speaker Designer", title_style))
    content.append(Paragraph("Report di Progetto", heading_style))

    project_name = project_data.get("name", "Progetto Senza Nome")
    speaker_type = project_data.get("speaker_type", "")
    geometry_type = project_data.get("geometry_type", "")

    content.append(Paragraph(f"<b>Progetto:</b> {project_name}", body_style))
    content.append(Paragraph(f"<b>Tipo:</b> {speaker_type}", body_style))
    content.append(Paragraph(f"<b>Geometria:</b> {geometry_type}", body_style))
    content.append(HRFlowable(width="100%", thickness=1, color=COLOR_PRIMARY))
    content.append(Spacer(1, 5*mm))

    # Parametri tromba
    content.append(Paragraph("Parametri della Tromba", heading_style))

    horn_data = [
        ["Parametro", "Valore"],
        ["Tipo espansione", horn_geometry.expansion_type],
        ["Frequenza di taglio", f"{horn_geometry.cutoff_frequency_hz:.1f} Hz"],
        ["Flare rate (m)", f"{horn_geometry.flare_rate_m:.4f} m⁻¹"],
        ["Area gola", f"{horn_geometry.throat_area_m2*10000:.2f} cm²"],
        ["Area bocca", f"{horn_geometry.mouth_area_m2*10000:.2f} cm²"],
        ["Rapporto espansione", f"{horn_geometry.expansion_ratio:.2f}"],
        ["Lunghezza tromba", f"{horn_geometry.horn_length_m*100:.2f} cm"],
        ["Impedenza gola", f"{horn_geometry.throat_impedance:.2f} Pa·s/m³"],
        ["Volume accoppiamento", f"{horn_geometry.coupling_volume_m3*1000:.3f} L"],
    ]

    table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#3A3A4E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#2A2A3E"), white]),
        ("GRID", (0, 0), (-1, -1), 0.5, grey),
        ("PADDING", (0, 0), (-1, -1), 4),
    ])

    horn_table = Table(horn_data, colWidths=[80*mm, 60*mm])
    horn_table.setStyle(table_style)
    content.append(horn_table)
    content.append(Spacer(1, 5*mm))

    # Dimensioni cabinet
    content.append(Paragraph("Dimensioni Cabinet", heading_style))

    cabinet_data = [
        ["Parametro", "Valore"],
        ["Tipo geometria", cabinet.geometry_type],
        ["Larghezza", f"{cabinet.total_width_mm:.1f} mm"],
        ["Altezza", f"{cabinet.total_height_mm:.1f} mm"],
        ["Profondità", f"{cabinet.total_depth_mm:.1f} mm"],
        ["Volume esterno", f"{cabinet.volume_m3*1000:.1f} L"],
    ]

    if cabinet.fold_points:
        for i, fold in enumerate(cabinet.fold_points, 1):
            cabinet_data.append([f"Piega {i}", f"x={fold.x_m*100:.1f}cm, dir={fold.direction}"])

    cab_table = Table(cabinet_data, colWidths=[80*mm, 60*mm])
    cab_table.setStyle(table_style)
    content.append(cab_table)
    content.append(Spacer(1, 5*mm))

    # Lista taglio pannelli
    content.append(Paragraph("Lista di Taglio Pannelli", heading_style))

    panels_data = [["Pannello", "Largh. (mm)", "Altez. (mm)", "Sp. (mm)", "Qtà", "Costo (€)"]]
    total_cost = 0.0

    for panel in cabinet.panels:
        cost = panel.cost(wood_price)
        total_cost += cost
        panels_data.append([
            panel.name,
            f"{panel.width_mm:.1f}",
            f"{panel.height_mm:.1f}",
            f"{panel.thickness_mm:.0f}",
            str(panel.quantity),
            f"{cost:.2f}",
        ])

    panels_data.append(["TOTALE", "", "", "", "", f"{total_cost:.2f}"])

    panels_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#3A3A4E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), HexColor("#3A3A4E")),
        ("TEXTCOLOR", (0, -1), (-1, -1), white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [HexColor("#2A2A3E"), white]),
        ("GRID", (0, 0), (-1, -1), 0.5, grey),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ])

    panels_table = Table(
        panels_data,
        colWidths=[55*mm, 25*mm, 25*mm, 20*mm, 15*mm, 25*mm]
    )
    panels_table.setStyle(panels_style)
    content.append(panels_table)

    # Footer
    content.append(Spacer(1, 10*mm))
    content.append(HRFlowable(width="100%", thickness=0.5, color=grey))
    content.append(Paragraph(
        "Generato con BTK Speaker Designer v1.0",
        ParagraphStyle("footer", parent=styles["Normal"],
                       fontSize=8, textColor=grey, alignment=TA_CENTER)
    ))

    # Genera PDF
    doc.build(content)
    return True
