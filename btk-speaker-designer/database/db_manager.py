"""
Gestore del database SQLite per BTK Speaker Designer.
Gestisce driver, trombe e progetti.
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..core.driver_model import DriverModel
from ..core.horn_model import HornModel

# Percorso del database
DB_DIR = Path(__file__).parent
DB_PATH = DB_DIR / "btk_speaker_designer.db"
SCHEMA_PATH = DB_DIR / "schema.sql"

# Directory dei dati JSON
DRIVERS_DIR = DB_DIR / "drivers"
HORNS_DIR = DB_DIR / "horns"


def get_connection() -> sqlite3.Connection:
    """Crea e restituisce una connessione al database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # permette accesso per nome colonna
    return conn


def initialize_database():
    """
    Inizializza il database creando le tabelle e caricando i dati seed.
    Se il database esiste già, non sovrascrive i dati.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Crea le tabelle
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    cursor.executescript(schema)
    conn.commit()

    # Carica dati seed solo se le tabelle sono vuote
    cursor.execute("SELECT COUNT(*) FROM drivers")
    if cursor.fetchone()[0] == 0:
        _seed_drivers(cursor)
        conn.commit()

    cursor.execute("SELECT COUNT(*) FROM horns")
    if cursor.fetchone()[0] == 0:
        _seed_horns(cursor)
        conn.commit()

    conn.close()


def _seed_drivers(cursor: sqlite3.Cursor):
    """Carica i driver dai file JSON nel database."""
    json_files = list(DRIVERS_DIR.glob("*.json"))

    for json_file in sorted(json_files):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                drivers = json.load(f)

            for d in drivers:
                cursor.execute("""
                    INSERT OR IGNORE INTO drivers (
                        manufacturer, model, driver_type,
                        fs_hz, re_ohm, qes, qms, qts,
                        vas_liters, sd_m2, xmax_mm, bl_tm, mms_g, le_mh,
                        spl_1w_1m, power_rms_w, power_program_w, impedance_nom_ohm,
                        diameter_inch, throat_diameter_inch, weight_kg,
                        magnet_type, cone_material, voice_coil_diameter_mm,
                        freq_range_low_hz, freq_range_high_hz,
                        description, notes
                    ) VALUES (
                        :manufacturer, :model, :driver_type,
                        :fs_hz, :re_ohm, :qes, :qms, :qts,
                        :vas_liters, :sd_m2, :xmax_mm, :bl_tm, :mms_g, :le_mh,
                        :spl_1w_1m, :power_rms_w, :power_program_w, :impedance_nom_ohm,
                        :diameter_inch, :throat_diameter_inch, :weight_kg,
                        :magnet_type, :cone_material, :voice_coil_diameter_mm,
                        :freq_range_low_hz, :freq_range_high_hz,
                        :description, :notes
                    )
                """, {
                    "manufacturer": d.get("manufacturer", ""),
                    "model": d.get("model", ""),
                    "driver_type": d.get("driver_type", "subwoofer"),
                    "fs_hz": d.get("fs_hz"),
                    "re_ohm": d.get("re_ohm"),
                    "qes": d.get("qes"),
                    "qms": d.get("qms"),
                    "qts": d.get("qts"),
                    "vas_liters": d.get("vas_liters"),
                    "sd_m2": d.get("sd_m2"),
                    "xmax_mm": d.get("xmax_mm"),
                    "bl_tm": d.get("bl_tm"),
                    "mms_g": d.get("mms_g"),
                    "le_mh": d.get("le_mh"),
                    "spl_1w_1m": d.get("spl_1w_1m"),
                    "power_rms_w": d.get("power_rms_w"),
                    "power_program_w": d.get("power_program_w"),
                    "impedance_nom_ohm": d.get("impedance_nom_ohm", 8),
                    "diameter_inch": d.get("diameter_inch", 0),
                    "throat_diameter_inch": d.get("throat_diameter_inch", 0),
                    "weight_kg": d.get("weight_kg"),
                    "magnet_type": d.get("magnet_type", ""),
                    "cone_material": d.get("cone_material", ""),
                    "voice_coil_diameter_mm": d.get("voice_coil_diameter_mm"),
                    "freq_range_low_hz": d.get("freq_range_low_hz"),
                    "freq_range_high_hz": d.get("freq_range_high_hz"),
                    "description": d.get("description", ""),
                    "notes": d.get("notes", ""),
                })
        except Exception as e:
            print(f"Errore caricamento {json_file}: {e}")


def _seed_horns(cursor: sqlite3.Cursor):
    """Carica le trombe dai file JSON nel database."""
    json_files = list(HORNS_DIR.glob("*.json"))

    for json_file in sorted(json_files):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                horns = json.load(f)

            for h in horns:
                cursor.execute("""
                    INSERT OR IGNORE INTO horns (
                        manufacturer, model, horn_type,
                        throat_diameter_inch, mouth_width_cm, mouth_height_cm,
                        length_cm, flare_rate,
                        coverage_h_deg, coverage_v_deg,
                        freq_range_low_hz, freq_range_high_hz,
                        cutoff_freq_hz, avg_spl_boost_db,
                        material, weight_kg, mounting_pattern,
                        compatible_throat_diameters,
                        description, notes
                    ) VALUES (
                        :manufacturer, :model, :horn_type,
                        :throat_diameter_inch, :mouth_width_cm, :mouth_height_cm,
                        :length_cm, :flare_rate,
                        :coverage_h_deg, :coverage_v_deg,
                        :freq_range_low_hz, :freq_range_high_hz,
                        :cutoff_freq_hz, :avg_spl_boost_db,
                        :material, :weight_kg, :mounting_pattern,
                        :compatible_throat_diameters,
                        :description, :notes
                    )
                """, {
                    "manufacturer": h.get("manufacturer", ""),
                    "model": h.get("model", ""),
                    "horn_type": h.get("horn_type", "constant_directivity"),
                    "throat_diameter_inch": h.get("throat_diameter_inch", 1.4),
                    "mouth_width_cm": h.get("mouth_width_cm"),
                    "mouth_height_cm": h.get("mouth_height_cm"),
                    "length_cm": h.get("length_cm"),
                    "flare_rate": h.get("flare_rate", 0.0),
                    "coverage_h_deg": h.get("coverage_h", 90.0),
                    "coverage_v_deg": h.get("coverage_v", 40.0),
                    "freq_range_low_hz": h.get("freq_range_low_hz"),
                    "freq_range_high_hz": h.get("freq_range_high_hz"),
                    "cutoff_freq_hz": h.get("cutoff_freq_hz"),
                    "avg_spl_boost_db": h.get("avg_spl_boost_db", 0.0),
                    "material": h.get("material", "plastic"),
                    "weight_kg": h.get("weight_kg"),
                    "mounting_pattern": h.get("mounting_pattern", ""),
                    "compatible_throat_diameters": json.dumps(
                        h.get("compatible_throat_diameters", [])
                    ),
                    "description": h.get("description", ""),
                    "notes": h.get("notes", ""),
                })
        except Exception as e:
            print(f"Errore caricamento {json_file}: {e}")


# ─── API Driver ───────────────────────────────────────────────────────────────

def get_manufacturers() -> List[str]:
    """Restituisce la lista dei produttori nel database."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT manufacturer FROM drivers ORDER BY manufacturer"
    ).fetchall()
    conn.close()
    return [r["manufacturer"] for r in rows]


def get_drivers_by_type(
    driver_type: Optional[str] = None,
    manufacturer: Optional[str] = None
) -> List[DriverModel]:
    """
    Recupera driver filtrati per tipo e/o produttore.

    Args:
        driver_type: 'subwoofer', 'compression_driver', 'woofer' o None per tutti
        manufacturer: Nome produttore o None per tutti

    Returns:
        Lista di DriverModel
    """
    conn = get_connection()
    query = "SELECT * FROM drivers WHERE 1=1"
    params = []

    if driver_type:
        query += " AND driver_type = ?"
        params.append(driver_type)
    if manufacturer:
        query += " AND manufacturer = ?"
        params.append(manufacturer)

    query += " ORDER BY manufacturer, model"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    return [_row_to_driver(r) for r in rows]


def get_driver_by_model(model: str) -> Optional[DriverModel]:
    """Recupera un driver specifico per nome modello."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM drivers WHERE model = ?", (model,)
    ).fetchone()
    conn.close()
    return _row_to_driver(row) if row else None


def _row_to_driver(row: sqlite3.Row) -> DriverModel:
    """Converte una riga del database in DriverModel."""
    return DriverModel(
        manufacturer=row["manufacturer"],
        model=row["model"],
        driver_type=row["driver_type"],
        fs=row["fs_hz"] or 50.0,
        re=row["re_ohm"] or 8.0,
        qes=row["qes"] or 0.5,
        qms=row["qms"] or 4.0,
        qts=row["qts"] or 0.0,
        vas=row["vas_liters"] or 100.0,
        sd=row["sd_m2"] or 0.01,
        xmax=row["xmax_mm"] or 10.0,
        bl=row["bl_tm"] or 12.0,
        mms=row["mms_g"] or 50.0,
        le=row["le_mh"] or 0.5,
        spl_1w_1m=row["spl_1w_1m"] or 100.0,
        power_rms=row["power_rms_w"] or 500.0,
        power_program=row["power_program_w"] or 1000.0,
        impedance_nominal=row["impedance_nom_ohm"] or 8.0,
        diameter_inch=row["diameter_inch"] or 15.0,
        throat_diameter_inch=row["throat_diameter_inch"] or 0.0,
        weight_kg=row["weight_kg"] or 5.0,
        magnet_type=row["magnet_type"] or "ferrite",
        freq_range_low=row["freq_range_low_hz"] or 0.0,
        freq_range_high=row["freq_range_high_hz"] or 0.0,
        description=row["description"] or "",
    )


# ─── API Trombe ───────────────────────────────────────────────────────────────

def get_horn_manufacturers() -> List[str]:
    """Restituisce la lista dei produttori di trombe nel database."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT manufacturer FROM horns ORDER BY manufacturer"
    ).fetchall()
    conn.close()
    return [r["manufacturer"] for r in rows]


def get_horns_by_throat(
    throat_diameter_inch: float,
    manufacturer: Optional[str] = None,
    tolerance: float = 0.15
) -> List[HornModel]:
    """
    Recupera trombe compatibili con un diametro di gola dato.

    Args:
        throat_diameter_inch: Diametro gola in pollici
        manufacturer: Filtro produttore (opzionale)
        tolerance: Tolleranza in pollici

    Returns:
        Lista di HornModel compatibili
    """
    conn = get_connection()
    query = """
        SELECT * FROM horns
        WHERE throat_diameter_inch BETWEEN ? AND ?
    """
    params = [
        throat_diameter_inch - tolerance,
        throat_diameter_inch + tolerance
    ]

    if manufacturer:
        query += " AND manufacturer = ?"
        params.append(manufacturer)

    query += " ORDER BY manufacturer, model"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    return [_row_to_horn(r) for r in rows]


def get_all_horns(manufacturer: Optional[str] = None) -> List[HornModel]:
    """Recupera tutte le trombe, opzionalmente filtrate per produttore."""
    conn = get_connection()
    if manufacturer:
        rows = conn.execute(
            "SELECT * FROM horns WHERE manufacturer = ? ORDER BY model",
            (manufacturer,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM horns ORDER BY manufacturer, model"
        ).fetchall()
    conn.close()
    return [_row_to_horn(r) for r in rows]


def _row_to_horn(row: sqlite3.Row) -> HornModel:
    """Converte una riga del database in HornModel."""
    try:
        compatible = json.loads(row["compatible_throat_diameters"] or "[]")
    except Exception:
        compatible = []

    return HornModel(
        manufacturer=row["manufacturer"],
        model=row["model"],
        horn_type=row["horn_type"],
        throat_diameter_inch=row["throat_diameter_inch"],
        mouth_width_cm=row["mouth_width_cm"] or 30.0,
        mouth_height_cm=row["mouth_height_cm"] or 20.0,
        length_cm=row["length_cm"] or 25.0,
        flare_rate=row["flare_rate"] or 0.0,
        coverage_h=row["coverage_h_deg"] or 90.0,
        coverage_v=row["coverage_v_deg"] or 40.0,
        freq_range_low=row["freq_range_low_hz"] or 500.0,
        freq_range_high=row["freq_range_high_hz"] or 20000.0,
        cutoff_freq=row["cutoff_freq_hz"] or 500.0,
        avg_spl_boost=row["avg_spl_boost_db"] or 0.0,
        material=row["material"] or "plastic",
        weight_kg=row["weight_kg"] or 0.5,
        mounting_pattern=row["mounting_pattern"] or "",
        compatible_throat_diameters=compatible,
        description=row["description"] or "",
    )


# ─── API Progetti ─────────────────────────────────────────────────────────────

def save_project(name: str, description: str, speaker_type: str,
                 geometry_type: str, project_data: dict) -> int:
    """
    Salva un progetto nel database.

    Returns:
        ID del progetto salvato
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO projects (name, description, speaker_type, geometry_type, project_json)
        VALUES (?, ?, ?, ?, ?)
    """, (name, description, speaker_type, geometry_type, json.dumps(project_data)))
    project_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return project_id


def load_project(project_id: int) -> Optional[dict]:
    """Carica un progetto dal database."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "speaker_type": row["speaker_type"],
        "geometry_type": row["geometry_type"],
        "project_data": json.loads(row["project_json"]),
        "created_at": row["created_at"],
    }


def list_projects() -> List[dict]:
    """Restituisce la lista di tutti i progetti salvati."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, description, speaker_type, geometry_type, created_at "
        "FROM projects ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
