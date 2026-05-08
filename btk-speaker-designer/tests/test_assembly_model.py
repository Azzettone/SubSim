"""
Test per gui.assembly_model.AssemblyModel.

Headless: usa QCoreApplication (no display) e niente generazione di solidi
3D nei test rapidi (auto_rebuild_solids=False) tranne in quelli marcati.
"""

from __future__ import annotations

import pytest

# Skip globale se Qt non disponibile
qtcore = pytest.importorskip(
    "PyQt5.QtCore", reason="PyQt5 non installato",
    exc_type=ImportError,
)
from PyQt5.QtCore import QCoreApplication       # noqa: E402

from btk_speaker_designer.core.constants import (  # noqa: E402
    EXPANSION_EXPONENTIAL,
    EXPANSION_HYPEX,
    GEOMETRY_2FOLDED,
    GEOMETRY_FOLDED,
    GEOMETRY_STRAIGHT,
    SPEAKER_TYPE_FULLRANGE,
    SPEAKER_TYPE_SUB,
)
from btk_speaker_designer.core.driver_model import DriverModel  # noqa: E402
from btk_speaker_designer.gui.assembly_model import (  # noqa: E402
    AssemblyModel,
    ChamberParams,
    HornParams,
    PortParams,
)


@pytest.fixture(scope="module")
def qapp():
    """QCoreApplication condivisa per emissione signals senza GUI."""
    app = QCoreApplication.instance() or QCoreApplication([])
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
def model(qapp):
    """Modello pulito con solidi disabilitati per test veloci."""
    m = AssemblyModel()
    m.auto_rebuild_solids = False
    return m


# ---------------------------------------------------------------------------
# Stato iniziale
# ---------------------------------------------------------------------------
class TestInitialState:
    def test_defaults(self, model):
        assert model.speaker_type == SPEAKER_TYPE_SUB
        assert model.geometry_type == GEOMETRY_STRAIGHT
        assert model.driver is None
        assert model.assembly is None
        assert isinstance(model.horn_params, HornParams)
        assert isinstance(model.chamber_params, ChamberParams)
        assert isinstance(model.port_params, PortParams)
        assert not model.has_valid_assembly()


# ---------------------------------------------------------------------------
# Setters + signals
# ---------------------------------------------------------------------------
class TestSetters:
    def test_set_speaker_type_emits(self, model):
        received = []
        model.speaker_type_changed.connect(lambda v: received.append(v))
        model.set_speaker_type(SPEAKER_TYPE_FULLRANGE)
        assert received == [SPEAKER_TYPE_FULLRANGE]
        assert model.speaker_type == SPEAKER_TYPE_FULLRANGE

    def test_set_speaker_type_idempotent(self, model):
        received = []
        model.speaker_type_changed.connect(lambda v: received.append(v))
        model.set_speaker_type(SPEAKER_TYPE_SUB)  # già default
        assert received == []  # nessun signal se valore uguale

    def test_set_geometry_syncs_fold(self, model):
        model.set_geometry_type(GEOMETRY_FOLDED)
        assert model.horn_params.fold == 1
        model.set_geometry_type(GEOMETRY_2FOLDED)
        assert model.horn_params.fold == 2
        model.set_geometry_type(GEOMETRY_STRAIGHT)
        assert model.horn_params.fold == 0

    def test_set_driver_emits(self, model, driver_18):
        received = []
        model.driver_changed.connect(lambda d: received.append(d))
        model.set_driver(driver_18)
        assert received == [driver_18]
        assert model.driver is driver_18

    def test_update_horn_params_partial(self, model):
        model.update_horn_params(cutoff_frequency=80.0, expansion=EXPANSION_EXPONENTIAL)
        assert model.horn_params.cutoff_frequency == 80.0
        assert model.horn_params.expansion == EXPANSION_EXPONENTIAL
        # Altri campi inalterati:
        assert model.horn_params.fold == 0

    def test_update_horn_params_empty_no_signal(self, model):
        received = []
        model.horn_params_changed.connect(lambda: received.append(1))
        model.update_horn_params()
        assert received == []

    def test_update_chamber_params(self, model):
        model.update_chamber_params(width=0.8, height=0.6)
        assert model.chamber_params.width == 0.8
        assert model.chamber_params.height == 0.6

    def test_update_port_params_enable(self, model):
        model.update_port_params(enabled=True, diameter=0.12, length=0.30)
        assert model.port_params.enabled is True
        assert model.port_params.diameter == 0.12


# ---------------------------------------------------------------------------
# Rebuild dell'assembly
# ---------------------------------------------------------------------------
class TestRebuild:
    def test_rebuild_without_driver_returns_false(self, model):
        failures = []
        model.validation_failed.connect(lambda msg: failures.append(msg))
        assert model.rebuild() is False
        assert model.assembly is None

    def test_rebuild_with_driver_succeeds(self, model, driver_18):
        model.set_driver(driver_18)            # auto-rebuild=False ma rebuild manuale
        assert model.rebuild() is True
        assert model.assembly is not None
        assert model.horn_block is not None
        assert model.chamber_block is not None  # default: enabled
        assert model.driver_block is not None
        # Port disabilitato di default
        assert model.port_block is None

    def test_rebuild_emits_assembly_changed(self, model, driver_18):
        model.set_driver(driver_18)
        received = []
        model.assembly_changed.connect(lambda: received.append(1))
        model.rebuild()
        assert received == [1]

    def test_auto_rebuild_on_horn_param_change(self, qapp, driver_18):
        """Con auto_rebuild_solids=False, il rebuild dell'assembly avviene
        comunque (rebuild_solids non è chiamato)."""
        m = AssemblyModel()
        m.auto_rebuild_solids = False
        m.set_driver(driver_18)        # innesca primo rebuild
        first = m.assembly
        m.update_horn_params(cutoff_frequency=90.0)
        assert m.assembly is not None
        assert m.assembly is not first  # nuovo Assembly

    def test_invalid_horn_emits_failure(self, model, driver_18):
        model.set_driver(driver_18)
        failures = []
        model.validation_failed.connect(lambda msg: failures.append(msg))
        model.update_horn_params(cutoff_frequency=-10.0)  # invalido
        assert any("HornBlock" in f for f in failures)
        assert model.assembly is None

    def test_rebuild_with_port(self, model, driver_18):
        model.set_driver(driver_18)
        model.update_port_params(enabled=True, diameter=0.10, length=0.20)
        assert model.rebuild() is True
        assert model.port_block is not None

    def test_rebuild_chamber_disabled(self, model, driver_18):
        model.set_driver(driver_18)
        model.update_chamber_params(enabled=False)
        assert model.rebuild() is True
        assert model.chamber_block is None


# ---------------------------------------------------------------------------
# Solidi 3D (richiede build123d) — slow
# ---------------------------------------------------------------------------
class TestSolids:
    def test_rebuild_solids_emits_dict(self, qapp, driver_18):
        pytest.importorskip("build123d")
        m = AssemblyModel()
        m.auto_rebuild_solids = False
        m.set_driver(driver_18)
        m.rebuild()
        received = []
        m.solids_rebuilt.connect(lambda d: received.append(d))
        solids = m.rebuild_solids()
        assert isinstance(solids, dict)
        assert len(received) == 1
        # Almeno cavità tromba e cabinet devono esserci
        assert "horn_cavity" in solids
        assert "chamber_inner" in solids

    def test_auto_rebuild_solids_default_on(self, qapp, driver_18):
        pytest.importorskip("build123d")
        m = AssemblyModel()
        # Default: auto_rebuild_solids=True
        received = []
        m.solids_rebuilt.connect(lambda d: received.append(d))
        m.set_driver(driver_18)   # → rebuild() → rebuild_solids()
        assert len(received) == 1
        assert "horn_cavity" in received[0]
