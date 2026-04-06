-- BTK Speaker Designer - Schema Database SQLite
-- Versione 1.0

-- ============================================================
-- TABELLA DRIVER
-- ============================================================
CREATE TABLE IF NOT EXISTS drivers (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    manufacturer            TEXT NOT NULL,
    model                   TEXT NOT NULL UNIQUE,
    driver_type             TEXT NOT NULL CHECK(driver_type IN ('subwoofer','woofer','compression_driver','fullrange')),

    -- Parametri Thiele-Small
    fs_hz                   REAL,           -- Frequenza risonanza (Hz)
    re_ohm                  REAL,           -- Resistenza DC (Ohm)
    qes                     REAL,           -- Fattore merito elettrico
    qms                     REAL,           -- Fattore merito meccanico
    qts                     REAL,           -- Fattore merito totale
    vas_liters              REAL,           -- Volume equivalente (litri)
    sd_m2                   REAL,           -- Area diaframma (m²)
    xmax_mm                 REAL,           -- Escursione massima (mm picco)
    bl_tm                   REAL,           -- Forza motrice (T·m)
    mms_g                   REAL,           -- Massa mobile (g)
    le_mh                   REAL,           -- Induttanza bobina (mH)

    -- Parametri elettro-acustici
    spl_1w_1m               REAL,           -- Sensibilità 1W/1m (dB)
    power_rms_w             REAL,           -- Potenza RMS/AES (W)
    power_program_w         REAL,           -- Potenza programma (W)
    impedance_nom_ohm       REAL,           -- Impedenza nominale (Ohm)

    -- Caratteristiche fisiche
    diameter_inch           REAL,           -- Diametro nominale (pollici)
    throat_diameter_inch    REAL DEFAULT 0, -- Diametro gola (pollici, solo CD)
    weight_kg               REAL,           -- Peso (kg)
    magnet_type             TEXT,           -- Tipo magnete: ferrite/neodymium/alnico
    cone_material           TEXT,           -- Materiale cono
    voice_coil_diameter_mm  REAL,           -- Diametro bobina mobile (mm)

    -- Range di frequenza
    freq_range_low_hz       REAL,           -- Frequenza minima (Hz)
    freq_range_high_hz      REAL,           -- Frequenza massima (Hz)

    -- Metadati
    description             TEXT DEFAULT '',
    notes                   TEXT DEFAULT '',
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABELLA TROMBE (HORNS)
-- ============================================================
CREATE TABLE IF NOT EXISTS horns (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    manufacturer                TEXT NOT NULL,
    model                       TEXT NOT NULL UNIQUE,
    horn_type                   TEXT NOT NULL,
    -- Tipi: constant_directivity, exponential, tractrix, radial, sector, multicell

    -- Geometria
    throat_diameter_inch        REAL NOT NULL,  -- Diametro gola (pollici)
    mouth_width_cm              REAL,           -- Larghezza bocca (cm)
    mouth_height_cm             REAL,           -- Altezza bocca (cm)
    length_cm                   REAL,           -- Lunghezza tromba (cm)
    flare_rate                  REAL DEFAULT 0, -- Tasso svasatura (m⁻¹)

    -- Pattern direttività
    coverage_h_deg              REAL,           -- Copertura orizzontale -6dB (gradi)
    coverage_v_deg              REAL,           -- Copertura verticale -6dB (gradi)

    -- Caratteristiche acustiche
    freq_range_low_hz           REAL,           -- Frequenza min consigliata (Hz)
    freq_range_high_hz          REAL,           -- Frequenza max consigliata (Hz)
    cutoff_freq_hz              REAL,           -- Frequenza di taglio (Hz)
    avg_spl_boost_db            REAL DEFAULT 0, -- Guadagno SPL medio (dB)

    -- Fisico
    material                    TEXT,           -- Materiale: plastic/aluminum/fiberglass/wood
    weight_kg                   REAL,           -- Peso (kg)
    mounting_pattern            TEXT DEFAULT '',-- Pattern viti (es. "4x60mm")

    -- Compatibilità gole (JSON array di valori in pollici)
    compatible_throat_diameters TEXT DEFAULT '[]',

    -- Metadati
    description                 TEXT DEFAULT '',
    notes                       TEXT DEFAULT '',
    created_at                  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at                  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABELLA PROGETTI
-- ============================================================
CREATE TABLE IF NOT EXISTS projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    speaker_type    TEXT NOT NULL CHECK(speaker_type IN ('SUB','CD','FULLRANGE')),
    geometry_type   TEXT NOT NULL,
    project_json    TEXT NOT NULL,  -- Progetto completo serializzato in JSON
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- INDICI
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_drivers_manufacturer ON drivers(manufacturer);
CREATE INDEX IF NOT EXISTS idx_drivers_type ON drivers(driver_type);
CREATE INDEX IF NOT EXISTS idx_horns_manufacturer ON horns(manufacturer);
CREATE INDEX IF NOT EXISTS idx_horns_type ON horns(horn_type);
CREATE INDEX IF NOT EXISTS idx_horns_throat ON horns(throat_diameter_inch);
