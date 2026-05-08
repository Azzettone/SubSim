"""
Test per geometry/panel_generator.py — conversione Block → solidi 3D.

Skippa automaticamente se build123d non è installato (CI senza libGL).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

# Skip intero modulo se build123d non importabile
bd = pytest.importorskip("build123d")

from btk_speaker_designer.blocks import ChamberBlock
from btk_speaker_designer.blocks.base_block import (
    Panel, DEFAULT_PANEL_THICKNESS,
)
from btk_speaker_designer.blocks.horn_block import HornBlock
from btk_speaker_designer.blocks.port_block import PortBlock
from btk_speaker_designer.blocks.driver_block import DriverBlock
from btk_speaker_designer.core.driver_model import DriverModel
from btk_speaker_designer.geometry import (
    panel_to_solid, chamber_shell, chamber_inner_volume,
    port_to_solid, driver_to_solid,
    horn_inner_volume, horn_wall_shell,
    export_step, export_stl, PanelGeometryError,
)


# ─── Test panel_to_solid ─────────────────────────────────────────────────────


class TestPanelToSolid:
    def _flat_xy_panel(self, side: float = 0.5, thickness: float = 0.018) -> Panel:
        """Pannello quadrato sul piano z=0, normale +Z."""
        v = np.array([
            [0.0, 0.0, 0.0],
            [side, 0.0, 0.0],
            [side, side, 0.0],
            [0.0, side, 0.0],
        ])
        return Panel(name="test_flat", vertices=v,
                     thickness=thickness, material="test", is_internal=False)

    def test_flat_panel_volume(self):
        side, t = 0.5, 0.018
        solid = panel_to_solid(self._flat_xy_panel(side, t))
        expected = side * side * t
        assert solid.volume == pytest.approx(expected, rel=1e-9)

    def test_panel_thickness_along_minus_normal(self):
        """Verifica che il solido si estenda da z=0 a z=-thickness."""
        t = 0.025
        solid = panel_to_solid(self._flat_xy_panel(0.3, t))
        bbox = solid.bounding_box()
        # build123d Vector ha attributi X/Y/Z (case-insensitive con .x/.y/.z)
        z_min, z_max = bbox.min.Z, bbox.max.Z
        # OCCT bbox ha tolleranza ~1e-6 di default
        assert z_max == pytest.approx(0.0, abs=1e-5)
        assert z_min == pytest.approx(-t, abs=1e-5)

    def test_label_set(self):
        solid = panel_to_solid(self._flat_xy_panel())
        assert solid.label == "test_flat"

    def test_degenerate_panel_raises(self):
        # Vertici collineari → normale nulla
        v = np.array([
            [0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0],
        ], dtype=float)
        p = Panel(name="bad", vertices=v, thickness=0.018,
                  material="x", is_internal=False)
        with pytest.raises(PanelGeometryError, match="degenere"):
            panel_to_solid(p)

    def test_zero_thickness_raises(self):
        p = self._flat_xy_panel(thickness=0.0)
        with pytest.raises(PanelGeometryError, match="thickness"):
            panel_to_solid(p)


# ─── Test chamber_shell ──────────────────────────────────────────────────────


class TestChamberShell:
    def test_rectangular_shell_six_panels(self):
        chamber = ChamberBlock.from_dimensions(
            width=0.4, height=0.5, depth=0.6,
        )
        shell = chamber_shell(chamber)
        # Compound deve contenere 6 child solids
        assert len(list(shell.children)) == 6

    def test_shell_volume_equals_six_panels(self):
        """Volume guscio = somma 6 pannelli (con sovrapposizione agli angoli)."""
        chamber = ChamberBlock.from_dimensions(
            width=0.4, height=0.5, depth=0.6,
        )
        shell = chamber_shell(chamber)
        t = chamber.panel_thickness
        # Volume "naive" senza overlap-correction:
        # 2 (front+back) × W×H×t + 2 (top+bot) × W×D×t + 2 (left+right) × H×D×t
        W, H, D = 0.4, 0.5, 0.6
        expected_naive = 2*t*(W*H + W*D + H*D)
        assert shell.volume == pytest.approx(expected_naive, rel=1e-6)

    def test_trapezoidal_shell_six_panels(self):
        chamber = ChamberBlock.from_dimensions(
            width=0.5, height=0.4, depth=0.6,
            rear_width=0.3, shape="trapezoidal",
        )
        shell = chamber_shell(chamber)
        assert len(list(shell.children)) == 6


# ─── Test chamber_inner_volume ───────────────────────────────────────────────


class TestChamberInnerVolume:
    def test_rectangular_inner_volume(self):
        W, H, D = 0.4, 0.5, 0.6
        chamber = ChamberBlock.from_dimensions(width=W, height=H, depth=D)
        cavity = chamber_inner_volume(chamber)
        t = chamber.panel_thickness
        expected = (W - 2*t) * (H - 2*t) * (D - 2*t)
        assert cavity.volume == pytest.approx(expected, rel=1e-6)

    def test_trapezoidal_inner_volume_loft(self):
        W, Wb, H, D = 0.5, 0.3, 0.4, 0.6
        chamber = ChamberBlock.from_dimensions(
            width=W, height=H, depth=D, rear_width=Wb, shape="trapezoidal",
        )
        cavity = chamber_inner_volume(chamber)
        t = chamber.panel_thickness
        # Volume prisma trapezoidale (sezione a "trapezio scorrevole" su z):
        # V = ∫₀^(D-2t) [W(z) × (H-2t)] dz, con W(z) lineare da Wb-2t a W-2t.
        # = (H-2t) × (D-2t) × ((W-2t) + (Wb-2t))/2
        H_in, D_in = H - 2*t, D - 2*t
        W_avg_in = ((W - 2*t) + (Wb - 2*t)) / 2
        expected = H_in * D_in * W_avg_in
        assert cavity.volume == pytest.approx(expected, rel=1e-6)

    def test_too_thick_panels_raise(self):
        chamber = ChamberBlock.from_dimensions(
            width=0.04, height=0.04, depth=0.04,
            panel_thickness=0.025,  # 25mm su 40mm → 25*2 > 40
        )
        with pytest.raises(PanelGeometryError, match="degenere"):
            chamber_inner_volume(chamber)


# ─── Test export ─────────────────────────────────────────────────────────────


class TestExport:
    def test_export_step(self, tmp_path: Path):
        chamber = ChamberBlock.from_dimensions(width=0.3, height=0.4, depth=0.5)
        cavity = chamber_inner_volume(chamber)
        out = tmp_path / "cavity.step"
        export_step(cavity, out)
        assert out.exists() and out.stat().st_size > 100

    def test_export_stl(self, tmp_path: Path):
        chamber = ChamberBlock.from_dimensions(width=0.3, height=0.4, depth=0.5)
        shell = chamber_shell(chamber)
        out = tmp_path / "shell.stl"
        export_stl(shell, out)
        assert out.exists() and out.stat().st_size > 100

    def test_export_step_no_scale(self, tmp_path: Path):
        chamber = ChamberBlock.from_dimensions(width=0.3, height=0.4, depth=0.5)
        cavity = chamber_inner_volume(chamber)
        out = tmp_path / "cavity_m.step"
        export_step(cavity, out, scale_to_mm=False)
        assert out.exists()


# ─── Test port_to_solid ──────────────────────────────────────────────────────


class TestPortToSolid:
    def test_circular_volume(self):
        """Cilindro: volume = π·r²·L"""
        d = 0.10
        L = 0.25
        port = PortBlock.from_dimensions(diameter=d, length=L)
        solid = port_to_solid(port)
        expected = math.pi * (d / 2) ** 2 * L
        assert solid.volume == pytest.approx(expected, rel=1e-5)

    def test_circular_along_z_default(self):
        """Porta circolare con normal=+Z → solido si estende da z=0 a z=L."""
        d, L = 0.08, 0.20
        port = PortBlock.from_dimensions(diameter=d, length=L, position=np.zeros(3))
        solid = port_to_solid(port)
        bb = solid.bounding_box()
        assert bb.min.Z == pytest.approx(0.0, abs=1e-5)
        assert bb.max.Z == pytest.approx(L, abs=1e-5)

    def test_circular_along_x(self):
        """Porta orientata lungo +X → estesa in X, non in Z."""
        d, L = 0.08, 0.20
        port = PortBlock.from_dimensions(
            diameter=d, length=L,
            normal=np.array([1.0, 0.0, 0.0]),
            position=np.zeros(3),
        )
        solid = port_to_solid(port)
        bb = solid.bounding_box()
        assert bb.max.X == pytest.approx(L, abs=1e-5)
        # Z-extent deve essere solo il diametro (non la lunghezza)
        assert (bb.max.Z - bb.min.Z) == pytest.approx(d, abs=1e-5)

    def test_circular_translated(self):
        """Porta con position=[1,2,3]: inlet-face centrata in [1,2,3]."""
        d, L = 0.10, 0.30
        pos = np.array([1.0, 2.0, 3.0])
        port = PortBlock.from_dimensions(diameter=d, length=L, position=pos)
        solid = port_to_solid(port)
        bb = solid.bounding_box()
        # Lungo Z (default normal): da z=3 a z=3+L
        assert bb.min.Z == pytest.approx(3.0, abs=1e-5)
        assert bb.max.Z == pytest.approx(3.0 + L, abs=1e-5)
        # Centro X,Y
        cx = (bb.min.X + bb.max.X) / 2
        cy = (bb.min.Y + bb.max.Y) / 2
        assert cx == pytest.approx(1.0, abs=1e-5)
        assert cy == pytest.approx(2.0, abs=1e-5)

    def test_rectangular_volume(self):
        """Slot rettangolare: volume = W × H × L"""
        W, H, L = 0.15, 0.06, 0.25
        port = PortBlock.from_dimensions(
            width=W, height=H, length=L, shape="rectangular",
        )
        solid = port_to_solid(port)
        expected = W * H * L
        assert solid.volume == pytest.approx(expected, rel=1e-5)

    def test_label(self):
        port = PortBlock.from_dimensions(diameter=0.10, length=0.20)
        solid = port_to_solid(port)
        assert "port" in solid.label

    def test_along_minus_z(self):
        """Porta verso -Z deve funzionare (rotazione 180°)."""
        d, L = 0.10, 0.20
        port = PortBlock.from_dimensions(
            diameter=d, length=L,
            normal=np.array([0.0, 0.0, -1.0]),
            position=np.zeros(3),
        )
        solid = port_to_solid(port)
        assert solid.volume == pytest.approx(math.pi * (d/2)**2 * L, rel=1e-5)


# ─── Test driver_to_solid ────────────────────────────────────────────────────


class TestDriverToSolid:
    def _make_driver(self, sd: float = 0.0346, depth: float = 0.12) -> DriverBlock:
        """Driver RCF 12" approssimato: Sd=346cm², depth=120mm."""
        dm = DriverModel(
            manufacturer="RCF",
            model="LF12X400",
            driver_type="subwoofer",
            fs=35.0, re=5.3, qes=0.28, qms=8.0,
            vas=90.0, sd=sd, xmax=10.0, bl=15.5,
            mms=120.0, spl_1w_1m=97.0, power_rms=400.0,
            impedance_nominal=8.0,
        )
        return DriverBlock(driver=dm, mounting_depth=depth)

    def test_volume_is_cylinder(self):
        """Volume = π·r²·max(depth,0.05)"""
        sd, depth = 0.0346, 0.12
        driver = self._make_driver(sd=sd, depth=depth)
        solid = driver_to_solid(driver)
        r = math.sqrt(sd / math.pi)
        expected = math.pi * r**2 * depth
        assert solid.volume == pytest.approx(expected, rel=1e-4)

    def test_min_depth_fallback(self):
        """mounting_depth=0 → usa 0.05 m come minimo."""
        driver = self._make_driver(depth=0.0)
        solid = driver_to_solid(driver)
        sd = driver.driver.sd
        r = math.sqrt(sd / math.pi)
        expected = math.pi * r**2 * 0.05
        assert solid.volume == pytest.approx(expected, rel=1e-4)

    def test_orientation_forward_along_z(self):
        """orientation='forward' (+Z): solido va da Z=0 a Z=depth."""
        driver = self._make_driver(depth=0.10)
        solid = driver_to_solid(driver)
        bb = solid.bounding_box()
        assert bb.min.Z == pytest.approx(0.0, abs=1e-5)
        assert bb.max.Z == pytest.approx(0.10, abs=1e-5)

    def test_orientation_backward_along_neg_z(self):
        """orientation='backward' (-Z): solido va da Z=-depth a Z=0."""
        dm = self._make_driver(depth=0.10).driver
        driver = DriverBlock(driver=dm, orientation="backward", mounting_depth=0.10)
        solid = driver_to_solid(driver)
        bb = solid.bounding_box()
        assert bb.min.Z == pytest.approx(-0.10, abs=1e-5)
        assert bb.max.Z == pytest.approx(0.0, abs=1e-5)

    def test_label_contains_manufacturer(self):
        driver = self._make_driver()
        solid = driver_to_solid(driver)
        assert "RCF" in solid.label


# ─── Test horn_inner_volume ──────────────────────────────────────────────────


class TestHornInnerVolume:
    """HornBlock.from_acoustics / fold=0,1 → solido cavità aria."""

    def _make_driver(self, sd: float = 0.0220) -> DriverModel:
        """Driver 12" generico."""
        return DriverModel(
            manufacturer="Test", model="Sub12",
            driver_type="subwoofer",
            fs=40.0, re=5.5, qes=0.35, qms=6.0,
            vas=80.0, sd=sd, xmax=8.0, bl=14.0,
            mms=100.0, spl_1w_1m=96.0, power_rms=300.0,
            impedance_nominal=8.0,
        )

    def test_fold0_volume_positive(self):
        horn = HornBlock.from_acoustics(
            driver=self._make_driver(),
            cutoff_frequency=60.0,
            expansion="exponential", fold=0,
            mouth_width=0.5, mouth_height=0.36,
        )
        solid = horn_inner_volume(horn)
        assert solid.volume > 0.0

    def test_fold0_volume_between_throat_and_mouth(self):
        """Volume aria deve essere tra V_gola_cilindrica e V_bocca_cilindrica."""
        horn = HornBlock.from_acoustics(
            driver=self._make_driver(),
            cutoff_frequency=60.0,
            expansion="exponential", fold=0,
            mouth_width=0.5, mouth_height=0.36,
        )
        solid = horn_inner_volume(horn)
        # Volume minimo (cilindro dalla gola): S_t * L
        v_min = horn.throat_area * horn.length
        # Volume massimo (cilindro dalla bocca): S_m * L
        v_max = horn.mouth_area * horn.length
        assert v_min < solid.volume < v_max

    def test_fold0_label(self):
        horn = HornBlock.from_acoustics(
            driver=self._make_driver(),
            cutoff_frequency=70.0,
            expansion="exponential", fold=0,
            mouth_width=0.45, mouth_height=0.32,
        )
        solid = horn_inner_volume(horn)
        assert "cavity" in solid.label

    def test_fold1_volume_positive(self):
        horn = HornBlock.from_acoustics(
            driver=self._make_driver(),
            cutoff_frequency=60.0,
            expansion="exponential", fold=1,
            mouth_width=0.5, mouth_height=0.36,
        )
        solid = horn_inner_volume(horn)
        assert solid.volume > 0.0

    def test_fold1_volume_larger_than_fold0(self):
        """fold=1 ha stessa tromba di fold=0: volume acustico deve essere uguale."""
        horn0 = HornBlock.from_acoustics(
            driver=self._make_driver(),
            cutoff_frequency=60.0,
            expansion="exponential", fold=0,
            mouth_width=0.5, mouth_height=0.36,
        )
        horn1 = HornBlock.from_acoustics(
            driver=self._make_driver(),
            cutoff_frequency=60.0,
            expansion="exponential", fold=1,
            mouth_width=0.5, mouth_height=0.36,
        )
        v0 = horn_inner_volume(horn0).volume
        v1 = horn_inner_volume(horn1).volume
        # Stesso profilo acustico: fold non cambia il volume d'aria.
        # Tolleranza 5%: il loft pairwise omette la slice alla cerniera di piega
        # (dot negativo tra normali consecutive → loft astronomicamente invalido).
        # La slice mancante contribuisce ~1.7% del volume totale.
        assert v1 == pytest.approx(v0, rel=0.05)

    def test_fold0_tractrix_volume_positive(self):
        horn = HornBlock.from_acoustics(
            driver=self._make_driver(),
            cutoff_frequency=60.0,
            expansion="tractrix", fold=0,
            mouth_width=0.5, mouth_height=0.36,
        )
        solid = horn_inner_volume(horn)
        assert solid.volume > 0.0

    def test_fold0_hypex_volume_positive(self):
        horn = HornBlock.from_acoustics(
            driver=self._make_driver(),
            cutoff_frequency=60.0,
            expansion="hypex", fold=0,
            mouth_width=0.5, mouth_height=0.36,
        )
        solid = horn_inner_volume(horn)
        assert solid.volume > 0.0


# ─── Test horn_wall_shell ────────────────────────────────────────────────────


class TestHornWallShell:
    def _make_driver(self) -> DriverModel:
        return DriverModel(
            manufacturer="Test", model="Sub12",
            driver_type="subwoofer",
            fs=40.0, re=5.5, qes=0.35, qms=6.0,
            vas=80.0, sd=0.022, xmax=8.0, bl=14.0,
            mms=100.0, spl_1w_1m=96.0, power_rms=300.0,
            impedance_nominal=8.0,
        )

    def test_shell_has_children(self):
        horn = HornBlock.from_acoustics(
            driver=self._make_driver(),
            cutoff_frequency=60.0,
            expansion="exponential", fold=0,
            mouth_width=0.5, mouth_height=0.36,
        )
        shell = horn_wall_shell(horn)
        children = list(shell.children)
        # Atteso: (N-1)*4 strip panels + throat_baffle + mouth_frame >= 4
        assert len(children) >= 4

    def test_shell_volume_positive(self):
        horn = HornBlock.from_acoustics(
            driver=self._make_driver(),
            cutoff_frequency=60.0,
            expansion="exponential", fold=0,
            mouth_width=0.5, mouth_height=0.36,
        )
        shell = horn_wall_shell(horn)
        assert shell.volume > 0.0

    def test_shell_fold1_skip_errors(self):
        """Fold=1 con skip_errors=True non deve sollevare eccezioni."""
        horn = HornBlock.from_acoustics(
            driver=self._make_driver(),
            cutoff_frequency=60.0,
            expansion="exponential", fold=1,
            mouth_width=0.5, mouth_height=0.36,
        )
        shell = horn_wall_shell(horn, skip_errors=True)
        assert len(list(shell.children)) >= 4
