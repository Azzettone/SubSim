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

    def update_from_reflex(self, reflex_result):
        """Mostra la risposta SPL di un enclosure reflex/bandpass."""
        if not MATPLOTLIB_AVAILABLE:
            return
        import numpy as np
        freqs = reflex_result.frequencies
        spl   = reflex_result.spl_db

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        _setup_ax(ax, "Risposta in frequenza (Reflex / Bandpass)",
                  "Frequenza (Hz)", "SPL (dB @ 1W/1m)")
        ax.semilogx(freqs, spl, color=C_BLUE, linewidth=2.0, label="SPL")
        ax.axhline(y=max(spl) - 3.0, color=C_ORANGE, linewidth=0.8,
                   linestyle=":", alpha=0.7, label="−3 dB")
        if hasattr(reflex_result, "f3_low_hz") and reflex_result.f3_low_hz > 0:
            ax.axvline(x=reflex_result.f3_low_hz, color=C_ORANGE,
                       linewidth=1.0, linestyle="--",
                       label=f"F3 low = {reflex_result.f3_low_hz:.0f} Hz")
        if hasattr(reflex_result, "f3_high_hz") and reflex_result.f3_high_hz > 0:
            ax.axvline(x=reflex_result.f3_high_hz, color=C_GREEN,
                       linewidth=1.0, linestyle="--",
                       label=f"F3 high = {reflex_result.f3_high_hz:.0f} Hz")
        ax.set_xlim(20, 1000)
        ax.legend(fontsize=8, framealpha=0.35, facecolor=C_BG,
                  edgecolor=C_GRID, labelcolor=C_TEXT)
        self.fig.tight_layout(pad=1.2)
        self.canvas.draw()

    def update_from_fullrange(self, result: dict):
        """Mostra la risposta combinata HF + LF del sistema Fullrange."""
        if not MATPLOTLIB_AVAILABLE:
            return
        import numpy as np

        freqs    = result["frequencies"]
        hf_spl   = result["hf_spl_db"]
        lf_spl   = result["lf_spl_db"]
        combined = result["combined_spl_db"]
        xover_hz = result.get("crossover_freq_hz", 700)

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        _setup_ax(ax, "Risposta Fullrange (HF + LF + Crossover)",
                  "Frequenza (Hz)", "SPL (dB @ 1W/1m)")

        ax.semilogx(freqs, lf_spl,   color=C_BLUE,   linewidth=1.4,
                    linestyle="--", alpha=0.7, label="LF (sub)")
        ax.semilogx(freqs, hf_spl,   color=C_ORANGE,  linewidth=1.4,
                    linestyle="--", alpha=0.7, label="HF (CD)")
        ax.semilogx(freqs, combined, color=C_GREEN,   linewidth=2.2,
                    label="Combinata")
        ax.axvline(x=xover_hz, color="#FF8080", linewidth=1.0,
                   linestyle=":", alpha=0.8, label=f"Xover = {xover_hz:.0f} Hz")

        ax.set_xlim(20, 20000)
        ax.legend(fontsize=8, framealpha=0.35, facecolor=C_BG,
                  edgecolor=C_GRID, labelcolor=C_TEXT)
        self.fig.tight_layout(pad=1.2)
        self.canvas.draw()

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
        Layout 3 pannelli:
          Pannello 1: SPL (dB) — curva sistema + guadagno tromba TMM + SPL grezzo
          Pannello 2: Fase totale (°) + fase tromba (twin Y)
          Pannello 3: Ritardo di gruppo (ms)

        Il pannello SPL mostra:
          - Linea sottile/semi-trasparente: SPL grezzo (rivela ripple TMM / risonanze tromba)
          - Linea principale (1/6 oct): risposta sistema totale normalizzata
          - Linea tratteggiata (1/6 oct): guadagno tromba riferito al livello di passband
            (evidenzia come i diversi profili tromba modellano la risposta)
          - Linea rossa puntata (1/6 oct): perdite strato limite BL (Kirchhoff 1868)
        """
        self.fig.clear()
        freqs = sim.frequencies
        fc    = self._horn_geometry.cutoff_frequency_hz if self._horn_geometry else 70.0

        driver_label = ""
        if self._driver:
            driver_label = f" — {self._driver.manufacturer} {self._driver.model}"

        # Smoothing 1/6 ottava per le curve principali
        spl_smooth    = _smooth_1_6_oct(freqs, sim.spl_db)
        phase_smooth  = _smooth_1_6_oct(freqs, sim.phase_deg)
        horn_smooth   = _smooth_1_6_oct(freqs, sim.horn_gain_db)
        bl_smooth     = _smooth_1_6_oct(freqs, sim.bl_loss_db)

        # ── Pannello 1: SPL + guadagno tromba + perdite BL ───────────────
        ax_spl = self.fig.add_subplot(311)
        ax_spl.set_facecolor(C_AX)
        ax_spl.set_title(f"SPL — driver + tromba (TMM){driver_label}",
                         color=C_TEXT, fontsize=10, pad=8)
        ax_spl.set_ylabel("SPL (dB)", color=C_TEXT, fontsize=9)
        ax_spl.tick_params(axis="x", colors=C_SUBTLE, labelsize=8)
        ax_spl.tick_params(axis="y", colors=C_SUBTLE, labelsize=8)
        for sp in ax_spl.spines.values():
            sp.set_color(C_GRID)
        ax_spl.grid(True, color=C_GRID, linewidth=0.5, alpha=0.8)

        # SPL grezzo (fine, semi-trasparente) — mostra ripple TMM reale
        ax_spl.semilogx(freqs, sim.spl_db,
                        color=C_BLUE, linewidth=0.6, alpha=0.22)

        # SPL con smoothing 1/6 oct — curva principale
        ax_spl.semilogx(freqs, spl_smooth,
                        color=C_BLUE, linewidth=2.2, label="SPL sistema (1/6 oct)")

        # Guadagno tromba TMM — offset al livello passband SPL per confronto visivo
        passband_mask = freqs > fc * 1.5
        if np.any(passband_mask):
            spl_ref  = float(np.nanmean(spl_smooth[passband_mask]))
            horn_ref = float(np.nanmean(horn_smooth[passband_mask]))
        else:
            spl_ref  = float(np.nanmean(spl_smooth))
            horn_ref = float(np.nanmean(horn_smooth))
        horn_shifted = horn_smooth + (spl_ref - horn_ref)
        ax_spl.semilogx(freqs, horn_shifted,
                        color=C_ORANGE, linewidth=1.5, linestyle="--", alpha=0.85,
                        label="Guadagno tromba TMM (shape)")

        # Perdite strato limite (Kirchhoff) — invertite per mostrare "quanto si perde"
        if np.nanmax(bl_smooth) > 0.05:
            bl_shifted = spl_smooth - bl_smooth     # mostra la "sottrazione"
            ax_spl.semilogx(freqs, bl_shifted,
                            color=C_RED, linewidth=1.0, linestyle=":",
                            alpha=0.7, label="SPL senza perdite BL")

        ax_spl.axvline(x=fc, color=C_ORANGE, linewidth=1.0, linestyle=":",
                       alpha=0.7, label=f"Fc = {fc:.0f} Hz")

        spl_max = float(np.nanmax(spl_smooth))
        spl_min = max(spl_max - 55.0, float(np.nanmin(spl_smooth)))
        ax_spl.set_xlim(20, 20000)
        ax_spl.set_ylim(spl_min - 3, spl_max + 3)

        # Info fisica
        info_parts = []
        if sim.boundary_layer_loss_avg_db > 0.01:
            info_parts.append(f"BL={sim.boundary_layer_loss_avg_db:.2f} dB")
        if sim.reynolds_throat > 0:
            info_parts.append(f"Re={sim.reynolds_throat:.0f}")
        if sim.goldberg_throat > 0:
            info_parts.append(f"Γ={sim.goldberg_throat:.3f}")
        if info_parts:
            ax_spl.text(0.01, 0.04, "  ".join(info_parts),
                        ha="left", va="bottom", transform=ax_spl.transAxes,
                        color=C_SUBTLE, fontsize=7.5)

        ax_spl.legend(fontsize=7.5, framealpha=0.35, facecolor=C_BG,
                      edgecolor=C_GRID, labelcolor=C_TEXT, loc="lower right")

        # ── Pannello 2: Fase + fase tromba (twin Y) ───────────────────────
        ax_pha = self.fig.add_subplot(312)
        ax_horn_pha = ax_pha.twinx()

        ax_pha.set_facecolor(C_AX)
        ax_pha.set_title("Fase totale + contributo tromba",
                         color=C_TEXT, fontsize=10, pad=8)
        ax_pha.set_ylabel("Fase totale (°)", color=C_PURPLE, fontsize=9)
        ax_horn_pha.set_ylabel("Fase tromba (°)", color=C_ORANGE, fontsize=9)
        ax_pha.tick_params(axis="x", colors=C_SUBTLE, labelsize=8)
        ax_pha.tick_params(axis="y", colors=C_PURPLE, labelsize=8)
        ax_horn_pha.tick_params(axis="y", colors=C_ORANGE, labelsize=8)
        for sp in ax_pha.spines.values():
            sp.set_color(C_GRID)
        ax_pha.grid(True, color=C_GRID, linewidth=0.5, alpha=0.8)
        ax_pha.spines["left"].set_color(C_PURPLE)
        ax_horn_pha.spines["right"].set_color(C_ORANGE)

        # Fase totale sistema (driver + tromba)
        ln_pha, = ax_pha.semilogx(freqs, phase_smooth,
                                   color=C_PURPLE, linewidth=2.0,
                                   label="Fase sistema (1/6 oct)")
        ax_pha.axhline(y=0, color=C_GRID, linewidth=0.6, linestyle=":")

        # Fase tromba (contributo TMM isolato)
        horn_phase_deg_smooth = _smooth_1_6_oct(freqs, np.degrees(sim.horn_phase_rad))
        ln_horn_pha, = ax_horn_pha.semilogx(
            freqs, horn_phase_deg_smooth,
            color=C_ORANGE, linewidth=1.4, linestyle="--", alpha=0.8,
            label="Fase tromba (TMM)")

        ax_pha.axvline(x=fc, color=C_ORANGE, linewidth=0.8, linestyle=":",
                       alpha=0.6)
        ax_pha.set_xlim(20, 20000)

        lines  = [ln_pha, ln_horn_pha]
        labels = [l.get_label() for l in lines]
        ax_pha.legend(lines, labels, fontsize=7.5, framealpha=0.35,
                      facecolor=C_BG, edgecolor=C_GRID, labelcolor=C_TEXT,
                      loc="lower right")

        # ── Pannello 3: Ritardo di gruppo ─────────────────────────────────
        ax_gd = self.fig.add_subplot(313)
        ax_gd.set_facecolor(C_AX)
        _setup_ax(ax_gd, "Ritardo di gruppo", "Frequenza (Hz)", "GD (ms)")

        gd_raw    = np.clip(sim.group_delay_ms, -20, 50)
        gd_smooth = _smooth_1_6_oct(freqs, gd_raw)
        ax_gd.semilogx(freqs, gd_smooth,
                       color=C_GREEN, linewidth=1.8, label="GD (1/6 oct)")
        ax_gd.axhline(y=0, color=C_GRID, linewidth=0.6, linestyle=":")
        ax_gd.axvline(x=fc, color=C_ORANGE, linewidth=0.8, linestyle=":",
                      alpha=0.6)
        ax_gd.set_xlim(20, 20000)
        ax_gd.legend(fontsize=7.5, framealpha=0.35, facecolor=C_BG,
                     edgecolor=C_GRID, labelcolor=C_TEXT)

        # ── Somma fronte/retro opzionale ──────────────────────────────────
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
                ax_spl.semilogx(freqs, result.combined_spl + offset,
                                color=C_GREEN, linewidth=1.3, linestyle="-.",
                                label="Fronte+Retro", alpha=0.8)
                ax_spl.legend(fontsize=7.5, framealpha=0.35, facecolor=C_BG,
                              edgecolor=C_GRID, labelcolor=C_TEXT, loc="lower right")
            except Exception:
                pass

        # ── Warnings ─────────────────────────────────────────────────────
        if sim.warnings:
            short = " | ".join(w.split("]")[0] + "]" for w in sim.warnings[:3])
            self._warn_label.setText(short)
        else:
            self._warn_label.setText("")

        self.fig.tight_layout(pad=1.0)
        self.canvas.draw()

    def _redraw_fallback(self):
        """
        Fallback senza driver: calcola il guadagno TMM della tromba diretta
        tramite _horn_pressure_gain() del simulation engine — non il vecchio HPF.
        Mostra gain (dB), fase TMM (°) e impedenza acustica alla gola (Ω acust.).
        """
        if self._horn_geometry is None:
            return

        try:
            from ..core.simulation_engine import (
                _horn_pressure_gain, _horn_input_impedance
            )
        except ImportError:
            # Improbabile ma safe
            return

        freqs = np.logspace(np.log10(20), np.log10(20000), 500)
        horn_gain_db, horn_phase_rad = _horn_pressure_gain(
            freqs, self._horn_geometry)
        Z_throat = _horn_input_impedance(freqs, self._horn_geometry)
        fc = self._horn_geometry.cutoff_frequency_hz

        gain_smooth  = _smooth_1_6_oct(freqs, horn_gain_db)
        phase_smooth = _smooth_1_6_oct(freqs, np.degrees(horn_phase_rad))
        z_smooth     = _smooth_1_6_oct(freqs, np.abs(Z_throat))

        self.fig.clear()

        # Pannello superiore: guadagno TMM tromba
        ax_gain = self.fig.add_subplot(211)
        _setup_ax(ax_gain, "Guadagno tromba TMM (no driver)", "", "Gain (dB)")
        ax_gain.semilogx(freqs, horn_gain_db,
                         color=C_BLUE, linewidth=0.5, alpha=0.2)
        ax_gain.semilogx(freqs, gain_smooth,
                         color=C_BLUE, linewidth=2.0, label="Guadagno TMM (1/6 oct)")
        ax_pha = ax_gain.twinx()
        ax_pha.semilogx(freqs, phase_smooth,
                        color=C_PURPLE, linewidth=1.4, linestyle="--", alpha=0.8,
                        label="Fase TMM (1/6 oct)")
        ax_pha.set_ylabel("Fase (°)", color=C_PURPLE, fontsize=9)
        ax_pha.tick_params(axis="y", colors=C_PURPLE, labelsize=8)
        ax_pha.spines["right"].set_color(C_PURPLE)
        ax_gain.axvline(x=fc, color=C_ORANGE, linewidth=1.2, linestyle="--",
                        label=f"Fc = {fc:.0f} Hz")
        ax_gain.set_xlim(20, 20000)
        lines  = [ax_gain.lines[-1]] + [ax_pha.lines[0]]
        ax_gain.legend(fontsize=8, framealpha=0.35, facecolor=C_BG,
                       edgecolor=C_GRID, labelcolor=C_TEXT)
        ax_gain.text(0.5, 0.93, "Seleziona un driver per la risposta SPL assoluta",
                     ha="center", va="top", transform=ax_gain.transAxes,
                     color=C_SUBTLE, fontsize=8.5)

        # Pannello inferiore: impedenza acustica alla gola
        ax_z = self.fig.add_subplot(212)
        _setup_ax(ax_z, "Impedenza acustica gola |Zin| (Pa·s/m³)",
                  "Frequenza (Hz)", "|Zin| (Pa·s/m³)")
        ax_z.semilogx(freqs, z_smooth,
                      color=C_GREEN, linewidth=1.8, label="|Zin| gola (1/6 oct)")
        ax_z.axvline(x=fc, color=C_ORANGE, linewidth=1.0, linestyle="--",
                     alpha=0.7)
        ax_z.set_xlim(20, 20000)
        ax_z.legend(fontsize=8, framealpha=0.35, facecolor=C_BG,
                    edgecolor=C_GRID, labelcolor=C_TEXT)

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
        self._horn_geometry = None
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

    def _compute_free_z(self, freqs: np.ndarray) -> np.ndarray:
        """
        Calcola l'impedenza elettrica complessa del driver libero (circuito T&S
        senza carico acustico della tromba).

        Args:
            freqs: array frequenze [Hz]

        Returns:
            array complesso Z(f) [Ω]
        """
        d = self._driver
        if d is None:
            return np.full(len(freqs), np.nan + 0j, dtype=complex)

        omega   = 2.0 * np.pi * freqs
        omega_s = 2.0 * np.pi * d.fs
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
        return Z_coil + Z_mot

    def _draw_impedance_from_sim(self, sim):
        """
        Layout a 2 pannelli per l'impedenza elettrica del driver con carico tromba.

        Pannello 1 — |Z|(f):
            Modulo impedenza libera (tratteggiata blu) vs caricata tromba (verde).
            Evidenzia variazione del picco di risonanza e livello di plateau.

        Pannello 2 — Re(Z) e Im(Z) con tromba (twin Y-axis, arancione/viola):
            Re(Z): parte resistiva — mostra la potenza effettivamente irradiata
                   dal carico acustico rif. alla back-EMF del driver.
            Im(Z): parte reattiva — mostra come la tromba sposta la frequenza
                   di risonanza equivalente elettrica.
            Entrambe anche come dashed per il driver libero (confronto).
        """
        freqs    = sim.frequencies
        Z_loaded = sim.z_electrical_complex          # complex: driver + carico tromba
        Z_free   = self._compute_free_z(freqs)       # complex: driver libero T&S
        d  = self._driver
        fc = self._horn_geometry.cutoff_frequency_hz if self._horn_geometry else None

        driver_label = f" — {d.manufacturer} {d.model}" if d else ""

        self.fig.clear()

        # ── Pannello 1: |Z(f)| confronto libero / con tromba ────────────
        ax_mag = self.fig.add_subplot(211)
        _setup_ax(ax_mag, f"Impedenza elettrica{driver_label}", "", "|Z| (Ω)")

        ax_mag.semilogx(freqs, np.abs(Z_free), color=C_BLUE, linewidth=1.4,
                        linestyle="--", alpha=0.75, label="|Z| driver libero")
        ax_mag.semilogx(freqs, np.abs(Z_loaded), color=C_GREEN, linewidth=2.0,
                        label="|Z| con tromba")

        if d:
            ax_mag.axvline(x=d.fs, color=C_ORANGE, linewidth=1.0, linestyle="--",
                           alpha=0.7, label=f"Fs = {d.fs:.0f} Hz")
            ax_mag.axhline(y=d.re, color=C_RED, linewidth=0.6, linestyle=":",
                           alpha=0.55, label=f"Re = {d.re:.1f} Ω")
        if fc is not None:
            ax_mag.axvline(x=fc, color=C_PURPLE, linewidth=0.8, linestyle=":",
                           alpha=0.7, label=f"Fc = {fc:.0f} Hz")

        z_max = max(np.nanmax(np.abs(Z_loaded)), np.nanmax(np.abs(Z_free))) * 1.15
        ax_mag.set_xlim(10, 20000)
        ax_mag.set_ylim(0, z_max)
        ax_mag.legend(fontsize=7.5, framealpha=0.35, facecolor=C_BG,
                      edgecolor=C_GRID, labelcolor=C_TEXT, loc="upper left")

        # ── Pannello 2: Re(Z) e Im(Z) twin-Y ─────────────────────────────
        ax_re = self.fig.add_subplot(212)
        ax_im = ax_re.twinx()

        ax_re.set_facecolor(C_AX)
        ax_re.set_title("Re(Z) / Im(Z) — effetto carico tromba",
                        color=C_TEXT, fontsize=10, pad=8)
        ax_re.set_xlabel("Frequenza (Hz)", color=C_SUBTLE, fontsize=9)
        ax_re.set_ylabel("Re(Z) (Ω)", color=C_ORANGE, fontsize=9)
        ax_im.set_ylabel("Im(Z) (Ω)", color=C_PURPLE, fontsize=9)
        ax_re.tick_params(axis="x", colors=C_SUBTLE, labelsize=8)
        ax_re.tick_params(axis="y", colors=C_ORANGE, labelsize=8)
        ax_im.tick_params(axis="y", colors=C_PURPLE,  labelsize=8)
        for sp in ax_re.spines.values():
            sp.set_color(C_GRID)
        ax_re.grid(True, color=C_GRID, linewidth=0.5, alpha=0.8)
        ax_re.spines["left"].set_color(C_ORANGE)
        ax_im.spines["right"].set_color(C_PURPLE)

        # Libero — tratteggiato, più sottile
        ax_re.semilogx(freqs, Z_free.real, color=C_ORANGE, linewidth=0.9,
                       linestyle="--", alpha=0.45, label="Re libero")
        ax_im.semilogx(freqs, Z_free.imag, color=C_PURPLE, linewidth=0.9,
                       linestyle="--", alpha=0.45)

        # Con tromba — solido, pieno
        ln_re, = ax_re.semilogx(freqs, Z_loaded.real, color=C_ORANGE,
                                 linewidth=2.0, label="Re(Z) con tromba")
        ln_im, = ax_im.semilogx(freqs, Z_loaded.imag, color=C_PURPLE,
                                 linewidth=2.0, linestyle="--",
                                 label="Im(Z) con tromba")

        ax_re.axhline(y=0, color=C_GRID, linewidth=0.6, linestyle=":")
        ax_im.axhline(y=0, color=C_GRID, linewidth=0.4, linestyle=":", alpha=0.6)
        if fc is not None:
            ax_re.axvline(x=fc, color=C_PURPLE, linewidth=0.8, linestyle=":",
                          alpha=0.5)
        ax_re.set_xlim(10, 20000)

        ax_re.legend([ln_re, ln_im], ["Re(Z) con tromba", "Im(Z) con tromba"],
                     fontsize=7.5, framealpha=0.35, facecolor=C_BG,
                     edgecolor=C_GRID, labelcolor=C_TEXT, loc="upper left")

        self.canvas.draw()

    def _draw_impedance(self, ax_override=None, freqs_override=None, label_free=False):
        """Curva impedenza driver libero (circuito T&S, senza carico tromba)."""
        d = self._driver
        if d is None:
            return

        freqs   = freqs_override if freqs_override is not None else \
                  np.logspace(np.log10(10), np.log10(20000), 800)
        Z_total = np.abs(self._compute_free_z(freqs))

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

    def update_reflex(self, reflex_result, driver=None):
        """
        Aggiorna i tab con il risultato di un calcolo reflex/bandpass.
        Mostra SPL vs frequenza (risposta in camera anecoica) e impedenza driver.
        """
        # SPL / Phase tab  — mostra la risposta in frequenza del reflex
        self.phase_mag_tab.update_from_reflex(reflex_result)
        # Impedance tab — mostra la curva del driver libero (senza tromba)
        if driver is not None:
            self.impedance_tab.update(driver)

    def update_fullrange(self, result: dict, system):
        """
        Aggiorna i tab con il risultato di un sistema Fullrange (CD + SUB).

        Args:
            result: dizionario da ``calculate_combined_response()`` con chiavi
                    frequencies, hf_spl_db, lf_spl_db, combined_spl_db,
                    combined_phase_deg, hpf_db, lpf_db, crossover_freq_hz
            system: FullrangeSystem
        """
        self.phase_mag_tab.update_from_fullrange(result)
        # Impedance: mostra il driver LF
        if system.lf_driver is not None:
            self.impedance_tab.update(system.lf_driver)
