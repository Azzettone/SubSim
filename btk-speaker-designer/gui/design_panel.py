"""
Pannello sinistro inferiore: Riepilogo dimensioni cabinet.

Mostra le dimensioni calcolate del cabinet (aggiornate dopo ogni calcolo).
La geometria e i parametri fisici sono ora gestiti in InputPanel.
"""

try:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QGridLayout, QFrame, QLabel
    )
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QFont
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QGridLayout, QFrame, QLabel
    )
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont

from ..core.constants import (
    GEOMETRY_STRAIGHT, GEOMETRY_FOLDED, GEOMETRY_2FOLDED,
)

# Valori di default usati nei calcoli (non esposti in UI)
_WOOD_PRICE_DEFAULT = 30.0    # €/m²
_TEMPERATURE_DEFAULT = 16.8   # °C


class DesignPanel(QWidget):
    """
    Pannello inferiore sinistro: riepilogo dimensioni cabinet.
    Aggiornato da main_window dopo ogni calcolo.
    """

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

    # ── API pubblica ──────────────────────────────────────────────────────────

    def get_params(self) -> dict:
        return {
            "wood_price":    _WOOD_PRICE_DEFAULT,
            "temperature_c": _TEMPERATURE_DEFAULT,
        }

    def set_params(self, params: dict):
        """Compatibilità con salvataggio progetti — nessun widget da ripristinare."""
        pass

    def update_cabinet_summary(self, cabinet):
        geom_labels = {
            GEOMETRY_STRAIGHT: "Straight",
            GEOMETRY_FOLDED:   "Folded",
            GEOMETRY_2FOLDED:  "2-Folded",
        }
        g_label = geom_labels.get(cabinet.geometry_type, cabinet.geometry_type)
        cost = cabinet.total_cost(_WOOD_PRICE_DEFAULT)
        self.summary_label.setText(
            f"Tipo:   {g_label}\n"
            f"L×A×P:  {cabinet.total_width_mm:.0f}×"
            f"{cabinet.total_height_mm:.0f}×"
            f"{cabinet.total_depth_mm:.0f} mm\n"
            f"Vol:    {cabinet.volume_m3 * 1000:.1f} L  |  "
            f"MDF: €{cost:.0f}"
        )
