"""
Widget per la selezione del tipo di speaker (SUB / CD / FULLRANGE).
Prima schermata del flusso di progettazione.
"""

try:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QButtonGroup, QGroupBox, QFrame,
        QRadioButton, QTextBrowser
    )
    from PyQt5.QtCore import Qt, pyqtSignal as Signal
    from PyQt5.QtGui import QFont
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QButtonGroup, QGroupBox, QFrame,
        QRadioButton, QTextBrowser
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont

from ..core.constants import (
    SPEAKER_TYPE_SUB, SPEAKER_TYPE_CD, SPEAKER_TYPE_FULLRANGE,
    SPEAKER_TYPE_LABELS, GEOMETRY_LABELS, GEOMETRY_STRAIGHT, GEOMETRY_FOLDED, GEOMETRY_2FOLDED
)


SPEAKER_DESCRIPTIONS = {
    SPEAKER_TYPE_SUB: """
        <h3>Subwoofer (SUB)</h3>
        <p><b>Range frequenze:</b> 20 - 200 Hz</p>
        <p><b>Driver:</b> Woofer/Subwoofer a cono (12" - 21")</p>
        <p><b>Applicazioni:</b> Casse da basso, subwoofer PA, sistemi subgrave</p>
        <p><b>Tromba:</b> Carico acustico per estendere le basse frequenze
        e aumentare l'efficienza meccanica del driver.</p>
        <p><b>Vantaggi:</b> SPL più elevato, migliore risposta ai transienti,
        controllo della direttività a basse frequenze.</p>
    """,
    SPEAKER_TYPE_CD: """
        <h3>Compression Driver (CD)</h3>
        <p><b>Range frequenze:</b> 500 - 20.000 Hz</p>
        <p><b>Driver:</b> Compression driver (1" - 2") a diaframma</p>
        <p><b>Applicazioni:</b> Medi-alti PA, monitor, line array</p>
        <p><b>Tromba:</b> Controlla la direttività e aumenta l'efficienza.
        La forma della tromba determina il pattern di dispersione.</p>
        <p><b>Vantaggi:</b> Alta efficienza (110+ dB/1W/1m), bassa distorsione,
        controllo preciso del pattern orizzontale/verticale.</p>
    """,
    SPEAKER_TYPE_FULLRANGE: """
        <h3>Fullrange (CD + SUB combinato)</h3>
        <p><b>Range frequenze:</b> 20 - 20.000 Hz</p>
        <p><b>Driver:</b> Compression driver + Woofer/Subwoofer</p>
        <p><b>Applicazioni:</b> Casse fullrange professionali, main system</p>
        <p><b>Caratteristiche:</b></p>
        <ul>
        <li>Sezione HF: CD + tromba medi-alti</li>
        <li>Sezione LF: Sub + tromba basse</li>
        <li>Crossover integrato (configurabile)</li>
        <li>Calcolo somma acustica delle due sezioni</li>
        </ul>
        <p><b>Vantaggi:</b> Sistema completo in un unico cabinet, ottimizzazione
        acustica integrata HF+LF, controllo crossover preciso.</p>
    """,
}


class SpeakerTypeSelectorWidget(QWidget):
    """
    Widget per la selezione del tipo di speaker e della geometria tromba.
    Emette segnali quando l'utente effettua una selezione.
    """

    speaker_type_changed = Signal(str)
    geometry_type_changed = Signal(str)
    selection_confirmed = Signal(str, str)  # (speaker_type, geometry_type)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_type = SPEAKER_TYPE_SUB
        self._selected_geometry = GEOMETRY_STRAIGHT
        self._build_ui()

    def _build_ui(self):
        """Costruisce l'interfaccia del selettore."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Titolo
        title = QLabel("Seleziona il tipo di sistema da progettare")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)

        # Layout orizzontale: selezione a sinistra, descrizione a destra
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        # ─── Pannello selezione tipo ──────────────────────────────────────
        type_group = QGroupBox("Tipo di Speaker")
        type_layout = QVBoxLayout(type_group)

        self.type_btn_group = QButtonGroup(self)

        type_data = [
            (SPEAKER_TYPE_SUB,       "🔊 Subwoofer (Basse Frequenze)",     "30 - 200 Hz"),
            (SPEAKER_TYPE_CD,        "📢 Compression Driver (Medi/Alti)",  "500 - 20.000 Hz"),
            (SPEAKER_TYPE_FULLRANGE, "🎵 Fullrange (CD + SUB)",            "20 - 20.000 Hz"),
        ]

        for i, (type_id, label, freq_range) in enumerate(type_data):
            btn = QRadioButton(f"{label}\n    {freq_range}")
            btn.setProperty("speaker_type", type_id)
            if i == 0:
                btn.setChecked(True)
            self.type_btn_group.addButton(btn, i)
            type_layout.addWidget(btn)
            # Spazio tra i pulsanti
            if i < len(type_data) - 1:
                type_layout.addSpacing(4)

        type_layout.addStretch()
        content_layout.addWidget(type_group, 2)

        # ─── Pannello selezione geometria ─────────────────────────────────
        geom_group = QGroupBox("Geometria Tromba")
        geom_layout = QVBoxLayout(geom_group)

        self.geom_btn_group = QButtonGroup(self)

        geom_data = [
            (GEOMETRY_STRAIGHT, "📏 Dritta (Straight)",
             "Tromba rettilinea\nMassima lunghezza, minima complessità"),
            (GEOMETRY_FOLDED,   "↩ Piegata 1 volta (Folded)",
             "Una piega a U\nRiduce la profondità del cabinet"),
            (GEOMETRY_2FOLDED,  "↩↩ Piegata 2 volte (2-Folded)",
             "Due pieghe\nMassima compattezza"),
        ]

        for i, (geom_id, label, desc) in enumerate(geom_data):
            btn = QRadioButton(f"{label}\n    {desc}")
            btn.setProperty("geometry_type", geom_id)
            if i == 0:
                btn.setChecked(True)
            self.geom_btn_group.addButton(btn, i)
            geom_layout.addWidget(btn)
            if i < len(geom_data) - 1:
                geom_layout.addSpacing(4)

        geom_layout.addStretch()
        content_layout.addWidget(geom_group, 2)

        # ─── Pannello descrizione ─────────────────────────────────────────
        self.description_browser = QTextBrowser()
        self.description_browser.setMinimumWidth(350)
        self.description_browser.setHtml(SPEAKER_DESCRIPTIONS[SPEAKER_TYPE_SUB])
        content_layout.addWidget(self.description_browser, 3)

        # ─── Pulsante conferma ────────────────────────────────────────────
        confirm_btn = QPushButton("Conferma e Continua →")
        confirm_btn.setMinimumHeight(40)
        confirm_btn.clicked.connect(self._confirm_selection)
        main_layout.addWidget(confirm_btn)

        # Connetti segnali
        self.type_btn_group.buttonClicked.connect(self._on_type_changed)

    def _on_type_changed(self, btn):
        """Aggiorna la descrizione quando cambia il tipo selezionato."""
        type_id = btn.property("speaker_type")
        if type_id:
            self._selected_type = type_id
            self.description_browser.setHtml(
                SPEAKER_DESCRIPTIONS.get(type_id, "")
            )
            self.speaker_type_changed.emit(type_id)

    def _confirm_selection(self):
        """Conferma la selezione e passa alla schermata successiva."""
        # Leggi tipo selezionato
        checked_type = self.type_btn_group.checkedButton()
        if checked_type:
            self._selected_type = checked_type.property("speaker_type")

        # Leggi geometria selezionata
        checked_geom = self.geom_btn_group.checkedButton()
        if checked_geom:
            self._selected_geometry = checked_geom.property("geometry_type")

        # Notifica il genitore
        if hasattr(self.parent(), 'set_speaker_type'):
            self.parent().set_speaker_type(self._selected_type)

        if hasattr(self.parent(), 'current_project'):
            self.parent().current_project["speaker_type"] = self._selected_type
            self.parent().current_project["geometry_type"] = self._selected_geometry

        # Passa alla tab successiva
        if hasattr(self.parent(), 'tab_widget'):
            self.parent().tab_widget.setCurrentIndex(1)

        self.selection_confirmed.emit(self._selected_type, self._selected_geometry)

    @property
    def selected_type(self) -> str:
        return self._selected_type

    @property
    def selected_geometry(self) -> str:
        return self._selected_geometry
