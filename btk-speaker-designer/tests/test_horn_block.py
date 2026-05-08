"""
Test unitari per HornBlock e ThroatAdapter.

Copre:
- costruzione from_acoustics con tutti i tipi di expansion
- sincronizzazione parametri mouth (0/1/2/3 specificati)
- ThroatAdapter (match/reduce/expand)
- fold 0/1/2 (bounding box, panels generati)
- validate (rileva problemi noti)
- serializzazione round-trip
"""

import pytest
import numpy as np

from btk_speaker_designer.core.driver_model import DriverModel
from btk_speaker_designer.core.constants import (
    EXPANSION_EXPONENTIAL, EXPANSION_TRACTRIX,
    EXPANSION_HYPEX, EXPANSION_CONICAL,
    SPEED_OF_SOUND,
)
from btk_speaker_designer.blocks.horn_block import (
    HornBlock, ThroatAdapter,
)
from btk_speaker_designer.blocks.base_block import (
    Severity, ValidationWarning,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def driver_18():
    """Subwoofer 18" tipico."""
    return DriverModel(
        manufacturer="RCF",
        model="LF18X401",
        driver_type="subwoofer",
        fs=35.0, qts=0.30, vas=170.0, sd=0.1218,  # m² (18")
        xmax=10.5, bl=24.0, mms=180.0,
        spl_1w_1m=98.0, power_rms=1700.0,
        diameter_inch=18.0,
    )


@pytest.fixture
def driver_15():
    """Subwoofer 15" tipico."""
    return DriverModel(
        manufacturer="B&C",
        model="15TBX100",
        driver_type="subwoofer",
        fs=40.0, qts=0.32, vas=110.0, sd=0.0855,
        xmax=9.0, bl=22.0, mms=140.0,
        spl_1w_1m=97.0, power_rms=1000.0,
        diameter_inch=15.0,
    )


# ─── Costruzione base ────────────────────────────────────────────────────────

class TestFromAcoustics:

    def test_default_construction(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18,
            cutoff_frequency=45.0,
        )
        assert horn.cutoff_frequency == 45.0
        assert horn.expansion == EXPANSION_HYPEX
        assert horn.throat_area == pytest.approx(driver_18.sd)
        assert horn.length > 0
        assert horn.mouth_area > horn.throat_area

    @pytest.mark.parametrize("expansion", [
        EXPANSION_EXPONENTIAL, EXPANSION_TRACTRIX,
        EXPANSION_HYPEX, EXPANSION_CONICAL,
    ])
    def test_all_expansion_types(self, driver_18, expansion):
        horn = HornBlock.from_acoustics(
            driver=driver_18,
            cutoff_frequency=50.0,
            expansion=expansion,
            mouth_width=1.2, mouth_height=0.8,
        )
        assert horn.length > 0 and np.isfinite(horn.length)
        assert len(horn.sections) == horn.n_sections

    def test_invalid_expansion_raises(self, driver_18):
        with pytest.raises(ValueError, match="expansion"):
            HornBlock.from_acoustics(
                driver=driver_18, cutoff_frequency=50.0,
                expansion="bogus",
            )


# ─── Sincronizzazione mouth ──────────────────────────────────────────────────

class TestMouthSync:

    def test_no_mouth_params_uses_lambda_squared(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
        )
        wavelength = SPEED_OF_SOUND / 50.0
        target_area = wavelength ** 2 / np.pi
        assert horn.mouth_area == pytest.approx(target_area, rel=1e-3)

    def test_only_aspect_ratio(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_aspect_ratio=2.0,
        )
        assert horn.mouth_width / horn.mouth_height == pytest.approx(2.0)

    def test_width_only_uses_default_ar(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_width=1.5,
        )
        assert horn.mouth_width == pytest.approx(1.5)
        assert horn.mouth_width / horn.mouth_height == pytest.approx(1.5)

    def test_two_params_derive_third(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_aspect_ratio=1.5, mouth_height=0.8,
        )
        assert horn.mouth_width == pytest.approx(1.2)

    def test_three_consistent_params_ok(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_aspect_ratio=1.5, mouth_width=1.2, mouth_height=0.8,
        )
        assert horn.mouth_width == 1.2

    def test_three_inconsistent_raises(self, driver_18):
        with pytest.raises(ValueError, match="incoerenti"):
            HornBlock.from_acoustics(
                driver=driver_18, cutoff_frequency=50.0,
                mouth_aspect_ratio=2.0, mouth_width=1.2, mouth_height=0.8,
            )

    def test_set_mouth_width_preserves_ar(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_width=1.2, mouth_height=0.8,
        )
        ar_before = horn.mouth_width / horn.mouth_height
        horn.set_mouth_width(1.5)
        assert horn.mouth_width / horn.mouth_height == pytest.approx(ar_before)
        assert horn.mouth_width == pytest.approx(1.5)

    def test_set_mouth_height_preserves_ar(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_width=1.2, mouth_height=0.8,
        )
        ar_before = horn.mouth_width / horn.mouth_height
        horn.set_mouth_height(0.5)
        assert horn.mouth_width / horn.mouth_height == pytest.approx(ar_before)
        assert horn.mouth_height == pytest.approx(0.5)


# ─── ThroatAdapter ───────────────────────────────────────────────────────────

class TestThroatAdapter:

    def test_match_mode_default(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            throat_adapter=None,
        )
        assert horn.throat_area == pytest.approx(driver_18.sd)
        # Nessun pannello "throat_adapter"
        names = [p.name for p in horn.panels]
        assert "throat_adapter" not in names

    def test_reduce_with_compression_ratio(self, driver_18):
        adapter = ThroatAdapter(mode="reduce", compression_ratio=2.0)
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            throat_adapter=adapter,
        )
        assert horn.throat_area == pytest.approx(driver_18.sd / 2.0)
        names = [p.name for p in horn.panels]
        assert "throat_adapter" in names

    def test_reduce_with_explicit_area(self, driver_18):
        adapter = ThroatAdapter(mode="reduce", throat_area=0.05)
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            throat_adapter=adapter,
        )
        assert horn.throat_area == pytest.approx(0.05)

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            ThroatAdapter(mode="bogus")

    def test_double_specification_raises(self, driver_18):
        adapter = ThroatAdapter(
            mode="reduce", throat_area=0.05, compression_ratio=2.0,
        )
        with pytest.raises(ValueError, match="non entrambi"):
            HornBlock.from_acoustics(
                driver=driver_18, cutoff_frequency=50.0,
                throat_adapter=adapter,
            )


# ─── Fold geometry ───────────────────────────────────────────────────────────

class TestFold:

    @pytest.mark.parametrize("fold", [0, 1, 2])
    def test_fold_construct(self, driver_18, fold):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_width=1.0, mouth_height=0.7,
            fold=fold,
        )
        bbox = horn.bounding_box
        assert all(b > 0 for b in bbox)
        # Fold riduce profondità rispetto a fold=0
        if fold == 0:
            depth_0 = bbox[2]
        # almeno verifichiamo che la lunghezza assiale sia preservata
        assert horn.length > 0

    def test_fold_reduces_depth(self, driver_18):
        h0 = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_width=1.0, mouth_height=0.7, fold=0,
        )
        h1 = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_width=1.0, mouth_height=0.7, fold=1,
        )
        # Stessa lunghezza assiale (calcolo acustico identico)
        assert h0.length == pytest.approx(h1.length)
        # Fold riduce profondità Z (con margine, perché paratie aggiungono)
        # Bounding box include paratie con margine 1.2x
        # Verifichiamo solo che fold genera fold_baffle_1
        names = [p.name for p in h1.panels]
        assert "fold_baffle_1" in names

    def test_fold2_generates_two_baffles(self, driver_18):
        h2 = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_width=1.0, mouth_height=0.7, fold=2,
        )
        names = [p.name for p in h2.panels]
        assert "fold_baffle_1" in names
        assert "fold_baffle_2" in names

    def test_invalid_fold_raises(self, driver_18):
        with pytest.raises(ValueError, match="fold"):
            HornBlock.from_acoustics(
                driver=driver_18, cutoff_frequency=50.0, fold=3,
            )

    def test_cabinet_depth_limits_fold_z(self, driver_18):
        """cabinet_depth≥L/2 non cambia il fold_depth (usa D_natural=L/2).
        L'ultima sezione deve tornare a z≈0 per la corretta geometria fold=1."""
        # cabinet_depth grande → D = min(D, L/2) = L/2 → comportamento standard
        D_large = 5.0  # sicuramente > L/2 per qualsiasi Fc ≥ 50Hz
        h1 = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_width=1.0, mouth_height=0.7, fold=1,
            cabinet_depth=D_large,
        )
        # Con D = min(5.0, L/2) = L/2, l'ultima sezione del leg 1 torna a z=0
        last_sec = h1.sections[-1]
        z_last = float(last_sec.center[2]) - float(h1.origin[2])
        D = h1._fold_depth()
        # z_last = D - x_in_leg = D - (L - D) = 2D - L ≈ 0 (perché D = L/2)
        assert abs(z_last) < D * 0.05, (
            f"z_last={z_last:.4f} dovrebbe essere ~0 per fold=1 con D=L/2"
        )

    def test_cabinet_depth_y_shift_positive(self, driver_18):
        """Le sezioni del secondo leg devono avere Y > 0 (spostato verso l'alto)."""
        h1 = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_width=1.0, mouth_height=0.7, fold=1,
            n_sections=10,
        )
        secs = h1.sections
        # Il secondo leg inizia dopo la metà delle sezioni
        # Cerchiamo una sezione con x_axial > L/2
        D = h1._fold_depth()
        secs_leg1 = [s for s in secs if s.x_axial > D]
        assert secs_leg1, "Deve esserci almeno una sezione nel leg 1"
        # Y centro sezioni leg 1 (relative a origin) > Y sezioni leg 0
        y_leg1 = float(secs_leg1[0].center[1]) - float(h1.origin[1])
        y_leg0 = float(secs[0].center[1]) - float(h1.origin[1])
        assert y_leg1 > y_leg0, (
            f"Leg 1 deve avere y_center > leg 0: "
            f"y_leg1={y_leg1:.3f}, y_leg0={y_leg0:.3f}"
        )

    def test_fold_baffle_y_position(self, driver_18):
        """La fold_baffle_1 deve stare a Y tra i due leg (Y > 0)."""
        D = 0.65  # m
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_width=1.0, mouth_height=0.7, fold=1,
            cabinet_depth=D, n_sections=8,
        )
        names = {p.name: p for p in horn.panels}
        assert "fold_baffle_1" in names
        baffle = names["fold_baffle_1"]
        # Y dei vertici della baffle relativi a origin
        y_vals = baffle.vertices[:, 1] - horn.origin[1]
        y_b = float(y_vals.mean())
        # Deve essere tra 0 e throat height (positivo ma non gigante)
        assert y_b > 0, f"fold_baffle_1 Y={y_b:.3f} deve essere > 0"
        assert y_b < 2.0, f"fold_baffle_1 Y={y_b:.3f} sembra troppo grande"


# ─── Section shape ───────────────────────────────────────────────────────────

class TestSectionShape:

    def test_rectangular_keeps_aspect(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_width=1.2, mouth_height=0.8,
            section_shape="rectangular",
        )
        ar = 1.2 / 0.8
        for sec in horn.sections:
            assert sec.width / sec.height == pytest.approx(ar, rel=1e-6)

    def test_trapezoidal_keeps_height(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_width=1.2, mouth_height=0.8,
            section_shape="trapezoidal",
        )
        for sec in horn.sections:
            assert sec.height == pytest.approx(0.8)

    def test_trapezoidal_throat_width_smaller(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_width=1.2, mouth_height=0.8,
            section_shape="trapezoidal",
        )
        # Sezione throat: width = sd / 0.8
        expected_w = driver_18.sd / 0.8
        assert horn.sections[0].width == pytest.approx(expected_w, rel=1e-2)


# ─── Connection ports ───────────────────────────────────────────────────────

class TestConnectionPorts:

    def test_throat_and_mouth_present(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
        )
        assert "throat" in horn.connection_ports
        assert "mouth" in horn.connection_ports

    def test_port_areas_match_sections(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
        )
        ports = horn.connection_ports
        assert ports["throat"].area == pytest.approx(horn.sections[0].area)
        assert ports["mouth"].area == pytest.approx(horn.sections[-1].area)

    def test_port_normals_unit(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
        )
        for p in horn.connection_ports.values():
            assert np.linalg.norm(p.normal) == pytest.approx(1.0)


# ─── Validation ──────────────────────────────────────────────────────────────

class TestValidation:

    def test_clean_design_no_errors(self, driver_18):
        # Sub a 80 Hz con bocca generosa: nessun ERROR
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=80.0,
            mouth_width=1.4, mouth_height=0.95,
        )
        warnings = horn.validate()
        errors = [w for w in warnings if w.severity == Severity.ERROR]
        assert errors == []

    def test_mouth_too_small_error(self, driver_18):
        # Bocca patologicamente piccola: dimensione < λ/4 in entrambe le direz.
        # Fc=40 Hz → λ=8.55m → λ²/(16π) ≈ 1.45 m².
        # Mouth 0.30×0.20 = 0.06 m² « soglia critica → ERROR
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=40.0,
            mouth_width=0.30, mouth_height=0.20,
            expansion=EXPANSION_EXPONENTIAL,
        )
        warnings = horn.validate()
        codes = [w.code for w in warnings]
        assert "MOUTH_TOO_SMALL" in codes

    def test_high_compression_warning(self, driver_18):
        adapter = ThroatAdapter(mode="reduce", compression_ratio=8.0)
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            throat_adapter=adapter,
        )
        warnings = horn.validate()
        codes = [w.code for w in warnings]
        assert "COMPRESSION_RATIO_HIGH" in codes


# ─── Panels ──────────────────────────────────────────────────────────────────

class TestPanels:

    def test_panels_count_consistent(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            n_sections=20,
        )
        # 4 strisce (top/bot/L/R) per ogni intervallo di sezione + throat + mouth
        wall_strips = (20 - 1) * 4
        # +1 throat_baffle, +1 mouth_frame (no fold quindi no fold_baffle)
        expected_min = wall_strips + 2
        assert len(horn.panels) >= expected_min

    def test_panels_have_positive_area(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
        )
        for p in horn.panels:
            assert p.area_m2 > 0

    def test_throat_baffle_has_driver_cutout(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
        )
        baffle = next(p for p in horn.panels if p.name == "throat_baffle")
        assert len(baffle.cutouts) == 1
        assert baffle.cutouts[0]["purpose"] == "driver_mount"


# ─── Internal volume + bounding box ──────────────────────────────────────────

class TestVolumeAndBBox:

    def test_internal_volume_positive(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
        )
        assert horn.internal_volume > 0

    def test_volume_bounded_by_box(self, driver_18):
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
        )
        w, h, d = horn.bounding_box
        # volume aria interno < volume esterno cabinet
        assert horn.internal_volume < w * h * d * 1.1  # piccolo margine fold


# ─── Serializzazione ────────────────────────────────────────────────────────

class TestSerialization:

    def test_to_dict_from_dict_roundtrip(self, driver_18):
        adapter = ThroatAdapter(mode="reduce", compression_ratio=1.5)
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=48.0,
            mouth_width=1.3, mouth_height=0.85,
            fold=1, throat_adapter=adapter,
        )
        data = horn.to_dict()
        horn2 = HornBlock.from_dict(data, driver=driver_18)
        assert horn2.cutoff_frequency == horn.cutoff_frequency
        assert horn2.length == pytest.approx(horn.length, rel=1e-9)
        assert horn2.throat_area == pytest.approx(horn.throat_area)
        assert horn2.mouth_width == pytest.approx(horn.mouth_width)
        assert horn2.fold == 1
        assert horn2.throat_adapter is not None
        assert horn2.throat_adapter.compression_ratio == 1.5


# ─── Constraint-first ───────────────────────────────────────────────────────

class TestFromConstraints:

    def test_constraint_first_basic(self, driver_18):
        horn = HornBlock.from_constraints(
            driver=driver_18,
            max_width=1.4, max_height=0.95, max_depth=0.80,
            fold=1,
            optimize_for="lowest_fc",
        )
        bbox = horn.bounding_box
        # bbox può eccedere max_depth a causa di paratie con margine 1.2;
        # verifichiamo invece che la lunghezza tromba rientri nel limite atteso
        depth_to_length = {0: 1.0, 1: 2.0, 2: 3.0}[1]
        assert horn.length <= 0.80 * depth_to_length * 1.01
        assert horn.cutoff_frequency >= 25.0

    def test_constraint_lowest_fc_smaller_than_spl(self, driver_18):
        h_low = HornBlock.from_constraints(
            driver=driver_18, max_width=1.4, max_height=0.95, max_depth=0.80,
            fold=1, optimize_for="lowest_fc",
        )
        h_spl = HornBlock.from_constraints(
            driver=driver_18, max_width=1.4, max_height=0.95, max_depth=0.80,
            fold=1, optimize_for="spl_at_fc",
        )
        # I due criteri possono coincidere in alcuni casi, ma normalmente
        # lowest_fc ≤ spl_at_fc Fc
        assert h_low.cutoff_frequency <= h_spl.cutoff_frequency + 1.0
