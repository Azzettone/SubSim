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
        QWidget, QVBoxLayout, QFormLayout, QGroupBox,
        QLabel, QComboBox, QDoubleSpinBox
    )
    from PyQt5.QtCore import Qt, pyqtSignal as Signal
    from PyQt5.QtGui import QFont
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QFormLayout, QGroupBox,
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
    Pannello inferiore sinistro: parametri di configurazione del design.
    Emette geometry_changed quando l'utente cambia la geometria.
    """

    geometry_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        self.setMinimumWidth(390)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(8)

        # ── Geometria tromba ───────────────────────────────────────────────
        group_geom = QGroupBox("Geometria Cabinet")
        form_geom = QFormLayout(group_geom)
        form_geom.setSpacing(7)
        form_geom.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.geometry_combo = QComboBox()
        for g in GEOMETRY_TYPES:
            self.geometry_combo.addItem(GEOMETRY_LABELS[g], g)
        self.geometry_combo.currentIndexChanged.connect(
            lambda: self.geometry_changed.emit(self.geometry_combo.currentData())
        )
        form_geom.addRow("Geometria:", self.geometry_combo)

        # Descrizione geometria selezionata
        self.geom_desc_label = QLabel(
            "Tromba dritta — massima lunghezza, costruzione semplice."
        )
        self.geom_desc_label.setWordWrap(True)
        self.geom_desc_label.setStyleSheet("color: #808080; font-size: 11px;")
        form_geom.addRow(self.geom_desc_label)
        self.geometry_combo.currentIndexChanged.connect(self._update_geom_desc)

        layout.addWidget(group_geom)

        # ── Parametri fisici ───────────────────────────────────────────────
        group_phys = QGroupBox("Parametri Fisici")
        form_phys = QFormLayout(group_phys)
        form_phys.setSpacing(7)
        form_phys.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(-20, 50)
        self.temperature_spin.setValue(16.8)
        self.temperature_spin.setSuffix(" °C")
        self.temperature_spin.setDecimals(1)
        self.temperature_spin.setToolTip(
            "Temperatura dell'aria. Influenza la velocità del suono "
            "e quindi il flare rate e la lunghezza della tromba.\n"
            "Default: 16.8°C (valore del foglio originale)"
        )
        form_phys.addRow("Temperatura aria:", self.temperature_spin)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0, 500)
        self.price_spin.setValue(30.0)
        self.price_spin.setSuffix(" €/m²")
        self.price_spin.setDecimals(2)
        self.price_spin.setToolTip("Prezzo del pannello MDF per m² — usato per la stima costo materiali")
        form_phys.addRow("Prezzo legno:", self.price_spin)

        layout.addWidget(group_phys)

        # ── Riepilogo dimensioni (aggiornato dopo calcolo) ─────────────────
        group_summary = QGroupBox("Dimensioni Cabinet")
        summary_layout = QVBoxLayout(group_summary)

        self.summary_label = QLabel("—\n—\n—")
        self.summary_label.setAlignment(Qt.AlignLeft)
        self.summary_label.setStyleSheet(
            "font-family: monospace; font-size: 12px; color: #C0C0E0;"
        )
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)

        layout.addWidget(group_summary)
        layout.addStretch()

    # ── Slot interni ──────────────────────────────────────────────────────────

    _GEOM_DESCRIPTIONS = {
        GEOMETRY_STRAIGHT: "Tromba dritta — massima lunghezza, costruzione semplice.",
        GEOMETRY_FOLDED:   "Una piega a U — riduce la profondità del cabinet a metà.",
        GEOMETRY_2FOLDED:  "Due pieghe — massima compattezza, costruzione più complessa.",
    }

    def _update_geom_desc(self):
        g = self.geometry_combo.currentData()
        self.geom_desc_label.setText(self._GEOM_DESCRIPTIONS.get(g, ""))

    # ── API pubblica ──────────────────────────────────────────────────────────

    def get_params(self) -> dict:
        return {
            "geometry_type":  self.geometry_combo.currentData(),
            "temperature_c":  self.temperature_spin.value(),
            "wood_price":     self.price_spin.value(),
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
        """
        Aggiorna il riepilogo dimensioni dopo un calcolo.
        cabinet: CabinetGeometry
        """
        geom_labels = {
            GEOMETRY_STRAIGHT: "Straight",
            GEOMETRY_FOLDED: "Folded",
            GEOMETRY_2FOLDED: "2-Folded",
        }
        g_label = geom_labels.get(cabinet.geometry_type, cabinet.geometry_type)
        cost = cabinet.total_cost(self.price_spin.value())
        self.summary_label.setText(
            f"Tipo:       {g_label}\n"
            f"L × A × P:  {cabinet.total_width_mm:.0f} × "
            f"{cabinet.total_height_mm:.0f} × "
            f"{cabinet.total_depth_mm:.0f} mm\n"
            f"Volume:     {cabinet.volume_m3 * 1000:.1f} L\n"
            f"Costo MDF:  € {cost:.2f}"
        )
