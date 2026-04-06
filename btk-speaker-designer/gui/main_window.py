"""
Finestra principale di BTK Speaker Designer.
Entry point dell'interfaccia grafica PyQt5/PySide6.
"""

try:
    from PyQt5.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTabWidget, QStatusBar, QMenuBar, QMenu, QAction,
        QFileDialog, QMessageBox, QSplitter, QLabel
    )
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QFont, QIcon
    PYQT_AVAILABLE = True
except ImportError:
    try:
        from PySide6.QtWidgets import (
            QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QTabWidget, QStatusBar, QMenuBar, QMenu, QAction,
            QFileDialog, QMessageBox, QSplitter, QLabel
        )
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QFont, QIcon
        PYQT_AVAILABLE = True
    except ImportError:
        PYQT_AVAILABLE = False

import json
import sys
from pathlib import Path

# Aggiunge il parent al path per i moduli condivisi
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ..core.constants import SPEAKER_TYPES, GEOMETRY_TYPES
from ..database.db_manager import initialize_database


if PYQT_AVAILABLE:
    class MainWindow(QMainWindow):
        """
        Finestra principale di BTK Speaker Designer.
        Coordina tutti i pannelli e gestisce il flusso dell'applicazione.
        """

        def __init__(self):
            super().__init__()
            # Inizializza database
            initialize_database()

            self.setWindowTitle("BTK Speaker Designer v1.0")
            self.setMinimumSize(1200, 800)
            self.resize(1400, 900)

            # Applica stile
            self._apply_style()

            # Costruisce UI
            self._build_menu()
            self._build_central_widget()
            self._build_status_bar()

            # Dati correnti del progetto
            self.current_project = {
                "name": "Nuovo Progetto",
                "speaker_type": None,
                "geometry_type": None,
                "driver": None,
                "horn": None,
                "parameters": {},
            }

        def _apply_style(self):
            """Applica il tema scuro all'applicazione."""
            try:
                import sys
                sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                from shared.ui_components import QSS_MAIN
                self.setStyleSheet(QSS_MAIN)
            except ImportError:
                pass

        def _build_menu(self):
            """Costruisce la barra dei menu."""
            menubar = self.menuBar()

            # Menu File
            file_menu = menubar.addMenu("&File")

            new_action = QAction("&Nuovo Progetto", self)
            new_action.setShortcut("Ctrl+N")
            new_action.triggered.connect(self._new_project)
            file_menu.addAction(new_action)

            open_action = QAction("&Apri Progetto...", self)
            open_action.setShortcut("Ctrl+O")
            open_action.triggered.connect(self._open_project)
            file_menu.addAction(open_action)

            save_action = QAction("&Salva Progetto", self)
            save_action.setShortcut("Ctrl+S")
            save_action.triggered.connect(self._save_project)
            file_menu.addAction(save_action)

            file_menu.addSeparator()

            exit_action = QAction("E&sci", self)
            exit_action.setShortcut("Ctrl+Q")
            exit_action.triggered.connect(self.close)
            file_menu.addAction(exit_action)

            # Menu Esporta
            export_menu = menubar.addMenu("&Esporta")

            dxf_action = QAction("Esporta &DXF (CNC)...", self)
            dxf_action.triggered.connect(self._export_dxf)
            export_menu.addAction(dxf_action)

            pdf_action = QAction("Esporta &Report PDF...", self)
            pdf_action.triggered.connect(self._export_pdf)
            export_menu.addAction(pdf_action)

            cutlist_action = QAction("Lista &Taglio Pannelli...", self)
            cutlist_action.triggered.connect(self._export_cutlist)
            export_menu.addAction(cutlist_action)

            # Menu Aiuto
            help_menu = menubar.addMenu("&Aiuto")
            about_action = QAction("&Informazioni...", self)
            about_action.triggered.connect(self._show_about)
            help_menu.addAction(about_action)

        def _build_central_widget(self):
            """Costruisce il widget centrale con tab."""
            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.setContentsMargins(8, 8, 8, 8)

            # Tab principale
            self.tab_widget = QTabWidget()
            layout.addWidget(self.tab_widget)

            # Importa e crea le tab
            self._create_tabs()

        def _create_tabs(self):
            """Crea le tab dell'applicazione."""
            try:
                from .speaker_type_selector import SpeakerTypeSelectorWidget
                self.type_selector = SpeakerTypeSelectorWidget(self)
                self.tab_widget.addTab(self.type_selector, "1. Tipo Speaker")
            except Exception as e:
                placeholder = QLabel(f"Tipo Speaker\n\nErrore: {e}")
                placeholder.setAlignment(Qt.AlignCenter)
                self.tab_widget.addTab(placeholder, "1. Tipo Speaker")

            try:
                from .driver_selector import DriverSelectorWidget
                self.driver_selector = DriverSelectorWidget(self)
                self.tab_widget.addTab(self.driver_selector, "2. Seleziona Driver")
            except Exception as e:
                placeholder = QLabel(f"Driver\n\nErrore: {e}")
                placeholder.setAlignment(Qt.AlignCenter)
                self.tab_widget.addTab(placeholder, "2. Driver")

            try:
                from .horn_designer import HornDesignerWidget
                self.horn_designer = HornDesignerWidget(self)
                self.tab_widget.addTab(self.horn_designer, "3. Progetta Tromba")
            except Exception as e:
                placeholder = QLabel(f"Tromba\n\nErrore: {e}")
                placeholder.setAlignment(Qt.AlignCenter)
                self.tab_widget.addTab(placeholder, "3. Tromba")

            try:
                from .visualization import VisualizationWidget
                self.visualization = VisualizationWidget(self)
                self.tab_widget.addTab(self.visualization, "4. Visualizzazione")
            except Exception as e:
                placeholder = QLabel(f"Visualizzazione\n\nErrore: {e}")
                placeholder.setAlignment(Qt.AlignCenter)
                self.tab_widget.addTab(placeholder, "4. Visualizzazione")

        def _build_status_bar(self):
            """Costruisce la barra di stato."""
            self.status_bar = QStatusBar()
            self.setStatusBar(self.status_bar)
            self.status_bar.showMessage("BTK Speaker Designer pronto.")

        def update_status(self, message: str):
            """Aggiorna il messaggio nella barra di stato."""
            self.status_bar.showMessage(message)

        def set_speaker_type(self, speaker_type: str):
            """Imposta il tipo di speaker corrente."""
            self.current_project["speaker_type"] = speaker_type
            self.update_status(f"Tipo selezionato: {speaker_type}")

        def set_driver(self, driver):
            """Imposta il driver corrente."""
            self.current_project["driver"] = driver
            if driver:
                self.update_status(f"Driver: {driver.manufacturer} {driver.model}")

        def _new_project(self):
            """Crea un nuovo progetto."""
            self.current_project = {
                "name": "Nuovo Progetto",
                "speaker_type": None,
                "geometry_type": None,
                "driver": None,
                "horn": None,
                "parameters": {},
            }
            self.tab_widget.setCurrentIndex(0)
            self.update_status("Nuovo progetto creato.")

        def _open_project(self):
            """Apre un progetto da file JSON."""
            path, _ = QFileDialog.getOpenFileName(
                self, "Apri Progetto", "", "Progetti BTK (*.btk.json);;Tutti i file (*)"
            )
            if path:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        self.current_project = json.load(f)
                    self.update_status(f"Progetto aperto: {path}")
                except Exception as e:
                    QMessageBox.critical(self, "Errore", f"Impossibile aprire il file:\n{e}")

        def _save_project(self):
            """Salva il progetto corrente su file JSON."""
            path, _ = QFileDialog.getSaveFileName(
                self, "Salva Progetto", "", "Progetti BTK (*.btk.json)"
            )
            if path:
                if not path.endswith(".btk.json"):
                    path += ".btk.json"
                try:
                    # Serializza solo dati serializzabili
                    save_data = {
                        k: v for k, v in self.current_project.items()
                        if isinstance(v, (str, int, float, bool, list, dict, type(None)))
                    }
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(save_data, f, indent=2, ensure_ascii=False)
                    self.update_status(f"Progetto salvato: {path}")
                except Exception as e:
                    QMessageBox.critical(self, "Errore", f"Impossibile salvare:\n{e}")

        def _export_dxf(self):
            """Esporta il progetto in formato DXF."""
            QMessageBox.information(
                self, "Export DXF",
                "Funzione export DXF disponibile dopo aver calcolato una geometria completa."
            )

        def _export_pdf(self):
            """Esporta report PDF."""
            QMessageBox.information(
                self, "Export PDF",
                "Funzione export PDF disponibile dopo aver calcolato una geometria completa."
            )

        def _export_cutlist(self):
            """Esporta lista di taglio pannelli."""
            QMessageBox.information(
                self, "Lista Taglio",
                "Lista taglio disponibile dopo aver calcolato una geometria completa."
            )

        def _show_about(self):
            """Mostra la finestra Informazioni."""
            QMessageBox.about(
                self,
                "BTK Speaker Designer",
                """<h2>BTK Speaker Designer v1.0</h2>
                <p>Software per il design di altoparlanti professionali.</p>
                <p>Caratteristiche:</p>
                <ul>
                <li>Design trombe acustiche (SUB, CD, FULLRANGE)</li>
                <li>Database driver: RCF, Beyma, B&C, LaVoce</li>
                <li>Database trombe commerciali</li>
                <li>Calcolo somma in fase fronte/retro</li>
                <li>Geometrie Straight/Folded/2-Folded</li>
                <li>Vincoli dimensionali</li>
                <li>Export DXF/STL/PDF</li>
                </ul>
                <p>Basato sul foglio di calcolo Horn Calculator originale.</p>"""
            )


def create_app():
    """Crea e restituisce l'applicazione Qt e la finestra principale."""
    if not PYQT_AVAILABLE:
        raise ImportError(
            "PyQt5 o PySide6 non trovato. "
            "Installa con: pip install PyQt5\n"
            "oppure: pip install PySide6"
        )

    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    return app, window
