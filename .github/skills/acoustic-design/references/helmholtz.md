# Helmholtz Resonator & Port Tuning

## Helmholtz Resonator

A volume V coupled to the outside via a neck of area S and length L behaves as a 2nd-order resonator:

$$f_h = \frac{c}{2\pi}\sqrt{\frac{S}{V \cdot L_{eff}}}$$

where:
- $c$ = 343 m/s (sound speed in air at 20°C, 1 atm)
- $L_{eff} = L + \Delta L$ (end correction)

End correction (one open end): $\Delta L \approx 0.85 \sqrt{S/\pi} = 0.85 r$ (round port).
Both ends radiating into half-space: $\Delta L_{total} \approx 1.7 r$.
Flanged port (port flush in baffle): $\Delta L = 0.85 r$ on the flanged end, $0.61 r$ on the unflanged end.

## Reference: Beranek "Acoustics" §5.3

## Port Design Procedure

Given: cabinet net volume $V_b$ [L], target tuning $f_b$ [Hz].

1. Choose port area $S_p$ from **air velocity criterion**:
   $$v_p = \frac{2\pi f_b X_{max} S_d}{S_p} \le v_{max}$$
   - $v_{max} \approx 17$ m/s (low chuffing for HiFi)
   - $v_{max} \approx 25$ m/s (PA, audible chuffing acceptable)
   - $v_{max} \approx 35$ m/s (extreme PA, transient only)
2. Compute required port length:
   $$L_p = \frac{c^2 S_p}{4\pi^2 f_b^2 V_b} - 1.7 \sqrt{S_p/\pi}$$
3. Verify $L_p > 0$. If negative → port too large for chosen $f_b$, reduce $S_p$.
4. Verify Mach number: $M = v_p/c < 0.05$ (else nonlinear distortion).

## Multiple Ports

N identical ports tuned to same $f_b$:
- Total area = $N \cdot S_p$
- Each port length unchanged
- End correction per port unchanged (assuming spacing > 2 diameters)

## Slot Ports

Rectangular slot of width $w$ × height $h$, length $L_p$:
- $S_p = w \cdot h$
- End correction depends on aspect ratio. For $w \gg h$: $\Delta L \approx 0.85 \cdot 2 h / \pi$ approximately.
- Empirical: use round-port formula with equivalent $r_{eq} = \sqrt{S_p/\pi}$ as first approximation, then validate with simulation.

## Cavity Resonance in Mounted Subs

For wall-mounted subs with front grille opening (not the bass-reflex port), the cavity between driver baffle and grille acts as a Helmholtz resonator that introduces a **dip** in response at $f_h$. Mitigations:
1. Make $f_h \gg f_{max}$ of sub (above 200 Hz).
2. Damp cavity with absorbent.
3. Open area > 50% (high $S$, low Q resonance).

## Example (18" sub, ported)

- $V_b = 130$ L, $f_b = 38$ Hz
- $S_d = 1210$ cm², $X_{max} = 12.5$ mm
- Required at full excursion: $v_p \le 25$ m/s (PA)
  $$S_p \ge \frac{2\pi \cdot 38 \cdot 0.0125 \cdot 0.121}{25} = 145\;\text{cm}^2$$
- Choose 2 round ports Ø 100 mm → $S_p = 157$ cm² each → 314 cm² total — overkill, can reduce. With 2× Ø 80 mm: $S_p = 100$ cm² each, 200 cm² total → $v_p = 18$ m/s → OK.
- Length per port: $L_p \approx \frac{343^2 \cdot 0.01}{4\pi^2 \cdot 38^2 \cdot 0.130} - 1.7 \cdot 0.040 = 0.49 - 0.068 = 0.42$ m
