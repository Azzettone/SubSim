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

        for name, solid in self._solids.items():
            if solid is None:
                continue
            mesh = self._solid_to_mesh(solid)
            if mesh is None:
                continue
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

        self._plotter.render()

    def _solid_to_mesh(self, solid):
        """Converte solid build123d → pyvista PolyData via STL temporaneo."""
        try:
            import pyvista as pv
            from btk_speaker_designer.geometry import export_stl as _exp_stl

            with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
                tmp = f.name
            try:
                _exp_stl(solid, tmp, scale_to_mm=False)
                return pv.read(tmp)
            finally:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        except Exception as exc:
            warnings.warn(f"Viewport3DWidget: mesh conversion failed: {exc}",
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
