"""
Area grafica destra: Profilo 2D della tromba.

Mostra il profilo della tromba calcolata con annotazioni:
  - Asse della tromba
  - Espansione del profilo (superiore e inferiore)
  - Indicatori gola / bocca con dimensioni
  - Punti di piega (se geometria Folded / 2-Folded)
  - Riepilogo parametri calcolati in overlay

Punti di sezione draggabili (asse X o Y, non in diagonale):
  - Drag X → sposta il punto di taglio lungo la tromba
             (il raggio si aggiorna dalla formula acustica)
  - Drag Y → modifica il raggio in quel punto
             (vincolo: monotonia + area ratio ≤ MAX_AREA_RATIO_ADJACENT)
  - Bottone Reset ripristina le sezioni originali calcolate
"""

import numpy as np
import os
import sys
from pathlib import Path

try:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
    )
    from PyQt5.QtCore import Qt, pyqtSignal as Signal
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
    )
    from PySide6.QtCore import Qt, Signal

try:
    os.environ.setdefault("MPLBACKEND", "Qt5Agg")
    import matplotlib
    matplotlib.use("Qt5Agg")
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    try:
        import matplotlib
        matplotlib.use("QtAgg")
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        import matplotlib.patches as mpatches
        MATPLOTLIB_AVAILABLE = True
    except ImportError:
        MATPLOTLIB_AVAILABLE = False

# Colori del tema scuro
C_BG       = "#12121E"
C_AX       = "#1A1A2E"
C_GRID     = "#2A2A44"
C_TEXT     = "#C0C0E0"
C_SUBTLE   = "#707090"
C_PROFILE  = "#7C9EF0"
C_THROAT   = "#F0A040"
C_MOUTH    = "#50C878"
C_FOLD     = "#E070E0"
C_AXIS     = "#445566"
C_DRAG     = "#FFE040"   # colore punto selezionato

# Vincolo fisico: maximum area ratio tra sezioni adiacenti (Olson 1957, cap.6)
# Rapporti superiori generano discontinuità forti che causano riflessioni interne.
MAX_AREA_RATIO_ADJACENT = 4.0   # S[i+1]/S[i] <= 4 (2:1 in raggio)

# Soglia di cattura in pixel per selezione del punto con il mouse
PICK_RADIUS_PX = 10

# Import costanti espansione per l'overlay
try:
    from ..core.constants import EXPANSION_HYPEX
except ImportError:
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from core.constants import EXPANSION_HYPEX
    except ImportError:
        EXPANSION_HYPEX = "hypex"


class HornView(QWidget):
    """
    Widget per la visualizzazione 2D del profilo della tromba.
    Si aggiorna ogni volta che viene chiamato update_horn().

    Segnali:
        sections_modified (list): emesso dopo drag confermato con lista sezioni
    """

    sections_modified = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._horn_geometry   = None
        self._cabinet_geometry = None
        # Copia delle sezioni modificata dall'utente (None = usa originale)
        self._custom_sections = None

        # Stato drag
        self._drag_idx        = None   # indice sezione in drag
        self._drag_axis       = None   # 'x' o 'y'
        self._drag_start_data = None   # (xdata, ydata) click iniziale
        self._drag_orig_x     = None   # x originale della sezione
        self._drag_orig_r     = None   # raggio originale della sezione

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        if not MATPLOTLIB_AVAILABLE:
            label = QLabel(
                "Matplotlib non disponibile.\n"
                "Installa con:  pip install matplotlib pyqt5\n\n"
                "I calcoli numerici funzionano comunque."
            )
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #808080;")
            layout.addWidget(label)
            return

        self.fig = Figure(facecolor=C_BG)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas)

        # Barra inferiore: hint drag + bottone reset
        bar = QHBoxLayout()
        bar.setContentsMargins(6, 2, 6, 2)
        hint = QLabel(
            "⟵ Drag X: sposta taglio sezione  |  Drag Y: mod. raggio  |  "
            "Ctrl+Drag: libero su asse Y"
        )
        hint.setStyleSheet("color: #505070; font-size: 10px;")
        bar.addWidget(hint, 1)
        self._reset_btn = QPushButton("↺ Reset sezioni")
        self._reset_btn.setFixedHeight(22)
        self._reset_btn.setStyleSheet(
            "QPushButton { background: #22223A; color: #8080B0; "
            "border: 1px solid #3A3A5A; border-radius: 3px; font-size: 10px; }"
            "QPushButton:hover { background: #2A2A4A; color: #A0A0D0; }"
        )
        self._reset_btn.clicked.connect(self._reset_sections)
        bar.addWidget(self._reset_btn)
        layout.addLayout(bar)

        # Connetti eventi mouse matplotlib per drag
        self._cid_press   = self.canvas.mpl_connect("button_press_event",   self._on_mpl_press)
        self._cid_motion  = self.canvas.mpl_connect("motion_notify_event",  self._on_mpl_motion)
        self._cid_release = self.canvas.mpl_connect("button_release_event", self._on_mpl_release)

        self._draw_placeholder()

    # ── Disegno ───────────────────────────────────────────────────────────────

    def _setup_ax(self, ax, title: str):
        ax.set_facecolor(C_AX)
        ax.set_title(title, color=C_TEXT, fontsize=11, pad=10)
        ax.tick_params(colors=C_SUBTLE, labelsize=9)
        for spine in ax.spines.values():
            spine.set_color(C_GRID)
        ax.grid(True, color=C_GRID, linewidth=0.6, alpha=0.8)

    def _draw_placeholder(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self._setup_ax(ax, "Profilo Tromba 2D")
        ax.text(
            0.5, 0.5,
            "Seleziona un driver e premi  ⚙ Calcola",
            ha="center", va="center", color=C_SUBTLE,
            fontsize=12, transform=ax.transAxes
        )
        ax.set_xlabel("Posizione asse (cm)", color=C_SUBTLE, fontsize=9)
        ax.set_ylabel("Raggio (cm)", color=C_SUBTLE, fontsize=9)
        self.fig.tight_layout(pad=1.5)
        self.canvas.draw()

    def update_horn(self, horn_geometry, cabinet_geometry=None):
        """
        Aggiorna il grafico con la nuova geometria calcolata.
        horn_geometry: HornGeometry
        cabinet_geometry: CabinetGeometry (opzionale, per fold points)
        """
        self._horn_geometry    = horn_geometry
        self._cabinet_geometry = cabinet_geometry
        self._custom_sections  = None   # reset drag ad ogni nuovo calcolo
        if MATPLOTLIB_AVAILABLE:
            self._draw_horn()

    # ── Drag helpers ──────────────────────────────────────────────────────────

    def _active_sections(self):
        """Restituisce le sezioni attive (custom se presente, altrimenti originali)."""
        if self._horn_geometry is None:
            return []
        if self._custom_sections is not None:
            return self._custom_sections
        return list(self._horn_geometry.sections)

    def _reset_sections(self):
        """Ripristina le sezioni originali calcolate dalla formula."""
        self._custom_sections = None
        if MATPLOTLIB_AVAILABLE:
            self._draw_horn()

    def _pick_section(self, xdata_cm: float, ydata_cm: float) -> int:
        """
        Trova l'indice della sezione più vicina al punto (xdata_cm, ydata_cm).
        Controlla i punti sia sul profilo superiore che inferiore.
        Restituisce -1 se nessun punto è abbastanza vicino.
        """
        if self._horn_geometry is None:
            return -1
        ax = self.fig.axes[0] if self.fig.axes else None
        if ax is None:
            return -1

        sections = self._active_sections()
        if not sections:
            return -1

        # Converte la soglia PICK_RADIUS_PX in unità dati
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
        for i, s in enumerate(sections):
            sx = s.x_m * 100
            sr = s.radius_m * 100
            for sign in (+1, -1):   # profilo sup e inf
                dx = (xdata_cm - sx) / max(thr_x, 1e-9)
                dy = (ydata_cm - sign * sr) / max(thr_y, 1e-9)
                dist = dx * dx + dy * dy
                if dist < best_dist:
                    best_dist = dist
                    best_idx  = i
        # threshold: distanza normalizzata <= 1 (= dentro il cerchio di pick)
        if best_dist <= 1.0:
            return best_idx
        return -1

    # ── Vincoli fisici sulle sezioni (Olson 1957, cap. 6) ────────────────────

    def _clamp_section_x(self, idx: int, new_x_cm: float) -> float:
        """
        Limita lo spostamento X della sezione idx entro i vicini ± margine minimo.
        Margine minimo = 2% della lunghezza totale della tromba.
        """
        sections = self._active_sections()
        L_cm     = self._horn_geometry.horn_length_m * 100
        gap      = max(L_cm * 0.02, 0.1)   # 2% di L, minimo 1 mm

        x_min = (sections[idx - 1].x_m * 100 + gap) if idx > 0 else gap * 0.5
        x_max = (sections[idx + 1].x_m * 100 - gap) if idx < len(sections) - 1 else L_cm - gap * 0.5
        return float(np.clip(new_x_cm, x_min, x_max))

    def _clamp_section_r(self, idx: int, new_r_cm: float) -> float:
        """
        Limita lo spostamento Y (raggio) della sezione idx:
          - Monotonia: r[i-1] < r[i] < r[i+1]
          - Area ratio: S[i]/S[i-1] <= MAX_AREA_RATIO_ADJACENT
                        S[i+1]/S[i] <= MAX_AREA_RATIO_ADJACENT
        Vincolo letteratura: Olson (1957) "Acoustical Engineering" cap. 6
        """
        sections = self._active_sections()

        r_throat_cm = self._horn_geometry.throat_radius_m * 100
        r_mouth_cm  = self._horn_geometry.mouth_radius_m  * 100

        # Limiti dal vicino precedente (o gola)
        if idx > 0:
            r_prev = sections[idx - 1].radius_m * 100
        else:
            r_prev = r_throat_cm
        # Limiti dal vicino successivo (o bocca)
        if idx < len(sections) - 1:
            r_next = sections[idx + 1].radius_m * 100
        else:
            r_next = r_mouth_cm

        # Margine minimo di monotonia (1% separazione in raggio)
        gap_r = max(r_throat_cm * 0.01, 0.002)

        # Vincolo area ratio: r_i <= sqrt(MAX_AREA_RATIO) * r_prev
        sqrt_max_ratio = np.sqrt(MAX_AREA_RATIO_ADJACENT)
        r_max_ratio    = r_prev * sqrt_max_ratio
        r_min_ratio    = r_next / sqrt_max_ratio

        r_min = max(r_prev + gap_r, r_min_ratio, r_throat_cm + gap_r)
        r_max = min(r_next - gap_r, r_max_ratio, r_mouth_cm  - gap_r)

        r_min = min(r_min, r_max)  # evita range invertito
        return float(np.clip(new_r_cm, r_min, r_max))

    # ── Event handlers matplotlib ─────────────────────────────────────────────

    def _on_mpl_press(self, event):
        if event.inaxes is None or event.button != 1:
            return
        if self._horn_geometry is None:
            return

        idx = self._pick_section(event.xdata, event.ydata)
        if idx < 0:
            return

        # Inizializza il drag: copia sezioni se non già customizzate
        if self._custom_sections is None:
            import copy
            self._custom_sections = copy.deepcopy(list(self._horn_geometry.sections))

        self._drag_idx        = idx
        self._drag_start_data = (event.xdata, event.ydata)
        self._drag_axis       = None   # determinato al primo motion
        self._drag_orig_x     = self._custom_sections[idx].x_m * 100
        self._drag_orig_r     = self._custom_sections[idx].radius_m * 100

    def _on_mpl_motion(self, event):
        if self._drag_idx is None or event.inaxes is None:
            return
        if event.xdata is None or event.ydata is None:
            return

        dx = event.xdata - self._drag_start_data[0]
        dy = abs(event.ydata) - abs(self._drag_start_data[1])

        # Determina asse al primo movimento significativo (>0.5% della L)
        if self._drag_axis is None:
            L_cm = self._horn_geometry.horn_length_m * 100
            threshold = max(L_cm * 0.005, 0.05)
            if abs(dx) >= threshold or abs(dy) >= threshold:
                self._drag_axis = "x" if abs(dx) >= abs(dy) else "y"
            else:
                return   # movimento troppo piccolo, aspetta

        idx = self._drag_idx
        s   = self._custom_sections[idx]

        if self._drag_axis == "x":
            # Sposta il taglio di sezione lungo X; ricalcola r dalla formula
            new_x_cm = self._clamp_section_x(idx, self._drag_orig_x + dx)
            new_x_m  = new_x_cm / 100.0

            from ..core.horn_calculator import area_at_position
            g    = self._horn_geometry
            area = area_at_position(
                new_x_m, g.throat_area_m2, g.flare_rate_m,
                g.expansion_type, g.hypex_T
            )
            new_r_m = float(np.sqrt(area / np.pi))

            s.x_m      = new_x_m
            s.area_m2  = area
            s.radius_m = new_r_m
            s.width_m  = 2 * new_r_m
            s.height_m = 2 * new_r_m
            s.position = new_x_m / max(g.horn_length_m, 1e-9)

        else:   # axis == "y"
            new_r_cm = self._clamp_section_r(idx, self._drag_orig_r + dy)
            new_r_m  = new_r_cm / 100.0
            new_area = np.pi * new_r_m ** 2

            s.radius_m = new_r_m
            s.area_m2  = new_area
            s.width_m  = 2 * new_r_m
            s.height_m = 2 * new_r_m
            # x rimane fisso

        # Ridisegna in modo leggero (solo scatter + profilo interpolato)
        self._redraw_drag()

    def _on_mpl_release(self, event):
        if self._drag_idx is None:
            return
        self._drag_idx        = None
        self._drag_axis       = None
        self._drag_start_data = None
        # Ridisegno completo con annotazioni
        self._draw_horn()
        # Notifica esternamente
        if self._custom_sections:
            self.sections_modified.emit(list(self._custom_sections))

    def _redraw_drag(self):
        """
        Ridisegno veloce durante il drag: aggiorna solo il profilo + scatter.
        Non rigenera le annotazioni per mantenere la fluidità.
        """
        if not self.fig.axes:
            return
        ax = self.fig.axes[0]

        # Rimuovi linee profilo e scatter precedenti (tenendo annotazioni)
        to_remove = [
            line for line in ax.lines
            if getattr(line, "_btk_profile", False)
        ] + [
            coll for coll in ax.collections
            if getattr(coll, "_btk_scatter", False)
        ]
        for artist in to_remove:
            artist.remove()

        sections  = self._custom_sections
        g         = self._horn_geometry
        x_vals    = np.array([s.x_m     * 100 for s in sections])
        r_vals    = np.array([s.radius_m * 100 for s in sections])
        x_full    = np.concatenate([[0.0], x_vals])
        r_full    = np.concatenate([[g.throat_radius_m * 100], r_vals])

        ln_top, = ax.plot(x_full,  r_full, color=C_PROFILE, linewidth=2.0)
        ln_bot, = ax.plot(x_full, -r_full, color=C_PROFILE, linewidth=2.0)
        [setattr(l, "_btk_profile", True) for l in (ln_top, ln_bot)]

        sc_top = ax.scatter(x_vals,  r_vals, color=C_DRAG, s=36, zorder=6,
                            edgecolors="#FFFFFF", linewidths=0.7)
        sc_bot = ax.scatter(x_vals, -r_vals, color=C_DRAG, s=36, zorder=6,
                            edgecolors="#FFFFFF", linewidths=0.7)
        sc_top._btk_scatter = True
        sc_bot._btk_scatter = True

        self.canvas.draw_idle()

    def _draw_horn(self):
        if self._horn_geometry is None:
            return

        g        = self._horn_geometry
        sections = self._active_sections()
        is_custom = (self._custom_sections is not None)

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        title = "Profilo Tromba 2D" + (" ✎ modificato" if is_custom else "")
        self._setup_ax(ax, title)

        # Coordinate delle sezioni (custom o originali)
        x_vals = np.array([s.x_m     * 100 for s in sections])
        r_vals = np.array([s.radius_m * 100 for s in sections])

        # Aggiungi il punto alla gola (x=0)
        x_full = np.concatenate([[0.0], x_vals])
        r_full = np.concatenate([[g.throat_radius_m * 100], r_vals])

        # Fill interno della tromba
        ax.fill_between(x_full, r_full, -r_full, alpha=0.15, color=C_PROFILE)

        # Profilo superiore e inferiore (con tag per drag-redraw)
        ln_top, = ax.plot(x_full,  r_full, color=C_PROFILE, linewidth=2.0, label="Profilo tromba")
        ln_bot, = ax.plot(x_full, -r_full, color=C_PROFILE, linewidth=2.0)
        ln_top._btk_profile = True
        ln_bot._btk_profile = True

        # Punti di sezione: gialli se modificati, blu se originali
        dot_color = C_DRAG if is_custom else C_PROFILE
        if len(x_vals) > 0:
            sc_top = ax.scatter(x_vals,  r_vals, color=dot_color, s=36, zorder=5,
                                edgecolors="#FFFFFF", linewidths=0.7, alpha=0.95)
            sc_bot = ax.scatter(x_vals, -r_vals, color=dot_color, s=36, zorder=5,
                                edgecolors="#FFFFFF", linewidths=0.7, alpha=0.95)
            sc_top._btk_scatter = True
            sc_bot._btk_scatter = True

        # Linea asse
        ax.axhline(y=0, color=C_AXIS, linewidth=0.8, linestyle="--", alpha=0.6)

        # Linea verticale gola
        ax.axvline(x=0, color=C_THROAT, linewidth=1.2, linestyle=":", alpha=0.9)
        ax.annotate(
            f"Gola\nØ {g.throat_diameter_m*100:.1f} cm",
            xy=(0, g.throat_radius_m * 100),
            xytext=(g.horn_length_m * 2, g.throat_radius_m * 100 * 1.6),
            color=C_THROAT, fontsize=8,
            arrowprops=dict(arrowstyle="->", color=C_THROAT, lw=0.8),
        )

        # Linea verticale bocca
        L_cm = g.horn_length_m * 100
        ax.axvline(x=L_cm, color=C_MOUTH, linewidth=1.2, linestyle=":", alpha=0.9)
        ax.annotate(
            f"Bocca\nØ {g.mouth_diameter_m*100:.1f} cm",
            xy=(L_cm, g.mouth_radius_m * 100),
            xytext=(L_cm * 0.72, g.mouth_radius_m * 100 * 1.5),
            color=C_MOUTH, fontsize=8,
            arrowprops=dict(arrowstyle="->", color=C_MOUTH, lw=0.8),
        )

        # Punti di piega (se Folded / 2-Folded)
        if self._cabinet_geometry and self._cabinet_geometry.fold_points:
            for fp in self._cabinet_geometry.fold_points:
                fold_x = fp.x_m * 100
                ax.axvline(x=fold_x, color=C_FOLD, linewidth=1.0,
                           linestyle="--", alpha=0.8)
                ax.text(
                    fold_x + L_cm * 0.01,
                    g.mouth_radius_m * 100 * 0.9,
                    "↩ piega", color=C_FOLD, fontsize=8, va="top"
                )

        # Riepilogo parametri in alto a sinistra
        n_sec = len(g.sections)
        _hypex_line = (
            f"T  = {g.hypex_T:.2f}\n"
            if g.expansion_type == EXPANSION_HYPEX else ""
        )
        summary = (
            f"Fc = {g.cutoff_frequency_hz:.0f} Hz\n"
            f"L  = {g.horn_length_m*100:.1f} cm\n"
            f"m  = {g.flare_rate_m:.4f} m\u207b\u00b9\n"
            f"Exp = {g.expansion_type}\n"
            + _hypex_line +
            f"Sez = {n_sec}"
        )
        ax.text(
            0.02, 0.97, summary,
            transform=ax.transAxes,
            verticalalignment="top",
            color=C_TEXT, fontsize=9,
            bbox=dict(boxstyle="round,pad=0.4", facecolor=C_BG, alpha=0.7, edgecolor=C_GRID),
        )

        ax.set_xlabel("Posizione asse (cm)", color=C_SUBTLE, fontsize=9)
        ax.set_ylabel("Raggio (cm)", color=C_SUBTLE, fontsize=9)

        # Legenda compatta
        legend_handles = [
            mpatches.Patch(color=C_PROFILE, label=f"{g.expansion_type.capitalize()}"),
            mpatches.Patch(color=C_THROAT, label="Gola"),
            mpatches.Patch(color=C_MOUTH, label="Bocca"),
        ]
        ax.legend(
            handles=legend_handles, loc="lower right",
            fontsize=8, framealpha=0.4,
            facecolor=C_BG, edgecolor=C_GRID, labelcolor=C_TEXT
        )

        self.fig.tight_layout(pad=1.5)
        self.canvas.draw()
