"""
Componenti UI condivisi tra SubSim e BTK Speaker Designer.
Fornisce widget e stili riutilizzabili basati su PyQt5/PySide6.
"""

# Questo modulo fornisce stili e costanti UI condivise.
# I widget concreti richiedono l'installazione di PyQt5 o PySide6.


# ─── Palette colori tema scuro professionale ─────────────────────────────────
THEME = {
    "background":       "#1E1E2E",
    "surface":          "#2A2A3E",
    "surface_light":    "#3A3A4E",
    "primary":          "#7C9EF0",
    "primary_dark":     "#5A7CD0",
    "accent":           "#F0A040",
    "text_primary":     "#E0E0F0",
    "text_secondary":   "#A0A0C0",
    "border":           "#4A4A6A",
    "success":          "#50C878",
    "warning":          "#FFB347",
    "error":            "#FF6B6B",
    "chart_bg":         "#181828",
}

# Colori per grafici (sequenza per linee multiple)
CHART_COLORS = [
    "#7C9EF0",  # blu
    "#F0A040",  # arancione
    "#50C878",  # verde
    "#FF6B6B",  # rosso
    "#C880E0",  # viola
    "#40D0D0",  # ciano
    "#FFD700",  # oro
    "#FF8C69",  # salmone
]

# ─── Stile Qt (QSS) ──────────────────────────────────────────────────────────
QSS_MAIN = f"""
QMainWindow, QDialog {{
    background-color: {THEME['background']};
    color: {THEME['text_primary']};
}}

QWidget {{
    background-color: {THEME['background']};
    color: {THEME['text_primary']};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}}

QGroupBox {{
    background-color: {THEME['surface']};
    border: 1px solid {THEME['border']};
    border-radius: 6px;
    margin-top: 12px;
    padding: 8px;
    font-weight: bold;
    color: {THEME['primary']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}}

QPushButton {{
    background-color: {THEME['primary_dark']};
    color: {THEME['text_primary']};
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: bold;
}}

QPushButton:hover {{
    background-color: {THEME['primary']};
}}

QPushButton:pressed {{
    background-color: {THEME['primary_dark']};
}}

QPushButton:disabled {{
    background-color: {THEME['border']};
    color: {THEME['text_secondary']};
}}

QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
    background-color: {THEME['surface_light']};
    border: 1px solid {THEME['border']};
    border-radius: 4px;
    padding: 4px 8px;
    color: {THEME['text_primary']};
}}

QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {THEME['primary']};
}}

QComboBox::drop-down {{
    border: none;
    background-color: {THEME['surface']};
}}

QComboBox QAbstractItemView {{
    background-color: {THEME['surface']};
    selection-background-color: {THEME['primary_dark']};
    border: 1px solid {THEME['border']};
}}

QTabWidget::pane {{
    border: 1px solid {THEME['border']};
    background-color: {THEME['surface']};
}}

QTabBar::tab {{
    background-color: {THEME['surface_light']};
    color: {THEME['text_secondary']};
    padding: 8px 16px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}

QTabBar::tab:selected {{
    background-color: {THEME['primary_dark']};
    color: {THEME['text_primary']};
}}

QTableWidget {{
    background-color: {THEME['surface']};
    alternate-background-color: {THEME['surface_light']};
    gridline-color: {THEME['border']};
    border: 1px solid {THEME['border']};
}}

QTableWidget::item:selected {{
    background-color: {THEME['primary_dark']};
}}

QHeaderView::section {{
    background-color: {THEME['surface_light']};
    color: {THEME['text_primary']};
    padding: 6px;
    border: 1px solid {THEME['border']};
    font-weight: bold;
}}

QScrollBar:vertical {{
    background-color: {THEME['surface']};
    width: 10px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background-color: {THEME['border']};
    border-radius: 5px;
    min-height: 20px;
}}

QLabel {{
    color: {THEME['text_primary']};
}}

QStatusBar {{
    background-color: {THEME['surface']};
    color: {THEME['text_secondary']};
    border-top: 1px solid {THEME['border']};
}}
"""

# ─── Configurazione Matplotlib tema scuro ────────────────────────────────────
MATPLOTLIB_STYLE = {
    "figure.facecolor": THEME["chart_bg"],
    "axes.facecolor": THEME["chart_bg"],
    "axes.edgecolor": THEME["border"],
    "axes.labelcolor": THEME["text_primary"],
    "axes.grid": True,
    "grid.color": THEME["border"],
    "grid.alpha": 0.5,
    "xtick.color": THEME["text_secondary"],
    "ytick.color": THEME["text_secondary"],
    "text.color": THEME["text_primary"],
    "legend.facecolor": THEME["surface"],
    "legend.edgecolor": THEME["border"],
    "legend.labelcolor": THEME["text_primary"],
    "lines.linewidth": 2.0,
}


def apply_matplotlib_theme():
    """Applica il tema scuro a Matplotlib."""
    try:
        import matplotlib as mpl
        for key, value in MATPLOTLIB_STYLE.items():
            mpl.rcParams[key] = value
    except ImportError:
        pass


def format_frequency(freq_hz: float) -> str:
    """Formatta una frequenza in modo leggibile."""
    if freq_hz >= 1000:
        return f"{freq_hz/1000:.1f} kHz"
    return f"{freq_hz:.0f} Hz"


def format_dimension(value_mm: float) -> str:
    """Formatta una dimensione in mm con 1 decimale."""
    return f"{value_mm:.1f} mm"


def format_spl(spl_db: float) -> str:
    """Formatta un valore SPL in dB."""
    return f"{spl_db:.1f} dB"
