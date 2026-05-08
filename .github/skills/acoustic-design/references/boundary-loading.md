# Boundary Loading (Acoustic Loading from Walls)

When a low-frequency source is placed near rigid surfaces, radiation impedance increases → higher SPL for same input.

## Solid Angles

| Configuration | Solid angle | Gain (dB re free field) |
|---|---|---|
| Free field (suspended in space) | 4π sr | 0 |
| Half-space (1 boundary, e.g. on floor) | 2π sr | +6 |
| Quarter-space (2 boundaries, floor + wall) | π sr | +12 |
| Eighth-space (3 boundaries, corner) | π/2 sr | +18 |

## Validity

The +6/+12/+18 dB gain is valid only when source dimensions and distance to boundaries are **small compared to wavelength**. At higher frequencies, the boundary becomes "far" → less coherent reinforcement → comb filtering instead of pure gain.

Crossover frequency (boundary dependent): $f_b \approx c/(4d)$ where $d$ is distance from source to boundary. Above $f_b$, comb-filter dips begin.

## Subwoofer Implications

- Floor placement: always +6 dB (we can't change that).
- Floor + back wall: +12 dB at LF, but comb filtering above ~80 Hz if sub is 1 m from wall.
- Corner: +18 dB at LF, max output, but coloration audible if not crossed over low.
- **Buried / soffit-mounted** (the SubSim use case): effectively half-space if flush with wall surface — no boundary distance → no comb filter, pure +6 dB.

## Code Pattern (SubSim)

```python
def boundary_gain_db(position: str) -> float:
    """Gain in dB for low-frequency source near rigid boundaries.
    Valid for f << c/(4d).
    Reference: Beranek, "Acoustics" §7.3.
    """
    table = {"free": 0.0, "half": 6.0, "quarter": 12.0, "eighth": 18.0}
    return table[position]
```

## SBIR (Speaker-Boundary Interference Response)

Comb filtering between direct sound and boundary reflection:
$$|H(f)|^2 = 2 + 2\cos(2\pi f \cdot 2d/c)$$

Dips at $f = (2k+1) c/(4d)$, peaks at $f = k c/(2d)$.
Mitigations:
- Place sub at $d < \lambda/8$ from boundary (always flush at LF).
- Use multiple subs spatially distributed (Welti / Devantier).

## Multi-Sub Optimization

For room mode mitigation:
- 2 subs centered front/back (Welti config)
- 4 subs at quarter points (best uniformity)
- DSP delay/level per sub for modal interference cancellation

References: Welti (2003 AES), Devantier (2004 AES).
