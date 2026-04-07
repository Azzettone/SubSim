"""
Area grafica destra: Profilo 2D della tromba.

Mostra il profilo della tromba calcolata con annotazioni:
  - Asse della tromba
  - Espansione del profilo (superiore e inferiore)
  - Indicatori gola / bocca con dimensioni
  - Punti di piega (se geometria Folded / 2-Folded)
  - Riepilogo parametri calcolati in overlay
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


class HornView(QWidget):
    """
    Widget per la visualizzazione 2D del profilo della tromba.
    Si aggiorna ogni volta che viene chiamato update_horn().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._horn_geometry = None
        self._cabinet_geometry = None
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
        self._horn_geometry = horn_geometry
        self._cabinet_geometry = cabinet_geometry
        if MATPLOTLIB_AVAILABLE:
            self._draw_horn()

    def _draw_horn(self):
        if self._horn_geometry is None:
            return

        g = self._horn_geometry
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self._setup_ax(ax, "Profilo Tromba 2D")

        # Coordinate delle sezioni
        x_vals = np.array([s.x_m * 100 for s in g.sections])
        r_vals = np.array([s.radius_m * 100 for s in g.sections])

        # Aggiungi il punto alla gola (x=0)
        x_full = np.concatenate([[0.0], x_vals])
        r_full = np.concatenate([[g.throat_radius_m * 100], r_vals])

        # Fill interno della tromba
        ax.fill_between(x_full, r_full, -r_full, alpha=0.15, color=C_PROFILE)

        # Profilo superiore e inferiore
        ax.plot(x_full, r_full,  color=C_PROFILE, linewidth=2.0, label="Profilo tromba")
        ax.plot(x_full, -r_full, color=C_PROFILE, linewidth=2.0)

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
        summary = (
            f"Fc = {g.cutoff_frequency_hz:.0f} Hz\n"
            f"L  = {g.horn_length_m*100:.1f} cm\n"
            f"m  = {g.flare_rate_m:.4f} m⁻¹\n"
            f"Exp = {g.expansion_type}"
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
