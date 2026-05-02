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
        QFrame, QScrollArea, QLabel, QComboBox, QDoubleSpinBox, QSpinBox,
        QPushButton, QSizePolicy, QDialog, QDialogButtonBox,
        QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
        QTextBrowser, QLineEdit, QFormLayout, QGroupBox, QButtonGroup
    )
    from PyQt5.QtCore import Qt, pyqtSignal as Signal
    from PyQt5.QtGui import QFont
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QFrame, QScrollArea, QLabel, QComboBox, QDoubleSpinBox, QSpinBox,
        QPushButton, QSizePolicy, QDialog, QDialogButtonBox,
        QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
        QTextBrowser, QLineEdit, QFormLayout, QGroupBox, QButtonGroup
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont

from ..core.constants import (
    SPEAKER_TYPE_SUB, SPEAKER_TYPE_CD, SPEAKER_TYPE_FULLRANGE,
    EXPANSION_TYPES, EXPANSION_LABELS, EXPANSION_EXPONENTIAL, EXPANSION_HYPEX,
    GEOMETRY_TYPES, GEOMETRY_LABELS, GEOMETRY_STRAIGHT,
    ENCLOSURE_CATEGORY_HORN, ENCLOSURE_CATEGORY_REFLEX, ENCLOSURE_CATEGORY_HYBRID,
    ENCLOSURE_CATEGORIES, ENCLOSURE_CATEGORY_LABELS,
    ENCLOSURE_VARIANTS, ENCLOSURE_LABELS,
    ENCLOSURE_HAS_HORN, ENCLOSURE_HAS_REFLEX, ENCLOSURE_IS_BANDPASS,
    ENCLOSURE_DEFAULT_FOR_SPEAKER,
    PORT_TYPES, PORT_TYPE_LABELS, PORT_TYPE_CIRCULAR, PORT_TYPE_SLOT,
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


# ─── Pannello input principale (nuovo layout mockup) ─────────────────────────

class InputPanel(QWidget):
    """
    Pannello sinistro principale — layout conforme al mockup.

    Sezioni (dall'alto):
      [1] TIPO ENCLOSURE   : 3 pulsanti  TROMBA | REFLEX | MIXED-HYBRID
      [2] VARIANTI         : combo varianti per categoria selezionata
      [3] TIPO SPEAKER     : SUB / CD / FULLRANGE
      [4] SELEZIONE DRIVER : combo + bottone browse
      [5] PARAMETRI ACUSTICI
            • Horn:   Fc, espansione, Sm/Sg, compressione, Hypex T
            • Reflex: Fb tuning, volume camera
            • Bandpass: volume cam. front/rear, freq range
      [6] LIMITI DIMENSIONALI  : larghezza, altezza, profondità
      [7] TIPO TROMBA / PORTA REFLEX
            • Horn geometry: straight/folded/2folded
            • Port type, diametro/slot
      [8] NUMERO SEZIONI / PORTE
      [CALCOLA]
    """

    calculate_requested = Signal(dict)   # dizionario con tutti i parametri
    driver_changed = Signal(object)      # DriverModel selezionato
    geometry_changed = Signal(str)       # geometria cabinet cambiata

    def __init__(self, parent=None):
        super().__init__(parent)
        initialize_database()
        self._selected_driver: DriverModel = None
        self._selected_hf_driver: DriverModel = None   # secondo driver per FULLRANGE
        self._enclosure_category = ENCLOSURE_CATEGORY_HORN
        self._enclosure_type = ENCLOSURE_VARIANTS[ENCLOSURE_CATEGORY_HORN][0]
        self._build_ui()

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #7C9EF0; font-size: 11px; font-weight: bold;"
            "border-bottom: 1px solid #2A2A44; padding-bottom: 2px; margin-top: 4px;"
        )
        return lbl

    @staticmethod
    def _hsep() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #2A2A44;")
        line.setFixedHeight(1)
        return line

    @staticmethod
    def _group(title: str, layout: "QLayout") -> "QGroupBox":
        gb = QGroupBox(title)
        gb.setLayout(layout)
        gb.setStyleSheet(
            "QGroupBox { border: 1px solid #2A2A44; border-radius:3px;"
            " margin-top: 6px; padding-top:10px; font-weight:bold; color:#A0A0C0; font-size:10px;}"
            "QGroupBox::title { subcontrol-origin: margin; left:8px; }"
        )
        return gb

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)

        inner = QWidget()
        vbox = QVBoxLayout(inner)
        vbox.setContentsMargins(10, 8, 10, 6)
        vbox.setSpacing(4)
        scroll.setWidget(inner)

        # ══ [1] TIPO ENCLOSURE — 3 pulsanti toggle ════════════════════════
        vbox.addWidget(self._section_label("TIPO SPEAKER"))

        btn_row = QHBoxLayout()
        btn_row.setSpacing(2)
        self._encl_btn_group = QButtonGroup(self)
        self._encl_btn_group.setExclusive(True)
        self._encl_btns = {}
        for cat in ENCLOSURE_CATEGORIES:
            btn = QPushButton(ENCLOSURE_CATEGORY_LABELS[cat])
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton { background:#1E1E32; border:1px solid #2A2A44;"
                " border-radius:3px; padding:4px 8px; color:#808090; font-size:10px;}"
                "QPushButton:checked { background:#2A4A8A; border-color:#5A7ACA; color:#E0E8FF;}"
                "QPushButton:hover { background:#2A2A44; }"
            )
            self._encl_btn_group.addButton(btn)
            btn_row.addWidget(btn)
            self._encl_btns[cat] = btn
        self._encl_btns[ENCLOSURE_CATEGORY_HORN].setChecked(True)
        self._encl_btn_group.buttonClicked.connect(self._on_category_changed)
        vbox.addLayout(btn_row)

        # ══ [2] VARIANTI ══════════════════════════════════════════════════
        self.variant_combo = QComboBox()
        self.variant_combo.currentIndexChanged.connect(self._on_variant_changed)
        vbox.addWidget(self.variant_combo)

        vbox.addWidget(self._hsep())

        # ══ [3] TIPO SPEAKER (SUB / CD / FULLRANGE) ══════════════════════
        vbox.addWidget(self._section_label("TIPO DRIVER"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("Subwoofer (SUB)", SPEAKER_TYPE_SUB)
        self.type_combo.addItem("Compression Driver (CD)", SPEAKER_TYPE_CD)
        self.type_combo.addItem("Fullrange (CD+SUB)", SPEAKER_TYPE_FULLRANGE)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        vbox.addWidget(self.type_combo)

        vbox.addWidget(self._hsep())

        # ══ [4] SELEZIONE DRIVER ═════════════════════════════════════════
        vbox.addWidget(self._section_label("SELEZIONE DRIVER"))

        driver_row_w = QWidget()
        driver_row_l = QHBoxLayout(driver_row_w)
        driver_row_l.setContentsMargins(0, 0, 0, 0)
        driver_row_l.setSpacing(4)
        self.driver_combo = QComboBox()
        self.driver_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.driver_combo.currentIndexChanged.connect(self._on_driver_combo_changed)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(32)
        browse_btn.setToolTip("Selettore driver completo con parametri T&S")
        browse_btn.clicked.connect(self._open_driver_picker)
        driver_row_l.addWidget(self.driver_combo, 1)
        driver_row_l.addWidget(browse_btn)
        vbox.addWidget(driver_row_w)

        self.driver_info_label = QLabel("Nessun driver selezionato")
        self.driver_info_label.setStyleSheet("color: #707090; font-size: 11px;")
        self.driver_info_label.setWordWrap(True)
        vbox.addWidget(self.driver_info_label)

        vbox.addWidget(self._hsep())

        # ══ [5a] PARAMETRI TROMBA (QGroupBox, visibile solo per horn) ════
        horn_param_layout = QGridLayout()
        horn_param_layout.setVerticalSpacing(4)
        horn_param_layout.setHorizontalSpacing(8)
        horn_param_layout.setColumnStretch(1, 1)

        r = 0
        horn_param_layout.addWidget(QLabel("Fc taglio:"), r, 0)
        self.fc_spin = QDoubleSpinBox()
        self.fc_spin.setRange(10, 2000)
        self.fc_spin.setValue(70.0)
        self.fc_spin.setSuffix(" Hz")
        self.fc_spin.setDecimals(1)
        self.fc_spin.setToolTip("Frequenza di taglio –3dB della tromba.\nm = 4π·Fc/c  (Webster 1919)")
        horn_param_layout.addWidget(self.fc_spin, r, 1); r += 1

        horn_param_layout.addWidget(QLabel("Espansione:"), r, 0)
        self.expansion_combo = QComboBox()
        for exp_type in EXPANSION_TYPES:
            self.expansion_combo.addItem(EXPANSION_LABELS[exp_type], exp_type)
        self.expansion_combo.currentIndexChanged.connect(self._on_expansion_changed)
        horn_param_layout.addWidget(self.expansion_combo, r, 1); r += 1

        self._hypex_t_label = QLabel("Hypex T:")
        self._hypex_t_spin = QDoubleSpinBox()
        self._hypex_t_spin.setRange(0.0, 0.99)
        self._hypex_t_spin.setValue(0.5)
        self._hypex_t_spin.setSingleStep(0.05)
        self._hypex_t_spin.setDecimals(2)
        self._hypex_t_spin.setToolTip("T=0 → cosh² horn, T=0.5 → Hypex, T→1 → esponenziale  (Salmon 1946)")
        horn_param_layout.addWidget(self._hypex_t_label, r, 0)
        horn_param_layout.addWidget(self._hypex_t_spin, r, 1)
        self._hypex_t_label.setVisible(False)
        self._hypex_t_spin.setVisible(False)
        r += 1

        horn_param_layout.addWidget(QLabel("Sm/Sg ratio:"), r, 0)
        self.ratio_spin = QDoubleSpinBox()
        self.ratio_spin.setRange(1.1, 200.0)
        self.ratio_spin.setValue(2.0)
        self.ratio_spin.setDecimals(2)
        horn_param_layout.addWidget(self.ratio_spin, r, 1); r += 1

        horn_param_layout.addWidget(QLabel("Compressione:"), r, 0)
        self.compression_spin = QDoubleSpinBox()
        self.compression_spin.setRange(1.0, 50.0)
        self.compression_spin.setValue(1.0)
        self.compression_spin.setDecimals(1)
        self.compression_spin.setToolTip("Sd_driver / S_gola.  1.0 = sub  |  3–10 = compression driver")
        horn_param_layout.addWidget(self.compression_spin, r, 1); r += 1

        self.gb_horn_params = self._group("PARAMETRI TROMBA", horn_param_layout)
        vbox.addWidget(self.gb_horn_params)

        # ══ [5b] PARAMETRI REFLEX ════════════════════════════════════════
        reflex_param_layout = QGridLayout()
        reflex_param_layout.setVerticalSpacing(4)
        reflex_param_layout.setHorizontalSpacing(8)
        reflex_param_layout.setColumnStretch(1, 1)

        r = 0
        reflex_param_layout.addWidget(QLabel("Fb accordo:"), r, 0)
        self.fb_spin = QDoubleSpinBox()
        self.fb_spin.setRange(10, 300)
        self.fb_spin.setValue(40.0)
        self.fb_spin.setSuffix(" Hz")
        self.fb_spin.setDecimals(1)
        self.fb_spin.setToolTip("Frequenza di accordo della porta reflex (Helmholtz).\nSmall (1973) JAES 21(6)")
        reflex_param_layout.addWidget(self.fb_spin, r, 1); r += 1

        reflex_param_layout.addWidget(QLabel("Volume box:"), r, 0)
        self.vbox_spin = QDoubleSpinBox()
        self.vbox_spin.setRange(1, 2000)
        self.vbox_spin.setValue(100.0)
        self.vbox_spin.setSuffix(" L")
        self.vbox_spin.setDecimals(1)
        self.vbox_spin.setToolTip("Volume interno dell'enclosure (litri). 0 = calcolo automatico.")
        reflex_param_layout.addWidget(self.vbox_spin, r, 1); r += 1

        self.gb_reflex_params = self._group("PARAMETRI REFLEX", reflex_param_layout)
        vbox.addWidget(self.gb_reflex_params)

        # ══ [5c] PARAMETRI BANDPASS ══════════════════════════════════════
        bp_param_layout = QGridLayout()
        bp_param_layout.setVerticalSpacing(4)
        bp_param_layout.setHorizontalSpacing(8)
        bp_param_layout.setColumnStretch(1, 1)

        r = 0
        bp_param_layout.addWidget(QLabel("Vol. cam. rear:"), r, 0)
        self.vb_rear_spin = QDoubleSpinBox()
        self.vb_rear_spin.setRange(1, 2000)
        self.vb_rear_spin.setValue(80.0)
        self.vb_rear_spin.setSuffix(" L")
        self.vb_rear_spin.setDecimals(1)
        bp_param_layout.addWidget(self.vb_rear_spin, r, 1); r += 1

        bp_param_layout.addWidget(QLabel("Freq. passabanda:"), r, 0)
        freq_range_w = QWidget()
        freq_range_l = QHBoxLayout(freq_range_w)
        freq_range_l.setContentsMargins(0, 0, 0, 0)
        freq_range_l.setSpacing(4)
        self.f_low_spin = QDoubleSpinBox()
        self.f_low_spin.setRange(10, 500)
        self.f_low_spin.setValue(40.0)
        self.f_low_spin.setSuffix(" Hz")
        self.f_low_spin.setDecimals(0)
        self.f_high_spin = QDoubleSpinBox()
        self.f_high_spin.setRange(20, 2000)
        self.f_high_spin.setValue(120.0)
        self.f_high_spin.setSuffix(" Hz")
        self.f_high_spin.setDecimals(0)
        freq_range_l.addWidget(self.f_low_spin)
        freq_range_l.addWidget(QLabel("–"))
        freq_range_l.addWidget(self.f_high_spin)
        bp_param_layout.addWidget(freq_range_w, r, 1); r += 1

        self.gb_bp_params = self._group("PARAMETRI BANDPASS", bp_param_layout)
        vbox.addWidget(self.gb_bp_params)

        vbox.addWidget(self._hsep())

        # ══ [6] DIMENSIONI ESTERNE CABINET ════════════════════════════════
        ext_dim_layout = QGridLayout()
        ext_dim_layout.setVerticalSpacing(4)
        ext_dim_layout.setHorizontalSpacing(8)
        ext_dim_layout.setColumnStretch(1, 1)

        r = 0
        ext_dim_layout.addWidget(QLabel("Larghezza ext:"), r, 0)
        self.ext_width_spin = QDoubleSpinBox()
        self.ext_width_spin.setRange(0, 5000)
        self.ext_width_spin.setValue(0)
        self.ext_width_spin.setSuffix(" mm")
        self.ext_width_spin.setDecimals(0)
        self.ext_width_spin.setToolTip("Larghezza esterna totale cabinet (0 = non vincolato)")
        ext_dim_layout.addWidget(self.ext_width_spin, r, 1); r += 1

        ext_dim_layout.addWidget(QLabel("Altezza ext:"), r, 0)
        self.ext_height_spin = QDoubleSpinBox()
        self.ext_height_spin.setRange(0, 5000)
        self.ext_height_spin.setValue(0)
        self.ext_height_spin.setSuffix(" mm")
        self.ext_height_spin.setDecimals(0)
        self.ext_height_spin.setToolTip("Altezza esterna totale cabinet (0 = non vincolato)")
        ext_dim_layout.addWidget(self.ext_height_spin, r, 1); r += 1

        ext_dim_layout.addWidget(QLabel("Profondità ext:"), r, 0)
        self.ext_depth_spin = QDoubleSpinBox()
        self.ext_depth_spin.setRange(0, 5000)
        self.ext_depth_spin.setValue(0)
        self.ext_depth_spin.setSuffix(" mm")
        self.ext_depth_spin.setDecimals(0)
        self.ext_depth_spin.setToolTip("Profondità esterna totale cabinet (0 = non vincolato)")
        ext_dim_layout.addWidget(self.ext_depth_spin, r, 1); r += 1

        ext_dim_layout.addWidget(QLabel("Spessore legno:"), r, 0)
        self.wood_thickness_spin = QDoubleSpinBox()
        self.wood_thickness_spin.setRange(6, 50)
        self.wood_thickness_spin.setValue(18)
        self.wood_thickness_spin.setSuffix(" mm")
        self.wood_thickness_spin.setDecimals(0)
        self.wood_thickness_spin.setToolTip(
            "Spessore pannelli MDF (tipico: MDF 18mm, Birch ply 15mm, truciolato 19mm)"
        )
        ext_dim_layout.addWidget(self.wood_thickness_spin, r, 1); r += 1

        self._vol_estimate_label = QLabel("Volume interno: —")
        self._vol_estimate_label.setStyleSheet(
            "color: #A0E0A0; font-size: 11px; font-weight: bold; padding: 2px;"
        )
        ext_dim_layout.addWidget(self._vol_estimate_label, r, 0, 1, 2)

        self.gb_cabinet_dims = self._group("DIMENSIONI ESTERNE CABINET", ext_dim_layout)
        vbox.addWidget(self.gb_cabinet_dims)

        for _sp in (self.ext_width_spin, self.ext_height_spin,
                    self.ext_depth_spin, self.wood_thickness_spin):
            _sp.valueChanged.connect(self._update_vol_estimate)

        vbox.addWidget(self._hsep())

        # ══ [7] TIPO TROMBA / TIPO PORTA REFLEX ══════════════════════════
        # ── Horn geometry (visibile solo per horn) ────────────────────────
        horn_type_layout = QGridLayout()
        horn_type_layout.setVerticalSpacing(4)
        horn_type_layout.setHorizontalSpacing(8)
        horn_type_layout.setColumnStretch(1, 1)

        horn_type_layout.addWidget(QLabel("Geometria:"), 0, 0)
        self.geometry_combo = QComboBox()
        for g in GEOMETRY_TYPES:
            self.geometry_combo.addItem(GEOMETRY_LABELS[g], g)
        self.geometry_combo.setToolTip(
            "Dritta: cabinet profondo, massima fedeltà.\n"
            "Folded: profondità dimezzata con 1 piega.\n"
            "2-Folded: massima compattezza con 2 pieghe."
        )
        self.geometry_combo.currentIndexChanged.connect(
            lambda: self.geometry_changed.emit(self.geometry_combo.currentData())
        )
        horn_type_layout.addWidget(self.geometry_combo, 0, 1)
        self.gb_horn_type = self._group("TIPO TROMBA", horn_type_layout)
        vbox.addWidget(self.gb_horn_type)

        # ── Reflex port settings (visibile solo per reflex) ───────────────
        port_layout = QGridLayout()
        port_layout.setVerticalSpacing(4)
        port_layout.setHorizontalSpacing(8)
        port_layout.setColumnStretch(1, 1)

        r = 0
        port_layout.addWidget(QLabel("Tipo porta:"), r, 0)
        self.port_type_combo = QComboBox()
        for pt in PORT_TYPES:
            self.port_type_combo.addItem(PORT_TYPE_LABELS[pt], pt)
        self.port_type_combo.currentIndexChanged.connect(self._on_port_type_changed)
        port_layout.addWidget(self.port_type_combo, r, 1); r += 1

        self._port_diam_label = QLabel("Diametro porta:")
        self.port_diam_spin = QDoubleSpinBox()
        self.port_diam_spin.setRange(20, 500)
        self.port_diam_spin.setValue(100.0)
        self.port_diam_spin.setSuffix(" mm")
        port_layout.addWidget(self._port_diam_label, r, 0)
        port_layout.addWidget(self.port_diam_spin, r, 1); r += 1

        self._slot_labels = []
        self._slot_w_label = QLabel("Slot larghezza:")
        self.slot_w_spin = QDoubleSpinBox()
        self.slot_w_spin.setRange(20, 1000)
        self.slot_w_spin.setValue(200.0)
        self.slot_w_spin.setSuffix(" mm")
        self._slot_h_label = QLabel("Slot altezza:")
        self.slot_h_spin = QDoubleSpinBox()
        self.slot_h_spin.setRange(10, 500)
        self.slot_h_spin.setValue(50.0)
        self.slot_h_spin.setSuffix(" mm")
        port_layout.addWidget(self._slot_w_label, r, 0)
        port_layout.addWidget(self.slot_w_spin, r, 1); r += 1
        port_layout.addWidget(self._slot_h_label, r, 0)
        port_layout.addWidget(self.slot_h_spin, r, 1); r += 1
        self._slot_w_label.setVisible(False)
        self.slot_w_spin.setVisible(False)
        self._slot_h_label.setVisible(False)
        self.slot_h_spin.setVisible(False)

        self.gb_port_type = self._group("TIPO PORTA REFLEX", port_layout)
        vbox.addWidget(self.gb_port_type)

        vbox.addWidget(self._hsep())

        # ══ [8] N. SEZIONI TROMBA / N. PORTE REFLEX ══════════════════════
        counts_layout = QGridLayout()
        counts_layout.setVerticalSpacing(4)
        counts_layout.setHorizontalSpacing(8)
        counts_layout.setColumnStretch(1, 1)

        r = 0
        self._n_sect_label = QLabel("N. sezioni tromba:")
        self.n_sections_spin = QSpinBox()
        self.n_sections_spin.setRange(4, 50)
        self.n_sections_spin.setValue(8)
        self.n_sections_spin.setToolTip("Sezioni del profilo tromba (4–50). Originale Excel: 8.")
        counts_layout.addWidget(self._n_sect_label, r, 0)
        counts_layout.addWidget(self.n_sections_spin, r, 1); r += 1

        self._n_ports_label = QLabel("N. porte reflex:")
        self.n_ports_spin = QSpinBox()
        self.n_ports_spin.setRange(1, 8)
        self.n_ports_spin.setValue(1)
        counts_layout.addWidget(self._n_ports_label, r, 0)
        counts_layout.addWidget(self.n_ports_spin, r, 1)

        self.gb_counts = self._group("NUMERO SEZIONI / PORTE", counts_layout)
        vbox.addWidget(self.gb_counts)

        # ══ [9] FULLRANGE — driver HF + crossover (visibile solo FULLRANGE) ═
        fr_layout = QGridLayout()
        fr_layout.setVerticalSpacing(4)
        fr_layout.setHorizontalSpacing(8)
        fr_layout.setColumnStretch(1, 1)

        r = 0
        fr_layout.addWidget(QLabel("Driver HF (CD):"), r, 0)
        hf_row_w = QWidget()
        hf_row_l = QHBoxLayout(hf_row_w)
        hf_row_l.setContentsMargins(0, 0, 0, 0)
        hf_row_l.setSpacing(4)
        self.hf_combo = QComboBox()
        self.hf_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.hf_combo.currentIndexChanged.connect(self._on_hf_combo_changed)
        hf_browse_btn = QPushButton("...")
        hf_browse_btn.setFixedWidth(32)
        hf_browse_btn.setToolTip("Selettore driver HF (compression driver)")
        hf_browse_btn.clicked.connect(self._open_hf_driver_picker)
        hf_row_l.addWidget(self.hf_combo, 1)
        hf_row_l.addWidget(hf_browse_btn)
        fr_layout.addWidget(hf_row_w, r, 1)
        r += 1

        self.hf_info_label = QLabel("Nessun driver HF selezionato")
        self.hf_info_label.setStyleSheet("color: #707090; font-size: 11px;")
        self.hf_info_label.setWordWrap(True)
        fr_layout.addWidget(self.hf_info_label, r, 0, 1, 2)
        r += 1

        fr_layout.addWidget(QLabel("Fc HF taglio:"), r, 0)
        self.hf_fc_spin = QDoubleSpinBox()
        self.hf_fc_spin.setRange(100, 5000)
        self.hf_fc_spin.setValue(700.0)
        self.hf_fc_spin.setSuffix(" Hz")
        self.hf_fc_spin.setDecimals(0)
        self.hf_fc_spin.setToolTip("Frequenza di taglio -3dB della tromba HF")
        fr_layout.addWidget(self.hf_fc_spin, r, 1)
        r += 1

        fr_layout.addWidget(QLabel("Sm/Sg HF:"), r, 0)
        self.hf_ratio_spin = QDoubleSpinBox()
        self.hf_ratio_spin.setRange(1.1, 100.0)
        self.hf_ratio_spin.setValue(5.0)
        self.hf_ratio_spin.setDecimals(1)
        fr_layout.addWidget(self.hf_ratio_spin, r, 1)
        r += 1

        fr_layout.addWidget(QLabel("Compressione HF:"), r, 0)
        self.hf_compression_spin = QDoubleSpinBox()
        self.hf_compression_spin.setRange(1.0, 50.0)
        self.hf_compression_spin.setValue(10.0)
        self.hf_compression_spin.setDecimals(1)
        self.hf_compression_spin.setToolTip("Tipicamente 4–16x per compression driver")
        fr_layout.addWidget(self.hf_compression_spin, r, 1)
        r += 1

        fr_layout.addWidget(self._hsep(), r, 0, 1, 2)
        r += 1

        fr_layout.addWidget(QLabel("Crossover:"), r, 0)
        self.xover_spin = QDoubleSpinBox()
        self.xover_spin.setRange(100, 5000)
        self.xover_spin.setValue(700.0)
        self.xover_spin.setSuffix(" Hz")
        self.xover_spin.setDecimals(0)
        self.xover_spin.setToolTip("Frequenza di crossover tra LF e HF")
        fr_layout.addWidget(self.xover_spin, r, 1)
        r += 1

        fr_layout.addWidget(QLabel("Pendenza:"), r, 0)
        self.xover_slope_combo = QComboBox()
        for label, val in [("12 dB/ott", 12), ("18 dB/ott", 18),
                           ("24 dB/ott", 24), ("48 dB/ott", 48)]:
            self.xover_slope_combo.addItem(label, val)
        self.xover_slope_combo.setCurrentIndex(2)   # 24 dB/ott default
        fr_layout.addWidget(self.xover_slope_combo, r, 1)
        r += 1

        fr_layout.addWidget(QLabel("Tipo crossover:"), r, 0)
        self.xover_type_combo = QComboBox()
        for label, val in [("Linkwitz-Riley", "linkwitz_riley"),
                           ("Butterworth", "butterworth"),
                           ("Bessel", "bessel")]:
            self.xover_type_combo.addItem(label, val)
        fr_layout.addWidget(self.xover_type_combo, r, 1)

        self.gb_fullrange = self._group("FULLRANGE: DRIVER HF + CROSSOVER", fr_layout)
        vbox.addWidget(self.gb_fullrange)

        # Spacer finale nello scroll
        vbox.addStretch(1)

        # ── Geometria cabinet (fr scroll e pulsante Calcola) ─────────────
        geom_row = QWidget()
        geom_grid = QGridLayout(geom_row)
        geom_grid.setContentsMargins(10, 4, 10, 2)

        # ── Pulsante Calcola fisso in fondo ───────────────────────────────
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

        # ── Popolamento iniziale ──────────────────────────────────────────
        self._refresh_variant_combo()
        self._update_section_visibility()
        self._reload_driver_combo(SPEAKER_TYPE_SUB)

    # ── Slot interni ──────────────────────────────────────────────────────────

    def _on_category_changed(self, btn):
        """Cambio categoria enclosure (TROMBA / REFLEX / HYBRID)."""
        for cat, b in self._encl_btns.items():
            if b is btn:
                self._enclosure_category = cat
                break
        self._refresh_variant_combo()
        self._update_section_visibility()

    def _refresh_variant_combo(self):
        """Aggiorna il combo varianti in base alla categoria selezionata."""
        self.variant_combo.blockSignals(True)
        self.variant_combo.clear()
        for v in ENCLOSURE_VARIANTS[self._enclosure_category]:
            self.variant_combo.addItem(ENCLOSURE_LABELS[v], v)
        self.variant_combo.blockSignals(False)
        self.variant_combo.setCurrentIndex(0)
        self._on_variant_changed()

    def _on_variant_changed(self):
        """Cambio variante (es. Horn → Reflex → Bandpass_4)."""
        v = self.variant_combo.currentData()
        if v:
            self._enclosure_type = v
        self._update_section_visibility()
        # Aggiorna Fc default all'accordo con il tipo di enclosure
        if self._enclosure_type in ENCLOSURE_HAS_HORN:
            if self.type_combo.currentData() == SPEAKER_TYPE_SUB:
                self.fc_spin.setValue(70.0)

    def _update_section_visibility(self):
        """Mostra/nasconde i GroupBox in base al tipo di enclosure selezionato."""
        enc = self._enclosure_type
        has_horn   = enc in ENCLOSURE_HAS_HORN
        has_reflex = enc in ENCLOSURE_HAS_REFLEX
        is_bp      = enc in ENCLOSURE_IS_BANDPASS

        self.gb_horn_params.setVisible(has_horn)
        self.gb_horn_type.setVisible(has_horn)
        self._n_sect_label.setVisible(has_horn)
        self.n_sections_spin.setVisible(has_horn)

        self.gb_reflex_params.setVisible(has_reflex and not is_bp)
        self.gb_bp_params.setVisible(is_bp)
        self.gb_port_type.setVisible(has_reflex)
        self._n_ports_label.setVisible(has_reflex)
        self.n_ports_spin.setVisible(has_reflex)

        # Fullrange: visibile solo quando speaker_type == FULLRANGE
        is_fullrange = (self.type_combo.currentData() == SPEAKER_TYPE_FULLRANGE)
        self.gb_fullrange.setVisible(is_fullrange)
        if is_fullrange and not self.hf_combo.count():
            self._reload_hf_combo()

    def _on_type_changed(self):
        """Cambio tipo speaker (SUB / CD / FULLRANGE)."""
        speaker_type = self.type_combo.currentData()
        if speaker_type == SPEAKER_TYPE_CD:
            self.fc_spin.setValue(500.0)
            self.compression_spin.setValue(4.0)
        elif speaker_type == SPEAKER_TYPE_SUB:
            self.fc_spin.setValue(70.0)
            self.compression_spin.setValue(1.0)
        elif speaker_type == SPEAKER_TYPE_FULLRANGE:
            self.fc_spin.setValue(50.0)          # LF cutoff
            self.compression_spin.setValue(1.0)
            self._reload_hf_combo()
        else:
            self.fc_spin.setValue(100.0)
            self.compression_spin.setValue(1.0)
        self._reload_driver_combo(speaker_type)
        self._update_section_visibility()

    def _on_expansion_changed(self):
        """Mostra/nasconde Hypex T."""
        is_hypex = (self.expansion_combo.currentData() == EXPANSION_HYPEX)
        self._hypex_t_label.setVisible(is_hypex)
        self._hypex_t_spin.setVisible(is_hypex)

    def _on_port_type_changed(self):
        """Mostra campo diametro o dimensioni slot."""
        pt = self.port_type_combo.currentData()
        is_circ = (pt == PORT_TYPE_CIRCULAR)
        is_slot = (pt == PORT_TYPE_SLOT)
        self._port_diam_label.setVisible(is_circ)
        self.port_diam_spin.setVisible(is_circ)
        self._slot_w_label.setVisible(is_slot)
        self.slot_w_spin.setVisible(is_slot)
        self._slot_h_label.setVisible(is_slot)
        self.slot_h_spin.setVisible(is_slot)

    def _update_vol_estimate(self):
        """Aggiorna il label con il volume interno stimato dalle dimensioni esterne."""
        w = self.ext_width_spin.value()
        h = self.ext_height_spin.value()
        d = self.ext_depth_spin.value()
        t = self.wood_thickness_spin.value()
        all_set = w > 0 and h > 0 and d > 0
        if not all_set:
            self._vol_estimate_label.setText("Volume interno: —")
            self._vol_estimate_label.setStyleSheet(
                "color: #A0E0A0; font-size: 11px; font-weight: bold; padding: 2px;"
            )
            return
        if w <= 2 * t or h <= 2 * t or d <= 2 * t:
            self._vol_estimate_label.setText("⚠ Dimensioni troppo piccole per lo spessore legno")
            self._vol_estimate_label.setStyleSheet(
                "color: #E0A040; font-size: 11px; font-weight: bold; padding: 2px;"
            )
            return
        wi = (w - 2 * t) / 1000.0
        hi = (h - 2 * t) / 1000.0
        di = (d - 2 * t) / 1000.0
        vol_l = wi * hi * di * 1000.0
        self._vol_estimate_label.setText(f"Volume interno: ~{vol_l:.1f} L")
        self._vol_estimate_label.setStyleSheet(
            "color: #A0E0A0; font-size: 11px; font-weight: bold; padding: 2px;"
        )

    def _reload_driver_combo(self, speaker_type: str):
        type_map = {
            SPEAKER_TYPE_SUB: "subwoofer",
            SPEAKER_TYPE_CD: "compression_driver",
            SPEAKER_TYPE_FULLRANGE: "subwoofer",   # LF section = subwoofer
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
        type_map = {
            SPEAKER_TYPE_SUB: "subwoofer",
            SPEAKER_TYPE_CD: "compression_driver",
            SPEAKER_TYPE_FULLRANGE: "subwoofer",  # LF driver per fullrange
        }
        filter_type = type_map.get(self.type_combo.currentData())
        dlg = DriverPickerDialog(self, filter_type=filter_type)
        if dlg.exec_() == QDialog.Accepted and dlg.selected_driver:
            self._set_driver(dlg.selected_driver)
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

    # ── HF driver (Fullrange) ─────────────────────────────────────────────────

    def _reload_hf_combo(self):
        """Popola il combo del driver HF con compression driver."""
        drivers = get_drivers_by_type("compression_driver")
        self.hf_combo.blockSignals(True)
        self.hf_combo.clear()
        self.hf_combo.addItem("-- Seleziona CD HF --", None)
        for d in drivers:
            label = f"{d.manufacturer}  {d.model}  ({d.diameter_inch}\" / {d.power_rms:.0f}W)"
            self.hf_combo.addItem(label, d)
        self.hf_combo.blockSignals(False)
        self.hf_combo.setCurrentIndex(0)
        self._selected_hf_driver = None
        self.hf_info_label.setText("Nessun driver HF selezionato")

    def _on_hf_combo_changed(self):
        driver = self.hf_combo.currentData()
        if isinstance(driver, DriverModel):
            self._set_hf_driver(driver)

    def _open_hf_driver_picker(self):
        dlg = DriverPickerDialog(self, filter_type="compression_driver")
        if dlg.exec_() == QDialog.Accepted and dlg.selected_driver:
            self._set_hf_driver(dlg.selected_driver)
            for i in range(self.hf_combo.count()):
                d = self.hf_combo.itemData(i)
                if isinstance(d, DriverModel) and d.model == dlg.selected_driver.model:
                    self.hf_combo.blockSignals(True)
                    self.hf_combo.setCurrentIndex(i)
                    self.hf_combo.blockSignals(False)
                    break

    def _set_hf_driver(self, driver: DriverModel):
        self._selected_hf_driver = driver
        self.hf_info_label.setText(
            f"<b>{driver.manufacturer} {driver.model}</b><br>"
            f"Fs={driver.fs:.0f}Hz  Qts={driver.qts:.3f}  "
            f"SPL={driver.spl_1w_1m:.1f}dB  {driver.power_rms:.0f}W"
        )

    def _on_calculate(self):
        speaker_type = self.type_combo.currentData()
        if self._selected_driver is None:
            self.calculate_requested.emit({"error": "no_driver"})
            return
        if speaker_type == SPEAKER_TYPE_FULLRANGE and self._selected_hf_driver is None:
            self.calculate_requested.emit({"error": "no_hf_driver"})
            return
        self.calculate_requested.emit(self.get_params())

    # ── API pubblica ──────────────────────────────────────────────────────────

    def get_params(self) -> dict:
        """Dizionario completo con tutti i parametri per il motore di calcolo."""
        return {
            "speaker_type":       self.type_combo.currentData(),
            "enclosure_category": self._enclosure_category,
            "enclosure_type":     self._enclosure_type,
            "driver":             self._selected_driver,
            # ── Horn params ──
            "fc_hz":              self.fc_spin.value(),
            "expansion_type":     self.expansion_combo.currentData(),
            "hypex_T":            self._hypex_t_spin.value(),
            "smouth_ratio":       self.ratio_spin.value(),
            "compression_ratio":  self.compression_spin.value(),
            "n_sections":         self.n_sections_spin.value(),
            "geometry_type":      self.geometry_combo.currentData(),
            # ── Fullrange params ──
            "hf_driver":          self._selected_hf_driver,
            "hf_fc_hz":           self.hf_fc_spin.value(),
            "hf_smouth_ratio":    self.hf_ratio_spin.value(),
            "hf_compression_ratio": self.hf_compression_spin.value(),
            "crossover_hz":       self.xover_spin.value(),
            "crossover_slope":    self.xover_slope_combo.currentData(),
            "crossover_type":     self.xover_type_combo.currentData(),
            # ── Reflex params ──
            "fb_hz":              self.fb_spin.value(),
            "box_volume_l":       self.vbox_spin.value(),
            "f_low_hz":           self.f_low_spin.value(),
            "f_high_hz":          self.f_high_spin.value(),
            "box_rear_volume_l":  self.vb_rear_spin.value(),
            "port_type":          self.port_type_combo.currentData(),
            "port_diameter_mm":   self.port_diam_spin.value(),
            "port_slot_width_mm": self.slot_w_spin.value(),
            "port_slot_height_mm":self.slot_h_spin.value(),
            "n_ports":            self.n_ports_spin.value(),
            # ── Dimensional constraints (external box dimensions) ──
            "ext_width_mm":      self.ext_width_spin.value() or None,
            "ext_height_mm":     self.ext_height_spin.value() or None,
            "ext_depth_mm":      self.ext_depth_spin.value() or None,
            "wood_thickness_mm": self.wood_thickness_spin.value(),
            "max_width_mm":      self.ext_width_spin.value() or None,
            "max_height_mm":     self.ext_height_spin.value() or None,
            "max_depth_mm":      self.ext_depth_spin.value() or None,
        }

    def set_params(self, params: dict):
        """Ricarica l'interfaccia da un dizionario (usato da Apri progetto)."""
        if "enclosure_category" in params:
            cat = params["enclosure_category"]
            if cat in self._encl_btns:
                self._encl_btns[cat].setChecked(True)
                self._enclosure_category = cat
                self._refresh_variant_combo()
        if "enclosure_type" in params:
            for i in range(self.variant_combo.count()):
                if self.variant_combo.itemData(i) == params["enclosure_type"]:
                    self.variant_combo.setCurrentIndex(i)
                    break
        if "speaker_type" in params:
            for i in range(self.type_combo.count()):
                if self.type_combo.itemData(i) == params["speaker_type"]:
                    self.type_combo.setCurrentIndex(i)
                    break
        if "fc_hz" in params:       self.fc_spin.setValue(params["fc_hz"])
        if "expansion_type" in params:
            for i in range(self.expansion_combo.count()):
                if self.expansion_combo.itemData(i) == params["expansion_type"]:
                    self.expansion_combo.setCurrentIndex(i); break
        if "hypex_T" in params:     self._hypex_t_spin.setValue(params["hypex_T"])
        if "smouth_ratio" in params: self.ratio_spin.setValue(params["smouth_ratio"])
        if "compression_ratio" in params: self.compression_spin.setValue(params["compression_ratio"])
        if "n_sections" in params:  self.n_sections_spin.setValue(params["n_sections"])
        if "geometry_type" in params:
            for i in range(self.geometry_combo.count()):
                if self.geometry_combo.itemData(i) == params["geometry_type"]:
                    self.geometry_combo.setCurrentIndex(i); break
        if "max_width_mm" in params and params["max_width_mm"]:
            self.ext_width_spin.setValue(params["max_width_mm"])
        if "max_height_mm" in params and params["max_height_mm"]:
            self.ext_height_spin.setValue(params["max_height_mm"])
        if "max_depth_mm" in params and params["max_depth_mm"]:
            self.ext_depth_spin.setValue(params["max_depth_mm"])
        if "ext_width_mm" in params and params["ext_width_mm"]:
            self.ext_width_spin.setValue(params["ext_width_mm"])
        if "ext_height_mm" in params and params["ext_height_mm"]:
            self.ext_height_spin.setValue(params["ext_height_mm"])
        if "ext_depth_mm" in params and params["ext_depth_mm"]:
            self.ext_depth_spin.setValue(params["ext_depth_mm"])
        if "wood_thickness_mm" in params:
            self.wood_thickness_spin.setValue(params["wood_thickness_mm"])

        # ── Reflex / Bandpass params ──────────────────────────────────────
        if "fb_hz" in params:
            self.fb_spin.setValue(params["fb_hz"])
        if "box_volume_l" in params and params["box_volume_l"]:
            self.vbox_spin.setValue(params["box_volume_l"])
        if "f_low_hz" in params:
            self.f_low_spin.setValue(params["f_low_hz"])
        if "f_high_hz" in params:
            self.f_high_spin.setValue(params["f_high_hz"])
        if "box_rear_volume_l" in params and params["box_rear_volume_l"]:
            self.vb_rear_spin.setValue(params["box_rear_volume_l"])
        if "port_type" in params:
            for i in range(self.port_type_combo.count()):
                if self.port_type_combo.itemData(i) == params["port_type"]:
                    self.port_type_combo.setCurrentIndex(i); break
        if "port_diameter_mm" in params:
            self.port_diam_spin.setValue(params["port_diameter_mm"])
        if "port_slot_width_mm" in params:
            self.slot_w_spin.setValue(params["port_slot_width_mm"])
        if "port_slot_height_mm" in params:
            self.slot_h_spin.setValue(params["port_slot_height_mm"])
        if "n_ports" in params:
            self.n_ports_spin.setValue(int(params["n_ports"]))
        # ── Fullrange params ──────────────────────────────────────────────
        if "hf_fc_hz" in params:
            self.hf_fc_spin.setValue(params["hf_fc_hz"])
        if "hf_smouth_ratio" in params:
            self.hf_ratio_spin.setValue(params["hf_smouth_ratio"])
        if "hf_compression_ratio" in params:
            self.hf_compression_spin.setValue(params["hf_compression_ratio"])
        if "crossover_hz" in params:
            self.xover_spin.setValue(params["crossover_hz"])
        if "crossover_slope" in params:
            for i in range(self.xover_slope_combo.count()):
                if self.xover_slope_combo.itemData(i) == params["crossover_slope"]:
                    self.xover_slope_combo.setCurrentIndex(i); break
        if "crossover_type" in params:
            for i in range(self.xover_type_combo.count()):
                if self.xover_type_combo.itemData(i) == params["crossover_type"]:
                    self.xover_type_combo.setCurrentIndex(i); break
        if "hf_driver_model" in params:
            d = get_driver_by_model(params["hf_driver_model"])
            if d:
                self._set_hf_driver(d)
        if "driver_model" in params:
            d = get_driver_by_model(params["driver_model"])
            if d:
                self._set_driver(d)
