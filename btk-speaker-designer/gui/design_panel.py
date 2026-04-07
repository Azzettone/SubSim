"""
Pannello sinistro inferiore: Parametri di modifica design.

Contiene:
  - Selezione geometria cabinet (Straight / Folded / 2-Folded)
  - Temperatura aria (influenza velocità del suono)
  - Prezzo legno (per stima costo materiali)
  - Riepilogo dimensioni cabinet (aggiornato dopo ogni calcolo)
"""

try:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QGridLayout, QFrame,
        QLabel, QComboBox, QDoubleSpinBox
    )
    from PyQt5.QtCore import Qt, pyqtSignal as Signal
    from PyQt5.QtGui import QFont
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QGridLayout, QFrame,
        QLabel, QComboBox, QDoubleSpinBox
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont

from ..core.constants import (
    GEOMETRY_STRAIGHT, GEOMETRY_FOLDED, GEOMETRY_2FOLDED,
    GEOMETRY_LABELS, GEOMETRY_TYPES,
)


class DesignPanel(QWidget):
    """
    Pannello inferiore sinistro: geometria, parametri fisici, riepilogo cabinet.
    Emette geometry_changed quando l'utente cambia la geometria.
    """

    geometry_changed = Signal(str)

    _GEOM_DESCRIPTIONS = {
        GEOMETRY_STRAIGHT: "Dritta — lunghezza massima, costruzione semplice.",
        GEOMETRY_FOLDED:   "Piega U — profondità dimezzata.",
        GEOMETRY_2FOLDED:  "2 Pieghe — massima compattezza.",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ── Utility ──────────────────────────────────────────────────────────────

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #7C9EF0; font-size: 11px; font-weight: bold;"
            "border-bottom: 1px solid #2A2A44; padding-bottom: 2px;"
        )
        return lbl

    @staticmethod
    def _hsep() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #2A2A44;")
        line.setFixedHeight(1)
        return line

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(0)

        grid = QGridLayout()
        grid.setVerticalSpacing(5)
        grid.setHorizontalSpacing(8)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        row = 0

        # ══ GEOMETRIA CABINET ════════════════════════════════════════════
        grid.addWidget(self._section_label("GEOMETRIA CABINET"), row, 0, 1, 2)
        row += 1

        grid.addWidget(QLabel("Geometria:"), row, 0)
        self.geometry_combo = QComboBox()
        for g in GEOMETRY_TYPES:
            self.geometry_combo.addItem(GEOMETRY_LABELS[g], g)
        self.geometry_combo.currentIndexChanged.connect(
            lambda: self.geometry_changed.emit(self.geometry_combo.currentData())
        )
        self.geometry_combo.currentIndexChanged.connect(self._update_geom_desc)
        grid.addWidget(self.geometry_combo, row, 1)
        row += 1

        self.geom_desc_label = QLabel(self._GEOM_DESCRIPTIONS[GEOMETRY_STRAIGHT])
        self.geom_desc_label.setWordWrap(True)
        self.geom_desc_label.setStyleSheet("color: #707090; font-size: 10px;")
        grid.addWidget(self.geom_desc_label, row, 0, 1, 2)
        row += 1

        grid.addWidget(self._hsep(), row, 0, 1, 2)
        row += 1

        # ══ PARAMETRI FISICI ═════════════════════════════════════════════
        grid.addWidget(self._section_label("PARAMETRI FISICI"), row, 0, 1, 2)
        row += 1

        grid.addWidget(QLabel("Temperatura:"), row, 0)
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(-20, 50)
        self.temperature_spin.setValue(16.8)
        self.temperature_spin.setSuffix(" °C")
        self.temperature_spin.setDecimals(1)
        self.temperature_spin.setToolTip("Influenza velocità del suono e flare rate. Default: 16.8°C")
        grid.addWidget(self.temperature_spin, row, 1)
        row += 1

        grid.addWidget(QLabel("Prezzo legno:"), row, 0)
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0, 500)
        self.price_spin.setValue(30.0)
        self.price_spin.setSuffix(" €/m²")
        self.price_spin.setDecimals(2)
        self.price_spin.setToolTip("Prezzo MDF per m² — stima costo materiali")
        grid.addWidget(self.price_spin, row, 1)
        row += 1

        grid.addWidget(self._hsep(), row, 0, 1, 2)
        row += 1

        # ══ RIEPILOGO CABINET ════════════════════════════════════════════
        grid.addWidget(self._section_label("DIMENSIONI CABINET"), row, 0, 1, 2)
        row += 1

        self.summary_label = QLabel("—\n—\n—")
        self.summary_label.setAlignment(Qt.AlignLeft)
        self.summary_label.setStyleSheet(
            "font-family: monospace; font-size: 11px; color: #C0C0E0;"
            "background: #1A1A2E; border-radius: 3px; padding: 6px;"
        )
        self.summary_label.setWordWrap(True)
        grid.addWidget(self.summary_label, row, 0, 1, 2)
        row += 1

        grid.setRowStretch(row, 1)
        layout.addStretch()

    # ── Slot ─────────────────────────────────────────────────────────────────

    def _update_geom_desc(self):
        g = self.geometry_combo.currentData()
        self.geom_desc_label.setText(self._GEOM_DESCRIPTIONS.get(g, ""))

    # ── API pubblica ──────────────────────────────────────────────────────────

    def get_params(self) -> dict:
        return {
            "geometry_type": self.geometry_combo.currentData(),
            "temperature_c": self.temperature_spin.value(),
            "wood_price":    self.price_spin.value(),
        }

    def set_params(self, params: dict):
        if "geometry_type" in params:
            for i in range(self.geometry_combo.count()):
                if self.geometry_combo.itemData(i) == params["geometry_type"]:
                    self.geometry_combo.setCurrentIndex(i)
                    break
        if "temperature_c" in params:
            self.temperature_spin.setValue(params["temperature_c"])
        if "wood_price" in params:
            self.price_spin.setValue(params["wood_price"])

    def update_cabinet_summary(self, cabinet):
        geom_labels = {
            GEOMETRY_STRAIGHT: "Straight",
            GEOMETRY_FOLDED:   "Folded",
            GEOMETRY_2FOLDED:  "2-Folded",
        }
        g_label = geom_labels.get(cabinet.geometry_type, cabinet.geometry_type)
        cost = cabinet.total_cost(self.price_spin.value())
        self.summary_label.setText(
            f"Tipo:   {g_label}\n"
            f"L×A×P:  {cabinet.total_width_mm:.0f}×"
            f"{cabinet.total_height_mm:.0f}×"
            f"{cabinet.total_depth_mm:.0f} mm\n"
            f"Vol:    {cabinet.volume_m3 * 1000:.1f} L  |  "
            f"MDF: €{cost:.0f}"
        )
