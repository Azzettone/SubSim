"""
Widget per il design della tromba acustica.
Permette di configurare i parametri della tromba e visualizzare i risultati.
"""

try:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
        QDoubleSpinBox, QSpinBox, QComboBox, QPushButton,
        QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
        QFormLayout, QTabWidget, QTextBrowser, QCheckBox
    )
    from PyQt5.QtCore import Qt, pyqtSignal as Signal
    from PyQt5.QtGui import QFont
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
        QDoubleSpinBox, QSpinBox, QComboBox, QPushButton,
        QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
        QFormLayout, QTabWidget, QTextBrowser, QCheckBox
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont

import sys
import numpy as np
from pathlib import Path

# Aggiunge il root del repo al path per permettere import di shared
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ..core.horn_calculator import design_horn, HornGeometry
from ..core.driver_model import DriverModel
from ..core.geometry import (
    design_straight_horn, design_folded_horn, design_2folded_horn,
    auto_select_geometry, CabinetGeometry
)
from ..core.constraint_solver import DimensionalConstraints, solve_with_constraints
from ..core.constants import (
    EXPANSION_TYPES, EXPANSION_LABELS,
    EXPANSION_EXPONENTIAL, SPEED_OF_SOUND, AIR_DENSITY,
    GEOMETRY_STRAIGHT, GEOMETRY_FOLDED, GEOMETRY_2FOLDED
)


class HornDesignerWidget(QWidget):
    """
    Widget per la configurazione e il calcolo della tromba acustica.
    """

    horn_calculated = Signal(object)  # HornGeometry

    def __init__(self, parent=None):
        super().__init__(parent)
        self._horn_geometry = None
        self._cabinet_geometry = None
        self._build_ui()

    def _build_ui(self):
        """Costruisce l'interfaccia del designer tromba."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Titolo
        title = QLabel("Progettazione Tromba Acustica")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        title.setFont(font)
        main_layout.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # ─── Pannello sinistro: parametri ─────────────────────────────────
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)

        # Parametri tromba
        params_group = QGroupBox("Parametri Tromba")
        params_form = QFormLayout(params_group)

        self.fcutoff_spin = QDoubleSpinBox()
        self.fcutoff_spin.setRange(10, 1000)
        self.fcutoff_spin.setValue(70.0)
        self.fcutoff_spin.setSuffix(" Hz")
        self.fcutoff_spin.setDecimals(1)
        params_form.addRow("Frequenza di taglio (Fc):", self.fcutoff_spin)

        self.expansion_combo = QComboBox()
        for exp_type in EXPANSION_TYPES:
            self.expansion_combo.addItem(EXPANSION_LABELS[exp_type], exp_type)
        params_form.addRow("Tipo espansione:", self.expansion_combo)

        self.ratio_spin = QDoubleSpinBox()
        self.ratio_spin.setRange(1.1, 100.0)
        self.ratio_spin.setValue(2.0)
        self.ratio_spin.setDecimals(2)
        params_form.addRow("Rapporto Sbocca/Sgola:", self.ratio_spin)

        self.compression_spin = QDoubleSpinBox()
        self.compression_spin.setRange(1.0, 50.0)
        self.compression_spin.setValue(1.0)
        self.compression_spin.setDecimals(1)
        params_form.addRow("Rapporto compressione gola:", self.compression_spin)

        left_layout.addWidget(params_group)

        # Vincoli dimensionali
        constraints_group = QGroupBox("Vincoli Dimensionali (lascia 0 per nessun limite)")
        constraints_form = QFormLayout(constraints_group)

        self.max_width_spin = QDoubleSpinBox()
        self.max_width_spin.setRange(0, 5000)
        self.max_width_spin.setValue(0)
        self.max_width_spin.setSuffix(" mm")
        constraints_form.addRow("Larghezza max:", self.max_width_spin)

        self.max_height_spin = QDoubleSpinBox()
        self.max_height_spin.setRange(0, 5000)
        self.max_height_spin.setValue(0)
        self.max_height_spin.setSuffix(" mm")
        constraints_form.addRow("Altezza max:", self.max_height_spin)

        self.max_depth_spin = QDoubleSpinBox()
        self.max_depth_spin.setRange(0, 5000)
        self.max_depth_spin.setValue(0)
        self.max_depth_spin.setSuffix(" mm")
        constraints_form.addRow("Profondità max:", self.max_depth_spin)

        left_layout.addWidget(constraints_group)

        # Parametri fisici
        phys_group = QGroupBox("Parametri Fisici")
        phys_form = QFormLayout(phys_group)

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(-20, 50)
        self.temperature_spin.setValue(16.8)
        self.temperature_spin.setSuffix(" °C")
        phys_form.addRow("Temperatura:", self.temperature_spin)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0, 1000)
        self.price_spin.setValue(30.0)
        self.price_spin.setSuffix(" €/m²")
        phys_form.addRow("Prezzo legno:", self.price_spin)

        left_layout.addWidget(phys_group)

        # Pulsante calcola
        calc_btn = QPushButton("🔧 Calcola Geometria")
        calc_btn.setMinimumHeight(45)
        calc_btn.clicked.connect(self._calculate)
        left_layout.addWidget(calc_btn)

        left_layout.addStretch()
        splitter.addWidget(left_widget)

        # ─── Pannello destro: risultati ───────────────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 0, 0, 0)

        result_tabs = QTabWidget()
        right_layout.addWidget(result_tabs, 1)

        # Tab: Parametri calcolati
        self.result_browser = QTextBrowser()
        self.result_browser.setHtml("<p><i>Clicca 'Calcola Geometria' per i risultati</i></p>")
        result_tabs.addTab(self.result_browser, "Parametri Tromba")

        # Tab: Sezioni
        self.sections_table = QTableWidget()
        self.sections_table.setColumnCount(5)
        self.sections_table.setHorizontalHeaderLabels([
            "Sezione", "x (cm)", "Area (cm²)", "Raggio (cm)", "Diametro (cm)"
        ])
        self.sections_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sections_table.setEditTriggers(QTableWidget.NoEditTriggers)
        result_tabs.addTab(self.sections_table, "Sezioni Tromba")

        # Tab: Lista taglio pannelli
        self.panels_table = QTableWidget()
        self.panels_table.setColumnCount(6)
        self.panels_table.setHorizontalHeaderLabels([
            "Pannello", "Larghezza (mm)", "Altezza (mm)", "Spessore (mm)", "Qtà", "Costo (€)"
        ])
        self.panels_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.panels_table.setEditTriggers(QTableWidget.NoEditTriggers)
        result_tabs.addTab(self.panels_table, "Lista Taglio Pannelli")

        splitter.addWidget(right_widget)
        splitter.setSizes([350, 650])

    def _calculate(self):
        """Esegue il calcolo della geometria della tromba."""
        # Recupera il DriverModel direttamente dal current_project
        driver = None
        if hasattr(self.parent(), 'current_project'):
            driver = self.parent().current_project.get("driver")

        # Accetta solo DriverModel (non dict)
        if not isinstance(driver, DriverModel):
            self.result_browser.setHtml(
                "<p><b>Attenzione:</b> Nessun driver selezionato. "
                "Torna alla scheda 'Seleziona Driver' e scegli un driver.</p>"
            )
            return

        # Velocità del suono corretta per temperatura
        try:
            from shared.acoustic_core import speed_of_sound
            c = speed_of_sound(self.temperature_spin.value())
        except ImportError:
            # Fallback: formula diretta (Barometric, ISO 9613-1)
            T = self.temperature_spin.value()
            c = 331.3 * (1 + T / 273.15) ** 0.5

        # Calcola geometria tromba
        try:
            expansion_type = self.expansion_combo.currentData()
            self._horn_geometry = design_horn(
                cutoff_freq_hz=self.fcutoff_spin.value(),
                driver_sd_m2=driver.sd,
                smouth_sthroat_ratio=self.ratio_spin.value(),
                throat_compression_ratio=self.compression_spin.value(),
                expansion_type=expansion_type,
                c=c,
            )
        except Exception as e:
            self.result_browser.setHtml(f"<p><b>Errore calcolo:</b> {e}</p>")
            return

        # Applica vincoli dimensionali
        max_w = self.max_width_spin.value() or None
        max_h = self.max_height_spin.value() or None
        max_d = self.max_depth_spin.value() or None

        constraints = DimensionalConstraints(
            max_width_mm=max_w,
            max_height_mm=max_h,
            max_depth_mm=max_d
        )

        if constraints.has_constraints():
            result = solve_with_constraints(self._horn_geometry, constraints)
            self._cabinet_geometry = result.cabinet
        else:
            self._cabinet_geometry = design_straight_horn(self._horn_geometry)

        # Mostra risultati
        self._show_results(driver)
        self._show_sections()
        self._show_panels()

        # Salva nel progetto corrente
        if hasattr(self.parent(), 'current_project'):
            self.parent().current_project["parameters"] = {
                "fcutoff": self.fcutoff_spin.value(),
                "expansion_type": expansion_type,
                "smouth_ratio": self.ratio_spin.value(),
                "compression_ratio": self.compression_spin.value(),
                "horn_length_m": self._horn_geometry.horn_length_m,
                "flare_rate_m": self._horn_geometry.flare_rate_m,
                "throat_area_m2": self._horn_geometry.throat_area_m2,
                "mouth_area_m2": self._horn_geometry.mouth_area_m2,
            }

        self.horn_calculated.emit(self._horn_geometry)

        if hasattr(self.parent(), 'update_status'):
            self.parent().update_status(
                f"Tromba calcolata: L={self._horn_geometry.horn_length_m*100:.1f}cm, "
                f"m={self._horn_geometry.flare_rate_m:.4f}m⁻¹"
            )

    def _show_results(self, driver):
        """Mostra i risultati del calcolo nella tab parametri."""
        g = self._horn_geometry
        c = self._cabinet_geometry

        html = f"""
        <style>
            table {{ width: 100%; border-collapse: collapse; }}
            td {{ padding: 4px 8px; }}
            td:first-child {{ font-weight: bold; color: #A0A0C0; width: 55%; }}
            tr:nth-child(even) {{ background-color: rgba(255,255,255,0.05); }}
            h3 {{ color: #7C9EF0; margin-top: 12px; }}
        </style>
        <h3>Parametri Calcolati - {driver.manufacturer} {driver.model}</h3>
        <table>
        <tr><td>Tipo espansione</td><td>{g.expansion_type}</td></tr>
        <tr><td>Frequenza di taglio</td><td>{g.cutoff_frequency_hz:.1f} Hz</td></tr>
        <tr><td>Flare rate (m)</td><td>{g.flare_rate_m:.4f} m⁻¹</td></tr>
        <tr><td>Area gola</td><td>{g.throat_area_m2*10000:.2f} cm² (r={g.throat_radius_m*100:.2f}cm)</td></tr>
        <tr><td>Area bocca</td><td>{g.mouth_area_m2*10000:.2f} cm² (r={g.mouth_radius_m*100:.2f}cm)</td></tr>
        <tr><td>Rapporto espansione</td><td>{g.expansion_ratio:.2f}</td></tr>
        <tr><td>Lunghezza tromba</td><td>{g.horn_length_m*100:.2f} cm ({g.horn_length_m:.4f} m)</td></tr>
        <tr><td>Impedenza alla gola</td><td>{g.throat_impedance:.2f} Pa·s/m³</td></tr>
        <tr><td>Volume accoppiamento</td><td>{g.coupling_volume_m3*1000:.2f} L ({g.coupling_volume_m3:.4f} m³)</td></tr>
        </table>

        <h3>Dimensioni Cabinet ({c.geometry_type})</h3>
        <table>
        <tr><td>Larghezza totale</td><td>{c.total_width_mm:.1f} mm</td></tr>
        <tr><td>Altezza totale</td><td>{c.total_height_mm:.1f} mm</td></tr>
        <tr><td>Profondità totale</td><td>{c.total_depth_mm:.1f} mm</td></tr>
        <tr><td>Volume esterno</td><td>{c.volume_m3*1000:.2f} L</td></tr>
        <tr><td>Area totale pannelli</td><td>{c.total_panel_area_m2():.3f} m²</td></tr>
        <tr><td>Costo materiale stimato</td><td>{c.total_cost(self.price_spin.value()):.2f} €</td></tr>
        </table>
        """

        if c.fold_points:
            html += "<h3>Punti di Piega</h3><table>"
            for i, fold in enumerate(c.fold_points, 1):
                html += f"<tr><td>Piega {i}</td><td>x={fold.x_m*100:.1f}cm, direzione={fold.direction}</td></tr>"
            html += "</table>"

        self.result_browser.setHtml(html)

    def _show_sections(self):
        """Popola la tabella delle sezioni tromba."""
        sections = self._horn_geometry.sections
        self.sections_table.setRowCount(len(sections))

        for row, s in enumerate(sections):
            items = [
                f"{row+1}",
                f"{s.x_m*100:.2f}",
                f"{s.area_m2*10000:.2f}",
                f"{s.radius_m*100:.2f}",
                f"{s.radius_m*200:.2f}",
            ]
            for col, text in enumerate(items):
                self.sections_table.setItem(row, col, QTableWidgetItem(text))

    def _show_panels(self):
        """Popola la tabella della lista di taglio pannelli."""
        panels = self._cabinet_geometry.panels
        self.panels_table.setRowCount(len(panels))

        for row, panel in enumerate(panels):
            cost = panel.cost(self.price_spin.value())
            items = [
                panel.name,
                f"{panel.width_mm:.1f}",
                f"{panel.height_mm:.1f}",
                f"{panel.thickness_mm:.0f}",
                f"{panel.quantity}",
                f"{cost:.2f}",
            ]
            for col, text in enumerate(items):
                self.panels_table.setItem(row, col, QTableWidgetItem(text))
