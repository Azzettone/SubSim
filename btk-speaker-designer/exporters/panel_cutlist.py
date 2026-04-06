"""
Generatore della lista di taglio dei pannelli per BTK Speaker Designer.
Produce output testuale e CSV con tutte le dimensioni per la costruzione.
"""

import csv
import json
from typing import List, Optional
from pathlib import Path

from ..core.geometry import CabinetGeometry, Panel
from ..core.horn_calculator import HornGeometry
from ..core.constants import DEFAULT_WOOD_PRICE_PER_M2


def generate_cutlist_text(
    cabinet: CabinetGeometry,
    project_name: str = "Progetto BTK",
    wood_price: float = DEFAULT_WOOD_PRICE_PER_M2
) -> str:
    """
    Genera la lista di taglio in formato testo leggibile.

    Args:
        cabinet: Geometria del cabinet
        project_name: Nome del progetto
        wood_price: Prezzo del legno in €/m²

    Returns:
        Stringa con la lista di taglio formattata
    """
    lines = []
    lines.append("=" * 70)
    lines.append(f"  LISTA DI TAGLIO PANNELLI")
    lines.append(f"  Progetto: {project_name}")
    lines.append(f"  Geometria: {cabinet.geometry_type}")
    lines.append("=" * 70)
    lines.append("")

    # Intestazione tabella
    header = f"{'Pannello':<30} {'Largh.':>10} {'Altez.':>10} {'Sp.':>8} {'Qtà':>5} {'Costo':>10}"
    lines.append(header)
    lines.append("-" * 70)

    total_cost = 0.0
    total_area = 0.0

    for panel in cabinet.panels:
        cost = panel.cost(wood_price)
        area = panel.area_m2 * panel.quantity
        total_cost += cost
        total_area += area

        row = (
            f"{panel.name:<30}"
            f"{panel.width_mm:>9.1f}mm"
            f"{panel.height_mm:>9.1f}mm"
            f"{panel.thickness_mm:>7.0f}mm"
            f"{panel.quantity:>5}"
            f"{cost:>9.2f}€"
        )
        lines.append(row)
        if panel.notes:
            lines.append(f"  → {panel.notes}")

    lines.append("-" * 70)
    lines.append(f"{'TOTALE':<30} {'':>10} {'':>10} {'':>8} {'':>5} {total_cost:>9.2f}€")
    lines.append("")
    lines.append(f"Area totale pannelli: {total_area:.3f} m²")
    lines.append(f"Prezzo legno: {wood_price:.2f} €/m²")
    lines.append("")

    # Dimensioni esterne cabinet
    lines.append("─" * 70)
    lines.append("  DIMENSIONI ESTERNE CABINET")
    lines.append("─" * 70)
    lines.append(f"  Larghezza:  {cabinet.total_width_mm:.1f} mm")
    lines.append(f"  Altezza:    {cabinet.total_height_mm:.1f} mm")
    lines.append(f"  Profondità: {cabinet.total_depth_mm:.1f} mm")
    lines.append(f"  Volume:     {cabinet.volume_m3*1000:.1f} L")

    if cabinet.fold_points:
        lines.append("")
        lines.append("─" * 70)
        lines.append("  PUNTI DI PIEGA")
        lines.append("─" * 70)
        for i, fold in enumerate(cabinet.fold_points, 1):
            lines.append(
                f"  Piega {i}: x={fold.x_m*100:.1f}cm, "
                f"direzione={fold.direction}, "
                f"larghezza={fold.width_m*1000:.0f}mm"
            )

    lines.append("=" * 70)
    return "\n".join(lines)


def export_cutlist_csv(
    cabinet: CabinetGeometry,
    output_path: str,
    wood_price: float = DEFAULT_WOOD_PRICE_PER_M2
) -> bool:
    """
    Esporta la lista di taglio in formato CSV.

    Args:
        cabinet: Geometria del cabinet
        output_path: Percorso del file CSV di output
        wood_price: Prezzo del legno in €/m²

    Returns:
        True se l'export ha avuto successo
    """
    fieldnames = [
        "Nome", "Larghezza_mm", "Altezza_mm", "Spessore_mm",
        "Quantità", "Materiale", "Area_m2", "Costo_EUR", "Note"
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for panel in cabinet.panels:
            writer.writerow({
                "Nome": panel.name,
                "Larghezza_mm": round(panel.width_mm, 1),
                "Altezza_mm": round(panel.height_mm, 1),
                "Spessore_mm": round(panel.thickness_mm, 0),
                "Quantità": panel.quantity,
                "Materiale": panel.material,
                "Area_m2": round(panel.area_m2, 4),
                "Costo_EUR": round(panel.cost(wood_price), 2),
                "Note": panel.notes,
            })

    return True


def export_project_json(
    project_data: dict,
    cabinet: CabinetGeometry,
    horn_geometry: HornGeometry,
    output_path: str
) -> bool:
    """
    Esporta il progetto completo in formato JSON.

    Args:
        project_data: Dati del progetto (tipo, driver, parametri)
        cabinet: Geometria del cabinet
        horn_geometry: Geometria della tromba
        output_path: Percorso del file JSON di output

    Returns:
        True se l'export ha avuto successo
    """
    export_data = {
        "project": project_data,
        "horn": {
            "throat_area_m2": horn_geometry.throat_area_m2,
            "mouth_area_m2": horn_geometry.mouth_area_m2,
            "horn_length_m": horn_geometry.horn_length_m,
            "flare_rate_m": horn_geometry.flare_rate_m,
            "cutoff_frequency_hz": horn_geometry.cutoff_frequency_hz,
            "throat_impedance": horn_geometry.throat_impedance,
            "coupling_volume_m3": horn_geometry.coupling_volume_m3,
            "expansion_type": horn_geometry.expansion_type,
            "sections": [
                {
                    "x_m": s.x_m,
                    "area_m2": s.area_m2,
                    "radius_m": s.radius_m,
                }
                for s in horn_geometry.sections
            ]
        },
        "cabinet": {
            "geometry_type": cabinet.geometry_type,
            "total_width_mm": cabinet.total_width_mm,
            "total_height_mm": cabinet.total_height_mm,
            "total_depth_mm": cabinet.total_depth_mm,
            "volume_l": cabinet.volume_m3 * 1000,
            "panels": cabinet.get_panel_cutlist(),
            "fold_points": [
                {
                    "x_m": f.x_m,
                    "direction": f.direction,
                }
                for f in cabinet.fold_points
            ]
        }
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    return True
