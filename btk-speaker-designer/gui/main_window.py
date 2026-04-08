"""
Finestra principale di BTK Speaker Designer.

Layout (corrisponde al mockup concordato):

  ┌───────────────────────────────────────────────────────┐
  │  TOOLBAR: Nuovo | Apri | Salva | ── | DXF | PDF       │
  ├──────────────────┬────────────────────────────────────┤
  │  INPUT UTENTE    │                                    │
  │  (tipo, driver,  │       GRAFICA 2D                   │
  │   Fc, espans.,   │       Profilo tromba               │
  │   ratio, vinc.)  │                                    │
  ├──────────────────┤                                    │
  │  MODIFICA DESIGN │                                    │
  │  (geom, temp,    │                                    │
  │   prezzo legno)  │                                    │
  ├──────────────────┴────────────────────────────────────┤
  │  TAB: Phase/Magnitude | Impedance | Panel List        │
  ├───────────────────────────────────────────────────────┤
  │  Status bar                                           │
  └───────────────────────────────────────────────────────┘
"""

import sys
import json
from pathlib import Path

# Assicura che il root del repo sia nel path per import di 'shared'
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from PyQt5.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QStatusBar, QToolBar, QAction, QFileDialog,
        QMessageBox, QSizePolicy, QApplication
    )
    from PyQt5.QtCore import Qt, QSize, QTimer
    from PyQt5.QtGui import QFont, QIcon
    PYQT_AVAILABLE = True
except ImportError:
    try:
        from PySide6.QtWidgets import (
            QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QSplitter, QStatusBar, QToolBar, QAction, QFileDialog,
            QMessageBox, QSizePolicy, QApplication
        )
        from PySide6.QtCore import Qt, QSize, QTimer
        from PySide6.QtGui import QFont, QIcon
        PYQT_AVAILABLE = True
    except ImportError:
        PYQT_AVAILABLE = False


if PYQT_AVAILABLE:

    class MainWindow(QMainWindow):
        """
        Finestra principale di BTK Speaker Designer.
        Implementa il layout a pannelli fissi concordato nel mockup.
        """

        def __init__(self):
            super().__init__()

            from ..database.db_manager import initialize_database
            initialize_database()

            self.setWindowTitle("BTK Speaker Designer  v1.0")
            self.setMinimumSize(1280, 820)
            self.resize(1500, 950)

            self._horn_geometry = None
            self._cabinet_geometry = None
            self._driver = None

            self._apply_style()
            self._build_toolbar()
            self._build_central_widget()
            self._build_status_bar()

        # ── Stile ──────────────────────────────────────────────────────────

        def _apply_style(self):
            try:
                from shared.ui_components import QSS_MAIN
                self.setStyleSheet(QSS_MAIN)
            except ImportError:
                self.setStyleSheet("""
                    QMainWindow, QWidget {
                        background-color: #12121E; color: #C0C0E0;
                    }
                    QGroupBox {
                        border: 1px solid #2A2A44; border-radius: 4px;
                        margin-top: 8px; padding-top: 6px;
                        font-weight: bold; color: #A0A0C0;
                    }
                    QGroupBox::title { subcontrol-origin: margin; left: 8px; }
                    QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit {
                        background-color: #1E1E32; border: 1px solid #2A2A44;
                        border-radius: 3px; padding: 3px 6px;
                        color: #C0C0E0; min-height: 22px;
                    }
                    QPushButton {
                        background-color: #2A2A44; border: 1px solid #4A4A6A;
                        border-radius: 4px; padding: 5px 12px; color: #C0C0E0;
                    }
                    QPushButton:hover  { background-color: #3A3A5A; }
                    QPushButton:pressed { background-color: #1A1A2E; }
                    QTabWidget::pane  { border: 1px solid #2A2A44; }
                    QTabBar::tab {
                        background: #1A1A2E; color: #808090;
                        padding: 6px 16px; border: 1px solid #2A2A44;
                        border-bottom: none;
                    }
                    QTabBar::tab:selected { background: #2A2A44; color: #C0C0E0; }
                    QTableWidget {
                        background-color: #1A1A2E;
                        alternate-background-color: #1E1E32;
                        gridline-color: #2A2A44; color: #C0C0E0;
                    }
                    QHeaderView::section {
                        background-color: #2A2A44; color: #A0A0C0;
                        padding: 4px; border: 1px solid #1A1A2E;
                    }
                    QStatusBar { background-color: #0E0E1A; color: #808090; }
                    QToolBar   { background-color: #16162A; border-bottom: 1px solid #2A2A44; }
                    QSplitter::handle { background-color: #2A2A44; width: 4px; height: 4px; }
                    QCheckBox { color: #C0C0E0; }
                    QTextBrowser { background-color: #1A1A2E; color: #C0C0E0;
                                   border: 1px solid #2A2A44; }
                """)

        # ── Toolbar ───────────────────────────────────────────────────────

        def _build_toolbar(self):
            toolbar = QToolBar("Principale")
            toolbar.setMovable(False)
            toolbar.setIconSize(QSize(18, 18))
            self.addToolBar(toolbar)

            for label, shortcut, slot, tip in [
                ("🗋  Nuovo",       "Ctrl+N", self._action_new,  "Nuovo progetto"),
                ("📂  Apri",        "Ctrl+O", self._action_open, "Apri progetto"),
                ("💾  Salva",       "Ctrl+S", self._action_save, "Salva progetto"),
            ]:
                act = QAction(label, self)
                act.setShortcut(shortcut)
                act.setToolTip(f"{tip} ({shortcut})")
                act.triggered.connect(slot)
                toolbar.addAction(act)

            toolbar.addSeparator()

            for label, slot, tip in [
                ("📐  Esporta DXF", self._action_export_dxf, "Esporta DXF per CNC"),
                ("📄  Esporta PDF", self._action_export_pdf, "Esporta report PDF"),
            ]:
                act = QAction(label, self)
                act.setToolTip(tip)
                act.triggered.connect(slot)
                toolbar.addAction(act)

            toolbar.addSeparator()
            act_about = QAction("ℹ  Info", self)
            act_about.triggered.connect(self._action_about)
            toolbar.addAction(act_about)

        # ── Layout centrale ───────────────────────────────────────────────

        def _build_central_widget(self):
            central = QWidget()
            self.setCentralWidget(central)
            root_layout = QVBoxLayout(central)
            root_layout.setContentsMargins(6, 6, 6, 4)
            root_layout.setSpacing(4)

            # Splitter verticale: [top] / [analysis_tabs]
            self.vsplit = QSplitter(Qt.Vertical)
            root_layout.addWidget(self.vsplit)

            # ── Top widget ─────────────────────────────────────────────────
            top_widget = QWidget()
            top_layout = QHBoxLayout(top_widget)
            top_layout.setContentsMargins(0, 0, 0, 0)
            top_layout.setSpacing(0)

            # Splitter orizzontale: [left_col] / [horn_view]
            self.hsplit = QSplitter(Qt.Horizontal)
            top_layout.addWidget(self.hsplit)

            # Colonna sinistra: [input_panel] / [design_panel]
            self.left_vsplit = QSplitter(Qt.Vertical)

            from .input_panel import InputPanel
            from .design_panel import DesignPanel

            self.input_panel = InputPanel(self)
            self.design_panel = DesignPanel(self)
            self.left_vsplit.addWidget(self.input_panel)
            self.left_vsplit.addWidget(self.design_panel)
            self.left_vsplit.setSizes([530, 300])
            self.left_vsplit.setMinimumWidth(410)

            self.hsplit.addWidget(self.left_vsplit)

            # Grafica 2D a destra
            from .horn_view import HornView
            self.horn_view = HornView(self)
            self.hsplit.addWidget(self.horn_view)
            self.hsplit.setSizes([430, 870])

            self.vsplit.addWidget(top_widget)

            # ── Tab di analisi in basso ────────────────────────────────────
            from .analysis_tabs import AnalysisTabs
            self.analysis_tabs = AnalysisTabs(self)
            self.analysis_tabs.setMinimumHeight(200)
            self.vsplit.addWidget(self.analysis_tabs)
            self.vsplit.setSizes([480, 400])

            # ── Connessione segnali ────────────────────────────────────────
            self.input_panel.calculate_requested.connect(self._on_calculate)
            self.input_panel.driver_changed.connect(self._on_driver_changed)
            self.input_panel.geometry_changed.connect(self._on_geometry_changed)

        def _build_status_bar(self):
            self.status_bar = QStatusBar()
            self.setStatusBar(self.status_bar)
            self.status_bar.showMessage(
                "BTK Speaker Designer  —  Seleziona un driver e premi  ⚙ Calcola."
            )

        # ── Calcolo principale ────────────────────────────────────────────

        def _on_calculate(self, params: dict):
            if params.get("error") == "no_driver":
                QTimer.singleShot(0, lambda: QMessageBox.warning(
                    self, "Driver mancante",
                    "Seleziona un driver dal menu a tendina o dal selettore (...)."
                ))
                return

            driver = params["driver"]
            self._driver = driver

            # Velocità del suono in funzione della temperatura
            temp_c = 16.8  # temperatura di default (orignal Excel: 16.8°C)
            try:
                from shared.acoustic_core import speed_of_sound
                c = speed_of_sound(temp_c)
            except ImportError:
                c = 331.3 * (1 + temp_c / 273.15) ** 0.5

            # 1. Calcola geometria tromba
            from ..core.horn_calculator import design_horn
            try:
                self._horn_geometry = design_horn(
                    cutoff_freq_hz=params["fc_hz"],
                    driver_sd_m2=driver.sd,
                    smouth_sthroat_ratio=params["smouth_ratio"],
                    throat_compression_ratio=params["compression_ratio"],
                    expansion_type=params["expansion_type"],
                    hypex_T=params.get("hypex_T", 0.5),
                    c=c,
                    n_sections=params.get("n_sections", 8),
                )
            except Exception as e:
                _err = str(e)
                QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Errore calcolo tromba", _err))
                return

            # 2. Geometria cabinet con eventuale fold / vincoli
            geometry_type = params.get("geometry_type", "straight")
            wood_price    = 30.0  # costo MDF di default €/m²

            from ..core.constraint_solver import DimensionalConstraints, solve_with_constraints
            from ..core.geometry import (
                design_straight_horn, design_folded_horn, design_2folded_horn
            )
            from ..core.constants import GEOMETRY_FOLDED, GEOMETRY_2FOLDED

            constraints = DimensionalConstraints(
                max_width_mm=params.get("max_width_mm"),
                max_height_mm=params.get("max_height_mm"),
                max_depth_mm=params.get("max_depth_mm"),
            )
            try:
                if constraints.has_constraints():
                    result = solve_with_constraints(self._horn_geometry, constraints)
                    self._cabinet_geometry = result.cabinet
                elif geometry_type == GEOMETRY_FOLDED:
                    self._cabinet_geometry = design_folded_horn(self._horn_geometry)
                elif geometry_type == GEOMETRY_2FOLDED:
                    self._cabinet_geometry = design_2folded_horn(self._horn_geometry)
                else:
                    self._cabinet_geometry = design_straight_horn(self._horn_geometry)
            except Exception as e:
                _err = str(e)
                QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Errore geometria cabinet", _err))
                return

            # 3. Aggiorna tutti i widget
            self.horn_view.update_horn(self._horn_geometry, self._cabinet_geometry)
            self.analysis_tabs.update_all(
                self._horn_geometry, self._cabinet_geometry, driver, wood_price
            )
            self.design_panel.update_cabinet_summary(self._cabinet_geometry)

            g = self._horn_geometry
            cab = self._cabinet_geometry
            self.status_bar.showMessage(
                f"Driver: {driver.manufacturer} {driver.model}  │  "
                f"Fc = {g.cutoff_frequency_hz:.0f} Hz  │  "
                f"L = {g.horn_length_m*100:.1f} cm  │  "
                f"m = {g.flare_rate_m:.4f} m⁻¹  │  "
                f"Cabinet: {cab.total_width_mm:.0f}×{cab.total_height_mm:.0f}×"
                f"{cab.total_depth_mm:.0f} mm"
            )

        def _on_driver_changed(self, driver):
            """Aggiorna la curva impedenza appena cambia il driver."""
            self._driver = driver
            self.analysis_tabs.impedance_tab.update(driver)

        def _on_geometry_changed(self, geometry_type: str):
            """Ricalcola il cabinet se c'è già una geometria tromba."""
            if self._horn_geometry is None:
                return
            from ..core.geometry import (
                design_straight_horn, design_folded_horn, design_2folded_horn
            )
            from ..core.constants import GEOMETRY_FOLDED, GEOMETRY_2FOLDED
            try:
                if geometry_type == GEOMETRY_FOLDED:
                    self._cabinet_geometry = design_folded_horn(self._horn_geometry)
                elif geometry_type == GEOMETRY_2FOLDED:
                    self._cabinet_geometry = design_2folded_horn(self._horn_geometry)
                else:
                    self._cabinet_geometry = design_straight_horn(self._horn_geometry)

                self.horn_view.update_horn(self._horn_geometry, self._cabinet_geometry)
                self.design_panel.update_cabinet_summary(self._cabinet_geometry)
                wood_price = 30.0  # costo MDF di default €/m²
                self.analysis_tabs.panel_list_tab.update(self._cabinet_geometry, wood_price)
            except Exception as e:
                self.status_bar.showMessage(f"Errore cambio geometria: {e}")

        # ── Azioni toolbar ────────────────────────────────────────────────

        def _action_new(self):
            self._horn_geometry = None
            self._cabinet_geometry = None
            self._driver = None
            if MATPLOTLIB_AVAILABLE_GUARD():
                self.horn_view._draw_placeholder()
            self.design_panel.summary_label.setText("—\n—\n—")
            self.status_bar.showMessage(
                "Nuovo progetto  —  Seleziona un driver e premi  ⚙ Calcola."
            )

        def _action_open(self):
            path, _ = QFileDialog.getOpenFileName(
                self, "Apri Progetto", "",
                "Progetti BTK (*.btk.json);;Tutti i file (*)"
            )
            if not path:
                return
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.input_panel.set_params(data.get("input", {}))
                self.design_panel.set_params(data.get("design", {}))
                self.status_bar.showMessage(f"Progetto aperto: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Errore apertura", str(e))

        def _action_save(self):
            path, _ = QFileDialog.getSaveFileName(
                self, "Salva Progetto", "",
                "Progetti BTK (*.btk.json)"
            )
            if not path:
                return
            if not path.endswith(".btk.json"):
                path += ".btk.json"
            try:
                input_params = self.input_panel.get_params()
                design_params = self.design_panel.get_params()
                driver = input_params.pop("driver", None)
                if driver and hasattr(driver, "to_dict"):
                    input_params["driver_model"] = driver.model
                    input_params["driver_dict"] = driver.to_dict()
                data = {
                    "version": "1.0",
                    "input": input_params,
                    "design": design_params,
                }
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self.status_bar.showMessage(f"Progetto salvato: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Errore salvataggio", str(e))

        def _action_export_dxf(self):
            if self._cabinet_geometry is None:
                QMessageBox.information(self, "Export DXF",
                                        "Calcola prima una geometria completa.")
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "Esporta DXF", "", "File DXF (*.dxf)"
            )
            if not path:
                return
            try:
                from ..exporters.dxf_export import export_cabinet_dxf
                export_cabinet_dxf(self._cabinet_geometry, path)
                self.status_bar.showMessage(f"DXF esportato: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Errore export DXF", str(e))

        def _action_export_pdf(self):
            if self._horn_geometry is None:
                QMessageBox.information(self, "Export PDF",
                                        "Calcola prima una geometria completa.")
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "Esporta Report PDF", "", "File PDF (*.pdf)"
            )
            if not path:
                return
            try:
                from ..exporters.pdf_report import generate_pdf_report
                project_data = {
                    "driver": self._driver,
                }
                generate_pdf_report(
                    project_data=project_data,
                    horn_geometry=self._horn_geometry,
                    cabinet=self._cabinet_geometry,
                    output_path=path,
                )
                self.status_bar.showMessage(f"Report PDF esportato: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Errore export PDF", str(e))

        def _action_about(self):
            QMessageBox.about(
                self, "BTK Speaker Designer",
                """<h2>BTK Speaker Designer  v1.0</h2>
                <p>Software professionale per il design di altoparlanti e trombe acustiche.</p>
                <hr>
                <p><b>Caratteristiche:</b></p>
                <ul>
                <li>Trombe: esponenziale, conica, tractrix, hypex</li>
                <li>Geometrie cabinet: Straight / Folded / 2-Folded</li>
                <li>Database driver: RCF, Beyma, B&amp;C, LaVoce</li>
                <li>Curva impedenza Z(f) con modello T&amp;S</li>
                <li>Phase/Magnitude e somma fronte/retro</li>
                <li>Vincoli dimensionali con risoluzione automatica</li>
                <li>Export DXF (CNC) e Report PDF</li>
                </ul>
                <p>Basato sul foglio Horn Calculator originale.</p>"""
            )


def MATPLOTLIB_AVAILABLE_GUARD() -> bool:
    """Guard per chiamate a metodi matplotlib opzionali."""
    try:
        import matplotlib
        return True
    except ImportError:
        return False


def create_app():
    """Crea e restituisce (QApplication, MainWindow)."""
    if not PYQT_AVAILABLE:
        raise ImportError(
            "PyQt5 o PySide6 non trovato.\n"
            "Installa con:  pip install PyQt5"
        )
    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    return app, window
