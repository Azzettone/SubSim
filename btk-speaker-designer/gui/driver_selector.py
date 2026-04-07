"""
Widget per la selezione del driver dal database.
Permette di filtrare per produttore e tipo e visualizzare i parametri T&S.
"""

try:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
        QComboBox, QTableWidget, QTableWidgetItem, QPushButton,
        QHeaderView, QSplitter, QTextBrowser, QDoubleSpinBox,
        QFormLayout, QFrame
    )
    from PyQt5.QtCore import Qt, pyqtSignal as Signal
    from PyQt5.QtGui import QColor, QFont
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
        QComboBox, QTableWidget, QTableWidgetItem, QPushButton,
        QHeaderView, QSplitter, QTextBrowser, QDoubleSpinBox,
        QFormLayout, QFrame
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QColor, QFont

from ..core.driver_model import DriverModel
from ..database.db_manager import (
    get_manufacturers, get_drivers_by_type, get_driver_by_model,
    initialize_database
)
from ..core.constants import SPEAKER_TYPE_SUB, SPEAKER_TYPE_CD, SPEAKER_TYPE_FULLRANGE


class DriverSelectorWidget(QWidget):
    """
    Widget per la selezione e visualizzazione dei driver dal database.
    """

    driver_selected = Signal(object)  # DriverModel

    def __init__(self, parent=None):
        super().__init__(parent)
        initialize_database()
        self._selected_driver = None
        self._build_ui()
        self._load_drivers()

    def _build_ui(self):
        """Costruisce l'interfaccia del selettore driver."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # Titolo
        title = QLabel("Seleziona il Driver dal Database")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        title.setFont(font)
        main_layout.addWidget(title)

        # Splitter: sinistra=filtri+lista, destra=dettagli
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # ─── Pannello sinistro: filtri + tabella ──────────────────────────
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Filtri
        filter_group = QGroupBox("Filtri")
        filter_layout = QFormLayout(filter_group)

        self.manufacturer_combo = QComboBox()
        self.manufacturer_combo.addItem("Tutti i produttori", None)
        for m in get_manufacturers():
            self.manufacturer_combo.addItem(m, m)
        self.manufacturer_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addRow("Produttore:", self.manufacturer_combo)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Tutti i tipi", None)
        self.type_combo.addItem("Subwoofer", "subwoofer")
        self.type_combo.addItem("Woofer", "woofer")
        self.type_combo.addItem("Compression Driver", "compression_driver")
        self.type_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addRow("Tipo:", self.type_combo)

        left_layout.addWidget(filter_group)

        # Tabella driver
        self.driver_table = QTableWidget()
        self.driver_table.setColumnCount(7)
        self.driver_table.setHorizontalHeaderLabels([
            "Produttore", "Modello", "Tipo", "Ø (\")", "Fs (Hz)", "SPL", "Potenza (W)"
        ])
        self.driver_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.driver_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.driver_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.driver_table.itemSelectionChanged.connect(self._on_driver_selected)
        self.driver_table.doubleClicked.connect(self._confirm_driver)
        left_layout.addWidget(self.driver_table, 1)

        splitter.addWidget(left_widget)

        # ─── Pannello destro: dettagli driver ─────────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 0, 0, 0)

        detail_group = QGroupBox("Parametri Thiele-Small")
        detail_layout = QVBoxLayout(detail_group)

        self.ts_browser = QTextBrowser()
        self.ts_browser.setHtml("<p><i>Seleziona un driver per vedere i parametri</i></p>")
        detail_layout.addWidget(self.ts_browser)

        right_layout.addWidget(detail_group, 1)

        # Pulsante selezione
        self.select_btn = QPushButton("Usa Questo Driver →")
        self.select_btn.setMinimumHeight(40)
        self.select_btn.setEnabled(False)
        self.select_btn.clicked.connect(self._confirm_driver)
        right_layout.addWidget(self.select_btn)

        splitter.addWidget(right_widget)
        splitter.setSizes([600, 400])

    def _load_drivers(self):
        """Carica tutti i driver nella tabella."""
        self._apply_filters()

    def _apply_filters(self):
        """Applica i filtri e ricarica la tabella."""
        manufacturer = self.manufacturer_combo.currentData()
        driver_type = self.type_combo.currentData()

        drivers = get_drivers_by_type(driver_type, manufacturer)
        self._populate_table(drivers)

    def _populate_table(self, drivers):
        """Popola la tabella con la lista di driver."""
        self.driver_table.setRowCount(len(drivers))

        for row, driver in enumerate(drivers):
            type_labels = {
                "subwoofer": "Subwoofer",
                "compression_driver": "CD",
                "woofer": "Woofer",
                "fullrange": "Fullrange",
            }
            items = [
                driver.manufacturer,
                driver.model,
                type_labels.get(driver.driver_type, driver.driver_type),
                f"{driver.diameter_inch:.1f}\"",
                f"{driver.fs:.0f}",
                f"{driver.spl_1w_1m:.1f}",
                f"{driver.power_rms:.0f}",
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, driver)
                self.driver_table.setItem(row, col, item)

    def _on_driver_selected(self):
        """Aggiorna i dettagli quando viene selezionato un driver."""
        rows = self.driver_table.selectedItems()
        if not rows:
            self.select_btn.setEnabled(False)
            return

        driver = self.driver_table.item(rows[0].row(), 0).data(Qt.UserRole)
        if driver:
            self._selected_driver = driver
            self.select_btn.setEnabled(True)
            self._show_driver_details(driver)

    def _show_driver_details(self, driver: DriverModel):
        """Mostra i parametri dettagliati del driver selezionato."""
        html = f"""
        <style>
            table {{ width: 100%; border-collapse: collapse; }}
            td {{ padding: 4px 8px; }}
            td:first-child {{ font-weight: bold; color: #A0A0C0; width: 45%; }}
            tr:nth-child(even) {{ background-color: rgba(255,255,255,0.05); }}
            h3 {{ color: #7C9EF0; }}
        </style>
        <h3>{driver.manufacturer} {driver.model}</h3>
        <p><i>{driver.description}</i></p>
        <table>
        <tr><td>Tipo</td><td>{driver.driver_type}</td></tr>
        <tr><td>Diametro nominale</td><td>{driver.diameter_inch}" ({driver.diameter_inch*2.54:.1f} cm)</td></tr>
        <tr><td>Potenza RMS</td><td>{driver.power_rms:.0f} W AES</td></tr>
        <tr><td>Impedenza</td><td>{driver.impedance_nominal:.0f} Ω</td></tr>
        <tr><td>Sensibilità</td><td>{driver.spl_1w_1m:.1f} dB (1W/1m)</td></tr>
        <tr><td colspan="2"><b>— Parametri Thiele-Small —</b></td></tr>
        <tr><td>Fs</td><td>{driver.fs:.1f} Hz</td></tr>
        <tr><td>Re</td><td>{driver.re:.2f} Ω</td></tr>
        <tr><td>Qes</td><td>{driver.qes:.3f}</td></tr>
        <tr><td>Qms</td><td>{driver.qms:.3f}</td></tr>
        <tr><td>Qts</td><td>{driver.qts:.3f}</td></tr>
        <tr><td>Vas</td><td>{driver.vas:.1f} L</td></tr>
        <tr><td>Sd</td><td>{driver.sd_cm2:.1f} cm²</td></tr>
        <tr><td>Xmax</td><td>{driver.xmax:.1f} mm</td></tr>
        <tr><td>BL</td><td>{driver.bl:.2f} T·m</td></tr>
        <tr><td>Mms</td><td>{driver.mms:.1f} g</td></tr>
        <tr><td>Le</td><td>{driver.le:.2f} mH</td></tr>
        """
        if driver.throat_diameter_inch > 0:
            html += f"""
        <tr><td>Gola (CD)</td><td>{driver.throat_diameter_inch}" ({driver.throat_diameter_inch*25.4:.0f} mm)</td></tr>
            """
        html += f"""
        <tr><td>Magnete</td><td>{driver.magnet_type}</td></tr>
        <tr><td>Cono/Diaframma</td><td>{driver.cone_material}</td></tr>
        <tr><td>Peso</td><td>{driver.weight_kg:.1f} kg</td></tr>
        </table>
        """
        self.ts_browser.setHtml(html)

    def _confirm_driver(self):
        """Conferma la selezione del driver e passa alla tab successiva."""
        if self._selected_driver:
            # Salva il DriverModel completo (non solo il dict) per permettere
            # a HornDesignerWidget di usare direttamente tutti i parametri T&S
            if hasattr(self.parent(), 'set_driver'):
                self.parent().set_driver(self._selected_driver)
            if hasattr(self.parent(), 'tab_widget'):
                self.parent().tab_widget.setCurrentIndex(2)
            self.driver_selected.emit(self._selected_driver)

    def set_filter_by_speaker_type(self, speaker_type: str):
        """
        Imposta il filtro tipo in base al tipo di speaker selezionato
        nella tab precedente (es. SUB → subwoofer, CD → compression_driver).
        """
        type_map = {
            "SUB": "subwoofer",
            "CD": "compression_driver",
            "FULLRANGE": None,  # mostra tutti
        }
        driver_type = type_map.get(speaker_type)
        # Trova l'indice corretto nel combo
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == driver_type:
                self.type_combo.setCurrentIndex(i)
                break
