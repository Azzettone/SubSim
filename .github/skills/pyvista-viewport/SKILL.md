---
name: pyvista-viewport
description: 'PyVista + pyvistaqt for 3D viewport visualization in PyQt5. Use when: integrating 3D viewport in GUI, debugging empty viewport, configuring camera (reset_camera, view_isometric, view_xy), grid/ruler/axes (show_bounds, show_grid, add_axes), mesh styling (color, opacity, show_edges, wireframe), screenshot capture, headless testing with Xvfb. Covers scale_to_mm convention, plotter lifecycle, signal-slot integration with AssemblyModel.'
---

# PyVista 3D Viewport

3D visualization library used in BTK Speaker Designer for the embedded 3D viewport.

## Stack

- **PyVista** — high-level VTK wrapper
- **pyvistaqt** — Qt integration (QtInteractor widget)
- **VTK** — rendering backend
- **Xvfb** — headless display in dev container / CI

## When to Use

- Editing `gui/viewport_widget.py`
- Debugging empty viewport, missing camera framing, missing grid
- Adding new view modes, screenshot, export
- Writing tests that exercise the viewport (with Xvfb)

## Embedding in PyQt5

```python
from pyvistaqt import QtInteractor

class Viewport3D(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._plotter = QtInteractor(self)
        layout.addWidget(self._plotter.interactor)

    def add_solid(self, mesh, color="lightgray", opacity=1.0):
        actor = self._plotter.add_mesh(
            mesh, color=color, opacity=opacity,
            show_edges=False, smooth_shading=True,
        )
        return actor

    def render(self):
        self._plotter.reset_camera()
        self._plotter.view_isometric()
        self._plotter.render()
```

## Critical: Camera Framing

After adding meshes, **always**:
```python
plotter.reset_camera()    # frame to bounds
plotter.view_isometric()  # apply standard view
```

Without `reset_camera()`, camera stays at default origin → meshes outside frustum → empty viewport.

## Grid + Ruler

```python
def _add_floor_grid(self, z_min: float, extent_mm: float = 2000.0):
    """Reference grid at z_min, spacing 100 mm."""
    grid = pv.Plane(
        center=(0, 0, z_min),
        direction=(0, 0, 1),
        i_size=extent_mm, j_size=extent_mm,
        i_resolution=20, j_resolution=20,
    )
    self._plotter.add_mesh(
        grid, style="wireframe", color="gray", opacity=0.3,
    )

def _add_ruler(self):
    self._plotter.show_bounds(
        grid="back",
        location="outer",
        ticks="both",
        xtitle="X [mm]",
        ytitle="Y [mm]",
        ztitle="Z [mm]",
        font_size=10,
    )
```

Note: `xlabel`/`ylabel`/`zlabel` are deprecated — use `xtitle`/`ytitle`/`ztitle`.

## Mesh Styling Conventions (BTK)

| Block | Color | Opacity | Edges |
|---|---|---|---|
| HornBlock | red | 1.0 | False |
| ChamberBlock | gray | 0.6 | True |
| DriverBlock | orange | 1.0 | False |
| PortBlock | yellow | 0.8 | False |
| Panel (internal) | tan | 0.4 | True |

## Scale Convention (mm vs m)

build123d works in meters; viewport uses **mm** for human-readable rulers. Always tessellate with `scale_to_mm=True`:

```python
mesh = solid_to_pyvista_mesh(solid, scale_to_mm=True)
```

Camera distances and grid extents in mm too:
```python
self._plotter.camera.position = (2000, 1500, 1500)  # 2 m / 1.5 m / 1.5 m
```

## Screenshot (headless OK)

```python
def screenshot(self, path: Optional[str] = None) -> Optional[str]:
    img = self._plotter.screenshot(filename=path, return_img=True)
    if path is None:
        # return base64 string for embedding
        import base64, io
        from PIL import Image
        buf = io.BytesIO()
        Image.fromarray(img).save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    return path
```

## Headless Testing (Xvfb)

In `tests/conftest.py`:
```python
import os, pytest
@pytest.fixture(autouse=True, scope="session")
def _xvfb():
    if "DISPLAY" not in os.environ:
        os.environ["DISPLAY"] = ":99"
        os.system("Xvfb :99 -screen 0 1024x768x24 &")
```

In dev container: Xvfb is already running.

## Signal-Slot Integration with AssemblyModel

```python
class Viewport3D(QWidget):
    def connect_model(self, model: AssemblyModel):
        model.assembly_changed.connect(self._on_assembly_changed)

    def _on_assembly_changed(self):
        solids = self._collect_solids(model.assembly)
        self._render_solids(solids)

    def _render_solids(self, solids):
        self._plotter.clear()
        z_min = float("inf")
        for name, solid, style in solids:
            mesh = solid_to_pyvista_mesh(solid)
            self._plotter.add_mesh(mesh, **style)
            z_min = min(z_min, mesh.bounds[4])
        self._add_floor_grid(z_min)
        self._add_ruler()
        self._plotter.reset_camera()
        self._plotter.view_isometric()
        self._plotter.render()
```

## Common Errors

| Symptom | Cause | Fix |
|---|---|---|
| Empty viewport, no error | Camera not framed | Add `reset_camera()` |
| Empty viewport, no meshes added | build123d not installed | `pip install build123d` |
| Tiny meshes (look like dot) | mm vs m mismatch | `scale_to_mm=True` |
| Crash on PyQt5 event loop close | Plotter not closed | `self._plotter.close()` in `closeEvent` |
| Grid / ruler not visible | Behind opaque mesh | Use `opacity` < 1 or render order |
| `xlabel deprecated` warning | New PyVista API | Use `xtitle` instead |

## References

- PyVista docs: https://docs.pyvista.org
- pyvistaqt: https://qtdocs.pyvista.org
- VTK Python: https://docs.vtk.org/en/latest/

## Related Project Files

- `btk-speaker-designer/gui/viewport_widget.py`
- `btk-speaker-designer/tests/test_viewport_widget.py`
