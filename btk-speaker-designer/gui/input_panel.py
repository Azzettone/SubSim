"""
Pannello sinistro superiore: Input valori utente.

Contiene:
  - Selezione tipo speaker (SUB / CD / FULLRANGE)
  - Selezione driver dal database (combo + bottone selettore completo)
  - Parametri tromba: Fc, tipo espansione, rapporto bocca/gola, compressione gola
  - Vincoli dimensionali: larghezza / altezza / profondità max
  - Pulsante "Calcola"
"""

try:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QFrame, QScrollArea, QLabel, QComboBox, QDoubleSpinBox,
        QPushButton, QSizePolicy, QDialog, QDialogButtonBox,
        QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
        QTextBrowser, QLineEdit, QFormLayout, QGroupBox
    )
    from PyQt5.QtCore import Qt, pyqtSignal as Signal
    from PyQt5.QtGui import QFont
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QFrame, QScrollArea, QLabel, QComboBox, QDoubleSpinBox,
        QPushButton, QSizePolicy, QDialog, QDialogButtonBox,
        QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
        QTextBrowser, QLineEdit, QFormLayout, QGroupBox
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont

from ..core.constants import (
    SPEAKER_TYPE_SUB, SPEAKER_TYPE_CD, SPEAKER_TYPE_FULLRANGE,
    EXPANSION_TYPES, EXPANSION_LABELS, EXPANSION_EXPONENTIAL,
)
from ..core.driver_model import DriverModel
from ..database.db_manager import (
    initialize_database, get_manufacturers, get_drivers_by_type, get_driver_by_model
)


# ─── Dialogo selezione driver completo ───────────────────────────────────────

class DriverPickerDialog(QDialog):
    """
    Finestra di dialogo per la selezione del driver dal database completo,
    con filtri per produttore e tipo e visualizzazione parametri T&S.
    """

    def __init__(self, parent=None, filter_type: str = None):
        super().__init__(parent)
        self.setWindowTitle("Seleziona Driver")
        self.setMinimumSize(900, 550)
        self._selected_driver: DriverModel = None
        self._filter_type = filter_type
        self._build_ui()
        self._load_drivers()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)

        # ── Sinistra: filtri + tabella ─────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)

        # Barra ricerca
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Cerca per modello...")
        self.search_edit.textChanged.connect(self._apply_filters)
        left_layout.addWidget(self.search_edit)

        filter_row = QHBoxLayout()

        self.manufacturer_combo = QComboBox()
        self.manufacturer_combo.addItem("Tutti i produttori", None)
        for m in get_manufacturers():
            self.manufacturer_combo.addItem(m, m)
        self.manufacturer_combo.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(QLabel("Produttore:"))
        filter_row.addWidget(self.manufacturer_combo, 1)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Tutti i tipi", None)
        self.type_combo.addItem("Subwoofer", "subwoofer")
        self.type_combo.addItem("Woofer", "woofer")
        self.type_combo.addItem("Compression Driver", "compression_driver")
        self.type_combo.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(QLabel("Tipo:"))
        filter_row.addWidget(self.type_combo, 1)

        left_layout.addLayout(filter_row)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Produttore", "Modello", "Tipo", "Ø (\")", "Fs (Hz)", "SPL", "Potenza (W)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_selection)
        self.table.doubleClicked.connect(self.accept)
        left_layout.addWidget(self.table, 1)
        splitter.addWidget(left)

        # ── Destra: dettagli T&S ───────────────────────────────────────────
        self.detail_browser = QTextBrowser()
        self.detail_browser.setHtml("<p><i>Seleziona un driver per i dettagli</i></p>")
        splitter.addWidget(self.detail_browser)
        splitter.setSizes([560, 340])

        # ── Bottoni OK / Annulla ───────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("Usa questo driver")
        buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._ok_btn = buttons.button(QDialogButtonBox.Ok)
        layout.addWidget(buttons)

        # Pre-imposta il filtro tipo se passato dal chiamante
        if self._filter_type:
            for i in range(self.type_combo.count()):
                if self.type_combo.itemData(i) == self._filter_type:
                    self.type_combo.setCurrentIndex(i)
                    break

    def _load_drivers(self):
        self._apply_filters()

    def _apply_filters(self):
        manufacturer = self.manufacturer_combo.currentData()
        driver_type = self.type_combo.currentData()
        search = self.search_edit.text().strip().lower()

        drivers = get_drivers_by_type(driver_type, manufacturer)
        if search:
            drivers = [d for d in drivers if search in d.model.lower()]

        self.table.setRowCount(len(drivers))
        type_labels = {"subwoofer": "Subwoofer", "compression_driver": "CD", "woofer": "Woofer"}
        for row, d in enumerate(drivers):
            items = [
                d.manufacturer, d.model,
                type_labels.get(d.driver_type, d.driver_type),
                f"{d.diameter_inch:.1f}\"",
                f"{d.fs:.0f}",
                f"{d.spl_1w_1m:.1f}",
                f"{d.power_rms:.0f}",
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, d)
                self.table.setItem(row, col, item)

    def _on_selection(self):
        rows = self.table.selectedItems()
        if not rows:
            self._ok_btn.setEnabled(False)
            return
        driver = self.table.item(rows[0].row(), 0).data(Qt.UserRole)
        if driver:
            self._selected_driver = driver
            self._ok_btn.setEnabled(True)
            self._show_details(driver)

    def _show_details(self, d: DriverModel):
        html = f"""
        <style>
            table {{ width:100%; border-collapse:collapse; font-size:12px; }}
            td {{ padding:3px 6px; }}
            td:first-child {{ font-weight:bold; color:#A0A0C0; width:50%; }}
            tr:nth-child(even) {{ background-color:rgba(255,255,255,0.04); }}
            h3 {{ color:#7C9EF0; margin:4px 0; }}
        </style>
        <h3>{d.manufacturer} {d.model}</h3>
        <p style="color:#A0A0C0;font-size:11px">{d.description}</p>
        <table>
        <tr><td>Tipo</td><td>{d.driver_type}</td></tr>
        <tr><td>Diametro</td><td>{d.diameter_inch}" ({d.diameter_inch*2.54:.1f} cm)</td></tr>
        <tr><td>Potenza RMS</td><td>{d.power_rms:.0f} W</td></tr>
        <tr><td>Sensibilità</td><td>{d.spl_1w_1m:.1f} dB @ 1W/1m</td></tr>
        <tr><td>Impedenza</td><td>{d.impedance_nominal:.0f} Ω</td></tr>
        <tr><td colspan="2"><b>— Thiele-Small —</b></td></tr>
        <tr><td>Fs</td><td>{d.fs:.1f} Hz</td></tr>
        <tr><td>Qts / Qes / Qms</td><td>{d.qts:.3f} / {d.qes:.3f} / {d.qms:.3f}</td></tr>
        <tr><td>Vas</td><td>{d.vas:.1f} L</td></tr>
        <tr><td>Sd</td><td>{d.sd_cm2:.1f} cm²</td></tr>
        <tr><td>Xmax</td><td>{d.xmax:.1f} mm</td></tr>
        <tr><td>BL</td><td>{d.bl:.2f} T·m</td></tr>
        <tr><td>Mms</td><td>{d.mms:.1f} g</td></tr>
        <tr><td>Re</td><td>{d.re:.2f} Ω</td></tr>
        <tr><td>Le</td><td>{d.le:.2f} mH</td></tr>
        """
        if d.throat_diameter_inch > 0:
            html += f"<tr><td>Gola (CD)</td><td>{d.throat_diameter_inch}\" ({d.throat_diameter_inch*25.4:.0f} mm)</td></tr>"
        html += "</table>"
        self.detail_browser.setHtml(html)

    @property
    def selected_driver(self) -> DriverModel:
        return self._selected_driver


# ─── Pannello input principale ────────────────────────────────────────────────

class InputPanel(QWidget):
    """
    Pannello superiore sinistro.
    Emette il segnale calculate_requested con tutti i parametri
    che servono al motore di calcolo.
    """

    calculate_requested = Signal(dict)   # dizionario con tutti i parametri
    driver_changed = Signal(object)      # DriverModel selezionato

    def __init__(self, parent=None):
        super().__init__(parent)
        initialize_database()
        self._selected_driver: DriverModel = None
        self._build_ui()

    # ── Utility: crea un separatore di sezione ────────────────────────────
    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #7C9EF0; font-size: 11px; font-weight: bold;"
            "border-bottom: 1px solid #2A2A44; padding-bottom: 2px;"
        )
        return lbl

    def _build_ui(self):
        # Layout esterno: scroll + pulsante fisso in fondo
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Area scorrevole ────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)

        # Widget interno allo scroll
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setContentsMargins(10, 10, 10, 6)
        grid.setVerticalSpacing(5)
        grid.setHorizontalSpacing(8)
        grid.setColumnStretch(1, 1)   # colonna widget si espande
        scroll.setWidget(inner)

        row = 0

        # ══ TIPO SPEAKER ══════════════════════════════════════════════════
        grid.addWidget(self._section_label("TIPO SPEAKER"), row, 0, 1, 2)
        row += 1

        self.type_combo = QComboBox()
        self.type_combo.addItem("Subwoofer (SUB)", SPEAKER_TYPE_SUB)
        self.type_combo.addItem("Compression Driver (CD)", SPEAKER_TYPE_CD)
        self.type_combo.addItem("Fullrange (CD+SUB)", SPEAKER_TYPE_FULLRANGE)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        grid.addWidget(self.type_combo, row, 0, 1, 2)
        row += 1

        grid.addWidget(self._hsep(), row, 0, 1, 2)
        row += 1

        # ══ DRIVER ════════════════════════════════════════════════════════
        grid.addWidget(self._section_label("DRIVER"), row, 0, 1, 2)
        row += 1

        self.driver_combo = QComboBox()
        self.driver_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.driver_combo.currentIndexChanged.connect(self._on_driver_combo_changed)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(32)
        browse_btn.setToolTip("Selettore driver completo con parametri T&S")
        browse_btn.clicked.connect(self._open_driver_picker)
        driver_row_w = QWidget()
        driver_row_l = QHBoxLayout(driver_row_w)
        driver_row_l.setContentsMargins(0, 0, 0, 0)
        driver_row_l.setSpacing(4)
        driver_row_l.addWidget(self.driver_combo, 1)
        driver_row_l.addWidget(browse_btn)
        grid.addWidget(driver_row_w, row, 0, 1, 2)
        row += 1

        self.driver_info_label = QLabel("Nessun driver selezionato")
        self.driver_info_label.setStyleSheet("color: #707090; font-size: 11px;")
        self.driver_info_label.setWordWrap(True)
        grid.addWidget(self.driver_info_label, row, 0, 1, 2)
        row += 1

        grid.addWidget(self._hsep(), row, 0, 1, 2)
        row += 1

        # ══ PARAMETRI TROMBA ══════════════════════════════════════════════
        grid.addWidget(self._section_label("PARAMETRI TROMBA"), row, 0, 1, 2)
        row += 1

        grid.addWidget(QLabel("Fc taglio:"), row, 0)
        self.fc_spin = QDoubleSpinBox()
        self.fc_spin.setRange(10, 2000)
        self.fc_spin.setValue(70.0)
        self.fc_spin.setSuffix(" Hz")
        self.fc_spin.setDecimals(1)
        self.fc_spin.setToolTip("Frequenza di taglio -3dB della tromba")
        grid.addWidget(self.fc_spin, row, 1)
        row += 1

        grid.addWidget(QLabel("Espansione:"), row, 0)
        self.expansion_combo = QComboBox()
        for exp_type in EXPANSION_TYPES:
            self.expansion_combo.addItem(EXPANSION_LABELS[exp_type], exp_type)
        grid.addWidget(self.expansion_combo, row, 1)
        row += 1

        grid.addWidget(QLabel("Sm/Sg ratio:"), row, 0)
        self.ratio_spin = QDoubleSpinBox()
        self.ratio_spin.setRange(1.1, 200.0)
        self.ratio_spin.setValue(2.0)
        self.ratio_spin.setDecimals(2)
        self.ratio_spin.setToolTip("Rapporto area bocca / area gola")
        grid.addWidget(self.ratio_spin, row, 1)
        row += 1

        grid.addWidget(QLabel("Compressione:"), row, 0)
        self.compression_spin = QDoubleSpinBox()
        self.compression_spin.setRange(1.0, 50.0)
        self.compression_spin.setValue(1.0)
        self.compression_spin.setDecimals(1)
        self.compression_spin.setToolTip(
            "Rapporto compressione gola (Sd/Sgola).\n"
            "1.0 per SUB, 3-10 per Compression Driver."
        )
        grid.addWidget(self.compression_spin, row, 1)
        row += 1

        grid.addWidget(self._hsep(), row, 0, 1, 2)
        row += 1

        # ══ VINCOLI DIMENSIONALI ══════════════════════════════════════════
        grid.addWidget(self._section_label("VINCOLI DIMENSIONALI  (0 = nessun limite)"), row, 0, 1, 2)
        row += 1

        grid.addWidget(QLabel("Larghezza max:"), row, 0)
        self.max_width_spin = QDoubleSpinBox()
        self.max_width_spin.setRange(0, 5000)
        self.max_width_spin.setValue(0)
        self.max_width_spin.setSuffix(" mm")
        grid.addWidget(self.max_width_spin, row, 1)
        row += 1

        grid.addWidget(QLabel("Altezza max:"), row, 0)
        self.max_height_spin = QDoubleSpinBox()
        self.max_height_spin.setRange(0, 5000)
        self.max_height_spin.setValue(0)
        self.max_height_spin.setSuffix(" mm")
        grid.addWidget(self.max_height_spin, row, 1)
        row += 1

        grid.addWidget(QLabel("Profondità max:"), row, 0)
        self.max_depth_spin = QDoubleSpinBox()
        self.max_depth_spin.setRange(0, 5000)
        self.max_depth_spin.setValue(0)
        self.max_depth_spin.setSuffix(" mm")
        grid.addWidget(self.max_depth_spin, row, 1)
        row += 1

        # Spazio finale
        grid.setRowStretch(row, 1)

        # ── Pulsante Calcola fisso in fondo (fuori dallo scroll) ───────────
        self.calc_btn = QPushButton("⚙  Calcola")
        self.calc_btn.setMinimumHeight(42)
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self.calc_btn.setFont(font)
        self.calc_btn.setStyleSheet(
            "QPushButton { background-color: #2A4A8A; border: none;"
            " border-radius: 4px; color: #E0E8FF; }"
            "QPushButton:hover { background-color: #3A5AAA; }"
            "QPushButton:pressed { background-color: #1A3A6A; }"
        )
        self.calc_btn.clicked.connect(self._on_calculate)
        outer.addWidget(self.calc_btn)

        # Carica driver iniziali (SUB di default)
        self._reload_driver_combo(SPEAKER_TYPE_SUB)

    @staticmethod
    def _hsep() -> QFrame:
        """Separatore orizzontale sottile."""
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #2A2A44;")
        line.setFixedHeight(1)
        return line

    # ── Slot interni ──────────────────────────────────────────────────────────

    def _on_type_changed(self):
        speaker_type = self.type_combo.currentData()
        # Imposta Fc default e compressione gola per tipo
        if speaker_type == SPEAKER_TYPE_CD:
            self.fc_spin.setValue(500.0)
            self.compression_spin.setValue(4.0)
        elif speaker_type == SPEAKER_TYPE_SUB:
            self.fc_spin.setValue(70.0)
            self.compression_spin.setValue(1.0)
        else:
            self.fc_spin.setValue(100.0)
            self.compression_spin.setValue(1.0)
        self._reload_driver_combo(speaker_type)

    def _reload_driver_combo(self, speaker_type: str):
        """Ricarica il combo driver filtrato per tipo speaker."""
        type_map = {
            SPEAKER_TYPE_SUB: "subwoofer",
            SPEAKER_TYPE_CD: "compression_driver",
            SPEAKER_TYPE_FULLRANGE: None,
        }
        db_type = type_map.get(speaker_type)
        drivers = get_drivers_by_type(db_type)

        self.driver_combo.blockSignals(True)
        self.driver_combo.clear()
        self.driver_combo.addItem("-- Seleziona driver --", None)
        for d in drivers:
            label = f"{d.manufacturer}  {d.model}  ({d.diameter_inch}\" / {d.power_rms:.0f}W)"
            self.driver_combo.addItem(label, d)
        self.driver_combo.blockSignals(False)
        self.driver_combo.setCurrentIndex(0)
        self._selected_driver = None
        self.driver_info_label.setText("Nessun driver selezionato")

    def _on_driver_combo_changed(self):
        driver = self.driver_combo.currentData()
        if isinstance(driver, DriverModel):
            self._set_driver(driver)

    def _open_driver_picker(self):
        """Apre il dialogo di selezione avanzata con dettagli T&S completi."""
        type_map = {
            SPEAKER_TYPE_SUB: "subwoofer",
            SPEAKER_TYPE_CD: "compression_driver",
            SPEAKER_TYPE_FULLRANGE: None,
        }
        filter_type = type_map.get(self.type_combo.currentData())
        dlg = DriverPickerDialog(self, filter_type=filter_type)
        if dlg.exec_() == QDialog.Accepted and dlg.selected_driver:
            self._set_driver(dlg.selected_driver)
            # Sincronizza il combo sulla voce corrispondente se esiste
            for i in range(self.driver_combo.count()):
                d = self.driver_combo.itemData(i)
                if isinstance(d, DriverModel) and d.model == dlg.selected_driver.model:
                    self.driver_combo.blockSignals(True)
                    self.driver_combo.setCurrentIndex(i)
                    self.driver_combo.blockSignals(False)
                    break

    def _set_driver(self, driver: DriverModel):
        self._selected_driver = driver
        self.driver_info_label.setText(
            f"<b>{driver.manufacturer} {driver.model}</b><br>"
            f"Fs={driver.fs:.0f}Hz  Qts={driver.qts:.3f}  "
            f"SPL={driver.spl_1w_1m:.1f}dB  {driver.power_rms:.0f}W"
        )
        self.driver_changed.emit(driver)

    def _on_calculate(self):
        if self._selected_driver is None:
            # Segnala al main window che manca il driver
            self.calculate_requested.emit({"error": "no_driver"})
            return
        self.calculate_requested.emit(self.get_params())

    # ── API pubblica ──────────────────────────────────────────────────────────

    def get_params(self) -> dict:
        """Restituisce un dizionario con tutti i parametri inseriti dall'utente."""
        return {
            "speaker_type":       self.type_combo.currentData(),
            "driver":             self._selected_driver,
            "fc_hz":              self.fc_spin.value(),
            "expansion_type":     self.expansion_combo.currentData(),
            "smouth_ratio":       self.ratio_spin.value(),
            "compression_ratio":  self.compression_spin.value(),
            "max_width_mm":       self.max_width_spin.value() or None,
            "max_height_mm":      self.max_height_spin.value() or None,
            "max_depth_mm":       self.max_depth_spin.value() or None,
        }

    def set_params(self, params: dict):
        """Ricarica l'interfaccia da un dizionario (usato da Apri progetto)."""
        if "speaker_type" in params:
            for i in range(self.type_combo.count()):
                if self.type_combo.itemData(i) == params["speaker_type"]:
                    self.type_combo.setCurrentIndex(i)
                    break
        if "fc_hz" in params:
            self.fc_spin.setValue(params["fc_hz"])
        if "expansion_type" in params:
            for i in range(self.expansion_combo.count()):
                if self.expansion_combo.itemData(i) == params["expansion_type"]:
                    self.expansion_combo.setCurrentIndex(i)
                    break
        if "smouth_ratio" in params:
            self.ratio_spin.setValue(params["smouth_ratio"])
        if "compression_ratio" in params:
            self.compression_spin.setValue(params["compression_ratio"])
        if "max_width_mm" in params and params["max_width_mm"]:
            self.max_width_spin.setValue(params["max_width_mm"])
        if "max_height_mm" in params and params["max_height_mm"]:
            self.max_height_spin.setValue(params["max_height_mm"])
        if "max_depth_mm" in params and params["max_depth_mm"]:
            self.max_depth_spin.setValue(params["max_depth_mm"])
        if "driver_model" in params:
            d = get_driver_by_model(params["driver_model"])
            if d:
                self._set_driver(d)
