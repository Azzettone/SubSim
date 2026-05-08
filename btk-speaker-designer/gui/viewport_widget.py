"""
Viewport3DWidget — widget Qt che embeds un QtInteractor pyvista.

Visualizza in real-time i solidi 3D dell'AssemblyModel:
- Cavità acustica tromba (rosso)
- Pannelli costruttivi tromba (rosso 30% opacity)
- Cavità cabinet (grigio)
- Porta bass-reflex (verde acqua)
- Driver (giallo)

La vista si aggiorna automaticamente connettendo il signal
``AssemblyModel.solids_rebuilt`` allo slot ``update_from_solids()``.

Toolbar integrata (QToolBar):
  Reset view · Iso · Front · Top · Side · ── · Wireframe ·
  Screenshot · Export STEP · Export STL

Nota sull'headless (Codespace):
  Qt xcb richiede DISPLAY impostato o plugin ``offscreen``.
  La classe gestisce il caso automaticamente tramite _ensure_display()
  (riusa il meccanismo di geometry/viewport.py).
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
import time
import warnings
from typing import Any, Dict, Optional, Union

try:
    from PyQt5.QtCore import Qt, pyqtSignal as Signal
    from PyQt5.QtWidgets import (
        QAction,
        QFileDialog,
        QLabel,
        QMessageBox,
        QSizePolicy,
        QToolBar,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    from PySide6.QtCore import Qt, Signal                     # type: ignore
    from PySide6.QtWidgets import (                           # type: ignore
        QAction,
        QFileDialog,
        QLabel,
        QMessageBox,
        QSizePolicy,
        QToolBar,
        QVBoxLayout,
        QWidget,
    )

# ---------------------------------------------------------------------------
# Colori (consistenti con geometry/viewport.py)
# ---------------------------------------------------------------------------
_COLORS: Dict[str, str] = {
    "horn_cavity":    "#E94F37",
    "horn_walls":     "#E94F37",
    "chamber_inner":  "#6B7B8D",
    "chamber_shell":  "#393E41",
    "port":           "#44BBA4",
    "driver":         "#F6AE2D",
}
_OPACITY: Dict[str, float] = {
    "horn_cavity":    0.75,
    "horn_walls":     0.20,
    "chamber_inner":  0.35,
    "chamber_shell":  0.15,
    "port":           0.90,
    "driver":         0.90,
}
_DEFAULT_COLOR = "#8BBDDA"

# ---------------------------------------------------------------------------
# Xvfb helper (condiviso con geometry/viewport.py — ma senza import circ.)
# ---------------------------------------------------------------------------
_xvfb_proc: Optional[subprocess.Popen] = None


def _ensure_display() -> None:
    """Avvia Xvfb su :99 se DISPLAY non è impostato."""
    global _xvfb_proc
    if os.environ.get("DISPLAY", "").strip():
        return
    if _xvfb_proc is not None and _xvfb_proc.poll() is None:
        return
    try:
        _xvfb_proc = subprocess.Popen(
            ["Xvfb", ":99", "-screen", "0", "1024x768x24"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        os.environ["DISPLAY"] = ":99"
        time.sleep(0.4)
    except FileNotFoundError:
        pass   # Nessun Xvfb disponibile, continua comunque


# ---------------------------------------------------------------------------
# Widget wrapper con fallback
# ---------------------------------------------------------------------------
def _make_interactor_class():
    """Ritorna la classe da usare per la vista 3D embed.
    
    Tenta di importare QtInteractor (pyvistaqt); in caso di fallimento
    (headless totale, pyvistaqt non installato, ecc.) ritorna
    _FallbackLabel che mostra un placeholder testuale.
    """
    try:
        from pyvistaqt import QtInteractor as _QTI
        return _QTI, True
    except ImportError:
        return None, False


class _FallbackLabel(QLabel):
    """Placeholder quando pyvistaqt non è disponibile."""
    def __init__(self, parent=None):
        super().__init__(
            "⚠ pyvistaqt non disponibile.\n"
            "Installa con: pip install pyvistaqt",
            parent,
        )
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("color: #FFAA00; background: #1A1A2E; font-size: 13px;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


class Viewport3DWidget(QWidget):
    """
    Widget che embeds un QtInteractor pyvista nella GUI principale.

    Signals:
        solid_clicked(str): nome del solido cliccato (future use)
    """

    solid_clicked = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        _ensure_display()
        self._plotter = None
        self._has_pyvistaqt = False
        self._solids: Dict[str, Any] = {}
        self._wireframe_mode = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar ──────────────────────────────────────────────────────
        self._toolbar = self._build_toolbar()
        layout.addWidget(self._toolbar)

        # Vista 3D (QtInteractor o fallback) ───────────────────────────
        InteractorClass, ok = _make_interactor_class()
        if ok:
            try:
                self._plotter = InteractorClass(self)
                self._plotter.set_background("#1A1A2E")
                self._plotter.add_axes(interactive=False)
                self._has_pyvistaqt = True
                layout.addWidget(self._plotter.interactor)
            except Exception as exc:
                warnings.warn(f"Viewport3DWidget: QtInteractor fallito ({exc}). "
                              "Uso placeholder.", stacklevel=2)
                layout.addWidget(_FallbackLabel(self))
        else:
            layout.addWidget(_FallbackLabel(self))

    # ------------------------------------------------------------------ build toolbar
    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar(self)
        tb.setMovable(False)
        tb.setStyleSheet(
            "QToolBar { background:#12121E; border:none; spacing:4px; }"
            "QToolButton { color:#C0C0E0; background:transparent; border-radius:3px; "
            "padding:3px 6px; font-size:12px; }"
            "QToolButton:hover { background:#2A2A3E; }"
            "QToolButton:pressed { background:#3A3A5E; }"
        )

        def _act(label: str, slot, shortcut: str = "") -> QAction:
            a = QAction(label, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(shortcut)
            return a

        tb.addAction(_act("⟳ Reset", self.reset_view, "R"))
        tb.addSeparator()
        tb.addAction(_act("Iso", self.view_isometric))
        tb.addAction(_act("Front", self.view_front))
        tb.addAction(_act("Top", self.view_top))
        tb.addAction(_act("Side", self.view_side))
        tb.addSeparator()
        tb.addAction(_act("◫ Wire", self.toggle_wireframe))
        tb.addSeparator()
        tb.addAction(_act("📷 Screenshot", self.save_screenshot))
        tb.addAction(_act("↓ STEP", self.export_step))
        tb.addAction(_act("↓ STL", self.export_stl))
        return tb

    # ------------------------------------------------------------------ public slots
    def update_from_solids(self, solids: Dict[str, Any]) -> None:
        """
        Slot principale: aggiorna la vista con il dizionario di solidi 3D.

        Args:
            solids: {name: build123d Solid} — da AssemblyModel.solids_rebuilt
        """
        # Diagnostica: stampa sempre, anche se il viewport non è disponibile.
        try:
            keys = list(solids.keys()) if solids else []
            non_none = [k for k, v in (solids or {}).items() if v is not None]
            print(f"[Viewport3D] update_from_solids: keys={keys} non_none={non_none} "
                  f"pyvista_ok={self._has_pyvistaqt} plotter={self._plotter is not None}")
        except Exception as e:
            print(f"[Viewport3D] update_from_solids print failed: {e}")
        if not self._has_pyvistaqt or self._plotter is None:
            return
        self._solids = dict(solids)
        self._render_solids()

    def update_from_model(self, model) -> None:
        """Alternativa quando si passa direttamente l'AssemblyModel."""
        self.update_from_solids(model.solids)

    def clear(self) -> None:
        """Rimuove tutti i mesh dalla scena."""
        if self._plotter is not None:
            self._plotter.clear()
            self._plotter.add_axes(interactive=False)
            self._plotter.render()
        self._solids = {}

    # ------------------------------------------------------------------ view controls
    def reset_view(self) -> None:
        if self._plotter:
            self._plotter.reset_camera()
            self._plotter.render()

    def view_isometric(self) -> None:
        if self._plotter:
            self._plotter.view_isometric()
            self._plotter.render()

    def view_front(self) -> None:
        if self._plotter:
            self._plotter.view_yz()
            self._plotter.render()

    def view_top(self) -> None:
        if self._plotter:
            self._plotter.view_xz()
            self._plotter.render()

    def view_side(self) -> None:
        if self._plotter:
            self._plotter.view_xy()
            self._plotter.render()

    def toggle_wireframe(self) -> None:
        if not self._plotter:
            return
        self._wireframe_mode = not self._wireframe_mode
        self._render_solids()

    # ------------------------------------------------------------------ export actions
    def save_screenshot(self) -> None:
        if not self._plotter:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Salva Screenshot", "", "PNG (*.png)"
        )
        if path:
            if not path.lower().endswith(".png"):
                path += ".png"
            self._plotter.screenshot(path)

    def export_step(self) -> None:
        self._export("STEP (*.step *.stp)", ".step", "step")

    def export_stl(self) -> None:
        self._export("STL (*.stl)", ".stl", "stl")

    def _export(self, filt: str, ext: str, fmt: str) -> None:
        from btk_speaker_designer.geometry import (
            PanelGeometryError,
            export_step,
            export_stl,
        )
        try:
            import build123d as bd
        except ImportError:
            QMessageBox.warning(self, "Export", "build123d non installato.")
            return

        if not self._solids:
            QMessageBox.information(self, "Export", "Nessun solido da esportare.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Esporta", "", filt)
        if not path:
            return
        if not path.lower().endswith(ext):
            path += ext

        # Raggruppa tutti i solidi in un Compound
        try:
            compound = bd.Compound(children=list(self._solids.values()))
            if fmt == "step":
                export_step(compound, path)
            else:
                export_stl(compound, path)
        except Exception as exc:
            QMessageBox.critical(self, "Export fallito", str(exc))

    # ------------------------------------------------------------------ internal
    def _render_solids(self) -> None:
        """Pulisce la scena e riaggiunge tutti i solidi in cache."""
        if not self._plotter:
            return
        self._plotter.clear()
        self._plotter.add_axes(interactive=False)

        n_added = 0
        all_bounds = []
        for name, solid in self._solids.items():
            if solid is None:
                continue
            mesh = self._solid_to_mesh(solid)
            if mesh is None or mesh.n_points == 0:
                print(f"[Viewport3D]   - skip {name!r}: mesh None or empty")
                continue
            print(f"[Viewport3D]   + add {name!r}: pts={mesh.n_points} "
                  f"bounds={tuple(round(b,3) for b in mesh.bounds)}")
            color = _COLORS.get(name, _DEFAULT_COLOR)
            opacity = _OPACITY.get(name, 0.8)
            style = "wireframe" if self._wireframe_mode else "surface"
            self._plotter.add_mesh(
                mesh,
                color=color,
                opacity=opacity,
                style=style,
                show_edges=self._wireframe_mode,
                label=name,
            )
            all_bounds.append(mesh.bounds)
            n_added += 1

        # Grid di riferimento e ruler con dimensioni in mm
        if n_added > 0:
            self._add_floor_grid(all_bounds)
            # show_bounds: ruler attorno alla scena con etichette in mm
            try:
                self._plotter.show_bounds(
                    grid=False,
                    ticks="outside",
                    minor_ticks=False,
                    xlabel="X (mm)",
                    ylabel="Y (mm)",
                    ztitle="Z (mm)",
                    padding=0.05,
                    color="#666688",
                    font_size=10,
                    fmt="%.0f",
                )
            except Exception:
                pass  # show_bounds è opzionale — non blocca il render
            self._plotter.reset_camera()
            self._plotter.view_isometric()
        else:
            print("[Viewport3D] _render_solids: NESSUN solido aggiunto alla scena")
        self._plotter.render()

    def _add_floor_grid(self, all_bounds) -> None:
        """Aggiunge una griglia di pavimento per riferimento visivo in mm."""
        try:
            import pyvista as pv
            import numpy as np
            # Estende i bounds totali della scena
            xs = [b[0] for b in all_bounds] + [b[1] for b in all_bounds]
            ys = [b[2] for b in all_bounds] + [b[3] for b in all_bounds]
            zs = [b[4] for b in all_bounds] + [b[5] for b in all_bounds]
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
            z_floor = min(zs)

            span = max(xmax - xmin, ymax - ymin, 1.0)
            pad = span * 0.15
            x0, x1 = xmin - pad, xmax + pad
            y0, y1 = ymin - pad, ymax + pad

            # Griglia: line spacing = 100 mm (10 cm)
            spacing = max(100.0, round(span / 15 / 100) * 100)
            # Linee parallele a Y (costante X)
            x_ticks = np.arange(
                round(x0 / spacing) * spacing,
                x1 + spacing,
                spacing
            )
            y_ticks = np.arange(
                round(y0 / spacing) * spacing,
                y1 + spacing,
                spacing
            )
            lines = []
            for x in x_ticks:
                lines += [[x, y0, z_floor], [x, y1, z_floor]]
            for y in y_ticks:
                lines += [[x0, y, z_floor], [x1, y, z_floor]]
            if lines:
                pts = np.array(lines, dtype=float)
                n_lines = len(pts) // 2
                cells = np.column_stack([
                    np.full(n_lines, 2),
                    np.arange(0, 2 * n_lines, 2),
                    np.arange(1, 2 * n_lines + 1, 2),
                ]).ravel()
                grid = pv.PolyData()
                grid.points = pts
                grid.lines = cells
                self._plotter.add_mesh(
                    grid, color="#2A2A4A", line_width=1, opacity=0.6,
                    render_lines_as_tubes=False,
                )
        except Exception:
            pass  # griglia opzionale

    def _solid_to_mesh(self, solid):
        """Converte solid build123d → pyvista PolyData via STL temporaneo.

        I solidi sono in metri ma vengono scalati a mm per l'export STL
        (tolleranza tessellazione è in mm). Pyvista poi li riscala
        visivamente: l'unità visualizzata sarà mm.
        """
        try:
            import pyvista as pv
            from btk_speaker_designer.geometry import export_stl as _exp_stl

            with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
                tmp = f.name
            try:
                _exp_stl(solid, tmp, scale_to_mm=True)
                mesh = pv.read(tmp)
                return mesh
            finally:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        except Exception as exc:
            import traceback
            print(f"[Viewport3D] _solid_to_mesh FAILED: {exc}")
            traceback.print_exc()
            warnings.warn(f"Viewport3DWidget: mesh conversion failed for solid: {exc}",
                          stacklevel=2)
            return None

    def screenshot(self, path: Union[str, pathlib.Path, None] = None) -> Optional[str]:
        """
        Salva screenshot headless (per test o export automati).
        Se path=None usa un file temp e restituisce il percorso.
        """
        if not self._plotter:
            return None
        if path is None:
            path = pathlib.Path(tempfile.mktemp(suffix=".png"))
        self._plotter.screenshot(str(path))
        return str(path)

    def closeEvent(self, event) -> None:
        if self._plotter is not None:
            try:
                self._plotter.close()
            except Exception:
                pass
        super().closeEvent(event)
