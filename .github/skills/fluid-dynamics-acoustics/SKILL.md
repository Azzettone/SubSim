---
name: fluid-dynamics-acoustics
description: 'Fluid dynamics for acoustic design: port airflow, chuffing, vortex shedding, Reynolds number, Mach criterion, boundary layer losses, thermo-viscous attenuation, nonlinear distortion (THD) at high SPL. Use when: sizing ports/vents, evaluating chuffing risk, computing minimum port area for given Xmax, analyzing turbulence in horn throats, implementing fluid_acoustics.py / grille_calculator.py / acoustic_engine.py. References Beranek, Backus, OpenFOAM acoustic CFD.'
---

# Fluid Dynamics in Acoustic Design

When sound becomes high-amplitude (high SPL, high particle velocity), linear acoustics breaks down and fluid-dynamic effects dominate.

## When to Use

- Sizing bass-reflex ports (chuffing prevention)
- Designing horn throats / phase plugs (turbulence at compression chamber)
- Computing grille open-area criteria (in SubSim wall-mounted use case)
- Estimating THD at high SPL
- Analyzing boundary-layer losses in long ducts

## Key Dimensionless Numbers

### Reynolds Number
$$Re = \frac{\rho v D}{\mu} = \frac{v D}{\nu}$$

- Air at 20°C: $\nu \approx 1.5 \cdot 10^{-5}$ m²/s
- Re < 2300: laminar
- 2300 < Re < 4000: transitional
- Re > 4000: turbulent

For a port Ø 100 mm at v=20 m/s: $Re = 20 \cdot 0.1 / 1.5 \cdot 10^{-5} \approx 130000$ → fully turbulent.

### Mach Number
$$M = v/c$$

- M < 0.05: linear acoustics OK (≤ 17 m/s)
- 0.05 < M < 0.1: nonlinear distortion measurable (~ 1–3% THD)
- M > 0.1: severe distortion, audible chuffing (> 34 m/s)

### Strouhal Number (vortex shedding)
$$St = f_v D / v$$

- $St \approx 0.2$ for cylinders/sharp edges
- $f_v$ = vortex shedding frequency
- Audible vortex tones occur at $f_v$ when port flow detaches at sharp edges → flared ports prevent this.

## Port Air Velocity

Peak velocity at port for sinusoidal excursion:
$$v_p = \frac{2\pi f X_{max} S_d}{S_p}$$

Same formula as in helmholtz reference but here used as **design constraint**:

| Application | $v_{max}$ |
|---|---|
| Studio monitor / HiFi | 12–17 m/s |
| Hi-end home | 17 m/s |
| PA tops / mids | 25 m/s |
| Pro subs (touring) | 25–30 m/s |
| Cinema / club fixed | 25 m/s (sustained), 30 m/s (peak) |

## Chuffing & Mitigations

Chuffing = audible turbulent noise from port edges. Causes:
1. Sharp port edges (use radius ≥ 1 cm)
2. Excessive velocity (see table)
3. Port too short (LF flow oscillation amplifies separation)
4. Port mouth obstructions (cabling, structure)

Mitigations:
- Flared ports (continuous radius from straight section to mouth, exit ratio 1.3–1.6×)
- Multiple smaller ports vs one large port (better edge condition)
- Internal flare (Linkwitz / SBE — slot ports with rounded throat)
- Power compression / DSP limiter at velocity threshold

## Boundary Layer Losses

In long ducts (horns, tuning ports):
$$\alpha_{thermal+viscous} \approx \frac{1}{r}\sqrt{\frac{\pi f \mu}{2\rho c^2}}\left(1 + \frac{\gamma-1}{\sqrt{Pr}}\right)$$

For a 100 mm port at 50 Hz: ≈ 0.005 dB/m → negligible.
For a 25 mm horn throat at 5 kHz: ≈ 1 dB/m → not negligible in compression drivers.

Reference: Pierce, "Acoustics", §10.

## Vortex Shedding at Edges

In horn throats with sharp transitions:
1. Flow separates at corner
2. Vortices shed at $f_v = St \cdot v / D$ ($St \approx 0.2$)
3. Vortex impingement on horn walls → broadband noise + tonal components
4. Solution: smooth tangent transitions, radius ≥ 0.1 × throat dimension

## Nonlinear Distortion (THD)

At high SPL, the wave equation becomes nonlinear (Burgers eq., shock formation):
$$\frac{\partial p}{\partial t} + (c_0 + \beta u)\frac{\partial p}{\partial x} = \delta\frac{\partial^2 p}{\partial x^2}$$

where $\beta = (\gamma+1)/2 \approx 1.2$ for air, $\delta$ accounts for thermo-viscous diffusion.

Practical: for sub at 130 dB SPL @ 1 m, particle velocity ≈ 1 m/s → distortion ~ 1% for 50 Hz tone, much higher in horn throat where v is amplified by area ratio.

## Code Pattern

```python
def port_velocity(f_hz, x_max_m, sd_m2, sp_m2):
    """Peak port air velocity for sinusoidal piston motion."""
    return 2 * np.pi * f_hz * x_max_m * sd_m2 / sp_m2

def reynolds_port(velocity_ms, diameter_m, nu=1.5e-5):
    return velocity_ms * diameter_m / nu

def chuffing_risk(velocity_ms):
    if velocity_ms < 17: return "ok_hifi"
    if velocity_ms < 25: return "ok_pa"
    if velocity_ms < 30: return "borderline"
    return "chuff"
```

## References

- Beranek, "Acoustics", ch. 10 (nonlinear)
- Backus, "Acoustical Foundations of Music", §3 (turbulence in wind instruments)
- Pierce, "Acoustics: An Introduction to its Physical Principles" (1981)
- Vanhille & Campos-Pozuelo, "Numerical model for nonlinear standing waves" (JASA 2002)
- Salvatti, Devantier, Button, "Maximizing Performance from Loudspeaker Ports" (AES 2002)
- Roozen et al., "Vortex sound in bass-reflex ports" (JSV 1998)

## Related Project Files

- `shared/fluid_acoustics.py` — fluid-dynamic helpers
- `shared/grille_calculator.py` — grille open-area + chuffing for SubSim
- `btk-speaker-designer/core/acoustic_engine.py` — port chuffing checks
- `uploads/FLUIDODINAMICA_DESIGN_ACUSTICO.md` — internal design notes
