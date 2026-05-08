"""
Test per il modulo geometry.viewport.

Tutti i test girano in modalità off-screen (nessun display richiesto):
passano off_screen=True e screenshot_path=tmp.png.
Si verifica che il file PNG venga creato e abbia dimensioni > 0.
"""

import pathlib
import tempfile

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Skip guards
# ---------------------------------------------------------------------------
pyvista = pytest.importorskip("pyvista", reason="pyvista non installato")
b123d = pytest.importorskip("build123d", reason="build123d non installato")

from btk_speaker_designer.geometry.viewport import (
    ViewportError,
    _color_for_label,
    show_assembly,
    show_solid,
)
from btk_speaker_designer.geometry.panel_generator import (
    chamber_inner_volume,
    driver_to_solid,
    horn_inner_volume,
    port_to_solid,
)
from btk_speaker_designer.blocks.chamber_block import ChamberBlock
from btk_speaker_designer.blocks.port_block import PortBlock
from btk_speaker_designer.blocks.driver_block import DriverBlock
from btk_speaker_designer.blocks.horn_block import HornBlock
from btk_speaker_designer.core.driver_model import DriverModel


# ---------------------------------------------------------------------------
# Fixture driver condiviso
# ---------------------------------------------------------------------------
@pytest.fixture
def driver():
    return DriverModel(
        manufacturer="Test",
        model="DRV",
        driver_type="subwoofer",
        fs=40.0,
        re=5.5,
        qes=0.35,
        qms=6.0,
        vas=80.0,
        sd=0.022,
        xmax=8.0,
        bl=14.0,
        mms=100.0,
        spl_1w_1m=96.0,
        power_rms=300.0,
        impedance_nominal=8.0,
    )


@pytest.fixture
def tiny_horn(driver):
    return HornBlock.from_acoustics(
        driver=driver,
        cutoff_frequency=60.0,
        expansion="exponential",
        fold=0,
        mouth_width=0.5,
        mouth_height=0.36,
    )


@pytest.fixture
def tiny_chamber():
    return ChamberBlock.from_dimensions(width=0.5, height=0.4, depth=0.3)


@pytest.fixture
def tiny_port():
    return PortBlock.from_dimensions(diameter=0.08, length=0.15)


@pytest.fixture
def tiny_driver_block(driver):
    return DriverBlock(driver=driver, mounting_depth=0.12)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _tmp_png() -> pathlib.Path:
    """Crea un percorso temporaneo PNG (il file non esiste ancora)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    p = pathlib.Path(tmp.name)
    p.unlink(missing_ok=True)  # assicura che non esista prima del test
    return p


# ---------------------------------------------------------------------------
# _color_for_label
# ---------------------------------------------------------------------------
class TestColorForLabel:
    def test_horn_label(self):
        assert _color_for_label("horn_exponential_cavity") == "#E94F37"

    def test_chamber_label(self):
        assert _color_for_label("chamber_shell") == "#393E41"

    def test_port_label(self):
        assert _color_for_label("port_solid") == "#44BBA4"

    def test_driver_label(self):
        assert _color_for_label("driver_solid") == "#F6AE2D"

    def test_unknown_label_returns_default(self):
        assert _color_for_label("mystery_block") == "#8BBDDA"

    def test_empty_label(self):
        assert _color_for_label("") == "#8BBDDA"


# ---------------------------------------------------------------------------
# _resolve_headless
# ---------------------------------------------------------------------------
class TestResolveHeadless:
    def test_off_screen_true_without_screenshot_raises(self):
        from btk_speaker_designer.geometry.viewport import ViewportError, _resolve_headless
        with pytest.raises(ViewportError, match="screenshot_path"):
            _resolve_headless(off_screen=True, screenshot_path=None)

    def test_off_screen_true_with_screenshot_returns_true(self, tmp_path):
        from btk_speaker_designer.geometry.viewport import _resolve_headless
        result = _resolve_headless(off_screen=True, screenshot_path=tmp_path / "out.png")
        assert result is True

    def test_off_screen_false_returns_false(self):
        from btk_speaker_designer.geometry.viewport import _resolve_headless
        result = _resolve_headless(off_screen=False, screenshot_path=None)
        assert result is False


# ---------------------------------------------------------------------------
# show_solid — headless tests
# ---------------------------------------------------------------------------
class TestShowSolid:
    def test_show_horn_cavity_creates_png(self, tiny_horn):
        out = _tmp_png()
        solid = horn_inner_volume(tiny_horn)
        show_solid(solid, title="Test Horn", off_screen=True, screenshot_path=out)
        assert out.exists(), "PNG non generato da show_solid"
        assert out.stat().st_size > 1000, "PNG troppo piccolo (probabile vuoto)"

    def test_show_chamber_inner_creates_png(self, tiny_chamber):
        out = _tmp_png()
        solid = chamber_inner_volume(tiny_chamber)
        show_solid(solid, off_screen=True, screenshot_path=out)
        assert out.exists()
        assert out.stat().st_size > 1000

    def test_show_port_creates_png(self, tiny_port):
        out = _tmp_png()
        solid = port_to_solid(tiny_port)
        show_solid(solid, off_screen=True, screenshot_path=out)
        assert out.exists()
        assert out.stat().st_size > 1000

    def test_show_driver_creates_png(self, tiny_driver_block):
        out = _tmp_png()
        solid = driver_to_solid(tiny_driver_block)
        show_solid(solid, off_screen=True, screenshot_path=out)
        assert out.exists()
        assert out.stat().st_size > 1000

    def test_custom_color_accepted(self, tiny_chamber):
        out = _tmp_png()
        solid = chamber_inner_volume(tiny_chamber)
        # Non deve sollevare eccezioni con colore custom
        show_solid(solid, color="#FF00FF", off_screen=True, screenshot_path=out)
        assert out.exists()


# ---------------------------------------------------------------------------
# show_assembly — headless tests
# ---------------------------------------------------------------------------
class TestShowAssembly:
    def test_empty_dict_creates_png(self):
        out = _tmp_png()
        show_assembly({}, off_screen=True, screenshot_path=out)
        assert out.exists()

    def test_none_values_skipped(self, tiny_chamber):
        out = _tmp_png()
        parts = {
            "chamber": chamber_inner_volume(tiny_chamber),
            "missing": None,
        }
        show_assembly(parts, off_screen=True, screenshot_path=out)
        assert out.exists()
        assert out.stat().st_size > 1000

    def test_multi_block_assembly_creates_png(self, tiny_horn, tiny_chamber, tiny_port):
        out = _tmp_png()
        parts = {
            "horn_cavity": horn_inner_volume(tiny_horn),
            "chamber": chamber_inner_volume(tiny_chamber),
            "port": port_to_solid(tiny_port),
        }
        show_assembly(parts, off_screen=True, screenshot_path=out)
        assert out.exists()
        assert out.stat().st_size > 1000

    def test_opacity_parameter_accepted(self, tiny_chamber):
        out = _tmp_png()
        solid = chamber_inner_volume(tiny_chamber)
        show_assembly({"chamber": solid}, opacity=0.5, off_screen=True, screenshot_path=out)
        assert out.exists()
