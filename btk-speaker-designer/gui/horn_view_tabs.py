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

        # Branch: tromba folded/2-folded → render a strisce orizzontali
        if self._cabinet_geometry and self._cabinet_geometry.fold_points:
            self._draw_folded_side(ax, g, sections, is_custom)
            self.fig.tight_layout(pad=1.2)
            self.canvas.draw()
            return

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

        _hypex = f"T={g.hypex_T:.2f}\n" if g.expansion_type == EXPANSION_HYPEX else ""
        ax.text(0.02, 0.97,
                f"Fc={g.cutoff_frequency_hz:.0f}Hz  L={L_cm:.1f}cm\n"
                f"m={g.flare_rate_m:.3f}m⁻¹  {g.expansion_type}\n{_hypex}"
                f"n={len(g.sections)} sezioni",
                transform=ax.transAxes, va="top", color=C_TEXT, fontsize=8,
                bbox=dict(boxstyle="round,pad=0.3", fc=C_BG, alpha=0.7, ec=C_GRID))

        # ── scala coerente con TOP (stesso X per confronto profondità) ──────
        L_cm      = g.horn_length_m * 100
        r_max_cm  = float(r_full.max()) if len(r_full) else g.mouth_radius_m * 100
        if self._cabinet_geometry:
            h_cm = self._cabinet_geometry.total_height_mm / 10
            r_max_cm = max(r_max_cm, h_cm / 2)
            x_end    = self._cabinet_geometry.total_depth_mm / 10
        else:
            x_end = L_cm
        ax.set_xlim(-x_end * 0.04, x_end * 1.06)
        ax.set_ylim(-r_max_cm * 1.25, r_max_cm * 1.25)

        ax.set_xlabel("Asse / Profondità (cm)", color=C_SUBTLE, fontsize=8)
        ax.set_ylabel("Raggio / Altezza (cm)", color=C_SUBTLE, fontsize=8)
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

    # ── Reflex / Bandpass ─────────────────────────────────────────────────────

    def update_reflex(self, result, driver):
        """Disegna sezione laterale del cabinet reflex/bandpass."""
        self._horn_geometry    = None
        self._cabinet_geometry = None
        self._custom_sections  = None
        if MATPLOTLIB_AVAILABLE:
            self._draw_reflex_side(result, driver)

    def _draw_reflex_side(self, result, driver):
        """
        Sezione laterale schematica del cabinet reflex o bandpass.
        Mostra camere, driver e porta reflex con dimensioni stimate.
        """
        try:
            from ..core.constants import ENCLOSURE_BANDPASS_4, ENCLOSURE_BANDPASS_6
        except ImportError:
            ENCLOSURE_BANDPASS_4 = "bandpass_4"
            ENCLOSURE_BANDPASS_6 = "bandpass_6"

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self._setup_ax(ax, "SIDE — Sezione trasversale cabinet")

        enc_type = result.enclosure_type
        vf_l = result.box_volume_front_l
        vr_l = result.box_volume_rear_l
        port = result.port_front
        is_bp = enc_type in (ENCLOSURE_BANDPASS_4, ENCLOSURE_BANDPASS_6)

        d_driver_cm  = driver.diameter_inch * 2.54
        r_outer_cm   = d_driver_cm / 2
        r_driver_cm  = float(np.sqrt(driver.sd * 1e4 / np.pi)) if driver.sd > 0 else r_outer_cm * 0.75

        if is_bp:
            total_v_l   = max(vf_l + vr_l, 1.0)
            total_w_cm  = max(d_driver_cm * 2.2, (total_v_l * 1e-3) ** (1/3) * 100 * 2.2)
            height_cm   = r_outer_cm * 2.0 * 1.35
            driver_w_cm = d_driver_cm * 0.12
            rear_frac   = vr_l / total_v_l
            x_driver    = total_w_cm * rear_frac

            # Camere
            for xA, xB, label, vol in [
                (0, x_driver, f"REAR\n{vr_l:.1f} L\n(chiusa)", vr_l),
                (x_driver + driver_w_cm, total_w_cm, f"FRONT\n{vf_l:.1f} L", vf_l),
            ]:
                ax.add_patch(mpatches.FancyBboxPatch(
                    (xA, 0), xB - xA, height_cm,
                    boxstyle="round,pad=0.3", lw=1.5,
                    edgecolor=C_CABINET, facecolor=C_AX, alpha=0.85,
                ))
                ax.text((xA + xB) / 2, height_cm / 2, label,
                        ha='center', va='center', color=C_TEXT, fontsize=8.5, fontweight='bold')

            # Driver (divisore tra camere)
            ax.add_patch(mpatches.FancyArrow(
                x_driver, height_cm / 2 - r_driver_cm, 0, r_driver_cm * 2,
                width=driver_w_cm * 0.85, head_width=0,
                color=C_DRIVER, alpha=0.85, zorder=5,
            ))
            ax.text(x_driver + driver_w_cm / 2, height_cm * 0.06,
                    f'{driver.diameter_inch}"', ha='center', va='bottom',
                    color=C_DRIVER, fontsize=8)

            # Porta (sul pannello frontale)
            if port:
                pd_cm = port.diameter_mm / 10
                pl_cm = port.length_mm / 10
                py    = height_cm / 2
                ax.add_patch(mpatches.Rectangle(
                    (total_w_cm, py - pd_cm / 2), pl_cm, pd_cm,
                    lw=1.5, edgecolor=C_MOUTH, facecolor=C_FILL, alpha=0.45,
                ))
                ax.text(total_w_cm + pl_cm / 2, py + pd_cm / 2 + 1.0,
                        f"porta Ø{port.diameter_mm:.0f}mm\nL={port.length_mm:.0f}mm",
                        ha='center', va='bottom', color=C_MOUTH, fontsize=7.5)
            ax.set_xlim(-1.5, total_w_cm + (port.length_mm / 10 + 5 if port else 5))
            ax.set_ylim(-3, height_cm + 4)

        else:
            # Bass-reflex singola camera
            side_cm = max(d_driver_cm * 1.7, (vf_l * 1e-3) ** (1/3) * 100 * 2.4)
            height_cm = r_outer_cm * 2.0 * 1.3

            ax.add_patch(mpatches.FancyBboxPatch(
                (0, 0), side_cm, height_cm,
                boxstyle="round,pad=0.4", lw=1.8,
                edgecolor=C_CABINET, facecolor=C_AX, alpha=0.85,
            ))
            ax.text(side_cm / 2, height_cm * 0.70,
                    f"Bass-Reflex\n{vf_l:.1f} L",
                    ha='center', va='center', color=C_TEXT, fontsize=10, fontweight='bold')

            # Driver (pannello posteriore)
            ax.add_patch(mpatches.Circle((0, height_cm / 2), r_driver_cm,
                lw=2, edgecolor=C_DRIVER, facecolor=C_DRIVER, alpha=0.22))
            ax.add_patch(mpatches.Circle((0, height_cm / 2), r_driver_cm,
                lw=2, edgecolor=C_DRIVER, facecolor='none'))
            ax.text(0 + 1.5, height_cm * 0.08, f'Driver {driver.diameter_inch}"',
                    ha='left', va='bottom', color=C_DRIVER, fontsize=8)

            # Porta (pannello frontale)
            if port:
                pd_cm = port.diameter_mm / 10
                pl_cm = port.length_mm / 10
                py    = height_cm / 3
                ax.add_patch(mpatches.Rectangle(
                    (side_cm, py - pd_cm / 2), pl_cm, pd_cm,
                    lw=1.5, edgecolor=C_MOUTH, facecolor=C_FILL, alpha=0.45,
                ))
                ax.text(side_cm + pl_cm / 2, py + pd_cm / 2 + 1.0,
                        f"porta Ø{port.diameter_mm:.0f}mm\nL={port.length_mm:.0f}mm\n"
                        f"Fb={result.tuning_freq_hz:.0f}Hz",
                        ha='center', va='bottom', color=C_MOUTH, fontsize=7.5)
            ax.set_xlim(-2, side_cm + (port.length_mm / 10 + 8 if port else 8))
            ax.set_ylim(-3, height_cm + 5)

        # Info box
        fb  = result.tuning_freq_hz
        f3l = result.f3_low_hz
        f3h = result.f3_high_hz
        ax.text(0.02, 0.97,
                f"Fb = {fb:.0f} Hz  |  F3: [{f3l:.0f}–{f3h:.0f}] Hz\n"
                f"{driver.manufacturer} {driver.model}  ({driver.diameter_inch}\")",
                transform=ax.transAxes, va='top', color=C_TEXT, fontsize=8,
                bbox=dict(boxstyle='round,pad=0.3', fc=C_BG, alpha=0.75, ec=C_GRID))
        if result.warnings:
            warn = "\n".join(f"⚠ {w[:65]}" for w in result.warnings[:2])
            ax.text(0.02, 0.03, warn, transform=ax.transAxes,
                    va='bottom', color=C_THROAT, fontsize=7.5,
                    bbox=dict(boxstyle='round,pad=0.2', fc=C_BG, alpha=0.7, ec=C_THROAT))

        ax.set_xlabel("Profondità (cm)", color=C_SUBTLE, fontsize=8)
        ax.set_ylabel("Altezza (cm)",    color=C_SUBTLE, fontsize=8)
        self.fig.tight_layout(pad=1.2)
        self.canvas.draw()

    # ── Folded horn rendering ──────────────────────────────────────────────────

    def _draw_folded_side(self, ax, g, sections, is_custom):
        """
        Rendering SIDE per tromba folded/2-folded.
        Disegna ogni segmento come striscia orizzontale impilata verticalmente;
        le pieghe sono collegate da frecce direzionali.
        """
        cab       = self._cabinet_geometry
        fold_pts  = sorted(cab.fold_points, key=lambda fp: fp.x_m)
        L_m       = g.horn_length_m
        bounds_m  = [0.0] + [fp.x_m for fp in fold_pts] + [L_m]
        n_segs    = len(bounds_m) - 1
        GAP_CM    = 2.5
        dot_col   = C_DRAG if is_custom else C_PROFILE
        SEG_COLS  = [C_PROFILE, C_FOLD, C_MOUTH, C_THROAT]

        # ── per ogni segmento calcola (xs, rs) nel sistema locale ──────────
        strips = []
        for i in range(n_segs):
            x0_m, x1_m = bounds_m[i], bounds_m[i + 1]
            seg_sects   = [s for s in sections if x0_m - 1e-9 <= s.x_m <= x1_m + 1e-9]
            seg_len_cm  = (x1_m - x0_m) * 100

            r_start = g.throat_radius_m * 100 if i == 0 else fold_pts[i - 1].height_m * 50.0
            pts_x = np.array([0.0] + [(s.x_m - x0_m) * 100 for s in seg_sects])
            pts_r = np.array([r_start] + [s.radius_m * 100 for s in seg_sects])

            if i % 2 == 1:          # segmenti dispari vanno a sinistra
                pts_x = seg_len_cm - pts_x[::-1]
                pts_r = pts_r[::-1]

            strips.append({
                'xs':          pts_x,
                'rs':          pts_r,
                'seg_len_cm':  seg_len_cm,
                'going_right': (i % 2 == 0),
            })

        # ── Y center per ogni strip (impilate dall'alto) ──────────────────
        y_tops, y_cur = [], 0.0
        for s in strips:
            r_max  = float(s['rs'].max()) if len(s['rs']) else 5.0
            y_tops.append(y_cur - r_max)
            y_cur  = y_tops[-1] - r_max - GAP_CM
        y_offset = (y_tops[0] + y_tops[-1]) / 2
        y_centers = [y - y_offset for y in y_tops]

        x_max_cm = max((s['seg_len_cm'] for s in strips), default=1.0)

        # ── disegna ogni segmento ─────────────────────────────────────────
        for i, (strip, y_c) in enumerate(zip(strips, y_centers)):
            col = SEG_COLS[i % len(SEG_COLS)]
            xs, rs = strip['xs'], strip['rs']

            ax.fill_between(xs, y_c + rs, y_c - rs, alpha=0.13, color=col)
            lt, = ax.plot(xs, y_c + rs, color=col, lw=2.0)
            lb, = ax.plot(xs, y_c - rs, color=col, lw=2.0)
            lt._btk_profile = lb._btk_profile = True

            if len(xs) > 1:
                st = ax.scatter(xs[1:], y_c + rs[1:], c=dot_col, s=28, zorder=5,
                                edgecolors='#FFF', lw=0.45)
                sb = ax.scatter(xs[1:], y_c - rs[1:], c=dot_col, s=28, zorder=5,
                                edgecolors='#FFF', lw=0.45)
                st._btk_scatter = sb._btk_scatter = True

            ax.axhline(y_c, color=C_AXIS, lw=0.45, ls='--', alpha=0.3)

            if i == 0:
                lbl = "◀ Gola"
            elif i == n_segs - 1:
                lbl = "Bocca ▶"
            else:
                lbl = f"Seg. {i + 1}"
            ax.text(float(np.mean(xs)), y_c + float(rs.max()) + 0.7,
                    lbl, ha='center', va='bottom', color=col, fontsize=7.5)

        # ── frecce di connessione alle pieghe ─────────────────────────────
        for i, fp in enumerate(fold_pts):
            s_i   = strips[i]
            x_loc = (fp.x_m - bounds_m[i]) * 100
            if not s_i['going_right']:
                x_loc = s_i['seg_len_cm'] - x_loc
            y1, y2 = y_centers[i], y_centers[i + 1]
            ax.annotate("", xytext=(x_loc, y1), xy=(x_loc, y2),
                        arrowprops=dict(arrowstyle="-|>", color=C_FOLD,
                                        lw=1.3, mutation_scale=10))
            ax.text(x_loc + 0.4, (y1 + y2) / 2,
                    f"  piega {i + 1}\n  @{fp.x_m * 100:.0f}cm",
                    color=C_FOLD, fontsize=7, va='center')

        # ── annotazioni gola / bocca ──────────────────────────────────────
        r_t_cm = g.throat_radius_m * 100
        r_m_cm = g.mouth_radius_m  * 100
        ax.annotate(f"Gola Ø{g.throat_diameter_m * 100:.1f}cm",
                    xy=(0, y_centers[0] + r_t_cm),
                    xytext=(x_max_cm * 0.3, y_centers[0] + r_t_cm + 2.5),
                    color=C_THROAT, fontsize=7.5,
                    arrowprops=dict(arrowstyle='->', color=C_THROAT, lw=0.7))
        xs_last = strips[-1]['xs']
        x_mouth = float(xs_last[-1]) if len(xs_last) else strips[-1]['seg_len_cm']
        ax.annotate(f"Bocca Ø{g.mouth_diameter_m * 100:.1f}cm",
                    xy=(x_mouth, y_centers[-1] + r_m_cm),
                    xytext=(x_max_cm * 0.55, y_centers[-1] + r_m_cm + 2.5),
                    color=C_MOUTH, fontsize=7.5,
                    arrowprops=dict(arrowstyle='->', color=C_MOUTH, lw=0.7))

        # ── info box ─────────────────────────────────────────────────────
        n_folds  = len(fold_pts)
        fold_lbl = f"Folded {n_folds}×" if n_folds > 1 else "Folded"
        ax.text(0.02, 0.97,
                f"{fold_lbl}  L={g.horn_length_m * 100:.1f}cm\n"
                f"Fc={g.cutoff_frequency_hz:.0f}Hz  {g.expansion_type}\n"
                f"Cabinet: {cab.total_depth_mm:.0f}×{cab.total_height_mm:.0f}mm (D×H)",
                transform=ax.transAxes, va='top', color=C_TEXT, fontsize=8,
                bbox=dict(boxstyle='round,pad=0.3', fc=C_BG, alpha=0.7, ec=C_GRID))

        ax.set_xlabel("Profondità segmento (cm)", color=C_SUBTLE, fontsize=8)
        ax.set_ylabel("Layout verticale (cm)",    color=C_SUBTLE, fontsize=8)


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
        # NON usa set_aspect("equal") — asse X uguale a SIDE per confronto profondità

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

        # ── scala identica a SIDE: stesso X, Y = larghezza cabinet ──────────
        L_cm      = g.horn_length_m * 100
        r_max_cm  = float(r_full.max()) if len(r_full) else g.mouth_radius_m * 100
        if self._cabinet_geometry:
            w_cm     = self._cabinet_geometry.total_width_mm / 10
            x_end    = self._cabinet_geometry.total_depth_mm / 10
            r_max_cm = max(r_max_cm, w_cm / 2)
        else:
            x_end = L_cm
        ax.set_xlim(-x_end * 0.04, x_end * 1.06)
        ax.set_ylim(-r_max_cm * 1.25, r_max_cm * 1.25)

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

    # ── Reflex ────────────────────────────────────────────────────────────────

    def update_reflex(self, result, driver):
        """Vista frontale del pannello del cabinet reflex/bandpass."""
        self._horn_geometry    = None
        self._cabinet_geometry = None
        if MATPLOTLIB_AVAILABLE:
            self._draw_reflex_front(result, driver)

    def _draw_reflex_front(self, result, driver):
        """
        Vista frontale schematica: pannello frontale con driver (tratteggiato,
        sul retro) e porta(e) reflex.
        """
        try:
            from ..core.constants import ENCLOSURE_BANDPASS_4, ENCLOSURE_BANDPASS_6
        except ImportError:
            ENCLOSURE_BANDPASS_4 = "bandpass_4"
            ENCLOSURE_BANDPASS_6 = "bandpass_6"

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self._setup_ax(ax, "FRONT — Pannello frontale")

        enc_type    = result.enclosure_type
        is_bp       = enc_type in (ENCLOSURE_BANDPASS_4, ENCLOSURE_BANDPASS_6)
        r_outer_cm  = driver.diameter_inch * 2.54 / 2
        r_driver_cm = float(np.sqrt(driver.sd * 1e4 / np.pi)) if driver.sd > 0 else r_outer_cm * 0.75
        cab_w       = r_outer_cm * 2.4
        cab_h       = r_outer_cm * 2.2

        # Bounding box cabinet
        ax.add_patch(mpatches.Rectangle(
            (-cab_w / 2, -cab_h / 2), cab_w, cab_h,
            lw=1.8, edgecolor=C_CABINET, facecolor=C_CABINET, alpha=0.12,
        ))

        if not is_bp:
            # Driver (tratteggiato = pannello posteriore, visibile in trasparenza)
            ax.add_patch(mpatches.Circle((0, 0), r_driver_cm,
                lw=1.5, edgecolor=C_DRIVER, facecolor=C_DRIVER, alpha=0.10, ls='--'))
            ax.add_patch(mpatches.Circle((0, 0), r_driver_cm,
                lw=1.5, edgecolor=C_DRIVER, facecolor='none', ls='--'))
            ax.text(0, 0, f'{driver.diameter_inch}"',
                    ha='center', va='center', color=C_DRIVER,
                    fontsize=10, fontweight='bold', alpha=0.65)

        # Porta(e) reflex sul pannello frontale
        port = result.port_front
        if port:
            n        = max(1, int(port.n_ports))
            pd_cm    = port.diameter_mm / 10
            offset_x = -cab_w * 0.15
            for p_i in range(n):
                oy = (p_i - (n - 1) / 2) * (pd_cm * 2.6)
                py = -r_outer_cm * 0.45 + oy
                ax.add_patch(mpatches.Circle(
                    (offset_x, py), pd_cm / 2,
                    lw=2.0, edgecolor=C_MOUTH, facecolor=C_FILL, alpha=0.40,
                ))
                ax.add_patch(mpatches.Circle(
                    (offset_x, py), pd_cm / 2,
                    lw=2.0, edgecolor=C_MOUTH, facecolor='none',
                ))
            lbl_y = -r_outer_cm * 0.45 - (n - 1) / 2 * pd_cm * 2.6 - pd_cm / 2 - 1.2
            ax.text(offset_x, lbl_y,
                    f"{n}× porta Ø{port.diameter_mm:.0f}mm\nFb={result.tuning_freq_hz:.0f}Hz",
                    ha='center', va='top', color=C_MOUTH, fontsize=8.5)

        margin = max(cab_w, cab_h) / 2 * 1.3
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
        g     = self._horn_geometry
        sects = list(g.sections)
        cab   = self._cabinet_geometry

        # Profilo del horn
        x_vals = np.array([0.0] + [s.x_m * 100 for s in sects])
        r_vals = np.array([g.throat_radius_m * 100] + [s.radius_m * 100 for s in sects])

        # Aspect ratio da cabinet (default: quadrato = 1.0)
        if cab and cab.total_width_mm > 0 and cab.total_height_mm > 0:
            asp = cab.total_width_mm / cab.total_height_mm
        else:
            asp = 1.0

        # Dimensioni rettangolari per ogni sezione
        # half-width (Z) e half-height (Y) = r√asp e r/√asp
        sqrt_asp  = float(np.sqrt(asp))
        hw_vals   = r_vals * sqrt_asp    # half-width  (+Z/-Z)
        hh_vals   = r_vals / sqrt_asp    # half-height (+Y/-Y)

        self.fig.clear()
        try:
            ax = self.fig.add_subplot(111, projection="3d")
        except Exception:
            ax = self.fig.add_subplot(111)
            ax.text(0.5, 0.5, "mpl_toolkits.mplot3d non disponibile.",
                    ha="center", va="center", color=C_SUBTLE, transform=ax.transAxes)
            self.canvas.draw()
            return

        ax.set_facecolor(C_AX)
        self.fig.patch.set_facecolor(C_BG)

        try:
            from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        except ImportError:
            Poly3DCollection = None

        # ── Disegna le 4 pareti come superfici piatte (top, bottom, left, right) ──
        n = len(x_vals)
        wall_polys = []
        wall_alpha = 0.28

        for i in range(n - 1):
            x0, x1   = x_vals[i], x_vals[i + 1]
            hw0, hw1 = hw_vals[i], hw_vals[i + 1]
            hh0, hh1 = hh_vals[i], hh_vals[i + 1]

            # Top wall  (+Y, varia Z)
            wall_polys.append([(x0, hh0,  hw0), (x1, hh1,  hw1),
                                (x1, hh1, -hw1), (x0, hh0, -hw0)])
            # Bottom wall (-Y, varia Z)
            wall_polys.append([(x0, -hh0,  hw0), (x1, -hh1,  hw1),
                                (x1, -hh1, -hw1), (x0, -hh0, -hw0)])
            # Left wall  (-Z, varia Y)
            wall_polys.append([(x0, -hh0, hw0), (x1, -hh1, hw1),
                                (x1,  hh1, hw1), (x0,  hh0, hw0)])
            # Right wall (+Z, varia Y)
            wall_polys.append([(x0, -hh0, -hw0), (x1, -hh1, -hw1),
                                (x1,  hh1, -hw1), (x0,  hh0, -hw0)])

        if Poly3DCollection and wall_polys:
            pc = Poly3DCollection(wall_polys,
                                  facecolor=C_FILL, alpha=wall_alpha,
                                  edgecolor=C_PROFILE, linewidth=0.35)
            ax.add_collection3d(pc)

        # ── Pannello gola (rettangolo anteriore) ─────────────────────────────
        hw_t, hh_t = hw_vals[0], hh_vals[0]
        throat_face = [(-hw_t, hh_t, 0.0), (hw_t, hh_t, 0.0),
                       (hw_t, -hh_t, 0.0), (-hw_t, -hh_t, 0.0)]
        # Converti a (x, y, z) con x=0
        throat_face_xyz = [(0.0, y, z) for z, y, _ in throat_face]
        if Poly3DCollection:
            ax.add_collection3d(Poly3DCollection(
                [throat_face_xyz], facecolor=C_THROAT,
                alpha=0.35, edgecolor=C_THROAT, linewidth=1.2))

        # ── Pannello bocca (rettangolo posteriore) ────────────────────────────
        x_m   = x_vals[-1]
        hw_m, hh_m = hw_vals[-1], hh_vals[-1]
        mouth_face_xyz = [(x_m, hh_m, hw_m), (x_m, hh_m, -hw_m),
                          (x_m, -hh_m, -hw_m), (x_m, -hh_m, hw_m)]
        if Poly3DCollection:
            ax.add_collection3d(Poly3DCollection(
                [mouth_face_xyz], facecolor=C_MOUTH,
                alpha=0.30, edgecolor=C_MOUTH, linewidth=1.2))

        # ── Bordi profilo (wireframe asse) ────────────────────────────────────
        for sign_y, sign_z in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
            ax.plot(x_vals, sign_y * hh_vals, sign_z * hw_vals,
                    color=C_PROFILE, lw=0.8, alpha=0.8)

        # ── Bounding box cabinet esterno (se disponibile) ─────────────────────
        if cab:
            L  = cab.total_depth_mm  / 10
            W  = cab.total_width_mm  / 10 / 2
            H  = cab.total_height_mm / 10 / 2
            bb_verts = np.array([
                [0, -H, -W], [0, -H, W], [0, H, W], [0, H, -W],
                [L, -H, -W], [L, -H, W], [L, H, W], [L, H, -W],
            ])
            edges = [(0,1),(1,2),(2,3),(3,0), (4,5),(5,6),(6,7),(7,4),
                     (0,4),(1,5),(2,6),(3,7)]
            for a_i, b_i in edges:
                ax.plot(*zip(bb_verts[a_i], bb_verts[b_i]),
                        color=C_CABINET, lw=0.8, ls="--", alpha=0.55)

        # ── Assi e labels ─────────────────────────────────────────────────────
        ax.set_xlabel("Profondità (cm)", color=C_SUBTLE, fontsize=7, labelpad=3)
        ax.set_ylabel("Altezza (cm)",    color=C_SUBTLE, fontsize=7, labelpad=3)
        ax.set_zlabel("Larghezza (cm)",  color=C_SUBTLE, fontsize=7, labelpad=3)
        ax.tick_params(colors=C_SUBTLE, labelsize=7)
        for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
            pane.set_edgecolor(C_GRID)
            pane.fill = False
        ax.set_title(
            f"3D — {g.expansion_type}  Fc={g.cutoff_frequency_hz:.0f}Hz"
            + (f"  {cab.total_depth_mm:.0f}×{cab.total_width_mm:.0f}×"
               f"{cab.total_height_mm:.0f}mm" if cab else ""),
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

    def update_reflex(self, result, driver):
        """
        Aggiorna tutte le viste con il risultato di un calcolo reflex/bandpass.
        SIDE: sezione trasversale con camere e porta.
        FRONT: pannello frontale con driver e porta.
        TOP e 3D: placeholder.
        """
        self._horn_geometry    = None
        self._cabinet_geometry = None
        self._pending_3d_update = False
        self._side_view.update_reflex(result, driver)
        self._front_view.update_reflex(result, driver)
        # TOP e 3D non hanno ancora un render reflex dedicato
        # → mostrano placeholder temporaneo
        if hasattr(self._top_view, '_draw_placeholder'):
            self._top_view._draw_placeholder()
        if hasattr(self._3d_view, '_draw_placeholder'):
            self._3d_view._draw_placeholder()

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
