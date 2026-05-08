"""
Test unitari per ChamberBlock, PortBlock, DriverBlock e Assembly.
"""

import numpy as np
import pytest

from btk_speaker_designer.core.driver_model import DriverModel
from btk_speaker_designer.core.constants import SPEED_OF_SOUND
from btk_speaker_designer.blocks import (
    ChamberBlock, PortBlock, DriverBlock, HornBlock, ThroatAdapter,
    Assembly, Severity,
    END_CORRECTION_FLANGED_ONE,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def driver_18():
    return DriverModel(
        manufacturer="RCF", model="LF18X401",
        driver_type="subwoofer",
        fs=35.0, qts=0.30, vas=170.0, sd=0.1218,
        xmax=10.5, bl=24.0, mms=180.0,
        spl_1w_1m=98.0, power_rms=1700.0, diameter_inch=18.0,
    )


# ─── ChamberBlock ────────────────────────────────────────────────────────────

class TestChamberBlock:

    def test_rectangular_dims(self):
        ch = ChamberBlock.from_dimensions(width=0.6, height=0.5, depth=0.4)
        assert ch.bounding_box == pytest.approx((0.6, 0.5, 0.4))
        assert ch.internal_volume == pytest.approx(0.6 * 0.5 * 0.4)
        assert len(ch.panels) == 6
        assert set(ch.connection_ports) == {
            "front", "back", "top", "bottom", "left", "right"
        }

    def test_from_volume_derives_third_dim(self):
        # V=0.080 m³ con W=0.6 H=0.5 → D=0.080/(0.6·0.5)=0.2667
        ch = ChamberBlock.from_volume(volume_m3=0.080, width=0.6, height=0.5)
        assert ch.depth == pytest.approx(0.080 / (0.6 * 0.5))
        assert ch.internal_volume == pytest.approx(0.080)

    def test_from_volume_needs_two_dims(self):
        with pytest.raises(ValueError, match="almeno 2"):
            ChamberBlock.from_volume(volume_m3=0.080, width=0.6)

    def test_from_volume_trapezoidal_rejected(self):
        with pytest.raises(ValueError, match="rectangular"):
            ChamberBlock.from_volume(
                volume_m3=0.080, width=0.6, height=0.5,
                shape="trapezoidal",
            )

    def test_trapezoidal_shape(self):
        ch = ChamberBlock(
            width=0.8, height=0.5, depth=0.4, rear_width=0.4,
            shape="trapezoidal",
        )
        # Volume = avg(W) * H * D
        expected_vol = 0.5 * (0.8 + 0.4) * 0.5 * 0.4
        assert ch.internal_volume == pytest.approx(expected_vol)

    def test_trapezoidal_requires_rear_width(self):
        with pytest.raises(ValueError, match="rear_width"):
            ChamberBlock(width=0.8, height=0.5, depth=0.4, shape="trapezoidal")

    def test_panels_have_outward_normals(self):
        ch = ChamberBlock.from_dimensions(width=0.6, height=0.5, depth=0.4)
        # front panel normale ≈ +Z
        front = next(p for p in ch.panels if p.name == "front")
        assert front.normal[2] > 0.9
        back = next(p for p in ch.panels if p.name == "back")
        assert back.normal[2] < -0.9

    def test_cubic_warning(self):
        ch = ChamberBlock.from_dimensions(width=0.5, height=0.5, depth=0.5)
        codes = [w.code for w in ch.validate()]
        assert "CUBIC_CHAMBER" in codes

    def test_serialization_roundtrip(self):
        ch = ChamberBlock.from_dimensions(width=0.6, height=0.5, depth=0.4)
        ch2 = ChamberBlock.from_dict(ch.to_dict())
        assert ch2.internal_volume == pytest.approx(ch.internal_volume)
        assert ch2.shape == ch.shape


# ─── PortBlock ───────────────────────────────────────────────────────────────

class TestPortBlock:

    def test_circular_from_diameter(self):
        port = PortBlock.from_dimensions(diameter=0.10, length=0.20)
        expected_area = np.pi * 0.05 ** 2
        assert port.area == pytest.approx(expected_area)
        assert port.shape == "circular"
        assert port.width == pytest.approx(0.10)
        assert port.internal_volume == pytest.approx(expected_area * 0.20)

    def test_rectangular_from_dims(self):
        port = PortBlock.from_dimensions(
            shape="rectangular", width=0.30, height=0.05, length=0.15,
        )
        assert port.area == pytest.approx(0.30 * 0.05)

    def test_from_tuning_basic(self):
        # Camera 80 L, Fb=42 Hz, porta diam 100 mm
        Vb = 0.080
        port = PortBlock.from_tuning(
            Fb=42.0, chamber_volume=Vb,
            diameter=0.10,
        )
        # Verifica che la stessa porta torni Fb≈42 quando applicata a Vb
        Fb_back = port.helmholtz_frequency(Vb)
        assert Fb_back == pytest.approx(42.0, rel=1e-3)

    def test_from_tuning_too_large_raises(self):
        # Fb alto + porta grande rispetto al volume → end correction > L_eff
        # (la sola end correction basta già a tunare la cassa, L_geom < 0)
        with pytest.raises(ValueError, match="troppo grande"):
            PortBlock.from_tuning(
                Fb=200.0, chamber_volume=0.020,
                diameter=0.15,
            )

    def test_short_port_warning(self):
        port = PortBlock.from_dimensions(diameter=0.20, length=0.05)
        codes = [w.code for w in port.validate()]
        assert "PORT_TOO_SHORT" in codes

    def test_extreme_slot_warning(self):
        port = PortBlock.from_dimensions(
            shape="rectangular", width=0.50, height=0.005, length=0.10,
        )
        codes = [w.code for w in port.validate()]
        assert "SLOT_ASPECT_EXTREME" in codes

    def test_connection_ports(self):
        port = PortBlock.from_dimensions(diameter=0.10, length=0.20)
        ports = port.connection_ports
        assert "inner" in ports and "outer" in ports
        # normali opposte
        dot = float(np.dot(ports["inner"].normal, ports["outer"].normal))
        assert dot == pytest.approx(-1.0, abs=1e-9)

    def test_helmholtz_freq_reasonable(self):
        port = PortBlock.from_dimensions(diameter=0.10, length=0.20)
        Fb = port.helmholtz_frequency(0.080)
        # Range plausibile per sub
        assert 25.0 < Fb < 80.0

    def test_serialization_roundtrip(self):
        port = PortBlock.from_dimensions(diameter=0.10, length=0.20)
        port2 = PortBlock.from_dict(port.to_dict())
        assert port2.area == pytest.approx(port.area)
        assert port2.length == pytest.approx(port.length)


# ─── DriverBlock ─────────────────────────────────────────────────────────────

class TestDriverBlock:

    def test_basic_construction(self, driver_18):
        db = DriverBlock(driver=driver_18, mounting_depth=0.18)
        assert db.driver.sd == driver_18.sd
        assert db.basket_volume > 0

    def test_orientation_normals(self, driver_18):
        db = DriverBlock(driver=driver_18, orientation="forward")
        assert db.front_normal[2] == pytest.approx(1.0)
        assert db.back_normal[2] == pytest.approx(-1.0)

    def test_invalid_orientation(self, driver_18):
        with pytest.raises(ValueError):
            DriverBlock(driver=driver_18, orientation="diagonal")

    def test_no_panels(self, driver_18):
        db = DriverBlock(driver=driver_18)
        assert db.panels == []

    def test_connection_ports(self, driver_18):
        db = DriverBlock(driver=driver_18, mounting_depth=0.15)
        ports = db.connection_ports
        assert "front" in ports and "back" in ports
        assert ports["front"].area == pytest.approx(driver_18.sd)
        # Distanza front-back = mounting_depth
        gap = np.linalg.norm(ports["front"].position - ports["back"].position)
        assert gap == pytest.approx(0.15)

    def test_cutout(self, driver_18):
        db = DriverBlock(driver=driver_18)
        cutout = db.cutout_for_panel()
        assert cutout["type"] == "circular"
        assert cutout["purpose"] == "driver_mount"


# ─── Assembly ────────────────────────────────────────────────────────────────

class TestAssembly:

    def test_add_and_id_generation(self, driver_18):
        asm = Assembly(name="Test")
        ch = ChamberBlock.from_dimensions(width=0.6, height=0.5, depth=0.4)
        bid = asm.add(ch)
        assert bid.startswith("chamber")
        assert bid in asm.block_ids

    def test_explicit_id(self, driver_18):
        asm = Assembly()
        ch = ChamberBlock.from_dimensions(width=0.6, height=0.5, depth=0.4)
        asm.add(ch, block_id="main")
        assert "main" in asm.block_ids

    def test_duplicate_id_raises(self):
        asm = Assembly()
        ch1 = ChamberBlock.from_dimensions(width=0.6, height=0.5, depth=0.4)
        ch2 = ChamberBlock.from_dimensions(width=0.5, height=0.4, depth=0.3)
        asm.add(ch1, block_id="main")
        with pytest.raises(ValueError, match="duplicato"):
            asm.add(ch2, block_id="main")

    def test_remove(self):
        asm = Assembly()
        ch = ChamberBlock.from_dimensions(width=0.6, height=0.5, depth=0.4)
        asm.add(ch, block_id="x")
        asm.remove("x")
        assert "x" not in asm.block_ids

    def test_connect_basic(self, driver_18):
        asm = Assembly()
        # Driver montato sul back della camera
        # Driver "back" → Chamber "front" (entrambi area circa Sd, normali opposte)
        ch = ChamberBlock.from_dimensions(width=0.5, height=0.5, depth=0.45)
        # Posizione driver davanti alla camera
        # ch.front_port: position al centro della faccia +Z (oz+depth)
        # vogliamo driver.front normale +Z → driver "back" guarda -Z
        # driver position: poniamolo sul piano front della camera (z=0.45)
        front_port = ch.connection_ports["front"]
        db = DriverBlock(
            driver=driver_18, orientation="forward",
            mounting_depth=0.15, position=front_port.position,
        )
        asm.add(db, block_id="drv")
        asm.add(ch, block_id="cab")
        asm.connect("drv", "back", "cab", "front")
        assert len(asm.connections) == 1

    def test_connect_unknown_port_raises(self):
        asm = Assembly()
        ch = ChamberBlock.from_dimensions(width=0.6, height=0.5, depth=0.4)
        ch2 = ChamberBlock.from_dimensions(width=0.6, height=0.5, depth=0.4)
        asm.add(ch, block_id="a")
        asm.add(ch2, block_id="b")
        with pytest.raises(KeyError, match="bogus"):
            asm.connect("a", "bogus", "b", "front")

    def test_connect_self_raises(self):
        asm = Assembly()
        ch = ChamberBlock.from_dimensions(width=0.6, height=0.5, depth=0.4)
        asm.add(ch, block_id="a")
        with pytest.raises(ValueError):
            asm.connect("a", "front", "a", "back")

    def test_double_connection_raises(self, driver_18):
        asm = Assembly()
        ch = ChamberBlock.from_dimensions(width=0.6, height=0.5, depth=0.4)
        ch2 = ChamberBlock.from_dimensions(width=0.6, height=0.5, depth=0.4)
        asm.add(ch, block_id="a")
        asm.add(ch2, block_id="b")
        asm.connect("a", "front", "b", "back")
        with pytest.raises(ValueError, match="già usata"):
            asm.connect("a", "front", "b", "front")

    def test_validate_area_mismatch(self, driver_18):
        # Camera grande, driver piccolo → area mismatch
        asm = Assembly()
        big = ChamberBlock.from_dimensions(width=1.0, height=1.0, depth=0.5)
        ch = ChamberBlock.from_dimensions(width=0.3, height=0.3, depth=0.3)
        asm.add(big, block_id="big")
        asm.add(ch, block_id="small")
        asm.connect("big", "front", "small", "back")
        codes = [w.code for w in asm.validate()]
        assert "CONNECTION_AREA_MISMATCH" in codes

    def test_horn_throat_not_connected_warning(self, driver_18):
        asm = Assembly()
        horn = HornBlock.from_acoustics(
            driver=driver_18, cutoff_frequency=50.0,
            mouth_width=1.2, mouth_height=0.8,
        )
        asm.add(horn, block_id="horn")
        codes = [w.code for w in asm.validate()]
        assert "HORN_THROAT_NOT_CONNECTED" in codes

    def test_total_volume_aggregates(self, driver_18):
        asm = Assembly()
        ch = ChamberBlock.from_dimensions(width=0.6, height=0.5, depth=0.4)
        port = PortBlock.from_dimensions(diameter=0.10, length=0.20)
        asm.add(ch, block_id="cab")
        asm.add(port, block_id="port")
        expected = ch.internal_volume + port.internal_volume
        assert asm.total_volume == pytest.approx(expected)

    def test_serialization(self, driver_18):
        asm = Assembly(name="Sub Reflex")
        ch = ChamberBlock.from_dimensions(width=0.6, height=0.5, depth=0.4)
        port = PortBlock.from_dimensions(diameter=0.10, length=0.20)
        asm.add(ch, block_id="cab")
        asm.add(port, block_id="port")
        asm.connect("cab", "right", "port", "inner")
        d = asm.to_dict()
        assert d["name"] == "Sub Reflex"
        assert len(d["blocks"]) == 2
        assert len(d["connections"]) == 1


# ─── Integrazione: sub bass-reflex completo ─────────────────────────────────

class TestIntegrationSubReflex:

    def test_complete_sub_reflex_no_errors(self, driver_18):
        """
        Assembla un sub bass-reflex tipico:
          Driver 18" + camera 100L + porta accordata a 38 Hz.
        """
        Vb = 0.100  # 100 L
        Fb = 38.0
        # Camera centrata in origine, con depth 0.50
        ch = ChamberBlock.from_volume(volume_m3=Vb, width=0.60, height=0.50)
        # Porta sulla faccia front della camera
        front_port = ch.connection_ports["front"]
        port = PortBlock.from_tuning(
            Fb=Fb, chamber_volume=Vb,
            diameter=0.10,
            position=front_port.position,
            normal=front_port.normal,  # uscente verso esterno
        )
        # Driver montato sul front della camera (rispetto alla porta, fingiamo
        # in posizione differente lateralmente; per il test basta il front)
        # Per evitare port-already-used, lo connettiamo al "top"
        top_port = ch.connection_ports["top"]
        db = DriverBlock(
            driver=driver_18, orientation="up",
            mounting_depth=0.18, position=top_port.position,
        )

        asm = Assembly(name="Sub 18 reflex 100L")
        asm.add(db, block_id="drv")
        asm.add(ch, block_id="cab")
        asm.add(port, block_id="port")
        asm.connect("drv", "back", "cab", "top")
        asm.connect("port", "inner", "cab", "front")

        warnings = asm.validate()
        errors = [w for w in warnings if w.severity == Severity.ERROR]
        assert errors == []
        # Fb di accordo verificabile
        assert port.helmholtz_frequency(Vb) == pytest.approx(Fb, rel=1e-2)
