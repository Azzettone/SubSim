"""
Widget per la visualizzazione 2D del profilo della tromba e
dei grafici di risposta in frequenza.
"""

try:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
        QPushButton, QLabel, QGroupBox, QCheckBox, QComboBox,
        QFormLayout
    )
    from PyQt5.QtCore import Qt, pyqtSignal as Signal
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
        QPushButton, QLabel, QGroupBox, QCheckBox, QComboBox,
        QFormLayout
    )
    from PySide6.QtCore import Qt, Signal

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class VisualizationWidget(QWidget):
    """
    Widget per la visualizzazione grafica del progetto:
    - Profilo 2D della tromba
    - Risposta in frequenza
    - Risposta in fase
    - Calcolo somma fronte/retro
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._horn_geometry = None
        self._build_ui()

    def _build_ui(self):
        """Costruisce l'interfaccia di visualizzazione."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Barra controlli in cima
        controls_layout = QHBoxLayout()
        main_layout.addLayout(controls_layout)

        update_btn = QPushButton("🔄 Aggiorna Grafici")
        update_btn.setMinimumHeight(35)
        update_btn.clicked.connect(self._update_all_plots)
        controls_layout.addWidget(update_btn)

        # Opzione back radiation
        self.back_radiation_check = QCheckBox("Mostra somma fronte/retro")
        controls_layout.addWidget(self.back_radiation_check)

        controls_layout.addStretch()

        if not MATPLOTLIB_AVAILABLE:
            label = QLabel(
                "Matplotlib non disponibile.\n"
                "Installa con: pip install matplotlib\n\n"
                "I calcoli sono disponibili nel modulo core."
            )
            label.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(label)
            return

        # Tab grafici
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget, 1)

        # Tab 1: Profilo tromba 2D
        self.fig_horn = Figure(figsize=(8, 4), facecolor="#181828")
        self.canvas_horn = FigureCanvas(self.fig_horn)
        self.tab_widget.addTab(self.canvas_horn, "Profilo Tromba 2D")
        self._plot_empty_horn()

        # Tab 2: Risposta in frequenza
        self.fig_freq = Figure(figsize=(8, 4), facecolor="#181828")
        self.canvas_freq = FigureCanvas(self.fig_freq)
        self.tab_widget.addTab(self.canvas_freq, "Risposta in Frequenza")
        self._plot_empty_freq()

        # Tab 3: Somma fronte/retro
        self.fig_phase = Figure(figsize=(8, 4), facecolor="#181828")
        self.canvas_phase = FigureCanvas(self.fig_phase)
        self.tab_widget.addTab(self.canvas_phase, "Somma Fronte/Retro")
        self._plot_empty_phase()

    def _setup_axes(self, ax, title: str, xlabel: str, ylabel: str):
        """Configura gli assi con il tema scuro."""
        ax.set_facecolor("#181828")
        ax.set_title(title, color="#E0E0F0", fontsize=11)
        ax.set_xlabel(xlabel, color="#A0A0C0")
        ax.set_ylabel(ylabel, color="#A0A0C0")
        ax.tick_params(colors="#A0A0C0")
        ax.spines['bottom'].set_color("#4A4A6A")
        ax.spines['top'].set_color("#4A4A6A")
        ax.spines['left'].set_color("#4A4A6A")
        ax.spines['right'].set_color("#4A4A6A")
        ax.grid(True, alpha=0.3, color="#4A4A6A")

    def _plot_empty_horn(self):
        """Mostra placeholder per il profilo tromba."""
        ax = self.fig_horn.add_subplot(111)
        self._setup_axes(ax, "Profilo Tromba 2D", "Posizione lungo l'asse (cm)", "Raggio (cm)")
        ax.text(0.5, 0.5, "Calcola una geometria per vedere il profilo",
                ha="center", va="center", color="#A0A0C0", transform=ax.transAxes)
        self.canvas_horn.draw()

    def _plot_empty_freq(self):
        """Mostra placeholder per la risposta in frequenza."""
        ax = self.fig_freq.add_subplot(111)
        self._setup_axes(ax, "Risposta in Frequenza", "Frequenza (Hz)", "SPL (dB)")
        ax.text(0.5, 0.5, "Calcola una geometria per vedere la risposta",
                ha="center", va="center", color="#A0A0C0", transform=ax.transAxes)
        self.canvas_freq.draw()

    def _plot_empty_phase(self):
        """Mostra placeholder per la somma fase."""
        ax = self.fig_phase.add_subplot(111)
        self._setup_axes(ax, "Somma Fronte/Retro", "Frequenza (Hz)", "SPL (dB)")
        ax.text(0.5, 0.5, "Abilita 'Mostra somma fronte/retro' e calcola",
                ha="center", va="center", color="#A0A0C0", transform=ax.transAxes)
        self.canvas_phase.draw()

    def update_horn_geometry(self, horn_geometry):
        """Aggiorna la geometria e ridisegna i grafici."""
        self._horn_geometry = horn_geometry
        self._update_all_plots()

    def _update_all_plots(self):
        """Aggiorna tutti i grafici."""
        # Tenta di recuperare la geometria dal progetto corrente
        if self._horn_geometry is None and hasattr(self.parent(), 'current_project'):
            params = self.parent().current_project.get("parameters", {})
            if params.get("fcutoff") and hasattr(self.parent(), 'current_project'):
                driver_data = self.parent().current_project.get("driver")
                if driver_data:
                    from ..database.db_manager import get_driver_by_model
                    from ..core.horn_calculator import design_horn
                    from ..core.constants import EXPANSION_EXPONENTIAL
                    driver = get_driver_by_model(driver_data.get("model", ""))
                    if driver:
                        try:
                            self._horn_geometry = design_horn(
                                cutoff_freq_hz=params["fcutoff"],
                                driver_sd_m2=driver.sd,
                                smouth_sthroat_ratio=params.get("smouth_ratio", 2.0),
                                throat_compression_ratio=params.get("compression_ratio", 1.0),
                            )
                        except Exception:
                            pass

        if self._horn_geometry is None:
            return

        self._plot_horn_profile()
        self._plot_frequency_response()
        if self.back_radiation_check.isChecked():
            self._plot_phase_summing()

    def _plot_horn_profile(self):
        """Disegna il profilo 2D della tromba."""
        if not MATPLOTLIB_AVAILABLE or self._horn_geometry is None:
            return

        self.fig_horn.clear()
        ax = self.fig_horn.add_subplot(111)
        self._setup_axes(ax, "Profilo Tromba 2D",
                         "Posizione lungo l'asse (cm)", "Raggio (cm)")

        g = self._horn_geometry
        x_vals = np.array([s.x_m * 100 for s in g.sections])
        r_vals = np.array([s.radius_m * 100 for s in g.sections])

        # Aggiungi punto alla gola (x=0)
        x_full = np.concatenate([[0], x_vals])
        r_full = np.concatenate([[g.throat_radius_m * 100], r_vals])

        # Profilo superiore e inferiore
        ax.plot(x_full, r_full, color="#7C9EF0", linewidth=2, label="Profilo")
        ax.plot(x_full, -r_full, color="#7C9EF0", linewidth=2)
        ax.fill_between(x_full, r_full, -r_full, alpha=0.2, color="#7C9EF0")

        # Linea asse
        ax.axhline(y=0, color="#4A4A6A", linewidth=0.5, linestyle="--")

        # Indicatori gola e bocca
        ax.axvline(x=0, color="#F0A040", linewidth=1, linestyle=":", alpha=0.8, label="Gola")
        ax.axvline(x=g.horn_length_m * 100, color="#50C878",
                   linewidth=1, linestyle=":", alpha=0.8, label="Bocca")

        # Annotazioni
        ax.text(0.5, g.throat_radius_m * 100 * 1.1,
                f"Ø gola: {g.throat_diameter_m*100:.1f}cm",
                color="#F0A040", fontsize=8)
        ax.text(g.horn_length_m * 100 - 1, g.mouth_radius_m * 100 * 1.1,
                f"Ø bocca: {g.mouth_diameter_m*100:.1f}cm",
                color="#50C878", fontsize=8, ha="right")

        ax.legend(loc="upper left", framealpha=0.3)
        ax.set_aspect("equal", "box")
        self.fig_horn.tight_layout()
        self.canvas_horn.draw()

    def _plot_frequency_response(self):
        """Disegna la risposta in frequenza della tromba."""
        if not MATPLOTLIB_AVAILABLE or self._horn_geometry is None:
            return

        from ..core.horn_calculator import horn_frequency_response

        self.fig_freq.clear()
        ax = self.fig_freq.add_subplot(111)
        self._setup_axes(ax, "Risposta in Frequenza della Tromba",
                         "Frequenza (Hz)", "SPL relativo (dB)")

        frequencies = np.logspace(np.log10(20), np.log10(20000), 500)

        # Risposta in frequenza
        amplitude_db, phase_rad = horn_frequency_response(frequencies, self._horn_geometry)

        ax.semilogx(frequencies, amplitude_db, color="#7C9EF0", linewidth=2,
                    label="Risposta ampiezza")
        ax.axvline(x=self._horn_geometry.cutoff_frequency_hz, color="#F0A040",
                   linewidth=1.5, linestyle="--", label=f"Fc = {self._horn_geometry.cutoff_frequency_hz:.0f}Hz")

        ax.set_xlim(20, 20000)
        ax.set_ylim(-70, 5)
        ax.legend(framealpha=0.3)
        self.fig_freq.tight_layout()
        self.canvas_freq.draw()

    def _plot_phase_summing(self):
        """Disegna la somma in fase fronte/retro."""
        if not MATPLOTLIB_AVAILABLE or self._horn_geometry is None:
            return

        from ..core.phase_summing import calculate_combined_response

        self.fig_phase.clear()
        ax1 = self.fig_phase.add_subplot(211)
        ax2 = self.fig_phase.add_subplot(212)

        self._setup_axes(ax1, "SPL Fronte vs Retro vs Combinato",
                         "", "SPL (dB)")
        self._setup_axes(ax2, "Differenza di Fase",
                         "Frequenza (Hz)", "Fase (gradi)")

        frequencies = np.logspace(np.log10(50), np.log10(5000), 400)

        try:
            # Recupera SPL driver dal progetto
            driver_spl = 100.0
            if hasattr(self.parent(), 'current_project'):
                driver_data = self.parent().current_project.get("driver")
                if driver_data:
                    from ..database.db_manager import get_driver_by_model
                    driver = get_driver_by_model(driver_data.get("model", ""))
                    if driver:
                        driver_spl = driver.spl_1w_1m

            horn_gain = 6.0  # dB (stima)
            result = calculate_combined_response(
                frequencies=frequencies,
                driver_spl_1w=driver_spl,
                horn_gain_db=horn_gain,
                horn_length_m=self._horn_geometry.horn_length_m,
                back_radiation_open=True,
                damping_factor=0.5,
            )

            ax1.semilogx(frequencies, result.front_spl,
                         color="#7C9EF0", linewidth=1.5, linestyle="--", label="Frontale (tromba)")
            ax1.semilogx(frequencies, result.back_spl,
                         color="#F0A040", linewidth=1.5, linestyle="--", label="Posteriore (retro)")
            ax1.semilogx(frequencies, result.combined_spl,
                         color="#50C878", linewidth=2, label="Somma combinata")
            ax1.legend(framealpha=0.3)

            ax2.semilogx(frequencies, result.phase_difference,
                         color="#C880E0", linewidth=1.5)
            ax2.axhline(y=90, color="#FF6B6B", linewidth=0.8, linestyle=":",
                        label="Interferenza distruttiva", alpha=0.7)
            ax2.axhline(y=270, color="#FF6B6B", linewidth=0.8, linestyle=":", alpha=0.7)
            ax2.set_ylim(0, 360)
            ax2.legend(framealpha=0.3)

        except Exception as e:
            ax1.text(0.5, 0.5, f"Errore: {e}", ha="center", va="center",
                     color="#FF6B6B", transform=ax1.transAxes)

        self.fig_phase.tight_layout()
        self.canvas_phase.draw()
