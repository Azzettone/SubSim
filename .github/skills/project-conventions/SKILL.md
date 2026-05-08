---
name: project-conventions
description: 'BTK Speaker Designer + SubSim project-specific conventions: directory layout, dataclass-based block model, AssemblyModel pattern, naming (HornBlock/ChamberBlock/PortBlock/DriverBlock), units (SI internal, mm display), test layout, dev container setup, git workflow with conventional commits. Use when: orienting in the codebase, deciding where new code goes, following existing patterns, writing tests.'
---

# Project Conventions

This workspace contains TWO related projects:

1. **BTK Speaker Designer** (`btk-speaker-designer/`) — horn / cabinet design tool with 3D CAD output
2. **SubSim** (root + `shared/`) — wall-mounted subwoofer simulator (still in scaffolding phase)

Shared modules live in `shared/`.

## Repository Layout

```
SubSim/
├── btk-speaker-designer/        # Main current development
│   ├── main.py
│   ├── core/                    # acoustic engine, geometry, simulation
│   ├── blocks/                  # HornBlock, ChamberBlock, PortBlock, DriverBlock, Assembly
│   ├── database/                # JSON drivers, horns; SQLite schema
│   ├── exporters/               # DXF, STEP, PDF panel cutlist
│   ├── gui/                     # PyQt5 widgets + AssemblyModel
│   └── tests/                   # pytest, 255+ tests
├── shared/                      # cross-project: acoustic_core, fluid_acoustics, ui_components
├── uploads/                     # design notes (FLUIDODINAMICA_DESIGN_ACUSTICO.md)
├── .github/
│   ├── copilot-instructions.md
│   ├── agents/                  # subsim-dev, btkspeaker-dev
│   └── skills/                  # this folder
└── conftest.py                  # pytest root config
```

## Block Model Pattern

Every physical sub-component is a `Block`:

```python
@dataclass
class Block:
    origin: np.ndarray  # (3,) world position in METERS
    panel_thickness: float = 0.018  # 18 mm default

    @property
    def panels(self) -> List[Panel]: ...
    @property
    def ports(self) -> Dict[str, ConnectionPort]: ...
    def to_solid(self) -> "build123d.Part": ...
    @property
    def bounding_box(self) -> Tuple[float, float, float]: ...
```

Specialized: `HornBlock`, `ChamberBlock`, `PortBlock`, `DriverBlock`.

**Constructor pattern**: `__init__` is low-level (give me w, h, depth, etc.). Factory `from_acoustics(...)` is high-level (give me Fc, Vas, expansion type → I compute geometry).

```python
horn = HornBlock.from_acoustics(
    driver=driver, cutoff_frequency=50.0,
    expansion="hypex", fold=1,
)
chamber = ChamberBlock.from_dimensions(
    width=0.6, height=0.5, depth=0.5, panel_thickness=0.018,
)
```

## Coordinate Convention

- **Origin** at horn throat; horn extends along $+\hat{z}$
- **Y up** (cabinet height)
- **X width** (cabinet width)
- **Chamber** behind throat: $z \in [-D, 0]$, origin at $(0, -H/2, -D)$
- **Driver** at throat: position `(0, 0, -50mm)` in chamber
- **Units**: meters internally (SI), mm only for viewport display & export

## Dataclass Parameters

User-editable params live as `@dataclass` in `assembly_model.py`:

```python
@dataclass
class HornParams:
    cutoff_frequency: float = 50.0
    expansion: str = "hypex"
    fold: int = 0
    ...

@dataclass
class ChamberParams:
    enabled: bool = True
    width: float = 0.6
    height: float = 0.5
    depth: float = 0.5
    panel_thickness: float = 0.018
    shape: str = "rectangular"
    rear_width: Optional[float] = None
```

## Testing

- **Framework**: pytest
- **Coverage target**: 80% minimum
- **Test layout**: mirrors source — `tests/test_<module>.py`
- **Fixtures**: in `tests/conftest.py`, e.g. `driver_18` (18" reference driver)
- **Headless GUI**: Xvfb auto-started in dev container

Run all:
```bash
python -m pytest btk-speaker-designer/tests/ -q
```

Run subset:
```bash
python -m pytest btk-speaker-designer/tests/test_horn_block.py -v -k fold
```

## Dev Environment

- Python 3.12 venv at `/workspaces/SubSim/.venv/`
- Activate: handled by VS Code Python extension automatically
- Install: `pip install -r btk-speaker-designer/requirements.txt`
- Key deps: `numpy`, `scipy`, `matplotlib`, `PyQt5`, `pyvista`, `pyvistaqt`, `build123d`, `pytest`

## Git Workflow

- Default branch: `main`
- Conventional commits format:
  - `feat(scope): ...` new feature
  - `fix(scope): ...` bug fix
  - `refactor(scope): ...` non-behavior change
  - `test(scope): ...` test additions
  - `docs(scope): ...` docs only
- Scope examples: `blocks`, `gui`, `core`, `acoustics`, `viewport`
- Multi-line bodies welcome with bullet points for changes
- Push immediately after green tests

## Code Style

- **Black**-compatible 88 char line, but in practice 100 is OK
- **Type hints** required on all public functions and dataclasses
- **Docstrings** in Italian for user-facing, English allowed for internal helpers
- **Comments referencing acoustic formulas** must include source: `# Beranek Eq. 5.32`
- **PEP 8** otherwise

## Communication

- Replies to user: **always Italian**
- Variable names / docstrings: Italian for domain terms (gola=throat, bocca=mouth, camera=chamber, paratia=baffle), English for tech terms (loft, mesh, signal, slot).

## Subagents Available

- `btkspeaker-dev` — BTK-specific
- `subsim-dev` — SubSim-specific
- `Explore` — read-only codebase Q&A

Invoke via `runSubagent` tool when needed for parallel exploration.

## When Adding New Code

1. **Acoustic formula** → goes in `core/` (BTK) or `shared/acoustic_core.py` (cross-project)
2. **Geometry block** → goes in `blocks/`, with both `__init__` and `from_acoustics` factories
3. **GUI widget** → goes in `gui/`, follows MVC pattern (see `pyqt-mvc-architecture` skill)
4. **3D solid generation** → use build123d (see `build123d-cad` skill)
5. **Visualization** → PyVista in viewport, Matplotlib in analysis tabs
6. **Test** → mirror source structure, use existing fixtures

## When Debugging

1. Check git status / branch
2. Run tests locally first (`pytest -x -q`)
3. Look at `print` debug output in `_on_calculate`, `update_from_solids`, `_render_solids`
4. For viewport empty: verify build123d is installed, scale_to_mm, reset_camera
5. For acoustic-result-wrong: check units (Hz vs rad/s, m vs mm, m² vs cm²)

## Reference Files in Workspace

- `uploads/FLUIDODINAMICA_DESIGN_ACUSTICO.md` — internal fluid dynamics notes
- `UPLOADS/HORN CALCULATOR - *.csv` — reference horn calculator data (Acutek)
- `.github/copilot-instructions.md` — SubSim agent prompt (high-level)
