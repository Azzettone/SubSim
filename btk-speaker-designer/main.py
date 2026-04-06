"""
BTK Speaker Designer - Entry point principale dell'applicazione.

Avvio dell'interfaccia grafica o esecuzione in modalità CLI.
"""

import sys
import os
from pathlib import Path

# Aggiunge la directory parent al path Python
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_gui():
    """Avvia l'interfaccia grafica dell'applicazione."""
    try:
        from gui.main_window import create_app
        app, window = create_app()
        window.show()
        return app.exec_()
    except ImportError as e:
        print(f"Impossibile avviare la GUI: {e}")
        print("Assicurati di avere PyQt5 o PySide6 installato:")
        print("  pip install PyQt5")
        print("  oppure: pip install PySide6")
        return 1


def run_demo():
    """
    Esegue una demo delle funzionalità core senza GUI.
    Utile per testing e debug.
    """
    print("=" * 60)
    print("  BTK Speaker Designer - Demo Core")
    print("=" * 60)

    # 1. Calcolo tromba di riferimento
    print("\n1. Calcolo tromba esponenziale (valori di riferimento):")
    from core.horn_calculator import design_horn
    from core.constants import EXPANSION_EXPONENTIAL

    geom = design_horn(
        cutoff_freq_hz=70.0,
        driver_sd_m2=0.091,        # ~18" woofer
        smouth_sthroat_ratio=2.0,
        expansion_type=EXPANSION_EXPONENTIAL,
        c=342.016                   # a 16.8°C come nel foglio Excel
    )
    print(f"   Frequenza di taglio: {geom.cutoff_frequency_hz} Hz")
    print(f"   Flare rate (m):      {geom.flare_rate_m:.4f} m⁻¹")
    print(f"   Area gola:           {geom.throat_area_m2:.4f} m² ({geom.throat_area_m2*10000:.2f} cm²)")
    print(f"   Area bocca:          {geom.mouth_area_m2:.4f} m²")
    print(f"   Lunghezza tromba:    {geom.horn_length_m:.4f} m ({geom.horn_length_m*100:.2f} cm)")
    print(f"   Impedenza gola:      {geom.throat_impedance:.2f} Pa·s/m³")
    print(f"   Volume accopp.:      {geom.coupling_volume_m3:.4f} m³ ({geom.coupling_volume_m3*1000:.3f} L)")

    print("\n   Sezioni tromba:")
    for s in geom.sections:
        print(f"   x={s.x_m*100:6.2f}cm  "
              f"A={s.area_m2*10000:8.2f}cm²  "
              f"r={s.radius_m*100:5.2f}cm  "
              f"Ø={s.radius_m*200:5.2f}cm")

    # 2. Geometria cabinet
    print("\n2. Calcolo geometria cabinet (Straight):")
    from core.geometry import design_straight_horn
    cabinet = design_straight_horn(geom)
    print(f"   Dimensioni: {cabinet.total_width_mm:.0f} × "
          f"{cabinet.total_height_mm:.0f} × "
          f"{cabinet.total_depth_mm:.0f} mm")
    print(f"   Volume: {cabinet.volume_m3*1000:.1f} L")
    print(f"   Pannelli da tagliare: {len(cabinet.panels)}")
    print(f"   Costo materiali (MDF 30€/m²): {cabinet.total_cost():.2f} €")

    # 3. Somma fronte/retro
    print("\n3. Calcolo somma fronte/retro:")
    import numpy as np
    from core.phase_summing import calculate_combined_response, find_interference_frequencies

    path_diff = 0.30  # 30 cm differenza di cammino
    interf = find_interference_frequencies(path_diff, c=342.016, f_min=50, f_max=2000)
    print(f"   Differenza di cammino: {path_diff*100:.0f} cm")
    print(f"   Frequenza fondamentale: {interf['fundamental_hz']:.1f} Hz")
    print(f"   Freq. costruttive: {interf['constructive_hz']}")
    print(f"   Freq. distruttive: {interf['destructive_hz']}")

    # 4. Database driver
    print("\n4. Driver nel database:")
    from database.db_manager import initialize_database, get_drivers_by_type, get_manufacturers

    # Usa il database nella directory corrente dello script
    db_dir = Path(__file__).parent / "database"
    os.makedirs(db_dir, exist_ok=True)
    initialize_database()

    manufacturers = get_manufacturers()
    print(f"   Produttori trovati: {manufacturers}")

    subwoofers = get_drivers_by_type("subwoofer")
    print(f"   Subwoofer nel database: {len(subwoofers)}")
    for d in subwoofers[:3]:
        print(f"   - {d}")

    cds = get_drivers_by_type("compression_driver")
    print(f"   Compression driver nel database: {len(cds)}")

    print("\n" + "=" * 60)
    print("  Demo completata con successo!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="BTK Speaker Designer - Software per il design di altoparlanti professionali"
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Esegui la demo CLI senza interfaccia grafica"
    )
    parser.add_argument(
        "--gui", action="store_true", default=True,
        help="Avvia l'interfaccia grafica (default)"
    )

    args = parser.parse_args()

    if args.demo:
        sys.exit(run_demo())
    else:
        sys.exit(run_gui())
