"""
Test per il modulo geometry.
Verifica il calcolo delle geometrie straight/folded/2-folded del cabinet.
"""

import sys
import os
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from btk_speaker_designer.core.horn_calculator import design_horn
from btk_speaker_designer.core.geometry import (
    design_straight_horn,
    design_folded_horn,
    design_2folded_horn,
    auto_select_geometry,
    CabinetGeometry,
    Panel,
)
from btk_speaker_designer.core.constraint_solver import (
    DimensionalConstraints,
    check_constraints,
    solve_with_constraints,
)
from btk_speaker_designer.core.constants import (
    GEOMETRY_STRAIGHT, GEOMETRY_FOLDED, GEOMETRY_2FOLDED
)


def make_horn_geometry():
    """Helper per creare una geometria tromba standard."""
    return design_horn(70.0, 0.091, 2.0)


class TestPanel:
    """Test per il modello Panel."""

    def test_area_calculation(self):
        """L'area deve essere larghezza × altezza."""
        panel = Panel("test", 0.5, 0.3, 0.018, 1)
        assert abs(panel.area_m2 - 0.5 * 0.3) < 1e-10

    def test_mm_conversion(self):
        """Le conversioni in mm devono essere corrette."""
        panel = Panel("test", 0.5, 0.3, 0.018, 1)
        assert abs(panel.width_mm - 500.0) < 0.001
        assert abs(panel.height_mm - 300.0) < 0.001
        assert abs(panel.thickness_mm - 18.0) < 0.001

    def test_cost_calculation(self):
        """Il costo deve essere area × prezzo × quantità."""
        panel = Panel("test", 1.0, 1.0, 0.018, 2)
        cost = panel.cost(30.0)  # 30€/m²
        assert abs(cost - 1.0 * 1.0 * 2 * 30.0) < 0.001


class TestStraightHorn:
    """Test per la geometria tromba dritta."""

    def test_returns_cabinet_geometry(self):
        """Deve restituire un oggetto CabinetGeometry."""
        horn = make_horn_geometry()
        cabinet = design_straight_horn(horn)
        assert isinstance(cabinet, CabinetGeometry)

    def test_geometry_type(self):
        """Il tipo di geometria deve essere STRAIGHT."""
        horn = make_horn_geometry()
        cabinet = design_straight_horn(horn)
        assert cabinet.geometry_type == GEOMETRY_STRAIGHT

    def test_positive_dimensions(self):
        """Le dimensioni devono essere positive."""
        horn = make_horn_geometry()
        cabinet = design_straight_horn(horn)
        assert cabinet.total_width_m > 0
        assert cabinet.total_height_m > 0
        assert cabinet.total_depth_m > 0

    def test_panels_not_empty(self):
        """Ci devono essere pannelli nel cabinet."""
        horn = make_horn_geometry()
        cabinet = design_straight_horn(horn)
        assert len(cabinet.panels) > 0

    def test_depth_includes_horn_length(self):
        """La profondità deve includere la lunghezza della tromba."""
        horn = make_horn_geometry()
        t = 0.018
        cabinet = design_straight_horn(horn, t)
        # La profondità deve essere almeno la lunghezza della tromba
        assert cabinet.total_depth_m >= horn.horn_length_m

    def test_no_fold_points(self):
        """Una tromba dritta non deve avere punti di piega."""
        horn = make_horn_geometry()
        cabinet = design_straight_horn(horn)
        assert len(cabinet.fold_points) == 0


class TestFoldedHorn:
    """Test per la geometria tromba piegata."""

    def test_geometry_type(self):
        """Il tipo di geometria deve essere FOLDED."""
        horn = make_horn_geometry()
        cabinet = design_folded_horn(horn, max_depth_m=0.3)
        assert cabinet.geometry_type == GEOMETRY_FOLDED

    def test_has_one_fold_point(self):
        """Ci deve essere esattamente 1 punto di piega."""
        horn = make_horn_geometry()
        cabinet = design_folded_horn(horn, max_depth_m=0.3)
        assert len(cabinet.fold_points) == 1

    def test_depth_within_max(self):
        """La profondità deve rispettare il massimo specificato."""
        horn = make_horn_geometry()
        max_depth = 0.3
        cabinet = design_folded_horn(horn, max_depth_m=max_depth)
        # La profondità del cabinet deve essere vicina al max_depth
        assert cabinet.total_depth_m <= max_depth + 0.1  # con margine pannelli


class TestTwoFoldedHorn:
    """Test per la geometria tromba con 2 pieghe."""

    def test_geometry_type(self):
        """Il tipo di geometria deve essere 2FOLDED."""
        horn = make_horn_geometry()
        cabinet = design_2folded_horn(horn, max_depth_m=0.2, max_height_m=2.0)
        assert cabinet.geometry_type == GEOMETRY_2FOLDED

    def test_has_two_fold_points(self):
        """Ci devono essere esattamente 2 punti di piega."""
        horn = make_horn_geometry()
        cabinet = design_2folded_horn(horn, max_depth_m=0.2, max_height_m=2.0)
        assert len(cabinet.fold_points) == 2


class TestAutoSelectGeometry:
    """Test per la selezione automatica della geometria."""

    def test_returns_cabinet(self):
        """Deve restituire un oggetto CabinetGeometry."""
        horn = make_horn_geometry()
        cabinet = auto_select_geometry(horn)
        assert isinstance(cabinet, CabinetGeometry)

    def test_straight_when_no_constraints(self):
        """Senza vincoli, deve scegliere la geometria dritta."""
        horn = make_horn_geometry()
        cabinet = auto_select_geometry(horn)
        assert cabinet.geometry_type == GEOMETRY_STRAIGHT

    def test_folded_when_depth_limited(self):
        """Con profondità limitata, deve scegliere geometria piegata."""
        horn = make_horn_geometry()
        # Profondità massima molto piccola per forzare una piega
        cabinet = auto_select_geometry(horn, max_depth_m=0.05)
        assert cabinet.geometry_type in [GEOMETRY_FOLDED, GEOMETRY_2FOLDED]


class TestCabinetGeometry:
    """Test per la classe CabinetGeometry."""

    def test_total_cost(self):
        """Il costo totale deve essere la somma di tutti i pannelli."""
        horn = make_horn_geometry()
        cabinet = design_straight_horn(horn)
        price = 25.0
        total = cabinet.total_cost(price)
        expected = sum(p.cost(price) for p in cabinet.panels)
        assert abs(total - expected) < 0.001

    def test_cutlist_format(self):
        """La lista di taglio deve avere le chiavi corrette."""
        horn = make_horn_geometry()
        cabinet = design_straight_horn(horn)
        cutlist = cabinet.get_panel_cutlist()
        assert len(cutlist) > 0
        required_keys = ["nome", "larghezza_mm", "altezza_mm", "quantità"]
        for key in required_keys:
            assert key in cutlist[0], f"Chiave '{key}' mancante"


class TestConstraintSolver:
    """Test per il risolutore di vincoli dimensionali."""

    def test_no_constraints_valid(self):
        """Senza vincoli, la verifica deve sempre passare."""
        horn = make_horn_geometry()
        cabinet = design_straight_horn(horn)
        constraints = DimensionalConstraints()
        result = check_constraints(cabinet, constraints)
        assert result.is_valid

    def test_very_tight_depth_constraint(self):
        """Con vincolo di profondità molto stretto, ci deve essere una violazione."""
        horn = make_horn_geometry()
        cabinet = design_straight_horn(horn)
        # Imposta una profondità massima di soli 10mm (impossibile)
        constraints = DimensionalConstraints(max_depth_mm=10.0)
        result = check_constraints(cabinet, constraints)
        assert not result.is_valid

    def test_violations_have_suggestions(self):
        """Le violazioni devono avere suggerimenti."""
        horn = make_horn_geometry()
        cabinet = design_straight_horn(horn)
        constraints = DimensionalConstraints(max_depth_mm=10.0)
        result = check_constraints(cabinet, constraints)
        if not result.is_valid:
            assert len(result.suggestions) > 0

    def test_solve_with_constraints_returns_result(self):
        """solve_with_constraints deve restituire un risultato."""
        from btk_speaker_designer.core.constraint_solver import ConstraintCheckResult
        horn = make_horn_geometry()
        constraints = DimensionalConstraints()
        result = solve_with_constraints(horn, constraints)
        assert isinstance(result, ConstraintCheckResult)
