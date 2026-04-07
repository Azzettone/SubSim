"""
Area inferiore: Tab con i grafici di analisi.

Tab 1 — Phase/Magnitude Plot:
    Risposta in ampiezza e fase della tromba vs frequenza.

Tab 2 — Impedance:
    Curva impedenza vs frequenza (placeholder — sarà implementato con il modello
    elettrico del driver: Z(f) = Re + j*2π*f*Le + back-EMF).

Tab 3 — Panel List:
    Tabella lista di taglio pannelli con dimensioni e costo per pezzo.
"""

import numpy as np
import os

try:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
        QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
        QCheckBox, QSizePolicy
    )
    from PyQt5.QtCore import Qt
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
        QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
        QCheckBox, QSizePolicy
    )
    from PySide6.QtCore import Qt

try:
    os.environ.setdefault("MPLBACKEND", "Qt5Agg")
    import matplotlib
    matplotlib.use("Qt5Agg")
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    try:
        import matplotlib
        matplotlib.use("QtAgg")
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        MATPLOTLIB_AVAILABLE = True
    except ImportError:
        MATPLOTLIB_AVAILABLE = False

# Palette dark theme — stessa di horn_view.py
C_BG     = "#12121E"
C_AX     = "#1A1A2E"
C_GRID   = "#2A2A44"
C_TEXT   = "#C0C0E0"
C_SUBTLE = "#707090"
C_BLUE   = "#7C9EF0"
C_ORANGE = "#F0A040"
C_GREEN  = "#50C878"
C_PURPLE = "#C880E0"
C_RED    = "#FF6B6B"


def _setup_ax(ax, title: str, xlabel: str, ylabel: str):
    ax.set_facecolor(C_AX)
    ax.set_title(title, color=C_TEXT, fontsize=10, pad=8)
    ax.set_xlabel(xlabel, color=C_SUBTLE, fontsize=9)
    ax.set_ylabel(ylabel, color=C_SUBTLE, fontsize=9)
    ax.tick_params(colors=C_SUBTLE, labelsize=8)
    for sp in ax.spines.values():
        sp.set_color(C_GRID)
    ax.grid(True, color=C_GRID, linewidth=0.5, alpha=0.8)


# ─── Tab 1: Phase / Magnitude ────────────────────────────────────────────────

class PhaseMagnitudeTab(QWidget):
    """
    Grafico a doppio pannello:
      - Superiore: risposta in ampiezza (dB) vs frequenza (scala log)
      - Inferiore: risposta in fase (°) vs frequenza (scala log)
    Opzione checkbox per sovrapporre la somma fronte/retro.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._horn_geometry = None
        self._driver = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Controllo opzionale somma fronte/retro
        ctrl_row = QHBoxLayout()
        self.back_rad_check = QCheckBox("Mostra somma fronte/retro")
        ctrl_row.addWidget(self.back_rad_check)
        self.back_rad_check.stateChanged.connect(self._redraw)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        if not MATPLOTLIB_AVAILABLE:
            layout.addWidget(QLabel("Matplotlib non disponibile."))
            return

        self.fig = Figure(facecolor=C_BG, constrained_layout=True)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas)
        self._draw_placeholder()

    def _draw_placeholder(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        _setup_ax(ax, "Phase / Magnitude", "Frequenza (Hz)", "SPL (dB)")
        ax.text(0.5, 0.5, "Calcola una geometria per vedere la risposta",
                ha="center", va="center", color=C_SUBTLE,
                fontsize=11, transform=ax.transAxes)
        self.canvas.draw()

    def update(self, horn_geometry, driver=None):
        self._horn_geometry = horn_geometry
        self._driver = driver
        if MATPLOTLIB_AVAILABLE:
            self._redraw()

    def _redraw(self):
        if self._horn_geometry is None:
            return

        from ..core.horn_calculator import horn_frequency_response

        self.fig.clear()
        ax_mag = self.fig.add_subplot(211)
        ax_pha = self.fig.add_subplot(212)

        freqs = np.logspace(np.log10(20), np.log10(20000), 600)
        amp_db, phase_rad = horn_frequency_response(freqs, self._horn_geometry)

        # ── Ampiezza ────────────────────────────────────────────────────
        _setup_ax(ax_mag, "Risposta in Ampiezza", "", "SPL relativo (dB)")
        ax_mag.semilogx(freqs, amp_db, color=C_BLUE, linewidth=1.8, label="Ampiezza")
        fc = self._horn_geometry.cutoff_frequency_hz
        ax_mag.axvline(x=fc, color=C_ORANGE, linewidth=1.2, linestyle="--",
                       label=f"Fc = {fc:.0f} Hz")
        ax_mag.set_xlim(20, 20000)
        ax_mag.set_ylim(-70, 5)
        ax_mag.legend(fontsize=8, framealpha=0.35, facecolor=C_BG,
                      edgecolor=C_GRID, labelcolor=C_TEXT)

        # Somma fronte/retro opzionale
        if self.back_rad_check.isChecked() and self._driver is not None:
            try:
                from ..core.phase_summing import calculate_combined_response
                result = calculate_combined_response(
                    frequencies=freqs,
                    driver_spl_1w=self._driver.spl_1w_1m,
                    horn_gain_db=6.0,
                    horn_length_m=self._horn_geometry.horn_length_m,
                    back_radiation_open=True,
                    damping_factor=0.5,
                )
                ax_mag.semilogx(freqs, result.combined_spl - self._driver.spl_1w_1m,
                                color=C_GREEN, linewidth=1.4, linestyle="--",
                                label="Combinato (fronte+retro)")
                ax_mag.legend(fontsize=8, framealpha=0.35, facecolor=C_BG,
                              edgecolor=C_GRID, labelcolor=C_TEXT)
            except Exception:
                pass

        # ── Fase ────────────────────────────────────────────────────────
        _setup_ax(ax_pha, "Risposta in Fase", "Frequenza (Hz)", "Fase (°)")
        phase_deg = np.degrees(phase_rad)
        ax_pha.semilogx(freqs, phase_deg, color=C_PURPLE, linewidth=1.8)
        ax_pha.axvline(x=fc, color=C_ORANGE, linewidth=1.2, linestyle="--")
        ax_pha.set_xlim(20, 20000)
        ax_pha.set_ylim(-5, 100)

        self.canvas.draw()


# ─── Tab 2: Impedance ────────────────────────────────────────────────────────

class ImpedanceTab(QWidget):
    """
    Curva impedenza Z(f) vs frequenza.
    Modello semplificato: Z(f) = Re + j·2π·f·Le + contributo risonanza meccanica.
    La curva mostra il picco di risonanza a Fs e la salita per effetto Le.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._driver = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        if not MATPLOTLIB_AVAILABLE:
            layout.addWidget(QLabel("Matplotlib non disponibile."))
            return

        self.fig = Figure(facecolor=C_BG, constrained_layout=True)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas)
        self._draw_placeholder()

    def _draw_placeholder(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        _setup_ax(ax, "Curva Impedenza Z(f)", "Frequenza (Hz)", "|Z| (Ω)")
        ax.text(0.5, 0.5, "Seleziona un driver per vedere la curva di impedenza",
                ha="center", va="center", color=C_SUBTLE,
                fontsize=11, transform=ax.transAxes)
        self.canvas.draw()

    def update(self, driver=None, horn_geometry=None):
        self._driver = driver
        if MATPLOTLIB_AVAILABLE and driver is not None:
            self._draw_impedance()

    def _draw_impedance(self):
        d = self._driver
        freqs = np.logspace(np.log10(10), np.log10(20000), 800)

        # Modello impedenza elettrica — circuito equivalente T&S
        # Zmec = meccanical mobility converted to electrical impedance
        omega = 2 * np.pi * freqs

        # Impedenza bobina: Re + j·ω·Le
        Z_coil = d.re + 1j * omega * (d.le * 1e-3)

        # Risonanza meccanica → picco di impedenza a Fs
        # Motional impedance: Zmot = BL² / Zmec
        # Zmec = Rms + j·(ω·Mms - 1/(ω·Cms))
        omega_s = 2 * np.pi * d.fs
        mms_kg = d.mms * 1e-3
        # Cms da Vas e Sd (se non disponibile, stima da Qms/Qes)
        if d.vas > 0 and d.sd > 0:
            rho, c = 1.225, 343.0
            cms = (d.vas * 1e-3) / (rho * c**2 * d.sd**2)
        else:
            cms = 1.0 / (mms_kg * omega_s**2)

        # Rms da Qms: Qms = omega_s * Mms / Rms
        rms = (omega_s * mms_kg) / d.qms if d.qms > 0 else 1.0

        Z_mec = rms + 1j * (omega * mms_kg - 1.0 / (omega * cms + 1e-30))
        Z_mot = (d.bl ** 2) / Z_mec

        Z_total = Z_coil + Z_mot
        Z_mag = np.abs(Z_total)

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        _setup_ax(ax, f"Curva Impedenza — {d.manufacturer} {d.model}",
                  "Frequenza (Hz)", "|Z| (Ω)")

        ax.semilogx(freqs, Z_mag, color=C_BLUE, linewidth=2.0, label="|Z(f)|")
        ax.axvline(x=d.fs, color=C_ORANGE, linewidth=1.2, linestyle="--",
                   label=f"Fs = {d.fs:.0f} Hz")
        ax.axhline(y=d.impedance_nominal, color=C_GREEN, linewidth=0.8,
                   linestyle=":", alpha=0.8, label=f"Znom = {d.impedance_nominal:.0f} Ω")

        ax.set_xlim(10, 20000)
        ax.set_ylim(0, max(Z_mag) * 1.2)
        ax.legend(fontsize=8, framealpha=0.35, facecolor=C_BG,
                  edgecolor=C_GRID, labelcolor=C_TEXT)

        self.canvas.draw()


# ─── Tab 3: Panel List ───────────────────────────────────────────────────────

class PanelListTab(QWidget):
    """
    Tabella lista di taglio dei pannelli MDF del cabinet.
    Mostra nome, dimensioni, quantità e costo unitario/totale.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wood_price = 30.0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Riga info totale
        self.total_label = QLabel("Nessun progetto calcolato")
        self.total_label.setStyleSheet("color: #A0A0C0; font-size: 11px;")
        layout.addWidget(self.total_label)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Pannello", "L (mm)", "A (mm)", "Sp. (mm)", "Qtà", "Area (m²)", "Costo (€)"
        ])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 7):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

    def update(self, cabinet_geometry, wood_price: float = 30.0):
        """Popola la tabella con i pannelli del cabinet."""
        self._wood_price = wood_price
        panels = cabinet_geometry.panels

        self.table.setRowCount(len(panels))
        total_cost = 0.0

        for row, p in enumerate(panels):
            cost = p.cost(wood_price)
            total_cost += cost * p.quantity
            items = [
                p.name,
                f"{p.width_mm:.1f}",
                f"{p.height_mm:.1f}",
                f"{p.thickness_mm:.0f}",
                f"{p.quantity}",
                f"{p.area_m2 * p.quantity:.4f}",
                f"{cost:.2f}",
            ]
            for col, text in enumerate(items):
                self.table.setItem(row, col, QTableWidgetItem(text))

        self.total_label.setText(
            f"{len(panels)} pannelli  —  "
            f"Area totale: {cabinet_geometry.total_panel_area_m2():.3f} m²  —  "
            f"Costo stimato: € {total_cost:.2f}  (MDF a {wood_price:.0f} €/m²)"
        )


# ─── Widget contenitore con i 3 tab ──────────────────────────────────────────

class AnalysisTabs(QWidget):
    """
    Widget contenitore per i 3 tab di analisi in fondo alla finestra.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        self.phase_mag_tab = PhaseMagnitudeTab()
        self.tab_widget.addTab(self.phase_mag_tab, "Phase / Magnitude")

        self.impedance_tab = ImpedanceTab()
        self.tab_widget.addTab(self.impedance_tab, "Impedance")

        self.panel_list_tab = PanelListTab()
        self.tab_widget.addTab(self.panel_list_tab, "Panel List")

    def update_all(self, horn_geometry, cabinet_geometry, driver, wood_price: float = 30.0):
        """Aggiorna tutti i tab con i dati del calcolo corrente."""
        self.phase_mag_tab.update(horn_geometry, driver)
        self.impedance_tab.update(driver, horn_geometry)
        self.panel_list_tab.update(cabinet_geometry, wood_price)
