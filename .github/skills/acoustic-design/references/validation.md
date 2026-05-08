# Validation Ranges & Sanity Checks

Always validate user / computed values against these ranges. Reject or warn outside.

## Driver T-S

| Parameter | Reasonable range | Hard limit |
|---|---|---|
| $f_s$ | 18–80 Hz (subs); 30–200 Hz (LF mids) | 10–500 Hz |
| $Q_{ts}$ | 0.25–0.55 | 0.10–1.5 |
| $V_{as}$ | 50–500 L (18"); 5–50 L (10") | > 0 |
| $S_d$ | 800–1300 cm² (18"); 350–550 cm² (12") | > 0 |
| $X_{max}$ | 6–25 mm | 1–50 mm |
| $BL$ | 15–35 T·m (pro 18") | > 0 |
| $R_e$ | 2.5–7 Ω | 0.5–32 Ω |

## Horn Geometry

| Parameter | Reasonable range | Hard limit |
|---|---|---|
| Fc | 30–120 Hz (sub); 200 Hz–1 kHz (mid) | > 10 Hz |
| Throat area | 0.3–1.0 × $S_d$ | > 0 |
| Mouth area | $\ge 0.4 \cdot c^2/(\pi f_c^2)$ | > throat |
| Length | 0.6–4 m (sub); 0.2–1 m (mid) | > 0.05 m |
| Mouth aspect | 0.5–2.5 | > 0 |
| Hypex T | 0–1 | clamp |
| Fold count | 0–2 | 0,1,2 only |

## Sealed/Vented Box

| Parameter | Reasonable range |
|---|---|
| $V_b/V_{as}$ sealed | 0.3–2.0 |
| $V_b/V_{as}$ vented | 0.5–2.5 |
| $f_b/f_s$ vented | 0.7–1.3 |
| $Q_{tc}$ sealed | 0.5–1.0 |
| Port air velocity | < 17 m/s (HiFi), < 25 m/s (PA) |

## Common Bugs to Catch

1. **Unit mismatch**: $V_{as}$ in liters vs m³ (ratio 1000). $S_d$ in cm² vs m² (ratio 10000).
2. **Sign of x in horn**: throat at x=0 (area = $A_T$), mouth at x=L (area = $A_M$). Some textbooks reverse.
3. **End correction** missing in port length → tuning off by 5–15 Hz.
4. **Frequency in rad/s vs Hz**: $\omega = 2\pi f$. Always store and pass as Hz; convert at use site.
5. **dB reference**: SPL @ 1m, 1W (2.83V@8Ω). For pro drivers usually 4Ω or 8Ω.

## Sanity Check Helper

```python
def validate_horn_params(throat_a, mouth_a, length, fc):
    issues = []
    if mouth_a <= throat_a:
        issues.append("mouth_area must be > throat_area")
    if fc <= 10:
        issues.append(f"Fc={fc} Hz is below realistic range")
    ideal_mouth = (343.0**2) / (np.pi * fc**2)
    if mouth_a < 0.4 * ideal_mouth:
        issues.append(
            f"mouth_area {mouth_a:.2f} m² is < 40% of ideal "
            f"{ideal_mouth:.2f} m² → strong mouth reflections expected"
        )
    return issues
```
