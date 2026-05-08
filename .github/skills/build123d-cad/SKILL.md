---
name: build123d-cad
description: 'build123d Python CAD library for 3D solid modeling with OpenCascade backend. Use when: creating Solid/Part objects, lofting horn sections, extruding panels, boolean ops (fuse/cut), exporting STEP/STL/DXF, debugging build123d Algebra mode (Part + Box + ...) vs Builder mode (with BuildPart()). Covers Sketch (Polyline, Rectangle, Circle), Plane, Location, Axis, units (Pa: build123d uses meters internally → convert mm). Used heavily in btk-speaker-designer/blocks/ and gui/viewport_widget.py.'
---

# build123d CAD Library

`build123d` is a Python OpenCascade CAD library. Used in BTK Speaker Designer to generate 3D solids from acoustic block geometry, then tessellate to mesh for the PyVista viewport and export to STEP/STL.

## When to Use

- Building solids in `blocks/` modules (HornBlock, ChamberBlock, PortBlock, DriverBlock)
- Implementing exporters in `exporters/` (STEP, STL, DXF panel cutlist)
- Debugging mesh generation, broken tessellation, viewport rendering empty
- Boolean operations (carve out internal volumes, drill driver cutout)

## Two API Modes

### 1. Algebra Mode (preferred in this project)

Operators on objects directly:

```python
from build123d import Part, Box, Cylinder, Location, Plane

# Create a box
cabinet = Part() + Box(0.6, 0.5, 0.7)  # width, height, depth in METERS

# Subtract a cylinder
hole = Cylinder(radius=0.05, height=0.5)
hole = Plane.YZ * hole  # rotate to face X
cabinet = cabinet - hole.locate(Location((0.3, 0, 0)))
```

Key operators:
- `+` fuse / union
- `-` cut / subtract
- `&` intersect
- `*` apply Location/Plane to object

### 2. Builder Mode (context manager)

```python
from build123d import BuildPart, Box, Cylinder

with BuildPart() as bp:
    Box(0.6, 0.5, 0.7)
    with Locations((0.3, 0, 0)):
        Cylinder(radius=0.05, height=0.5, mode=Mode.SUBTRACT)
result = bp.part
```

We **prefer Algebra mode** in BTK — composes better with `from_acoustics` factory pattern.

## Units

build123d uses **meters** internally for spatial dimensions and **radians** for angles. Always pass SI units:

```python
# WRONG — mm interpreted as meters
Box(600, 500, 700)  # creates a 600 m × 500 m × 700 m box!

# CORRECT
Box(0.6, 0.5, 0.7)  # 600 mm × 500 mm × 700 mm
```

For STL export, the viewport scales mm→m or m→mm explicitly (see `viewport_widget._solid_to_mesh(scale_to_mm=True)`).

## Lofting Horn Sections

```python
from build123d import Part, Polygon, Plane, loft

sections = []
for sec in horn_block.sections:
    pts = [(v[0], v[1]) for v in sec.vertices_local_2d]  # 2D in section plane
    poly = Plane(origin=sec.center, z_dir=sec.normal) * Polygon(*pts)
    sections.append(poly)

horn_solid = Part() + loft(sections)
```

Caveats:
- Sections must have **same vertex count** (4 for rectangular).
- Sections must be **ordered consistently** (all CCW from same viewpoint).
- A fold (normal flips by 180°) breaks loft → split into groups, loft each, then fuse.

## Fold Loft Pattern

```python
groups = []
current = [sections[0]]
for i in range(1, len(sections)):
    if np.dot(sections[i-1].normal, sections[i].normal) < 0:
        groups.append(current)
        current = [sections[i-1], sections[i]]  # share boundary
    else:
        current.append(sections[i])
groups.append(current)

solids = [loft(g) for g in groups if len(g) >= 2]
horn = sum(solids[1:], solids[0])  # fuse all
```

## Common Operations

```python
# Translate (in meters)
obj.locate(Location((0.1, 0, 0)))

# Rotate
from build123d import Axis, Rot
Rot(0, 0, 90) * obj  # 90° around Z

# Drill hole through baffle
baffle = Box(0.6, 0.5, 0.018)
driver_cut = Cylinder(radius=0.18, height=0.05)
baffle = baffle - driver_cut
```

## Tessellation for PyVista

```python
def solid_to_pyvista_mesh(solid, scale_to_mm: bool = True):
    """build123d Part → pyvista PolyData."""
    import pyvista as pv
    import numpy as np
    vertices, triangles = solid.tessellate(tolerance=0.001)
    verts = np.array([(v.X, v.Y, v.Z) for v in vertices])
    if scale_to_mm:
        verts *= 1000.0
    faces = np.column_stack([
        np.full(len(triangles), 3),
        triangles,
    ]).flatten()
    return pv.PolyData(verts, faces)
```

## Export

```python
from build123d import export_step, export_stl

export_step(solid, "horn.step")
export_stl(solid, "horn.stl", tolerance=0.001, angular_tolerance=0.1)
```

DXF (2D panel cutlist) requires sketch projection:
```python
from build123d import export_dxf
sketch = solid.faces().filter_by(Plane.XY).first  # bottom face
export_dxf(sketch, "panel.dxf")
```

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| `Empty solid after loft` | Sections not coplanar with their normal | Check `Plane(z_dir=normal)` |
| `boolean op failed` | OCCT tolerance | Increase tolerance in `solid.tessellate()` or repair: `solid.fix()` |
| Empty viewport | mm/m unit mismatch | Use `scale_to_mm=True` consistently |
| `numpy.dot` non si esegue | Section normals are np.float32 | Cast to float64 |

## Installation

build123d on Mac/Linux:
```bash
pip install build123d  # ≥ 0.10.0 needed for current BTK
```

On Windows: requires VC++ Build Tools. Use `pip install build123d --prefer-binary`.

In dev container: already in `requirements.txt`.

## References

- Official docs: https://build123d.readthedocs.io
- GitHub: https://github.com/gumyr/build123d
- OpenCascade docs (underlying engine): https://dev.opencascade.org

## Related Project Files

- `btk-speaker-designer/blocks/horn_block.py` (`to_solid()` method)
- `btk-speaker-designer/blocks/chamber_block.py`, `port_block.py`
- `btk-speaker-designer/gui/viewport_widget.py` (`_solid_to_mesh`)
- `btk-speaker-designer/exporters/dxf_export.py`
