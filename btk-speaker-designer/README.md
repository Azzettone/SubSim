# BTK Speaker Designer

Software professionale per il design di altoparlanti e trombe acustiche.

## Caratteristiche Principali

- **3 tipi di speaker**: SUB (Subwoofer), CD (Compression Driver), FULLRANGE (CD + SUB)
- **3 geometrie tromba**: Straight (dritta), Folded (1 piega), 2-Folded (2 pieghe)
- **Database driver**: RCF, Beyma, B&C Speakers, LaVoce — con parametri Thiele-Small completi
- **Database trombe commerciali**: RCF, Beyma, B&C, JBL
- **Vincoli dimensionali**: Ottimizzazione automatica nei limiti di ingombro
- **Somma fronte/retro**: Calcolo dell'interferenza acustica tra emissione frontale (tromba) e posteriore (back radiation)
- **Export**: DXF per CNC, lista taglio pannelli CSV, report PDF

## Struttura del Progetto

```
btk-speaker-designer/
├── core/
│   ├── constants.py            # Costanti fisiche e di progetto
│   ├── horn_calculator.py      # Formule espansione tromba (esponenziale, conico, tractrix, hypex)
│   ├── driver_model.py         # Modello driver con parametri T&S
│   ├── horn_model.py           # Modello trombe commerciali
│   ├── phase_summing.py        # Calcolo somma in fase fronte/retro
│   ├── geometry.py             # Geometrie Straight/Folded/2-Folded
│   ├── fullrange_combiner.py   # Sistema combinato CD+SUB con crossover
│   └── constraint_solver.py    # Risolutore vincoli dimensionali
│
├── database/
│   ├── schema.sql              # Schema SQLite
│   ├── db_manager.py           # Gestore database
│   ├── drivers/
│   │   ├── rcf_drivers.json    # Subwoofer e CD RCF
│   │   ├── beyma_drivers.json  # Subwoofer e CD Beyma
│   │   ├── bc_drivers.json     # Subwoofer e CD B&C Speakers
│   │   └── lavoce_drivers.json # Subwoofer e CD LaVoce
│   └── horns/
│       ├── rcf_horns.json      # Trombe RCF
│       ├── beyma_horns.json    # Trombe Beyma
│       ├── bc_horns.json       # Trombe B&C
│       └── jbl_horns.json      # Trombe JBL (riferimento)
│
├── gui/
│   ├── main_window.py          # Finestra principale PyQt5/PySide6
│   ├── speaker_type_selector.py # Selezione tipo (SUB/CD/FULLRANGE)
│   ├── driver_selector.py      # Selezione driver dal database
│   ├── horn_designer.py        # Progettazione tromba con vincoli
│   └── visualization.py        # Grafici Matplotlib (profilo, risposta, fase)
│
├── exporters/
│   ├── dxf_export.py           # Export DXF per CNC/laser
│   ├── panel_cutlist.py        # Lista taglio pannelli (testo/CSV/JSON)
│   └── pdf_report.py           # Report PDF completo
│
├── tests/
│   ├── test_horn_calculator.py # Test calcoli tromba
│   ├── test_driver_model.py    # Test modello driver
│   ├── test_phase_summing.py   # Test somma fronte/retro
│   └── test_geometry.py        # Test geometrie cabinet
│
├── main.py                     # Entry point applicazione
└── requirements.txt
```

## Installazione

```bash
# Clona il repository
cd btk-speaker-designer

# Installa le dipendenze
pip install -r requirements.txt

# Avvia l'applicazione
python main.py

# Oppure esegui la demo CLI
python main.py --demo
```

## Avvio Rapido

### Modalità GUI
```bash
python btk-speaker-designer/main.py
```

### Modalità Demo (senza GUI)
```bash
python btk-speaker-designer/main.py --demo
```

### Uso Programmatico
```python
from btk_speaker_designer.core.horn_calculator import design_horn
from btk_speaker_designer.core.geometry import auto_select_geometry
from btk_speaker_designer.core.constraint_solver import DimensionalConstraints

# Progetta una tromba
geom = design_horn(
    cutoff_freq_hz=70.0,
    driver_sd_m2=0.091,        # 18" woofer
    smouth_sthroat_ratio=2.0,
)
print(f"Lunghezza tromba: {geom.horn_length_m*100:.2f} cm")
print(f"Flare rate: {geom.flare_rate_m:.4f} m⁻¹")

# Calcola geometria cabinet con vincoli
constraints = DimensionalConstraints(
    max_depth_mm=600.0,
    max_width_mm=700.0
)
from btk_speaker_designer.core.constraint_solver import solve_with_constraints
result = solve_with_constraints(geom, constraints)
cabinet = result.cabinet
print(f"Geometria scelta: {cabinet.geometry_type}")
print(f"Dimensioni: {cabinet.total_width_mm:.0f}×{cabinet.total_height_mm:.0f}×{cabinet.total_depth_mm:.0f} mm")
```

## Formule Implementate

### Espansione Tromba Esponenziale
```
S(x) = S_throat × exp(m × x)
m = 4π × fc / c
L = ln(Smouth/Sthroat) / m
```

### Somma Fronte/Retro
```python
delay = path_difference / c
phase_shift = 2π × f × delay
total_pressure = front_pressure + back_pressure × exp(j × phase_shift)
combined_spl = 20 × log10(|total_pressure|)
```

### Vincoli Dimensionali
Il software seleziona automaticamente tra le geometrie:
- **Straight**: se la lunghezza tromba ≤ profondità max
- **Folded**: se la lunghezza tromba ≤ 2 × profondità max
- **2-Folded**: altrimenti

## Test

```bash
# Dalla directory root del repository
pytest btk-speaker-designer/tests/ -v

# Con report copertura
pytest btk-speaker-designer/tests/ -v --cov=btk_speaker_designer
```

## Integrazione con SubSim

Il progetto condivide con SubSim i moduli in `shared/`:
- `acoustic_core.py` — Formule acustiche fondamentali
- `material_properties.py` — Database materiali da costruzione
- `grille_calculator.py` — Calcolo foratura griglie frontali
- `ui_components.py` — Tema grafico e stili Qt condivisi

## Costanti di Riferimento (dal foglio Excel originale)

| Parametro | Valore |
|-----------|--------|
| Temperatura | 16.8°C |
| Velocità suono | 342.016 m/s |
| Densità aria | 1.225 kg/m³ |
| Frequenza taglio (esempio) | 70.0 Hz |
| Flare rate (m) | 2.5706 m⁻¹ |
| Area gola (S₀) | 0.9503 m² |
| Lunghezza tromba | 0.2696 m |
| Impedenza gola | 440.8648 Pa·s/m³ |

## Stack Tecnologico

- **Python** 3.9+
- **NumPy** — Calcoli matematici e array
- **SciPy** — Ottimizzazione e interpolazione
- **PyQt5/PySide6** — Interfaccia grafica
- **Matplotlib** — Grafici
- **SQLite** — Database driver e trombe
- **ezdxf** — Export DXF per CNC
- **ReportLab** — Report PDF

## Licenza

Progetto sviluppato per BTK. Tutti i diritti riservati.
