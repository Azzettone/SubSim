"""
Area grafica destra: 4 viste della tromba/cabinet in tab.

  TOP   — proiezione dall'alto (XZ plane) con sezioni draggabili Y
  FRONT — proiezione frontale (YZ plane) con ingombro cabinet
  SIDE  — profilo laterale 2D (XY plane) — vista storica con drag X/Y completo
  3D    — rendering tridimensionale con matplotlib Axes3D

Tutte le viste vengono aggiornate automaticamente dopo ogni calcolo.
Le modifiche drag nelle viste 2D emettono il segnale sections_modified.

Vincoli fisici drag:
  - Sezioni mono-toniche (r crescente dalla gola alla bocca)
  - Area ratio adiacente <= 4.0 (Olson 1957, cap.6)
  - Spostamento solo su asse X oppure asse Y (non diagonale)
"""

from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

import numpy as np

try:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
        QLabel, QPushButton, QSizePolicy,
    )
    from PyQt5.QtCore import Qt, pyqtSignal as Signal
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
        QLabel, QPushButton, QSizePolicy,
    )
    from PySide6.QtCore import Qt, Signal

try:
    os.environ.setdefault("MPLBACKEND", "Qt5Agg")
    import matplotlib
    matplotlib.use("Qt5Agg")
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.patches as mpatches
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  — registra la projection
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    try:
        import matplotlib
        matplotlib.use("QtAgg")
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        import matplotlib.patches as mpatches
        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
        MATPLOTLIB_AVAILABLE = True
    except ImportError:
        MATPLOTLIB_AVAILABLE = False

# ── Palette dark ─────────────────────────────────────────────────────────────
C_BG      = "#12121E"
C_AX      = "#1A1A2E"
C_GRID    = "#2A2A44"
C_TEXT    = "#C0C0E0"
C_SUBTLE  = "#707090"
C_PROFILE = "#7C9EF0"
C_THROAT  = "#F0A040"
C_MOUTH   = "#50C878"
C_FOLD    = "#E070E0"
C_AXIS    = "#445566"
C_DRAG    = "#FFE040"
C_FILL    = "#7C9EF0"
C_CABINET = "#4A4A6A"
C_DRIVER  = "#C880E0"

# Vincolo fisico sezioni
MAX_AREA_RATIO_ADJACENT = 4.0   # Olson (1957) cap.6
PICK_RADIUS_PX = 10             # pixel per selezione punto

try:
    from ..core.constants import EXPANSION_HYPEX
except ImportError:
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from core.constants import EXPANSION_HYPEX
    except ImportError:
        EXPANSION_HYPEX = "hypex"


# ─────────────────────────────────────────────────────────────────────────────
# MIXIN drag — condiviso tra le viste 2D
# ─────────────────────────────────────────────────────────────────────────────

class _DragMixin:
    """
    Logica drag condivisa tra SideView, TopView e FrontView.
    Richiede che la sottoclasse abbia:
      _horn_geometry, _custom_sections, canvas, fig
      _clamp_section_x(), _clamp_section_r()
      _draw_full(), _redraw_drag()
    E definisca sections_modified = Signal(list).
    """

    def _init_drag_state(self):
        self._drag_idx        = None
        self._drag_axis       = None
        self._drag_start_data = None
        self._drag_orig_x     = None
        self._drag_orig_r     = None

    def _active_sections(self):
        if self._horn_geometry is None:
            return []
        if self._custom_sections is not None:
            return self._custom_sections
        return list(self._horn_geometry.sections)

    def _reset_sections(self):
        self._custom_sections = None
        if MATPLOTLIB_AVAILABLE:
            self._draw_full()

    def _connect_drag_events(self):
        self._cid_press   = self.canvas.mpl_connect("button_press_event",   self._on_mpl_press)
        self._cid_motion  = self.canvas.mpl_connect("motion_notify_event",  self._on_mpl_motion)
        self._cid_release = self.canvas.mpl_connect("button_release_event", self._on_mpl_release)

    def _pick_section(self, xdata, ydata, x_vals, r_vals, ax) -> int:
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        bbox = ax.get_window_extent()
        if bbox.width < 1 or bbox.height < 1:
            return -1
        px_to_x = (xlim[1] - xlim[0]) / bbox.width
        px_to_y = (ylim[1] - ylim[0]) / bbox.height
        thr_x = PICK_RADIUS_PX * px_to_x
        thr_y = PICK_RADIUS_PX * px_to_y

        best_idx  = -1
        best_dist = float("inf")
        for i, (sx, sr) in enumerate(zip(x_vals, r_vals)):
            for sign in (+1, -1):
                dx = (xdata - sx) / max(thr_x, 1e-9)
                dy = (ydata - sign * sr) / max(thr_y, 1e-9)
                dist = dx * dx + dy * dy
                if dist < best_dist:
                    best_dist = dist
                    best_idx  = i
        return best_idx if best_dist <= 1.0 else -1

    def _clamp_section_x(self, idx: int, new_x_cm: float) -> float:
        sections = self._active_sections()
        L_cm = self._horn_geometry.horn_length_m * 100
        gap  = max(L_cm * 0.02, 0.1)
        x_min = (sections[idx - 1].x_m * 100 + gap) if idx > 0 else gap * 0.5
        x_max = (sections[idx + 1].x_m * 100 - gap) if idx < len(sections) - 1 else L_cm - gap * 0.5
        return float(np.clip(new_x_cm, x_min, x_max))

    def _clamp_section_r(self, idx: int, new_r_cm: float) -> float:
        sections = self._active_sections()
        r_throat_cm = self._horn_geometry.throat_radius_m * 100
        r_mouth_cm  = self._horn_geometry.mouth_radius_m  * 100
        r_prev = sections[idx - 1].radius_m * 100 if idx > 0 else r_throat_cm
        r_next = sections[idx + 1].radius_m * 100 if idx < len(sections) - 1 else r_mouth_cm
        gap_r = max(r_throat_cm * 0.01, 0.002)
        sqrt_max = np.sqrt(MAX_AREA_RATIO_ADJACENT)
        r_min = max(r_prev + gap_r,  r_next / sqrt_max, r_throat_cm + gap_r)
        r_max = min(r_next - gap_r, r_prev * sqrt_max,  r_mouth_cm  - gap_r)
        r_min = min(r_min, r_max)
        return float(np.clip(new_r_cm, r_min, r_max))

    def _on_mpl_press(self, event):
        if event.inaxes is None or event.button != 1 or self._horn_geometry is None:
            return
        sections = self._active_sections()
        if not sections:
            return
        ax = self.fig.axes[0]
        x_vals = [s.x_m * 100      for s in sections]
        r_vals = [s.radius_m * 100 for s in sections]
        idx = self._pick_section(event.xdata, event.ydata, x_vals, r_vals, ax)
        if idx < 0:
            return
        if self._custom_sections is None:
            self._custom_sections = copy.deepcopy(list(self._horn_geometry.sections))
        self._drag_idx        = idx
        self._drag_start_data = (event.xdata, event.ydata)
        self._drag_axis       = None
        self._drag_orig_x     = self._custom_sections[idx].x_m * 100
        self._drag_orig_r     = self._custom_sections[idx].radius_m * 100

    def _on_mpl_motion(self, event):
        if self._drag_idx is None or event.inaxes is None:
            return
        if event.xdata is None or event.ydata is None:
            return
        dx = event.xdata - self._drag_start_data[0]
        dy = abs(event.ydata) - abs(self._drag_start_data[1])
        if self._drag_axis is None:
            L_cm = self._horn_geometry.horn_length_m * 100
            thr  = max(L_cm * 0.005, 0.05)
            if abs(dx) >= thr or abs(dy) >= thr:
                self._drag_axis = "x" if abs(dx) >= abs(dy) else "y"
            else:
                return
        idx = self._drag_idx
        s   = self._custom_sections[idx]
        if self._drag_axis == "x":
            new_x_cm = self._clamp_section_x(idx, self._drag_orig_x + dx)
            new_x_m  = new_x_cm / 100.0
            from ..core.horn_calculator import area_at_position
            g    = self._horn_geometry
            area = area_at_position(new_x_m, g.throat_area_m2, g.flare_rate_m,
                                    g.expansion_type, g.hypex_T)
            r    = float(np.sqrt(area / np.pi))
            s.x_m = new_x_m; s.area_m2 = area
            s.radius_m = r;  s.width_m = 2*r; s.height_m = 2*r
            s.position = new_x_m / max(g.horn_length_m, 1e-9)
        else:
            new_r_cm = self._clamp_section_r(idx, self._drag_orig_r + dy)
            r = new_r_cm / 100.0
            s.radius_m = r; s.area_m2 = np.pi*r**2
            s.width_m = 2*r; s.height_m = 2*r
        self._redraw_drag()

    def _on_mpl_release(self, event):
        if self._drag_idx is None:
            return
        self._drag_idx = self._drag_axis = self._drag_start_data = None
        self._draw_full()
        if self._custom_sections:
            self.sections_modified.emit(list(self._custom_sections))


# ─────────────────────────────────────────────────────────────────────────────
# SIDE VIEW (vista laterale — profilo classico)
# ─────────────────────────────────────────────────────────────────────────────

class _SideCanvas(_DragMixin, QWidget):
    sections_modified = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._horn_geometry    = None
        self._cabinet_geometry = None
        self._custom_sections  = None
        self._init_drag_state()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if not MATPLOTLIB_AVAILABLE:
            layout.addWidget(QLabel("Matplotlib non disponibile."))
            return
        self.fig    = Figure(facecolor=C_BG)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas)
        self._connect_drag_events()
        self._draw_placeholder()

    def _setup_ax(self, ax, title=""):
        ax.set_facecolor(C_AX)
        ax.set_title(title, color=C_TEXT, fontsize=10, pad=6)
        ax.tick_params(colors=C_SUBTLE, labelsize=8)
        for sp in ax.spines.values():
            sp.set_color(C_GRID)
        ax.grid(True, color=C_GRID, linewidth=0.5, alpha=0.7)

    def _draw_placeholder(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self._setup_ax(ax, "SIDE — Profilo laterale")
        ax.text(0.5, 0.5, "Calcola una geometria", ha="center", va="center",
                color=C_SUBTLE, fontsize=11, transform=ax.transAxes)
        self.canvas.draw()

    def update_horn(self, horn_geometry, cabinet_geometry=None):
        self._horn_geometry    = horn_geometry
        self._cabinet_geometry = cabinet_geometry
        self._custom_sections  = None
        if MATPLOTLIB_AVAILABLE:
            self._draw_full()

    def _draw_full(self):
        if self._horn_geometry is None:
            return
        g        = self._horn_geometry
        sections = self._active_sections()
        is_custom = self._custom_sections is not None

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        title = "SIDE — Profilo laterale" + (" ✎" if is_custom else "")
        self._setup_ax(ax, title)

        x_vals = np.array([s.x_m     * 100 for s in sections])
        r_vals = np.array([s.radius_m * 100 for s in sections])
        x_full = np.concatenate([[0.0], x_vals])
        r_full = np.concatenate([[g.throat_radius_m * 100], r_vals])

        ax.fill_between(x_full, r_full, -r_full, alpha=0.12, color=C_FILL)
        ln_t, = ax.plot(x_full,  r_full, color=C_PROFILE, lw=2.0)
        ln_b, = ax.plot(x_full, -r_full, color=C_PROFILE, lw=2.0)
        ln_t._btk_profile = ln_b._btk_profile = True

        dot_col = C_DRAG if is_custom else C_PROFILE
        if len(x_vals):
            st = ax.scatter(x_vals,  r_vals, c=dot_col, s=36, zorder=5, edgecolors="#FFF", lw=0.6)
            sb = ax.scatter(x_vals, -r_vals, c=dot_col, s=36, zorder=5, edgecolors="#FFF", lw=0.6)
            st._btk_scatter = sb._btk_scatter = True

        ax.axhline(0, color=C_AXIS, lw=0.8, ls="--", alpha=0.6)

        L_cm = g.horn_length_m * 100
        ax.axvline(0,    color=C_THROAT, lw=1.1, ls=":", alpha=0.8)
        ax.axvline(L_cm, color=C_MOUTH,  lw=1.1, ls=":", alpha=0.8)

        ax.annotate(f"Ø{g.throat_diameter_m*100:.1f}cm",
                    xy=(0, g.throat_radius_m*100),
                    xytext=(L_cm*0.06, g.throat_radius_m*100*1.7),
                    color=C_THROAT, fontsize=7.5,
                    arrowprops=dict(arrowstyle="->", color=C_THROAT, lw=0.7))
        ax.annotate(f"Ø{g.mouth_diameter_m*100:.1f}cm",
                    xy=(L_cm, g.mouth_radius_m*100),
                    xytext=(L_cm*0.72, g.mouth_radius_m*100*1.4),
                    color=C_MOUTH, fontsize=7.5,
                    arrowprops=dict(arrowstyle="->", color=C_MOUTH, lw=0.7))

        # Punti di piega
        if self._cabinet_geometry and self._cabinet_geometry.fold_points:
            for fp in self._cabinet_geometry.fold_points:
                ax.axvline(fp.x_m*100, color=C_FOLD, lw=1.0, ls="--", alpha=0.8)

        _hypex = f"T={g.hypex_T:.2f}\n" if g.expansion_type == EXPANSION_HYPEX else ""
        ax.text(0.02, 0.97,
                f"Fc={g.cutoff_frequency_hz:.0f}Hz  L={L_cm:.1f}cm\n"
                f"m={g.flare_rate_m:.3f}m⁻¹  {g.expansion_type}\n{_hypex}"
                f"n={len(g.sections)} sezioni",
                transform=ax.transAxes, va="top", color=C_TEXT, fontsize=8,
                bbox=dict(boxstyle="round,pad=0.3", fc=C_BG, alpha=0.7, ec=C_GRID))

        ax.set_xlabel("Asse (cm)", color=C_SUBTLE, fontsize=8)
        ax.set_ylabel("Raggio (cm)", color=C_SUBTLE, fontsize=8)
        self.fig.tight_layout(pad=1.2)
        self.canvas.draw()

    def _redraw_drag(self):
        if not self.fig.axes:
            return
        ax = self.fig.axes[0]
        for a in [l for l in ax.lines if getattr(l, "_btk_profile", False)] + \
                 [c for c in ax.collections if getattr(c, "_btk_scatter", False)]:
            a.remove()
        g       = self._horn_geometry
        sects   = self._custom_sections
        x_vals  = np.array([s.x_m*100 for s in sects])
        r_vals  = np.array([s.radius_m*100 for s in sects])
        x_full  = np.concatenate([[0.], x_vals])
        r_full  = np.concatenate([[g.throat_radius_m*100], r_vals])
        lt, = ax.plot(x_full,  r_full, color=C_PROFILE, lw=2.0)
        lb, = ax.plot(x_full, -r_full, color=C_PROFILE, lw=2.0)
        lt._btk_profile = lb._btk_profile = True
        st = ax.scatter(x_vals,  r_vals, c=C_DRAG, s=36, zorder=6, edgecolors="#FFF", lw=0.6)
        sb = ax.scatter(x_vals, -r_vals, c=C_DRAG, s=36, zorder=6, edgecolors="#FFF", lw=0.6)
        st._btk_scatter = sb._btk_scatter = True
        self.canvas.draw_idle()


# ─────────────────────────────────────────────────────────────────────────────
# TOP VIEW (vista dall'alto — proiezione XZ)
# ─────────────────────────────────────────────────────────────────────────────

class _TopCanvas(_DragMixin, QWidget):
    """
    Vista dall'alto: asse tromba lungo X, larghezza lungo Z.
    Mostra il rettangolo esterno del cabinet e il profilo della tromba.
    I punti sezione si possono spostare su X (taglio sezione) o Z (larghezza).
    """
    sections_modified = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._horn_geometry    = None
        self._cabinet_geometry = None
        self._custom_sections  = None
        self._init_drag_state()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if not MATPLOTLIB_AVAILABLE:
            layout.addWidget(QLabel("Matplotlib non disponibile."))
            return
        self.fig    = Figure(facecolor=C_BG)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas)
        self._connect_drag_events()
        self._draw_placeholder()

    def _setup_ax(self, ax, title=""):
        ax.set_facecolor(C_AX)
        ax.set_title(title, color=C_TEXT, fontsize=10, pad=6)
        ax.tick_params(colors=C_SUBTLE, labelsize=8)
        for sp in ax.spines.values():
            sp.set_color(C_GRID)
        ax.grid(True, color=C_GRID, linewidth=0.5, alpha=0.7)
        ax.set_aspect("equal", adjustable="datalim")

    def _draw_placeholder(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self._setup_ax(ax, "TOP — Vista dall'alto")
        ax.text(0.5, 0.5, "Calcola una geometria", ha="center", va="center",
                color=C_SUBTLE, fontsize=11, transform=ax.transAxes)
        self.canvas.draw()

    def update_horn(self, horn_geometry, cabinet_geometry=None):
        self._horn_geometry    = horn_geometry
        self._cabinet_geometry = cabinet_geometry
        self._custom_sections  = None
        if MATPLOTLIB_AVAILABLE:
            self._draw_full()

    def _draw_full(self):
        if self._horn_geometry is None:
            return
        g       = self._horn_geometry
        sects   = self._active_sections()
        is_cust = self._custom_sections is not None

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self._setup_ax(ax, "TOP — Vista dall'alto" + (" ✎" if is_cust else ""))

        x_vals = np.array([s.x_m*100      for s in sects])
        r_vals = np.array([s.radius_m*100 for s in sects])
        x_full = np.concatenate([[0.], x_vals])
        r_full = np.concatenate([[g.throat_radius_m*100], r_vals])

        # Fill profilo (vista dall'alto: stessa forma del SIDE ma asse Y=larghezza)
        ax.fill_between(x_full, r_full, -r_full, alpha=0.12, color=C_FILL)
        lt, = ax.plot(x_full,  r_full, color=C_PROFILE, lw=1.8)
        lb, = ax.plot(x_full, -r_full, color=C_PROFILE, lw=1.8)
        lt._btk_profile = lb._btk_profile = True

        dot_col = C_DRAG if is_cust else C_PROFILE
        if len(x_vals):
            st = ax.scatter(x_vals,  r_vals, c=dot_col, s=32, zorder=5, edgecolors="#FFF", lw=0.6)
            sb = ax.scatter(x_vals, -r_vals, c=dot_col, s=32, zorder=5, edgecolors="#FFF", lw=0.6)
            st._btk_scatter = sb._btk_scatter = True

        # Cabinet bounding box (se disponibile)
        if self._cabinet_geometry:
            cab = self._cabinet_geometry
            L   = cab.total_depth_mm  / 10  # cm
            W   = cab.total_width_mm  / 10
            rect = mpatches.Rectangle((0, -W/2), L, W,
                                       lw=1.2, edgecolor=C_CABINET,
                                       facecolor="none", ls="--", alpha=0.6)
            ax.add_patch(rect)

        ax.axvline(0,                  color=C_THROAT, lw=1.0, ls=":", alpha=0.7)
        ax.axvline(g.horn_length_m*100, color=C_MOUTH,  lw=1.0, ls=":", alpha=0.7)
        ax.axhline(0, color=C_AXIS, lw=0.6, ls="--", alpha=0.5)

        ax.set_xlabel("Profondità (cm)", color=C_SUBTLE, fontsize=8)
        ax.set_ylabel("Larghezza (cm)",  color=C_SUBTLE, fontsize=8)
        self.fig.tight_layout(pad=1.2)
        self.canvas.draw()

    def _redraw_drag(self):
        if not self.fig.axes:
            return
        ax = self.fig.axes[0]
        for a in [l for l in ax.lines if getattr(l, "_btk_profile", False)] + \
                 [c for c in ax.collections if getattr(c, "_btk_scatter", False)]:
            a.remove()
        g      = self._horn_geometry
        sects  = self._custom_sections
        x_vals = np.array([s.x_m*100      for s in sects])
        r_vals = np.array([s.radius_m*100 for s in sects])
        x_full = np.concatenate([[0.], x_vals])
        r_full = np.concatenate([[g.throat_radius_m*100], r_vals])
        lt, = ax.plot(x_full,  r_full, color=C_PROFILE, lw=1.8)
        lb, = ax.plot(x_full, -r_full, color=C_PROFILE, lw=1.8)
        lt._btk_profile = lb._btk_profile = True
        st = ax.scatter(x_vals,  r_vals, c=C_DRAG, s=32, zorder=6, edgecolors="#FFF", lw=0.6)
        sb = ax.scatter(x_vals, -r_vals, c=C_DRAG, s=32, zorder=6, edgecolors="#FFF", lw=0.6)
        st._btk_scatter = sb._btk_scatter = True
        self.canvas.draw_idle()


# ─────────────────────────────────────────────────────────────────────────────
# FRONT VIEW (vista frontale — proiezione YZ)
# ─────────────────────────────────────────────────────────────────────────────

class _FrontCanvas(QWidget):
    """
    Vista frontale: mostra la bocca della tromba e il profilo del cabinet.
    Per tromba circolare: cerchio bocca centrato.
    Per cabinet reflex: mostra driver + porte.
    Non ha drag (la geometria frontale è determinata dalla bocca, parametro derivato).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._horn_geometry    = None
        self._cabinet_geometry = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if not MATPLOTLIB_AVAILABLE:
            layout.addWidget(QLabel("Matplotlib non disponibile."))
            return
        self.fig    = Figure(facecolor=C_BG)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas)
        self._draw_placeholder()

    def _setup_ax(self, ax, title=""):
        ax.set_facecolor(C_AX)
        ax.set_title(title, color=C_TEXT, fontsize=10, pad=6)
        ax.tick_params(colors=C_SUBTLE, labelsize=8)
        for sp in ax.spines.values():
            sp.set_color(C_GRID)
        ax.grid(True, color=C_GRID, linewidth=0.5, alpha=0.7)
        ax.set_aspect("equal", adjustable="datalim")

    def _draw_placeholder(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self._setup_ax(ax, "FRONT — Vista frontale")
        ax.text(0.5, 0.5, "Calcola una geometria", ha="center", va="center",
                color=C_SUBTLE, fontsize=11, transform=ax.transAxes)
        self.canvas.draw()

    def update_horn(self, horn_geometry, cabinet_geometry=None):
        self._horn_geometry    = horn_geometry
        self._cabinet_geometry = cabinet_geometry
        if MATPLOTLIB_AVAILABLE:
            self._draw_front()

    def _draw_front(self):
        if self._horn_geometry is None:
            return
        g = self._horn_geometry

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self._setup_ax(ax, "FRONT — Vista frontale (bocca)")

        r_mouth_cm = g.mouth_radius_m * 100
        r_throat_cm = g.throat_radius_m * 100

        # Cabinet bounding box da vista frontale
        if self._cabinet_geometry:
            cab = self._cabinet_geometry
            W = cab.total_width_mm  / 10   # cm
            H = cab.total_height_mm / 10
            rect = mpatches.Rectangle((-W/2, -H/2), W, H,
                                       lw=1.5, edgecolor=C_CABINET,
                                       facecolor=C_CABINET, alpha=0.15,
                                       ls="-")
            ax.add_patch(rect)
            # Tratteggio esterno
            rect2 = mpatches.Rectangle((-W/2, -H/2), W, H,
                                        lw=1.5, edgecolor=C_CABINET,
                                        facecolor="none", ls="--")
            ax.add_patch(rect2)

        # Bocca tromba (cerchio)
        mouth_circle = mpatches.Circle((0, 0), r_mouth_cm,
                                        lw=2.0, edgecolor=C_MOUTH,
                                        facecolor=C_FILL, alpha=0.2)
        ax.add_patch(mouth_circle)
        mouth_edge = mpatches.Circle((0, 0), r_mouth_cm,
                                      lw=2.0, edgecolor=C_MOUTH,
                                      facecolor="none")
        ax.add_patch(mouth_edge)

        # Gola tromba (cerchio interno tratteggiato)
        throat_circle = mpatches.Circle((0, 0), r_throat_cm,
                                         lw=1.0, edgecolor=C_THROAT,
                                         facecolor="none", ls="--", alpha=0.7)
        ax.add_patch(throat_circle)

        # Annotazioni
        ax.text(r_mouth_cm * 0.72, r_mouth_cm * 0.72,
                f"Bocca\nØ{g.mouth_diameter_m*100:.1f}cm",
                color=C_MOUTH, fontsize=8, ha="left")
        ax.text(r_throat_cm * 0.5, -r_throat_cm * 1.5,
                f"Gola Ø{g.throat_diameter_m*100:.1f}cm",
                color=C_THROAT, fontsize=7.5, ha="center")

        # Crosshair asse
        ax.axhline(0, color=C_AXIS, lw=0.6, ls="--", alpha=0.5)
        ax.axvline(0, color=C_AXIS, lw=0.6, ls="--", alpha=0.5)

        margin = r_mouth_cm * 1.35
        if self._cabinet_geometry:
            margin = max(margin, self._cabinet_geometry.total_width_mm / 10 / 2 * 1.1)
        ax.set_xlim(-margin, margin)
        ax.set_ylim(-margin, margin)

        ax.set_xlabel("Larghezza (cm)", color=C_SUBTLE, fontsize=8)
        ax.set_ylabel("Altezza (cm)",   color=C_SUBTLE, fontsize=8)
        self.fig.tight_layout(pad=1.2)
        self.canvas.draw()


# ─────────────────────────────────────────────────────────────────────────────
# 3D VIEW — rendering matplotlib 3D
# ─────────────────────────────────────────────────────────────────────────────

class _3DCanvas(QWidget):
    """
    Vista 3D della tromba: solid of revolution con profilo della tromba.
    Usa matplotlib mpl_toolkits.mplot3d.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._horn_geometry    = None
        self._cabinet_geometry = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if not MATPLOTLIB_AVAILABLE:
            layout.addWidget(QLabel("Matplotlib non disponibile."))
            return
        self.fig    = Figure(facecolor=C_BG)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas)
        self._draw_placeholder()

    def _draw_placeholder(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111, projection="3d")
        ax.set_facecolor(C_AX)
        ax.text(0, 0, 0, "Calcola una geometria", color=C_SUBTLE, ha="center")
        self.canvas.draw()

    def update_horn(self, horn_geometry, cabinet_geometry=None):
        self._horn_geometry    = horn_geometry
        self._cabinet_geometry = cabinet_geometry
        if MATPLOTLIB_AVAILABLE:
            self._draw_3d()

    def _draw_3d(self):
        if self._horn_geometry is None:
            return
        g       = self._horn_geometry
        sects   = list(g.sections)

        # Profilo del horn
        x_vals = np.array([0.0] + [s.x_m*100      for s in sects])
        r_vals = np.array([g.throat_radius_m*100]  + [s.radius_m*100 for s in sects])

        # Solid of revolution: rotazione intorno all'asse X
        n_phi = 36   # segmenti angolari
        phi   = np.linspace(0, 2*np.pi, n_phi)

        # Mesh: X, Y, Z
        # X = posizione asse (invariante per phi), Y = r·cos(phi), Z = r·sin(phi)
        X = np.tile(x_vals, (n_phi, 1))           # (n_phi, n_x)
        R = np.tile(r_vals, (n_phi, 1))           # (n_phi, n_x)
        PHI = np.tile(phi[:, np.newaxis], (1, len(x_vals)))
        Y = R * np.cos(PHI)
        Z = R * np.sin(PHI)

        self.fig.clear()
        try:
            ax = self.fig.add_subplot(111, projection="3d")
        except Exception:
            # Fallback se mpl_toolkits non disponibile
            ax = self.fig.add_subplot(111)
            ax.text(0.5, 0.5, "mpl_toolkits.mplot3d non disponibile.\nInstalla matplotlib >= 3.5",
                    ha="center", va="center", color=C_SUBTLE, transform=ax.transAxes)
            self.canvas.draw()
            return

        ax.set_facecolor(C_AX)
        self.fig.patch.set_facecolor(C_BG)

        # Superficie horn
        ax.plot_surface(X, Y, Z,
                        color=C_FILL, alpha=0.35, linewidth=0,
                        antialiased=True)
        # Wireframe bordi
        ax.plot_wireframe(X, Y, Z,
                          color=C_PROFILE, alpha=0.45, linewidth=0.4,
                          rstride=4, cstride=1)

        # Cerchi gola e bocca
        phi_c = np.linspace(0, 2*np.pi, 100)
        r_t = g.throat_radius_m * 100
        r_m = g.mouth_radius_m  * 100
        ax.plot(np.zeros(100), r_t*np.cos(phi_c), r_t*np.sin(phi_c),
                color=C_THROAT, lw=1.5, alpha=0.9)
        ax.plot(np.full(100, g.horn_length_m*100), r_m*np.cos(phi_c), r_m*np.sin(phi_c),
                color=C_MOUTH, lw=1.5, alpha=0.9)

        # Assi
        ax.set_xlabel("Asse (cm)", color=C_SUBTLE, fontsize=7, labelpad=3)
        ax.set_ylabel("Y (cm)",    color=C_SUBTLE, fontsize=7, labelpad=3)
        ax.set_zlabel("Z (cm)",    color=C_SUBTLE, fontsize=7, labelpad=3)
        ax.tick_params(colors=C_SUBTLE, labelsize=7)
        ax.xaxis.pane.set_edgecolor(C_GRID)
        ax.yaxis.pane.set_edgecolor(C_GRID)
        ax.zaxis.pane.set_edgecolor(C_GRID)
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.set_title(f"3D — {g.expansion_type}  Fc={g.cutoff_frequency_hz:.0f}Hz",
                     color=C_TEXT, fontsize=9, pad=6)
        try:
            self.fig.tight_layout(pad=1.0)
        except Exception:
            pass
        self.canvas.draw()


# ─────────────────────────────────────────────────────────────────────────────
# WIDGET CONTENITORE: 4 TAB
# ─────────────────────────────────────────────────────────────────────────────

class HornViewTabs(QWidget):
    """
    Widget principale area grafica destra.
    Contiene 4 tab: TOP / FRONT / SIDE / 3D.

    Segnali:
        sections_modified (list): emesso da qualsiasi vista 2D dopo drag confermato.
    """

    sections_modified = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barra inferiore con hint drag + reset
        bar = QHBoxLayout()
        bar.setContentsMargins(6, 1, 6, 1)
        hint = QLabel(
            "⟵ Drag X: sposta sezione  |  Drag Y: modifica raggio"
        )
        hint.setStyleSheet("color: #404060; font-size: 9px;")
        bar.addWidget(hint, 1)
        self._reset_btn = QPushButton("↺ Reset")
        self._reset_btn.setFixedHeight(20)
        self._reset_btn.setStyleSheet(
            "QPushButton { background:#1C1C30; color:#6060A0; "
            "border:1px solid #2A2A40; border-radius:3px; font-size:9px; padding:0 8px; }"
            "QPushButton:hover { background:#24243C; }"
        )
        self._reset_btn.clicked.connect(self._on_reset)
        bar.addWidget(self._reset_btn)

        # Tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setStyleSheet("""
            QTabBar::tab {
                background: #1A1A2E; color: #6060A0;
                padding: 5px 22px; border: 1px solid #2A2A44;
                border-bottom: none; font-size: 10px; font-weight: bold;
            }
            QTabBar::tab:selected { background: #2A2A44; color: #C0C0E0; }
            QTabBar::tab:hover    { background: #222238; color: #A0A0CC; }
        """)
        layout.addWidget(self.tab_widget)
        layout.addLayout(bar)

        # Creazione viste
        self._top_view   = _TopCanvas()
        self._front_view = _FrontCanvas()
        self._side_view  = _SideCanvas()
        self._3d_view    = _3DCanvas()

        self.tab_widget.addTab(self._top_view,   "TOP")
        self.tab_widget.addTab(self._front_view, "FRONT")
        self.tab_widget.addTab(self._side_view,  "SIDE")
        self.tab_widget.addTab(self._3d_view,    "3D")

        # Connetti segnali drag → segnale esterno unico
        self._top_view.sections_modified.connect(self.sections_modified)
        self._side_view.sections_modified.connect(self.sections_modified)

        # Default: tab SIDE attiva (la più informativa dopo calcolo)
        self.tab_widget.setCurrentIndex(2)

        # Aggiorna vista 3D solo quando diventa visibile (lazy rendering)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self._pending_3d_update = False

    # ── API pubblica ────────────────────────────────────────────────────────

    def update_horn(self, horn_geometry, cabinet_geometry=None):
        """Aggiorna tutte le viste con la nuova geometria."""
        self._horn_geometry    = horn_geometry
        self._cabinet_geometry = cabinet_geometry

        # Aggiorna le viste attualmente visibili
        current = self.tab_widget.currentIndex()
        self._top_view.update_horn(horn_geometry, cabinet_geometry)
        self._front_view.update_horn(horn_geometry, cabinet_geometry)
        self._side_view.update_horn(horn_geometry, cabinet_geometry)

        if current == 3:
            self._3d_view.update_horn(horn_geometry, cabinet_geometry)
            self._pending_3d_update = False
        else:
            self._pending_3d_update = True   # aggiorna quando si apre il tab 3D

    # ── Slot ────────────────────────────────────────────────────────────────

    def _on_reset(self):
        """Reset sezioni su tutte le viste draggabili."""
        self._top_view._reset_sections()
        self._side_view._reset_sections()

    def _on_tab_changed(self, idx: int):
        """Rendering 3D lazy: solo quando il tab 3D diventa visibile."""
        if idx == 3 and self._pending_3d_update:
            horn = getattr(self, "_horn_geometry", None)
            cab  = getattr(self, "_cabinet_geometry", None)
            if horn is not None:
                self._3d_view.update_horn(horn, cab)
            self._pending_3d_update = False
