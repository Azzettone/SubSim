# Thiele-Small Parameters & Box Alignments

## Core T-S Parameters

| Symbol | Meaning | Units |
|---|---|---|
| $f_s$ | Free-air resonance | Hz |
| $Q_{ts}$ | Total Q at $f_s$ | – |
| $Q_{es}$ | Electrical Q | – |
| $Q_{ms}$ | Mechanical Q ($1/Q_{ts} = 1/Q_{es} + 1/Q_{ms}$) | – |
| $V_{as}$ | Equivalent compliance volume | L (or m³) |
| $S_d$ | Effective diaphragm area | m² (or cm²) |
| $X_{max}$ | Linear excursion (one-way) | mm |
| $R_e$ | DC voice-coil resistance | Ω |
| $L_e$ | Voice-coil inductance | mH |
| $BL$ | Force factor | T·m (or N/A) |
| $M_{ms}$ | Moving mass | g |
| $C_{ms}$ | Suspension compliance | mm/N |
| $\eta_0$ | Reference efficiency | – |

## Sealed Box (Closed Box, "QB")

System Q:
$$Q_{tc} = Q_{ts}\sqrt{1 + V_{as}/V_b}$$
$$f_c = f_s \sqrt{1 + V_{as}/V_b}$$

Common alignments:
- $Q_{tc}=0.5$ — critically damped, transient-perfect (HiFi)
- $Q_{tc}=0.707$ — Butterworth (B2), maximally flat
- $Q_{tc}=1.0$+ — peaked, "EBP" alignment

EBP rule: $EBP = f_s/Q_{es}$. EBP < 50 → sealed; > 100 → vented; in between → either.

## Vented (Bass-Reflex)

4th-order alignment. Tuning frequency $f_b$ from port:
$$f_b = \frac{c}{2\pi}\sqrt{\frac{S_p}{V_b (L_p + 1.7 r_p)}}$$
where $S_p$ = port area, $L_p$ = physical port length, $r_p$ = port radius (end correction = 0.85·r per open end, sum 1.7r).

Common alignments (from Small/Thiele):
- B4 (Butterworth): $f_b/f_s = 1$, $V_b/V_{as} \approx 1$, response −3 dB at $f_3 = f_b$.
- C4 (Chebyshev): higher Vb, lower f3, ripple in passband.
- QB3 (quasi-Butterworth): smaller Vb, higher f3.
- SBB4 (Super-Boom-Box): tuned below fs, "1-note bass".

## Bandpass (4th / 6th order)

4th-order BP: vented chamber on one side of driver, sealed on the other. Driver is hidden, output via port.
- Bandwidth controlled by tuning ratio.
- High output, narrow band — good for sub.

## Group Delay & Time Domain

Vented systems exhibit higher group delay near $f_b$ (typically 15–25 ms). Sealed boxes < 10 ms. Horn-loaded subs can have substantial group delay (length / c) → needs digital alignment in club PA.

## Drivers Database (BTK / SubSim)

Driver JSON schema (see `database/drivers/*.json`):
```json
{
  "manufacturer": "B&C",
  "model": "18SW115-4",
  "fs_hz": 33,
  "qts": 0.39,
  "qes": 0.42,
  "qms": 5.7,
  "vas_l": 184,
  "sd_cm2": 1210,
  "xmax_mm": 12.5,
  "re_ohm": 3.5,
  "le_mh": 1.8,
  "bl_tm": 26.5,
  "mms_g": 195,
  "power_w_aes": 1700
}
```

## References

- Small, R.H., "Direct-Radiator Loudspeaker System Analysis," IEEE/AES (1972).
- Thiele, A.N., "Loudspeakers in Vented Boxes," AES (1971).
- Dickason, "The Loudspeaker Design Cookbook," 7th ed., Audio Amateur Press.
- Beranek, "Acoustics," ch. 8.
