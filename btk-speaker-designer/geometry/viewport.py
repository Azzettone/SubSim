"""
Viewport 3D standalone — visualizzazione pyvista dei solidi acustici.

Converte solidi build123d in mesh pyvista via STL temporaneo e mostra
una finestra interattiva (con trackball mouse). Color-coded per tipo di blocco.

Utilizzo tipico::

    from btk_speaker_designer.geometry.viewport import show_solid, show_assembly

    solid = horn_inner_volume(horn)
    show_solid(solid, title="Cavità tromba")

    parts = {
        "horn_cavity": horn_inner_volume(horn),
        "chamber": chamber_inner_volume(chamber),
        "port": port_to_solid(port),
    }
    show_assembly(parts)

NOTE sull'headless environment (codespace, CI):
  Se la variabile d'ambiente DISPLAY non è impostata, il modulo avvia
  automaticamente un server Xvfb virtuale su :99. In modalità off-screen
  è obbligatorio passare ``screenshot_path`` per salvare l'immagine PNG;
  senza di esso verrà sollevato ViewportError.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
import time
import warnings
from typing import Dict, Optional, Union

# ---------------------------------------------------------------------------
# Colori per tipo di blocco (chiave = sottostringa nel label del solido)
# ---------------------------------------------------------------------------
_BLOCK_COLORS: Dict[str, str] = {
    "horn": "#E94F37",       # rosso — cavità tromba
    "chamber": "#393E41",    # grigio scuro — cabinet
    "port": "#44BBA4",       # verde acqua — porta bass-reflex
    "driver": "#F6AE2D",     # giallo — driver
}
_DEFAULT_COLOR = "#8BBDDA"   # azzurro neutro


def _color_for_label(label: str) -> str:
    """Restituisce il colore hex per un label di solido."""
    lbl = (label or "").lower()
    for key, color in _BLOCK_COLORS.items():
        if key in lbl:
            return color
    return _DEFAULT_COLOR


# ---------------------------------------------------------------------------
# Xvfb — virtual display management (headless environments)
# ---------------------------------------------------------------------------
_xvfb_proc: Optional[subprocess.Popen] = None
_XVFB_DISPLAY = ":99"


def _ensure_display() -> None:
    """
    Garantisce che la variabile d'ambiente DISPLAY sia impostata.

    Se DISPLAY è già presente (ambiente con display reale o Xvfb già avviato),
    non fa nulla. Altrimenti avvia un processo Xvfb su :99 e imposta
    ``os.environ["DISPLAY"]``.

    Il processo Xvfb viene tenuto in vita per tutta la durata del processo
    Python corrente (singleton a livello di modulo).
    """
    global _xvfb_proc

    if os.environ.get("DISPLAY", "").strip():
        return  # display già disponibile

    if _xvfb_proc is not None and _xvfb_proc.poll() is None:
        return  # Xvfb già in esecuzione

    try:
        _xvfb_proc = subprocess.Popen(
            ["Xvfb", _XVFB_DISPLAY, "-screen", "0", "1024x768x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        os.environ["DISPLAY"] = _XVFB_DISPLAY
        time.sleep(0.4)  # lascia il tempo a Xvfb di inizializzarsi
    except FileNotFoundError as exc:
        raise ViewportError(
            "Xvfb non trovato. Installa con: sudo apt-get install xvfb"
        ) from exc


# ---------------------------------------------------------------------------
# Lazy import pyvista
# ---------------------------------------------------------------------------
def _pv():
    """Import lazy di pyvista con messaggio chiaro se mancante."""
    try:
        import pyvista as pv
        return pv
    except ImportError as exc:
        raise ViewportError(
            "pyvista non è installato. Esegui: pip install pyvista"
        ) from exc


class ViewportError(Exception):
    """Errore nel layer di visualizzazione 3D."""


# ---------------------------------------------------------------------------
# Conversione build123d → pyvista mesh
# ---------------------------------------------------------------------------
def _solid_to_pv_mesh(solid):
    """
    Converte un solido build123d in un oggetto pyvista.PolyData.

    Strategia: export STL in file temporaneo → lettura con pyvista.read().
    """
    from .panel_generator import export_stl as _export_stl

    pv = _pv()
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        _export_stl(solid, tmp_path, scale_to_mm=False)   # mantieni scala metri
        mesh = pv.read(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return mesh


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------
def show_solid(
    solid,
    title: str = "BTK Speaker 3D",
    color: Optional[str] = None,
    opacity: float = 1.0,
    off_screen: Optional[bool] = None,
    screenshot_path: Optional[Union[str, pathlib.Path]] = None,
) -> None:
    """
    Mostra un singolo solido build123d in una finestra pyvista interattiva.

    Args:
        solid:           Qualsiasi oggetto build123d con metodo volume
                         (Part, Compound, etc.)
        title:           Titolo della finestra.
        color:           Colore hex opzionale. Se None usa colore dal label.
        opacity:         Opacità [0, 1].
        off_screen:      True = headless (no finestra). None = auto-detect
                         da variabile d'ambiente DISPLAY.
        screenshot_path: Percorso PNG per salvare screenshot (off-screen
                         richiede questo parametro).

    Raises:
        ViewportError:   pyvista non disponibile, export STL fallito, o
                         off_screen senza screenshot_path.
    """
    pv = _pv()
    headless = _resolve_headless(off_screen, screenshot_path)
    _ensure_display()

    mesh = _solid_to_pv_mesh(solid)
    c = color or _color_for_label(getattr(solid, "label", ""))

    plotter = pv.Plotter(title=title, off_screen=headless)
    plotter.add_mesh(mesh, color=c, opacity=opacity, show_edges=False)
    plotter.add_axes()
    plotter.background_color = "white"

    _finalize(plotter, headless, screenshot_path)


def show_assembly(
    parts: Dict[str, object],
    title: str = "BTK Speaker Assembly",
    opacity: float = 0.85,
    off_screen: Optional[bool] = None,
    screenshot_path: Optional[Union[str, pathlib.Path]] = None,
) -> None:
    """
    Mostra un assembly di solidi build123d, color-coded per tipo di blocco.

    Args:
        parts:           Dizionario {label: solid}. Il label determina il
                         colore (vedi _BLOCK_COLORS). I valori None vengono
                         silenziosamente saltati.
        title:           Titolo della finestra.
        opacity:         Opacità globale per tutti i solidi.
        off_screen:      True = headless. None = auto-detect da DISPLAY.
        screenshot_path: Percorso PNG (obbligatorio in modalità headless).

    Raises:
        ViewportError:   pyvista non disponibile.
    """
    pv = _pv()
    headless = _resolve_headless(off_screen, screenshot_path)
    _ensure_display()

    plotter = pv.Plotter(title=title, off_screen=headless)
    plotter.background_color = "white"

    for label, solid in parts.items():
        if solid is None:
            continue
        try:
            mesh = _solid_to_pv_mesh(solid)
        except Exception as exc:
            warnings.warn(
                f"viewport: impossibile convertire '{label}' in mesh ({exc})",
                stacklevel=2,
            )
            continue

        color = _color_for_label(label)
        plotter.add_mesh(mesh, color=color, opacity=opacity,
                         show_edges=False, label=label)

    plotter.add_axes()
    if parts:
        plotter.add_legend(size=(0.15, 0.15))

    _finalize(plotter, headless, screenshot_path)


# ---------------------------------------------------------------------------
# Helper interni
# ---------------------------------------------------------------------------
def _resolve_headless(
    off_screen: Optional[bool],
    screenshot_path: Optional[Union[str, pathlib.Path]],
) -> bool:
    """
    Determina se usare modalità headless.

    - off_screen=True → headless, screenshot_path obbligatorio
    - off_screen=False → finestra interattiva (serve un display)
    - off_screen=None → headless se DISPLAY non impostato
    """
    if off_screen is True:
        if screenshot_path is None:
            raise ViewportError(
                "off_screen=True richiede screenshot_path per salvare l'output."
            )
        return True

    if off_screen is False:
        return False

    # Auto-detect: headless se nessun DISPLAY
    has_display = bool(os.environ.get("DISPLAY", "").strip())
    if not has_display and screenshot_path is None:
        raise ViewportError(
            "Nessun DISPLAY disponibile e screenshot_path non specificato. "
            "Passa screenshot_path=<percorso.png> oppure imposta DISPLAY."
        )
    return not has_display


def _finalize(plotter, headless: bool, screenshot_path) -> None:
    """Mostra la finestra o salva screenshot, poi chiude il plotter."""
    if headless:
        plotter.render()
        plotter.screenshot(str(screenshot_path))
        plotter.close()
    else:
        plotter.show()
