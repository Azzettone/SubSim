# Horn Theory

## Webster Equation (1D wave in horn of varying area)

$$\frac{1}{A(x)}\frac{d}{dx}\left(A(x)\frac{dp}{dx}\right) + k^2 p = 0,\quad k=\omega/c$$

Assumes plane wave in the cross-section. Valid when transverse dimensions ≪ λ/4.

Reference: Webster (1919 PNAS), Beranek "Acoustics" §5.13.

## Expansion Profiles

| Profile | A(x) | Cutoff Fc | Notes |
|---|---|---|---|
| Conical | $A_0 (1+x/x_0)^2$ | none (no Fc) | smooth load, large mouth needed |
| Exponential | $A_0 e^{m x}$ | $f_c = m c / (4\pi)$ | classic; impedance ringing |
| Hypex (Salmon) | $A_0(\cosh(m x/2) + T \sinh(m x/2))^2$ | $f_c = m c / (4\pi)$ | T ∈ [0,1]; T=0 catenoidal, T=1 exponential |
| Tractrix | $r(x)$ from $r_m \tanh$ inverse | $f_c \approx c/(2\pi r_m)$ | optimal phase, harder to fold |

`m` is the **flare rate** [1/m]. Relation to Fc:
$$m = \frac{4\pi f_c}{c}$$

## Cutoff Frequency

Below Fc the horn does **not** load — radiation impedance becomes mostly reactive, output collapses ~12 dB/oct. Practical rule:
- **System** Fc target = 0.7–0.8 × **driver Fs** (avoid wasting horn loading on a region where the driver is impedance-limited).

## Mouth Area Criterion

For full loading at Fc, mouth area should be ≈ λc²/(4π) (half-space) or λc²/π (full-space):
$$A_{mouth, min} \approx \frac{c^2}{\pi f_c^2} \quad \text{(2π space)}$$

Sub-mouth horns work but with **mouth reflections** → ripple in response. Acceptable if mouth ≥ ~0.4 × ideal.

## Throat Area

Throat area $A_T$ matched to driver Sd (typically $A_T = 0.3$ to $1.0 \times S_d$ for direct-radiator subs, or much smaller via phase plug for compression drivers).

Throat impedance (real part) at high f:
$$R_T = \rho c / A_T$$

## Length

For a Salmon hypex horn from throat $A_T$ to mouth $A_M$:
$$L = \frac{1}{m}\ln\frac{A_M}{A_T}\quad\text{(exponential)}$$
For hypex with general T, use numerical inversion.

## Folding

Acoustically, fold = mirror of axis around a baffle plate. Each fold introduces:
- Reflection at fold (small if w < λ/4 at Fc)
- Length penalty (acoustic length > physical depth)
- HF cutoff: $f_{fold} \approx c/(8 w_{fold})$ where $w_{fold}$ is the leg width

Z-fold (1 fold): leg pattern +Z then −Z, stacked in Y. Used in 186 Horn, 1850 Folded Horn.
W-fold (2 folds): +Z, −Z, +Z. Used in scoops, MT102.

## Practical Validation Ranges (subwoofer horns)

| Parameter | Typical range |
|---|---|
| Fc | 25–80 Hz |
| Throat Area / Sd | 0.3–1.0 |
| Mouth Area | 0.5–4 m² |
| Length | 0.8–3.5 m |
| Mouth aspect ratio | 1:1 to 2:1 |
| Hypex T | 0.5–0.8 (sweet spot) |
