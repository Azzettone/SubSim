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


def _smooth_1_6_oct(freqs: np.ndarray, values: np.ndarray) -> np.ndarray:
    """
    Smoothing 1/6 ottava: per ogni frequenza media i valori entro ±1/12 ottava.
    1/6 ottava = factor 2^(1/6); metà banda = 2^(1/12).

    Args:
        freqs:  array frequenze in Hz (monotono crescente)
        values: array valori da lisciare (stessa lunghezza)

    Returns:
        array lisciato (stessa forma di values)
    """
    smoothed = np.empty_like(values, dtype=float)
    half_band = 2.0 ** (1.0 / 12.0)   # √(2^(1/6)) — metà banda 1/6 oct
    for i, f in enumerate(freqs):
        f_lo = f / half_band
        f_hi = f * half_band
        mask = (freqs >= f_lo) & (freqs <= f_hi)
        if np.any(mask):
            smoothed[i] = float(np.mean(values[mask]))
        else:
            smoothed[i] = values[i]
    return smoothed


# ─── Tab 1: Phase / Magnitude ────────────────────────────────────────────────

class PhaseMagnitudeTab(QWidget):
    """
    Plot a 3 pannelli dal motore di simulazione completo:
      - SPL assoluto (dB) — calcolato con T&S + tromba TMM + perdite BL
      - Fase totale (°) — unwrapped
      - Ritardo di gruppo (ms)

    Il plot si aggiorna automaticamente ogni volta che si chiama update().
    Le perdite fluidodinamiche (Kirchhoff 1868) sono già integrate nel SPL.
    Gli eventuali warnings fisici appaiono come testo in overlay.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._simulation = None
        self._horn_geometry = None
        self._driver = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        ctrl_row = QHBoxLayout()
        self.back_rad_check = QCheckBox("Mostra somma fronte/retro")
        ctrl_row.addWidget(self.back_rad_check)
        self.back_rad_check.stateChanged.connect(self._redraw)
        self._warn_label = QLabel("")
        self._warn_label.setStyleSheet(
            "color: #FF9040; font-size: 10px; padding-left: 8px;"
        )
        self._warn_label.setWordWrap(True)
        ctrl_row.addWidget(self._warn_label, 1)
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
        ax1 = self.fig.add_subplot(211)
        _setup_ax(ax1, "Magnitudine + Fase  (1/6 oct smooth)", "Frequenza (Hz)", "SPL (dB)")
        ax1.text(0.5, 0.5, "Calcola una geometria per attivare il motore di simulazione",
                 ha="center", va="center", color=C_SUBTLE,
                 fontsize=10, transform=ax1.transAxes)
        ax2 = self.fig.add_subplot(212)
        _setup_ax(ax2, "Ritardo di gruppo", "Frequenza (Hz)", "GD (ms)")
        self.canvas.draw()

    # ── API pubblica ─────────────────────────────────────────────────────

    def update(self, horn_geometry, driver=None):
        """Ricalcola con il simulation engine e ridisegna."""
        self._horn_geometry = horn_geometry
        self._driver = driver
        self._simulation = None
        if MATPLOTLIB_AVAILABLE and horn_geometry is not None and driver is not None:
            self._run_simulation_and_draw()
        elif MATPLOTLIB_AVAILABLE and horn_geometry is not None:
            # Nessun driver: usa il vecchio fallback passabasso
            self._redraw_fallback()

    def update_from_simulation(self, sim_result):
        """Aggiorna il plot con un SimulationResult già calcolato (es. da drag)."""
        self._simulation = sim_result
        if MATPLOTLIB_AVAILABLE:
            self._redraw()

    # ── Simulazione ──────────────────────────────────────────────────────

    def _run_simulation_and_draw(self):
        try:
            from ..core.simulation_engine import simulate
            self._simulation = simulate(self._horn_geometry, self._driver)
        except Exception as exc:
            self._simulation = None
            self._warn_label.setText(f"Errore simulazione: {exc}")
        self._redraw()

    def _redraw(self):
        if self._simulation is not None:
            self._draw_from_simulation(self._simulation)
        elif self._horn_geometry is not None:
            self._redraw_fallback()

    def _draw_from_simulation(self, sim):
        """
        Layout 2 pannelli:
          Pannello 1: Magnitudine (linea continua, asse Y sinistro, dB)
                    + Fase (linea tratteggiata, asse Y destro, °)
                    — entrambi con smoothing 1/6 ottava
          Pannello 2: Ritardo di gruppo (ms)
        """
        self.fig.clear()
        freqs = sim.frequencies
        fc    = self._horn_geometry.cutoff_frequency_hz if self._horn_geometry else 70.0

        # ── Pannello 1: Magnitudine + Fase ───────────────────────────────
        ax_mag = self.fig.add_subplot(211)
        ax_pha = ax_mag.twinx()   # asse Y destro per la fase

        driver_label = ""
        if self._driver:
            driver_label = f" — {self._driver.manufacturer} {self._driver.model}"
        ax_mag.set_title(
            f"Magnitudine + Fase (1/6 oct){driver_label}",
            color=C_TEXT, fontsize=10, pad=8
        )

        # Smoothing 1/6 ottava
        spl_smooth   = _smooth_1_6_oct(freqs, sim.spl_db)
        phase_smooth = _smooth_1_6_oct(freqs, sim.phase_deg)

        # Magnitudine — linea continua (asse sinistro)
        ln_spl, = ax_mag.semilogx(freqs, spl_smooth,
                                   color=C_BLUE, linewidth=2.0,
                                   label="SPL (1/6 oct)")
        ax_mag.set_facecolor(C_AX)
        ax_mag.set_xlabel("", color=C_SUBTLE, fontsize=9)
        ax_mag.set_ylabel("SPL (dB)", color=C_BLUE, fontsize=9)
        ax_mag.tick_params(axis="y", colors=C_BLUE, labelsize=8)
        ax_mag.tick_params(axis="x", colors=C_SUBTLE, labelsize=8)
        for sp in ax_mag.spines.values():
            sp.set_color(C_GRID)
        ax_mag.grid(True, color=C_GRID, linewidth=0.5, alpha=0.8)
        ax_mag.spines["left"].set_color(C_BLUE)

        spl_max = np.nanmax(spl_smooth)
        spl_min = max(spl_max - 50.0, np.nanmin(spl_smooth))
        ax_mag.set_xlim(20, 20000)
        ax_mag.set_ylim(spl_min - 3, spl_max + 3)

        # Fase — linea tratteggiata (asse destro)
        ln_pha, = ax_pha.semilogx(freqs, phase_smooth,
                                   color=C_PURPLE, linewidth=1.6,
                                   linestyle="--", label="Fase (1/6 oct)")
        ax_pha.set_ylabel("Fase (°)", color=C_PURPLE, fontsize=9)
        ax_pha.tick_params(axis="y", colors=C_PURPLE, labelsize=8)
        ax_pha.spines["right"].set_color(C_PURPLE)
        ax_pha.set_xlim(20, 20000)

        # Linea Fc
        ax_mag.axvline(x=fc, color=C_ORANGE, linewidth=1.0, linestyle=":",
                       alpha=0.7, label=f"Fc={fc:.0f}Hz")

        # Legenda combinata
        lines  = [ln_spl, ln_pha]
        labels = [l.get_label() for l in lines]
        ax_mag.legend(lines, labels, fontsize=7.5, framealpha=0.35,
                      facecolor=C_BG, edgecolor=C_GRID, labelcolor=C_TEXT,
                      loc="lower right")

        # Info fisica compatta
        info_parts = []
        if sim.boundary_layer_loss_avg_db > 0.01:
            info_parts.append(f"BL={sim.boundary_layer_loss_avg_db:.2f}dB")
        if sim.reynolds_throat > 0:
            info_parts.append(f"Re={sim.reynolds_throat:.0f}")
        if sim.goldberg_throat > 0:
            info_parts.append(f"Γ={sim.goldberg_throat:.3f}")
        if info_parts:
            ax_mag.text(0.01, 0.04, "  ".join(info_parts),
                        ha="left", va="bottom", transform=ax_mag.transAxes,
                        color=C_SUBTLE, fontsize=7.5)

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
                ref_idx = np.argmin(np.abs(freqs - 1000))
                offset  = spl_smooth[ref_idx] - result.combined_spl[ref_idx]
                ax_mag.semilogx(freqs, result.combined_spl + offset,
                                color=C_GREEN, linewidth=1.3, linestyle="-.",
                                label="Fronte+Retro", alpha=0.8)
            except Exception:
                pass

        # ── Pannello 2: Ritardo di gruppo ─────────────────────────────────
        ax_gd = self.fig.add_subplot(212)
        ax_gd.set_facecolor(C_AX)
        _setup_ax(ax_gd, "Ritardo di gruppo", "Frequenza (Hz)", "GD (ms)")

        gd_raw     = np.clip(sim.group_delay_ms, -20, 50)
        gd_smooth  = _smooth_1_6_oct(freqs, gd_raw)
        ax_gd.semilogx(freqs, gd_smooth,
                       color=C_GREEN, linewidth=1.8, label="GD (1/6 oct)")
        ax_gd.axhline(y=0, color=C_GRID, linewidth=0.6, linestyle=":")
        ax_gd.axvline(x=fc, color=C_ORANGE, linewidth=1.0, linestyle=":", alpha=0.7)
        ax_gd.set_xlim(20, 20000)
        ax_gd.legend(fontsize=7.5, framealpha=0.35, facecolor=C_BG,
                     edgecolor=C_GRID, labelcolor=C_TEXT)

        # ── Warnings ─────────────────────────────────────────────────────
        if sim.warnings:
            short = " | ".join(w.split("]")[0] + "]" for w in sim.warnings[:3])
            self._warn_label.setText(short)
        else:
            self._warn_label.setText("")

        self.fig.tight_layout(pad=1.2)
        self.canvas.draw()

    def _redraw_fallback(self):
        """Fallback senza driver: vecchio filtro passa-alto."""
        from ..core.horn_calculator import horn_frequency_response
        self.fig.clear()
        ax_mag = self.fig.add_subplot(211)
        ax_pha = self.fig.add_subplot(212)
        freqs = np.logspace(np.log10(20), np.log10(20000), 600)
        amp_db, phase_rad = horn_frequency_response(freqs, self._horn_geometry)
        fc = self._horn_geometry.cutoff_frequency_hz
        _setup_ax(ax_mag, "Risposta tromba (no driver)", "", "Gain (dB)")
        ax_mag.semilogx(freqs, amp_db, color=C_BLUE, linewidth=1.8)
        ax_mag.axvline(x=fc, color=C_ORANGE, linewidth=1.2, linestyle="--",
                       label=f"Fc = {fc:.0f} Hz")
        ax_mag.set_xlim(20, 20000)
        ax_mag.legend(fontsize=8, framealpha=0.35, facecolor=C_BG,
                      edgecolor=C_GRID, labelcolor=C_TEXT)
        _setup_ax(ax_pha, "Fase", "Frequenza (Hz)", "Fase (°)")
        ax_pha.semilogx(freqs, np.degrees(phase_rad), color=C_PURPLE, linewidth=1.8)
        ax_pha.axvline(x=fc, color=C_ORANGE, linewidth=1.2, linestyle="--")
        ax_pha.set_xlim(20, 20000)
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
        self._horn_geometry = horn_geometry
        if MATPLOTLIB_AVAILABLE and driver is not None:
            self._draw_impedance()

    def update_from_simulation(self, sim_result):
        """Aggiorna impedanza con i dati del SimulationResult (tromba caricata)."""
        if MATPLOTLIB_AVAILABLE and sim_result is not None:
            self._draw_impedance_from_sim(sim_result)

    def _draw_impedance_from_sim(self, sim):
        """Impedenza elettrica con carico acustico della tromba integrato."""
        freqs = sim.frequencies
        Z_free = np.abs(sim.z_electrical_complex)  # già calcolata dal sim engine

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        driver_label = ""
        if self._driver:
            driver_label = f" — {self._driver.manufacturer} {self._driver.model}"
        _setup_ax(ax, f"Impedenza elettrica (con carico tromba){driver_label}",
                  "Frequenza (Hz)", "|Z| (Ω)")

        # Impedenza libera (solo driver, senza tromba)
        self._draw_impedance(ax_override=ax, freqs_override=freqs, label_free=True)

        # Impedenza con carico tromba
        ax.semilogx(freqs, Z_free, color=C_GREEN, linewidth=2.0,
                    label="|Z| con tromba")

        if self._driver:
            ax.axvline(x=self._driver.fs, color=C_ORANGE, linewidth=1.0,
                       linestyle="--", alpha=0.7, label=f"Fs = {self._driver.fs:.0f} Hz")

        ax.set_xlim(10, 20000)
        ax.legend(fontsize=8, framealpha=0.35, facecolor=C_BG,
                  edgecolor=C_GRID, labelcolor=C_TEXT)
        self.canvas.draw()

    def _draw_impedance(self, ax_override=None, freqs_override=None, label_free=False):
        """Curva impedenza driver libero (circuito T&S, senza carico tromba)."""
        d = self._driver
        if d is None:
            return

        freqs = freqs_override if freqs_override is not None else \
                np.logspace(np.log10(10), np.log10(20000), 800)
        omega   = 2 * np.pi * freqs
        omega_s = 2 * np.pi * d.fs
        mms_kg  = d.mms * 1e-3

        if d.vas > 0 and d.sd > 0:
            from ..core.constants import AIR_DENSITY, SPEED_OF_SOUND
            cms = (d.vas * 1e-3) / (AIR_DENSITY * SPEED_OF_SOUND**2 * d.sd**2)
        else:
            cms = 1.0 / (mms_kg * omega_s**2 + 1e-30)

        rms   = (omega_s * mms_kg) / max(d.qms, 1e-6)
        Z_mec = rms + 1j * (omega * mms_kg - 1.0 / (omega * cms + 1e-30))
        Z_mot = (d.bl ** 2) / Z_mec
        Z_coil = d.re + 1j * omega * (d.le * 1e-3)
        Z_total = np.abs(Z_coil + Z_mot)

        if ax_override is not None:
            ax = ax_override
            ax.semilogx(freqs, Z_total, color=C_BLUE, linewidth=1.4,
                        linestyle="--", alpha=0.6,
                        label="|Z| driver libero" if label_free else "|Z(f)|")
        else:
            self.fig.clear()
            ax = self.fig.add_subplot(111)
            _setup_ax(ax, f"Curva Impedenza — {d.manufacturer} {d.model}",
                      "Frequenza (Hz)", "|Z| (Ω)")
            ax.semilogx(freqs, Z_total, color=C_BLUE, linewidth=2.0, label="|Z(f)|")
            ax.axvline(x=d.fs, color=C_ORANGE, linewidth=1.2, linestyle="--",
                       label=f"Fs = {d.fs:.0f} Hz")
            ax.axhline(y=d.impedance_nominal, color=C_GREEN, linewidth=0.8,
                       linestyle=":", alpha=0.8,
                       label=f"Znom = {d.impedance_nominal:.0f} Ω")
            ax.set_xlim(10, 20000)
            ax.set_ylim(0, max(Z_total) * 1.2)
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
        self._last_simulation = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        self.phase_mag_tab = PhaseMagnitudeTab()
        self.tab_widget.addTab(self.phase_mag_tab, "SPL / Phase")

        self.impedance_tab = ImpedanceTab()
        self.tab_widget.addTab(self.impedance_tab, "Impedance")

        self.panel_list_tab = PanelListTab()
        self.tab_widget.addTab(self.panel_list_tab, "Panel List")

    def update_all(self, horn_geometry, cabinet_geometry, driver,
                   wood_price: float = 30.0,
                   simulation=None):
        """
        Aggiorna tutti i tab.

        Args:
            simulation: SimulationResult opzionale già calcolato.
                        Se None, PhaseMagnitudeTab esegue la simulazione internamente.
        """
        if simulation is not None:
            self._last_simulation = simulation
            self.phase_mag_tab._horn_geometry = horn_geometry
            self.phase_mag_tab._driver = driver
            self.phase_mag_tab.update_from_simulation(simulation)
            self.impedance_tab._driver = driver
            self.impedance_tab._horn_geometry = horn_geometry
            self.impedance_tab.update_from_simulation(simulation)
        else:
            self.phase_mag_tab.update(horn_geometry, driver)
            self.impedance_tab.update(driver, horn_geometry)

        self.panel_list_tab.update(cabinet_geometry, wood_price)

    def update_from_simulation(self, sim_result, horn_geometry=None, driver=None):
        """
        Aggiorna solo i tab grafici con un nuovo SimulationResult.
        Usato dal drag interattivo in horn_view.
        """
        self._last_simulation = sim_result
        if horn_geometry is not None:
            self.phase_mag_tab._horn_geometry = horn_geometry
            self.impedance_tab._horn_geometry  = horn_geometry
        if driver is not None:
            self.phase_mag_tab._driver = driver
            self.impedance_tab._driver = driver
        self.phase_mag_tab.update_from_simulation(sim_result)
        self.impedance_tab.update_from_simulation(sim_result)
