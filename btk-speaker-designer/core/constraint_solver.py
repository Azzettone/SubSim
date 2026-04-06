"""
Risolutore vincoli dimensionali per BTK Speaker Designer.
Verifica che la geometria calcolata rispetti i limiti imposti dall'utente
e propone alternative se i vincoli non sono rispettabili.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, List, Tuple

from .geometry import CabinetGeometry, auto_select_geometry
from .horn_calculator import HornGeometry, design_horn
from .constants import GEOMETRY_STRAIGHT, GEOMETRY_FOLDED, GEOMETRY_2FOLDED


@dataclass
class DimensionalConstraints:
    """
    Vincoli dimensionali imposti dall'utente per il cabinet.
    Tutti i valori in millimetri. None = nessun limite.
    """
    max_width_mm: Optional[float] = None
    max_height_mm: Optional[float] = None
    max_depth_mm: Optional[float] = None
    max_weight_kg: Optional[float] = None

    def has_constraints(self) -> bool:
        return any(v is not None for v in [
            self.max_width_mm, self.max_height_mm,
            self.max_depth_mm, self.max_weight_kg
        ])

    def to_meters(self) -> "DimensionalConstraints":
        return DimensionalConstraints(
            max_width_mm=(self.max_width_mm / 1000) if self.max_width_mm else None,
            max_height_mm=(self.max_height_mm / 1000) if self.max_height_mm else None,
            max_depth_mm=(self.max_depth_mm / 1000) if self.max_depth_mm else None,
            max_weight_kg=self.max_weight_kg,
        )


@dataclass
class ConstraintViolation:
    """Descrive una violazione di vincolo."""
    constraint_name: str
    required_mm: float
    max_allowed_mm: float
    excess_mm: float
    severity: str  # 'critical', 'warning'

    def __str__(self) -> str:
        return (
            f"{self.constraint_name}: richiesto {self.required_mm:.0f}mm, "
            f"massimo consentito {self.max_allowed_mm:.0f}mm "
            f"(eccesso: {self.excess_mm:.0f}mm)"
        )


@dataclass
class ConstraintCheckResult:
    """Risultato della verifica dei vincoli dimensionali."""
    is_valid: bool
    violations: List[ConstraintViolation]
    cabinet: CabinetGeometry
    suggestions: List[str]

    @property
    def has_warnings(self) -> bool:
        return any(v.severity == 'warning' for v in self.violations)

    @property
    def has_critical(self) -> bool:
        return any(v.severity == 'critical' for v in self.violations)


def check_constraints(
    cabinet: CabinetGeometry,
    constraints: DimensionalConstraints
) -> ConstraintCheckResult:
    """
    Verifica se un cabinet rispetta i vincoli dimensionali.

    Args:
        cabinet: Geometria del cabinet da verificare
        constraints: Vincoli dimensionali

    Returns:
        ConstraintCheckResult con dettagli delle violazioni
    """
    violations = []
    suggestions = []

    # Margine di tolleranza (5mm)
    tolerance_mm = 5.0

    # Verifica larghezza
    if constraints.max_width_mm is not None:
        actual = cabinet.total_width_mm
        limit = constraints.max_width_mm
        if actual > limit + tolerance_mm:
            violations.append(ConstraintViolation(
                "Larghezza", actual, limit,
                actual - limit, "critical"
            ))
            suggestions.append(
                f"Ridurre il rapporto Sbocca/Sgola per diminuire la larghezza. "
                f"Oppure usare una tromba con bocca rettangolare stretta e alta."
            )

    # Verifica altezza
    if constraints.max_height_mm is not None:
        actual = cabinet.total_height_mm
        limit = constraints.max_height_mm
        if actual > limit + tolerance_mm:
            violations.append(ConstraintViolation(
                "Altezza", actual, limit,
                actual - limit, "critical"
            ))
            if cabinet.geometry_type == GEOMETRY_STRAIGHT:
                suggestions.append(
                    "Usare geometria Folded per ridurre l'altezza del cabinet."
                )
            elif cabinet.geometry_type == GEOMETRY_FOLDED:
                suggestions.append(
                    "Usare geometria 2-Folded per ridurre ulteriormente l'altezza."
                )

    # Verifica profondità
    if constraints.max_depth_mm is not None:
        actual = cabinet.total_depth_mm
        limit = constraints.max_depth_mm
        if actual > limit + tolerance_mm:
            violations.append(ConstraintViolation(
                "Profondità", actual, limit,
                actual - limit, "critical"
            ))
            if cabinet.geometry_type == GEOMETRY_STRAIGHT:
                suggestions.append(
                    "Usare geometria Folded o 2-Folded per ridurre la profondità."
                )

    is_valid = len(violations) == 0
    return ConstraintCheckResult(
        is_valid=is_valid,
        violations=violations,
        cabinet=cabinet,
        suggestions=list(set(suggestions))  # rimuovi duplicati
    )


def solve_with_constraints(
    horn_geometry: HornGeometry,
    constraints: DimensionalConstraints,
    panel_thickness_m: float = 0.018
) -> ConstraintCheckResult:
    """
    Progetta il cabinet ottimale rispettando i vincoli dimensionali.

    Tenta automaticamente le geometrie Straight, Folded, 2-Folded in ordine
    e verifica quale soddisfa i vincoli. Se nessuna li soddisfa, restituisce
    la migliore soluzione disponibile con avvisi.

    Args:
        horn_geometry: Parametri della tromba calcolati
        constraints: Vincoli dimensionali
        panel_thickness_m: Spessore pannelli in m

    Returns:
        ConstraintCheckResult con la migliore geometria trovata
    """
    c_m = constraints.to_meters()

    max_depth = c_m.max_depth_mm   # già in m
    max_height = c_m.max_height_mm
    max_width = c_m.max_width_mm

    best_cabinet = None
    best_result = None

    # Tenta le geometrie in ordine di complessità
    geometries_to_try = []

    # 1. Straight (se nessun vincolo di profondità o tromba corta)
    horn_length = horn_geometry.horn_length_m
    if max_depth is None or horn_length + 2 * panel_thickness_m <= (max_depth or float('inf')):
        from .geometry import design_straight_horn
        geometries_to_try.append(design_straight_horn(horn_geometry, panel_thickness_m))

    # 2. Folded
    if max_depth is not None:
        from .geometry import design_folded_horn
        geometries_to_try.append(design_folded_horn(horn_geometry, max_depth, panel_thickness_m))
    else:
        from .geometry import design_folded_horn
        geometries_to_try.append(design_folded_horn(horn_geometry, horn_length / 2, panel_thickness_m))

    # 3. 2-Folded
    from .geometry import design_2folded_horn
    depth_2f = max_depth or (horn_length / 3 + 0.1)
    height_2f = max_height or (horn_length * 1.5)
    geometries_to_try.append(design_2folded_horn(horn_geometry, depth_2f, height_2f, panel_thickness_m))

    # Verifica ogni geometria
    for cabinet in geometries_to_try:
        result = check_constraints(cabinet, constraints)
        if result.is_valid:
            return result
        if best_result is None or len(result.violations) < len(best_result.violations):
            best_result = result
            best_cabinet = cabinet

    # Nessuna geometria soddisfa tutti i vincoli: restituisce la migliore
    if best_result is None:
        # Fallback: usa auto_select_geometry
        cabinet = auto_select_geometry(horn_geometry, max_width, max_height, max_depth, panel_thickness_m)
        best_result = check_constraints(cabinet, constraints)

    best_result.suggestions.append(
        "Considerare di aumentare i vincoli dimensionali o ridurre la frequenza di taglio "
        "per ottenere una tromba più corta."
    )
    return best_result


def suggest_cutoff_for_constraints(
    constraints: DimensionalConstraints,
    driver_sd_m2: float,
    smouth_sthroat_ratio: float = 2.0,
    c: float = 343.0
) -> List[dict]:
    """
    Suggerisce frequenze di taglio compatibili con i vincoli dimensionali.

    Args:
        constraints: Vincoli dimensionali
        driver_sd_m2: Area diaframma driver in m²
        smouth_sthroat_ratio: Rapporto area bocca/gola
        c: Velocità del suono in m/s

    Returns:
        Lista di dizionari con frequenza e geometria suggerita
    """
    suggestions = []

    if constraints.max_depth_mm is None:
        return suggestions

    max_depth_m = constraints.max_depth_mm / 1000

    # Per tromba esponenziale: L = ln(ratio) / m = ln(ratio) * c / (4π * fc)
    # Quindi: fc = ln(ratio) * c / (4π * L)
    # Per geometria straight: L_max = max_depth - 2*pannelli
    L_max_straight = max_depth_m - 0.04  # margine pannelli
    L_max_folded = max_depth_m * 2 - 0.08
    L_max_2folded = max_depth_m * 3 - 0.12

    for L_max, geom_type in [
        (L_max_straight, GEOMETRY_STRAIGHT),
        (L_max_folded, GEOMETRY_FOLDED),
        (L_max_2folded, GEOMETRY_2FOLDED),
    ]:
        if L_max > 0:
            fc_min = np.log(smouth_sthroat_ratio) * c / (4 * np.pi * L_max)
            if fc_min > 0:
                suggestions.append({
                    "geometria": geom_type,
                    "fc_minima_hz": round(fc_min, 1),
                    "lunghezza_max_m": round(L_max, 3),
                    "descrizione": (
                        f"Con geometria {geom_type}: "
                        f"frequenza taglio minima {fc_min:.0f}Hz"
                    )
                })

    return suggestions
