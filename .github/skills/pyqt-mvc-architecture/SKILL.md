---
name: pyqt-mvc-architecture
description: 'PyQt5 MVC architecture pattern used in BTK Speaker Designer. Use when: editing GUI files (input_panel.py, design_panel.py, main_window.py, assembly_model.py, viewport_widget.py), adding new parameters/widgets, handling signals/slots, debugging missing UI updates after model changes, syncing widget state to model. Covers QObject signals, blockSignals(), pyqtSignal patterns, dataclass-based parameters (HornParams, ChamberParams), validation flow.'
---

# PyQt5 MVC Architecture (BTK Speaker Designer)

## Architecture Overview

```
┌──────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  InputPanel  │──┐   │                 │  ┌──→│  Viewport3D     │
│  DesignPanel │  ├──→│  AssemblyModel  │──┤   │  AnalysisTabs   │
│  DriverSel.  │──┘   │   (Model/Ctrl)  │  ├──→│  HornView       │
└──────────────┘      └─────────────────┘  └──→│  PanelCutlist   │
       │                       │                └─────────────────┘
       │                       │
       │  signals (Qt)         │  signals (Qt)
       │  to model             │  from model
       └───────────────────────┘
```

## Layers

### Model: `AssemblyModel`

Single source of truth. Holds:
- `_horn_params: HornParams` (dataclass)
- `_chamber_params: ChamberParams`
- `_port_params: PortParams`
- `_driver: Optional[DriverModel]`
- `_assembly: Optional[Assembly]` (built from blocks)
- `_horn_block`, `_chamber_block`, `_port_block`, `_driver_block`

Emits signals:
```python
horn_params_changed = pyqtSignal()
chamber_params_changed = pyqtSignal()
driver_changed = pyqtSignal(object)  # DriverModel
assembly_changed = pyqtSignal()
rebuild_started = pyqtSignal()
validation_failed = pyqtSignal(str)
```

API:
```python
model.set_driver(driver)
model.update_horn_params(cutoff_frequency=50.0, fold=1)
model.set_geometry_type(GEOMETRY_FOLDED)
model.rebuild()  # builds blocks + emits assembly_changed
```

### Views: GUI panels

Read from model on signal, write to model via setters/updaters. **Never** mutate model state directly via attribute access.

```python
class InputPanel(QWidget):
    def __init__(self, model: AssemblyModel, parent=None):
        super().__init__(parent)
        self._model = model
        self._build_ui()
        self._connect_signals()

    def _connect_signals(self):
        # widget → model
        self._fc_spin.valueChanged.connect(self._sync_model_state)
        # model → widget
        self._model.horn_params_changed.connect(self._refresh_from_model)

    def _sync_model_state(self):
        self._model.update_horn_params(
            cutoff_frequency=self._fc_spin.value(),
            fold=self._fold_combo.currentData(),
            ...
        )

    def _refresh_from_model(self):
        with self._block_signals():
            self._fc_spin.setValue(self._model.horn_params.cutoff_frequency)
            ...
```

## Critical Pattern: Signal Loop Prevention

When you set a widget value programmatically, it emits `valueChanged` → triggers `_sync_model_state` → updates model → emits `horn_params_changed` → calls `_refresh_from_model` → sets widget value → loop.

Solution — `blockSignals()`:
```python
@contextmanager
def _block_signals(self):
    blockers = [QSignalBlocker(w) for w in self._all_widgets]
    try:
        yield
    finally:
        del blockers  # restore on exit
```

OR use the `QSignalBlocker` RAII pattern directly.

## Dataclass Parameters

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class HornParams:
    cutoff_frequency: float = 50.0
    expansion: str = "hypex"
    hypex_T: float = 0.7
    fold: int = 0
    n_sections: int = 12
    section_shape: str = "rectangular"
    mouth_width: Optional[float] = None
    mouth_height: Optional[float] = None
    mouth_aspect_ratio: Optional[float] = None
```

`update_horn_params(**kwargs)` does:
```python
def update_horn_params(self, **kwargs):
    changed = False
    for k, v in kwargs.items():
        if hasattr(self._horn_params, k):
            old = getattr(self._horn_params, k)
            if old != v:
                setattr(self._horn_params, k, v)
                changed = True
    if changed:
        self.horn_params_changed.emit()
```

## Validation Flow

User clicks "Calcola" → `_on_calculate` → `model.rebuild()`:
1. `rebuild_started` signal
2. Try to build HornBlock from params (may raise)
3. If raise: emit `validation_failed(str(exc))`, reset blocks, emit `assembly_changed` (with empty)
4. If success: build chamber/port/driver blocks, assemble, emit `assembly_changed`

InputPanel listens to `validation_failed` and shows a status bar / message box.

## Naming Conventions

- Private attributes: `_horn_params`, `_fc_spin`, `_model`
- Slot methods: `_on_xxx_changed`, `_sync_model_state`, `_refresh_from_model`
- Public API: `model.driver`, `model.horn_params`, `model.update_horn_params(...)`
- Signals: `<noun>_<verb>` past tense, e.g. `horn_params_changed`, `driver_changed`

## Constants

In `assembly_model.py`:
```python
GEOMETRY_STRAIGHT = "straight"
GEOMETRY_FOLDED = "folded"
GEOMETRY_DOUBLE_FOLDED = "double_folded"

EXPANSION_HYPEX = "hypex"
EXPANSION_EXPONENTIAL = "exponential"
EXPANSION_CONICAL = "conical"
EXPANSION_TRACTRIX = "tractrix"
```

`set_geometry_type(geom)` maps `GEOMETRY_*` → `fold` int via `fold_map`.

## Common Bugs

| Symptom | Cause | Fix |
|---|---|---|
| Widget edit doesn't trigger rebuild | `valueChanged` not connected to `_sync_model_state` | Add connection in `_connect_signals` |
| Infinite update loop | Signal feedback | Use `QSignalBlocker` in `_refresh_from_model` |
| Model emits signal but view stale | View not connected | Connect in InputPanel.__init__ |
| Ctrl+Z (undo) not supported | No QUndoStack | Out of scope for now |
| Assembly None after rebuild | Driver not set yet | Check `model.driver is None` before render |

## File Locations

```
btk-speaker-designer/gui/
├── main_window.py        # QMainWindow, hosts panels + viewport
├── input_panel.py        # Driver + acoustic params widgets
├── design_panel.py       # Geometry / dimensions widgets
├── driver_selector.py    # Database picker
├── speaker_type_selector.py
├── viewport_widget.py    # 3D PyVista viewport
├── analysis_tabs.py      # Frequency/SPL/impedance plots
├── horn_view.py          # 2D horn cross-section view
├── horn_designer.py      # Horn-specific design widget
└── assembly_model.py     # AssemblyModel (THE model)
```

## References

- Qt for Python (PyQt5): https://doc.qt.io/qtforpython-5/
- Model/View Programming: https://doc.qt.io/qt-5/model-view-programming.html
- Signals & Slots: https://doc.qt.io/qt-5/signalsandslots.html
