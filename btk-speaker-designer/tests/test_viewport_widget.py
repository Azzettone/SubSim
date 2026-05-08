"""
Test per gui.viewport_widget.Viewport3DWidget.

Tutti i test girano headless (Xvfb avviato da _ensure_display() nel widget).
"""

from __future__ import annotations

import pathlib
import tempfile

import pytest

# Skip globale se PyQt5 non disponibile
pytest.importorskip("PyQt5.QtWidgets", reason="PyQt5 non installato",
                    exc_type=ImportError)
pytest.importorskip("pyvistaqt", reason="pyvistaqt non installato")
pytest.importorskip("build123d", reason="build123d non installato")

from PyQt5.QtWidgets import QApplication                        # noqa: E402

from btk_speaker_designer.core.driver_model import DriverModel  # noqa: E402
from btk_speaker_designer.gui.assembly_model import AssemblyModel  # noqa: E402
from btk_speaker_designer.gui.viewport_widget import (          # noqa: E402
    Viewport3DWidget,
    _ensure_display,
)


@pytest.fixture(scope="module")
def qapp():
    _ensure_display()   # Xvfb prima di QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def driver_18():
    return DriverModel(
        manufacturer="RCF", model="LF18X401",
        driver_type="subwoofer",
        fs=35.0, qts=0.30, vas=170.0, sd=0.1218,
        xmax=10.5, bl=24.0, mms=180.0,
        spl_1w_1m=98.0, power_rms=1700.0, diameter_inch=18.0,
    )


@pytest.fixture
def model(driver_18):
    m = AssemblyModel()
    m.auto_rebuild_solids = False  # gestiremo noi manualmente
    m.set_driver(driver_18)
    m.rebuild()
    m.rebuild_solids()
    return m


# ---------------------------------------------------------------------------
class TestViewport3DWidgetCreation:

    def test_widget_creation(self, qapp):
        """Il widget si crea senza eccezioni."""
        w = Viewport3DWidget()
        assert w is not None
        w.close()

    def test_has_pyvistaqt(self, qapp):
        """In questo ambiente pyvistaqt deve essere attivo (non fallback)."""
        w = Viewport3DWidget()
        assert w._has_pyvistaqt is True
        w.close()

    def test_toolbar_present(self, qapp):
        """La toolbar deve esistere con azioni."""
        w = Viewport3DWidget()
        assert w._toolbar is not None
        assert len(w._toolbar.actions()) > 0
        w.close()


class TestViewport3DUpdateFromSolids:

    def test_update_from_solids_runs(self, qapp, model):
        """update_from_solids non deve sollevare eccezioni."""
        w = Viewport3DWidget()
        w.update_from_solids(model.solids)   # non deve sollevare
        w.close()

    def test_clear_resets_scene(self, qapp, model):
        """clear() svuota la scena."""
        w = Viewport3DWidget()
        w.update_from_solids(model.solids)
        w.clear()
        assert w._solids == {}
        w.close()

    def test_empty_solids_dict_accepted(self, qapp):
        """Passare {} non deve causare errori."""
        w = Viewport3DWidget()
        w.update_from_solids({})
        w.close()

    def test_none_solid_skipped(self, qapp):
        """Solidi None nel dict vengono silenziosamente saltati."""
        w = Viewport3DWidget()
        w.update_from_solids({"horn_cavity": None, "port": None})
        w.close()


class TestViewport3DViewControls:

    def test_view_controls_run(self, qapp, model):
        """I metodi di cambio vista non devono sollevare eccezioni."""
        w = Viewport3DWidget()
        w.update_from_solids(model.solids)
        w.view_isometric()
        w.view_front()
        w.view_top()
        w.view_side()
        w.reset_view()
        w.close()

    def test_toggle_wireframe(self, qapp, model):
        """toggle_wireframe cambia la modalità e ridisegna."""
        w = Viewport3DWidget()
        w.update_from_solids(model.solids)
        assert w._wireframe_mode is False
        w.toggle_wireframe()
        assert w._wireframe_mode is True
        w.toggle_wireframe()
        assert w._wireframe_mode is False
        w.close()


class TestViewport3DScreenshot:

    def test_screenshot_headless(self, qapp, model):
        """screenshot() salva un PNG valido senza display reale."""
        w = Viewport3DWidget()
        w.update_from_solids(model.solids)

        out = pathlib.Path(tempfile.mktemp(suffix=".png"))
        try:
            result = w.screenshot(out)
            assert result == str(out)
            assert out.exists()
            assert out.stat().st_size > 500
        finally:
            out.unlink(missing_ok=True)

        w.close()

    def test_screenshot_no_path_returns_string(self, qapp, model):
        """screenshot() senza path usa un temp file e ritorna il percorso."""
        w = Viewport3DWidget()
        w.update_from_solids(model.solids)
        result = w.screenshot()
        assert result is not None
        p = pathlib.Path(result)
        assert p.exists()
        p.unlink(missing_ok=True)
        w.close()


class TestViewport3DModelIntegration:

    def test_signal_integration(self, qapp, driver_18):
        """solids_rebuilt del model connesso al widget aggiorna la scena."""
        m = AssemblyModel()
        m.auto_rebuild_solids = False
        m.set_driver(driver_18)
        m.rebuild()

        w = Viewport3DWidget()
        # Connetti signal del model al slot del widget
        m.solids_rebuilt.connect(w.update_from_solids)

        # Triggero rebuild_solids → deve aggiornare il widget
        m.rebuild_solids()
        assert "horn_cavity" in w._solids
        w.close()
