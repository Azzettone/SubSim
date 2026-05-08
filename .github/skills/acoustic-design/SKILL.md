---
name: acoustic-design
description: 'Acoustic design fundamentals for loudspeakers, horns, subwoofers and enclosures. Use when: implementing or reviewing acoustic formulas (Webster equation, Thiele-Small parameters, horn cutoff Fc, mouth area, throat area, expansion profiles hypex/exponential/conical/tractrix, Helmholtz resonator, sealed/ported/bandpass alignments, port tuning, room boundary gain, SPL calculations, group delay, phase plug). References Beranek "Acoustics", Olson, Dickason, Leach, Salmon. Use for reviewing physical correctness of horn_block, enclosure_model, subwoofer_model, acoustic_engine code.'
---

# Acoustic Design Fundamentals

Domain knowledge for SubSim (subwoofer simulation) and BTK Speaker Designer (horn / cabinet design).

## When to Use

- Implementing acoustic formulas in `core/`, `blocks/`, `formulas/`
- Reviewing physical correctness of horn / cabinet / subwoofer models
- Choosing default values, validation ranges, sanity checks
- Explaining acoustic phenomena to the user (always in Italian, with physics behind the formula)

## Reference Library

- Beranek, **"Acoustics"** (1954, ASA reprint 1996) — the canonical reference. Chapters: 5 (transmission lines), 7 (horns), 9 (loudspeakers).
- Olson, **"Acoustical Engineering"** (1957) — chapter 5 on horns, dynamic loudspeakers.
- Dickason, **"The Loudspeaker Design Cookbook"** (7th ed.) — practical T-S, alignments.
- Leach, **"Introduction to Electroacoustics & Audio Amplifier Design"** — closed/vented box theory.
- Salmon (1946 JASA) — hypex / hyperbolic-exponential horn family.
- Keele (1973 AES) — finite-mouth horn directivity.

## Core Topics

Load the topic file you need:

| Topic | File |
|---|---|
| Horn theory (Webster, expansions, Fc, mouth) | [./references/horns.md](./references/horns.md) |
| Thiele-Small + alignments (closed/vented/BP) | [./references/thiele-small.md](./references/thiele-small.md) |
| Helmholtz resonator + port tuning | [./references/helmholtz.md](./references/helmholtz.md) |
| Boundary loading (4π / 2π / π / π/2 space) | [./references/boundary-loading.md](./references/boundary-loading.md) |
| Validation ranges / sanity checks | [./references/validation.md](./references/validation.md) |

## Procedure for Acoustic Code Changes

1. Identify the **physical phenomenon** (don't just match a formula).
2. Locate the canonical reference (Beranek section, AES paper).
3. Verify **range of validity** (frequency band, geometric assumptions).
4. Implement with clear units in docstring (SI: Hz, m, m², kg/m³, Pa·s/m, dB).
5. Add a unit test that compares against a known textbook value.
6. Comment the formula with reference: `# Beranek Eq. 5.32, p. 152`.
7. Validate edge cases (Fc → 0, mouth → ∞, T-S Qts ≪ 0.2).

## Output Style

- Always Italian for explanations.
- Always state the **physical "why"** before the "how".
- Always include the bibliographic reference next to the formula.
- Always provide realistic numeric example (e.g., 18" sub: Fs=35 Hz, Vas=180 L, Qts=0.32).
