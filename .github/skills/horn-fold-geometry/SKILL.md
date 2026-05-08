---
name: horn-fold-geometry
description: 'Geometry of folded horn cabinets: Z-fold (1 piega), W-fold (2 pieghe), scoop, tapped horn, bandpass-horn hybrids. Use when: implementing or debugging HornBlock fold logic, _apply_fold_transform, fold_baffle positioning, cabinet_depth constraints, leg stacking in Y. Reference archetypes: Klipsch La Scala, Cerwin-Vega 186 Horn, RCF/d&b 1850 Folded, Mogale Super Scooper, Soundlab Scoop, FunktionOne F221, MT102. Includes coordinate conventions for BTK Speaker Designer.'
---

# Folded Horn Geometry

Folding lets a long horn fit in a compact cabinet. Each fold mirrors the acoustic axis through a baffle plate.

## When to Use

- Editing `btk-speaker-designer/blocks/horn_block.py` fold methods
- Implementing new fold archetypes (W-fold, scoop, tapped)
- Debugging fold visualization (viewport not aligned, legs overlapping/gapping)
- Validating that fold geometry matches acoustic length

## Coordinate Convention (BTK)

- **Throat** at $z=0$, normal $+\hat{z}$
- **Horn unfolded** extends to $z=L$ (full acoustic length)
- **Y axis** = cabinet height (vertical), Y=0 = throat center
- **X axis** = cabinet width
- **Driver chamber** at $z \in [-D_{ch}, 0]$, behind throat
- **Driver block** centered on z-axis, displaced $-50\;mm$ from throat

## Z-Fold (fold = 1) — Archetype A

Pattern: **one fold**, leg 0 goes $+\hat{z}$, leg 1 returns $-\hat{z}$, stacked vertically.

```
    leg 1: ←──────── (Y = h₁)
                     ┃
                     ┃ fold baffle 1
                     ┃
    leg 0: ────────→ (Y = 0, throat at z=0)
```

Reference designs:
- Cerwin-Vega 186 Horn (18", direct radiator)
- RCF/L-Acoustics 1850 Folded
- Klipsch La Scala (mid horn)
- d&b J-Sub style (compact reflex-horn hybrid)

Geometry (BTK implementation):
- $D = $ leg depth $= \min(\text{cabinet\_depth},\; L/(fold+1))$
- Leg $k$ Y position $=\sum_{j=1}^{k} h(j \cdot D)$ where $h(x)$ = section height at axial position $x$
- Even legs: $+\hat{z}$, $z = x_{in\_leg}$
- Odd legs: $-\hat{z}$, $z = D - x_{in\_leg}$
- Fold baffle $k$ at Y = midpoint between leg $k-1$ and leg $k$, spans $z \in [0, D]$

## W-Fold (fold = 2) — Archetype B

Pattern: **two folds**, legs alternate $+\hat{z}, -\hat{z}, +\hat{z}$, stacked.

```
    leg 2: ────────→ (Y = h₁ + h₂)
                     ┃ fold baffle 2
    leg 1: ←──────── (Y = h₁)
                     ┃ fold baffle 1
    leg 0: ────────→ (Y = 0)
```

Reference designs:
- Mogale Super Scooper (touring sub)
- Soundlab Scoop
- MT102 (cinema scoop)
- EV MT-4 / TL-606

## Scoop (fold = 1, narrow throat) — Archetype C

Special case of Z-fold where throat is very narrow (driver fires into a small chamber, then expansion into scoop). Driver mounted on side of cabinet, not on throat baffle. Common in JBL 4520, Klipsch Scala variants.

Currently NOT modeled separately in BTK — use fold=1 + custom chamber.

## Tapped Horn — Archetype D

Both sides of the driver couple to the horn at different positions:
- Front of cone → throat
- Back of cone → mid-horn (≈ L/4 from throat)

Cancellation/reinforcement creates extended LF response below classic horn cutoff. Used in Danley TH series.

NOT yet implemented in BTK. Would require dual port / two coupling locations on horn.

## Validation Checks for Fold Geometry

1. **Acoustic length preserved**: $\sum$ leg lengths = $L$.
2. **Legs do not overlap** in $(Y, z)$ projection: for each pair (leg $i$, leg $j>i$), Y ranges disjoint OR Z ranges disjoint.
3. **Section continuity at folds**: section at end of leg $k$ matches section at start of leg $k+1$ (same area, same w×h).
4. **Fold baffle thickness**: leg-to-leg gap ≥ panel thickness (else physically infeasible).
5. **Fold cutoff** $f_{fold} = c/(8 \cdot w_{fold}) > F_{c,target}$ where $w_{fold}$ = perpendicular dimension at fold.

## HF Loss at Folds

At fold, the section "rotates" around a corner. For wavelengths comparable to fold dimension, this introduces:
- Reflection (impedance mismatch at corner)
- HF cutoff at $f \approx c/(8 w_{fold})$

For sub horns (Fc 30–60 Hz), fold dimension ~50 cm → fold cutoff ~85 Hz. Acceptable for sub, problematic for mids.

## Code: HornBlock Fold Helpers (current BTK)

```python
def _fold_depth(self) -> float:
    D_natural = self.length / (self.fold + 1)
    if self.cabinet_depth is not None and self.cabinet_depth > 0:
        return min(float(self.cabinet_depth), D_natural)
    return D_natural

def _fold_y_shift_at(self, leg: int) -> float:
    if leg == 0: return 0.0
    D = self._fold_depth()
    return sum(self._section_h_at(k * D) for k in range(1, leg + 1))

def _apply_fold_transform(self, x_axial, w, h):
    if self.fold == 0:
        return np.array([0,0,x_axial]), np.array([0,0,1])
    D = self._fold_depth()
    leg = min(int(x_axial / D), self.fold)
    x_in_leg = x_axial - leg * D
    shift_y = self._fold_y_shift_at(leg)
    if leg % 2 == 0:
        return np.array([0, shift_y, x_in_leg]), np.array([0,0,1])
    return np.array([0, shift_y, D - x_in_leg]), np.array([0,0,-1])
```
