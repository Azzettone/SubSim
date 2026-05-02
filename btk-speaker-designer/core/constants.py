"""
Costanti fisiche e di progetto per BTK Speaker Designer.
Basate sui dati del foglio di calcolo Horn Calculator originale.
"""

import numpy as np

# ─── Costanti fisiche (dal CSV "Constant") ────────────────────────────────────
TEMPERATURE_DEFAULT = 16.8      # °C (temperatura standard di riferimento)
SPEED_OF_SOUND = 342.016        # m/s (velocità del suono a 16.8°C)
AIR_DENSITY = 1.225             # kg/m³ (densità aria standard)

# ─── Unità di misura ──────────────────────────────────────────────────────────
INCHES_TO_METERS = 0.0254
METERS_TO_INCHES = 39.3701
MM_TO_METERS = 0.001
METERS_TO_MM = 1000.0
CM_TO_METERS = 0.01
METERS_TO_CM = 100.0
LITERS_TO_M3 = 0.001
M3_TO_LITERS = 1000.0

# ─── Costanti acustiche ───────────────────────────────────────────────────────
REFERENCE_PRESSURE = 20e-6      # Pa (soglia di udibilità 20μPa)
REFERENCE_POWER = 1e-12         # W (potenza di riferimento)

# ─── Tipi di speaker ─────────────────────────────────────────────────────────
SPEAKER_TYPE_SUB = "SUB"
SPEAKER_TYPE_CD = "CD"
SPEAKER_TYPE_FULLRANGE = "FULLRANGE"

SPEAKER_TYPES = [SPEAKER_TYPE_SUB, SPEAKER_TYPE_CD, SPEAKER_TYPE_FULLRANGE]

SPEAKER_TYPE_LABELS = {
    SPEAKER_TYPE_SUB: "Subwoofer (Basse Frequenze)",
    SPEAKER_TYPE_CD: "Compression Driver (Medi/Alti)",
    SPEAKER_TYPE_FULLRANGE: "Fullrange (CD + SUB combinato)",
}

# ─── Geometrie tromba ─────────────────────────────────────────────────────────
GEOMETRY_STRAIGHT = "straight"
GEOMETRY_FOLDED = "folded"
GEOMETRY_2FOLDED = "2-folded"

GEOMETRY_TYPES = [GEOMETRY_STRAIGHT, GEOMETRY_FOLDED, GEOMETRY_2FOLDED]

GEOMETRY_LABELS = {
    GEOMETRY_STRAIGHT: "Dritta (Straight)",
    GEOMETRY_FOLDED:   "Piegata 1 volta (Folded)",
    GEOMETRY_2FOLDED:  "Piegata 2 volte (2-Folded)",
}

# ─── Tipi di espansione tromba ────────────────────────────────────────────────
EXPANSION_EXPONENTIAL = "exponential"
EXPANSION_CONICAL = "conical"
EXPANSION_TRACTRIX = "tractrix"
EXPANSION_HYPEX = "hypex"

EXPANSION_TYPES = [
    EXPANSION_EXPONENTIAL,
    EXPANSION_CONICAL,
    EXPANSION_TRACTRIX,
    EXPANSION_HYPEX,
]

EXPANSION_LABELS = {
    EXPANSION_EXPONENTIAL: "Esponenziale",
    EXPANSION_CONICAL:     "Conico",
    EXPANSION_TRACTRIX:    "Tractrix",
    EXPANSION_HYPEX:       "Hypex (ibrido)",
}

# ─── Range di frequenza per tipo ─────────────────────────────────────────────
FREQ_RANGE_SUB = (20, 200)          # Hz
FREQ_RANGE_CD = (500, 20000)        # Hz
FREQ_RANGE_FULLRANGE = (20, 20000)  # Hz

# Frequenza di crossover default per sistema fullrange
CROSSOVER_FREQ_DEFAULT = 500.0      # Hz

# ─── Dimensioni gola tromba standard (pollici) ───────────────────────────────
THROAT_DIAMETERS_INCH = [1.0, 1.4, 1.75, 2.0, 3.0, 4.0]

# ─── Parametri default dal foglio di calcolo originale ───────────────────────
DEFAULT_FCUTOFF = 70.0              # Hz (frequenza di taglio tromba)
DEFAULT_SMOUTH_STHROAT_RATIO = 2.0  # rapporto area bocca/gola

# Parametri calcolati di riferimento dal foglio originale
REFERENCE_FLARE_RATE = 2.5706       # m⁻¹
REFERENCE_THROAT_AREA = 0.9503      # m²
REFERENCE_HORN_LENGTH = 0.2696      # m
REFERENCE_THROAT_IMPEDANCE = 440.8648  # mkh

# ─── Materiali per pannelli (prezzi default) ──────────────────────────────────
DEFAULT_WOOD_PRICE_PER_M2 = 30.0    # €/m²

# ─── Numero di sezioni per calcolo profilo tromba ────────────────────────────
NUM_HORN_SECTIONS = 8

# ─── Tolleranza numerica ──────────────────────────────────────────────────────
EPSILON = 1e-10

# ─── Tipi di enclosure (caricamento acustico) ────────────────────────────────
# Categorie principali (per il selector a 3 opzioni del mockup)
ENCLOSURE_CATEGORY_HORN   = "horn"
ENCLOSURE_CATEGORY_REFLEX = "reflex"
ENCLOSURE_CATEGORY_HYBRID = "mixed_hybrid"

ENCLOSURE_CATEGORIES = [
    ENCLOSURE_CATEGORY_HORN,
    ENCLOSURE_CATEGORY_REFLEX,
    ENCLOSURE_CATEGORY_HYBRID,
]
ENCLOSURE_CATEGORY_LABELS = {
    ENCLOSURE_CATEGORY_HORN:   "Tromba",
    ENCLOSURE_CATEGORY_REFLEX: "Reflex / Bandpass",
    ENCLOSURE_CATEGORY_HYBRID: "Mixed-Hybrid",
}

# Varianti specifiche per ogni categoria
ENCLOSURE_HORN         = "horn"              # Tromba caricata pura
ENCLOSURE_REFLEX       = "reflex"            # Bass-reflex standard
ENCLOSURE_BANDPASS_4   = "bandpass_4"        # Bandpass 4° ordine (cassa chiusa + reflex front)
ENCLOSURE_BANDPASS_6   = "bandpass_6"        # Bandpass 6° ordine (reflex rear + reflex front)
ENCLOSURE_HORN_REFLEX  = "horn_reflex"       # Tromba frontale + porta reflex (ibrido)
ENCLOSURE_BANDPASS_HORN   = "bandpass_horn"     # Bandpass + carico a tromba (stile DC10)
ENCLOSURE_BANDPASS_REFLEX = "bandpass_reflex"   # Bandpass + extra porta reflex

# Varianti per categoria
ENCLOSURE_VARIANTS = {
    ENCLOSURE_CATEGORY_HORN: [
        ENCLOSURE_HORN,
        ENCLOSURE_HORN_REFLEX,
    ],
    ENCLOSURE_CATEGORY_REFLEX: [
        ENCLOSURE_REFLEX,
        ENCLOSURE_BANDPASS_4,
        ENCLOSURE_BANDPASS_6,
    ],
    ENCLOSURE_CATEGORY_HYBRID: [
        ENCLOSURE_BANDPASS_HORN,
        ENCLOSURE_BANDPASS_REFLEX,
        ENCLOSURE_HORN_REFLEX,
    ],
}
ENCLOSURE_LABELS = {
    ENCLOSURE_HORN:           "Tromba caricata (Horn Loaded)",
    ENCLOSURE_REFLEX:         "Bass-Reflex standard",
    ENCLOSURE_BANDPASS_4:     "Bandpass 4° ordine",
    ENCLOSURE_BANDPASS_6:     "Bandpass 6° ordine",
    ENCLOSURE_HORN_REFLEX:    "Tromba + Porta Reflex (ibrido)",
    ENCLOSURE_BANDPASS_HORN:  "Bandpass + Tromba (stile DC10/SPKP)",
    ENCLOSURE_BANDPASS_REFLEX:"Bandpass + Porta Reflex aggiuntiva",
}

# Quali varianti contengono una tromba (→ mostrare parametri horn)
ENCLOSURE_HAS_HORN = {
    ENCLOSURE_HORN, ENCLOSURE_HORN_REFLEX, ENCLOSURE_BANDPASS_HORN
}
# Quali varianti contengono una porta reflex (→ mostrare parametri reflex)
ENCLOSURE_HAS_REFLEX = {
    ENCLOSURE_REFLEX, ENCLOSURE_BANDPASS_4, ENCLOSURE_BANDPASS_6,
    ENCLOSURE_HORN_REFLEX, ENCLOSURE_BANDPASS_HORN, ENCLOSURE_BANDPASS_REFLEX,
}
# Quali varianti sono bandpass (→ mostrare volumi camera front/rear)
ENCLOSURE_IS_BANDPASS = {
    ENCLOSURE_BANDPASS_4, ENCLOSURE_BANDPASS_6,
    ENCLOSURE_BANDPASS_HORN, ENCLOSURE_BANDPASS_REFLEX,
}

# Default enclosure per tipo speaker
ENCLOSURE_DEFAULT_FOR_SPEAKER = {
    SPEAKER_TYPE_SUB:       ENCLOSURE_HORN,
    SPEAKER_TYPE_CD:        ENCLOSURE_HORN,
    SPEAKER_TYPE_FULLRANGE: ENCLOSURE_BANDPASS_HORN,
}

# ─── Tipi di porta reflex ────────────────────────────────────────────────────
PORT_TYPE_CIRCULAR = "circular"
PORT_TYPE_SLOT     = "slot"
PORT_TYPE_PASSIVE  = "passive_radiator"

PORT_TYPES = [PORT_TYPE_CIRCULAR, PORT_TYPE_SLOT, PORT_TYPE_PASSIVE]
PORT_TYPE_LABELS = {
    PORT_TYPE_CIRCULAR: "Circolare",
    PORT_TYPE_SLOT:     "Slot / Fessura",
    PORT_TYPE_PASSIVE:  "Radiatore Passivo",
}
