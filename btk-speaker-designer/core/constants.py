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
