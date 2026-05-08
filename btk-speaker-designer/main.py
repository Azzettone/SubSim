"""
BTK Speaker Designer - Entry point principale dell'applicazione.

Avvio dell'interfaccia grafica o esecuzione in modalità CLI.
"""

import sys
import os
import types
import importlib
from pathlib import Path

_PKG_DIR  = Path(__file__).parent          # btk-speaker-designer/
_ROOT_DIR = _PKG_DIR.parent               # SubSim/
_PKG_NAME = "btk_speaker_designer"

# SubSim/ nel path per il modulo 'shared'
sys.path.insert(0, str(_ROOT_DIR))


def _bootstrap_package():
    """
    Rende 'btk_speaker_designer' importabile anche quando lanciato direttamente
    come script (python btk_speaker_designer/main.py).

    Se il pacchetto è già in sys.modules (es: python -m btk_speaker_designer)
    non fa niente — lascia che l'import normale di Python gestisca tutto.
    """
    if _PKG_NAME in sys.modules:
        return   # pacchetto già caricato correttamente, nulla da fare

    # Controlla se è un vero pacchetto Python (ha __init__.py)
    init_file = _PKG_DIR / "__init__.py"
    if init_file.exists():
        # Carica il pacchetto reale tramite importlib invece di creare un modulo sintetico
        import importlib.util as _ilu
        for sub in ["", ".core", ".gui", ".database", ".exporters"]:
            full_name = _PKG_NAME + sub
            if full_name in sys.modules:
                continue
            sub_dir = _PKG_DIR if sub == "" else (_PKG_DIR / sub.lstrip("."))
            init = sub_dir / "__init__.py"
            if not init.exists():
                continue
            spec = _ilu.spec_from_file_location(full_name, str(init),
                                                submodule_search_locations=[str(sub_dir)])
            if spec is None:
                continue
            mod = _ilu.module_from_spec(spec)
            mod.__path__ = [str(sub_dir)]
            mod.__package__ = full_name
            sys.modules[full_name] = mod
            try:
                spec.loader.exec_module(mod)
            except Exception:
                pass  # __init__.py può essere vuoto o avere import opzionali
    else:
        # Directory con trattino: usa moduli sintetici (btk-speaker-designer)
        def _reg(name: str, path: Path):
            if name not in sys.modules:
                m = types.ModuleType(name)
                m.__path__ = [str(path)]
                m.__package__ = name
                m.__name__ = name
                sys.modules[name] = m

        _reg(_PKG_NAME,               _PKG_DIR)
        _reg(f"{_PKG_NAME}.core",     _PKG_DIR / "core")
        _reg(f"{_PKG_NAME}.gui",      _PKG_DIR / "gui")
        _reg(f"{_PKG_NAME}.database", _PKG_DIR / "database")
        _reg(f"{_PKG_NAME}.exporters",_PKG_DIR / "exporters")


_bootstrap_package()


def run_gui():
    """Avvia l'interfaccia grafica dell'applicazione."""
    try:
        from btk_speaker_designer.gui.main_window import create_app
        app, window = create_app()
        window.show()
        # PySide6 usa exec(), PyQt5 usa exec_() — entrambi funzionano
        return app.exec() if hasattr(app, "exec") and not hasattr(app, "exec_") \
               else app.exec_()
    except Exception as e:
        print(f"Impossibile avviare la GUI: {e}")
        print("Assicurati di avere PyQt5 o PySide6 installato:")
        print("  pip install PyQt5")
        print("  oppure: pip install PySide6")
        import traceback
        traceback.print_exc()
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


def main():
    """Entrypoint pubblico (usato da __main__.py e da python -m btk_speaker_designer)."""
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


if __name__ == "__main__":
    main()
