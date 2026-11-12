# Design and verification

Design notes and generated references for [Jamaican Flag Fonts](../README.md).

## Measurements and geometry

The [reference image](../assets/alphabet-reference.webp) is the **1080 × 723** WebP in `assets/`. The build measures its flag cells and samples the three dominant colors. [src/geometry.py](../src/geometry.py) reconstructs the shapes on a **190 × 95** grid using straight bands, circles, and ellipses. The **2:1** proportions follow the [Jamaican flag’s official dimensions](https://jis.gov.jm/information/symbols/jamaica-national-flag/).

Most gold bands are **16 design pixels** thick. J/U use analytically cropped circular bowls. Cubic paths become smooth quadratic TrueType curves with a conversion error below **0.5 font units**, followed by integer coordinate rounding.

Both fonts use **1,000 units per em**, **5 units per design pixel**, and **950 × 475-unit** flag cores. The **475-unit space** is half a flag wide. The **713-unit baseline distance** leaves approximately half a flag’s height between rows. Source measurements are in [metadata/jamaican.json](../generated/metadata/jamaican.json).

## Shaping rules and visual proofs

Connected’s generated [feature source](../generated/metadata/connected/features.fea), [color and glyph metadata](../generated/metadata/connected/font.json), and [pair measurements](../generated/metadata/connected/spacing.json) document the shaping rules. Per-letter SVGs are in [glyphs/](../generated/glyphs/). Native proofs show [color variants](../generated/previews/connected/native-variant-proof.png), [corner overlaps](../generated/previews/connected/corner-overlaps.png), [VE and LAZY](../generated/previews/connected/pair-refinements.png), [kerning](../generated/previews/connected/native-kerning-proof.png), and [fractional-pixel joins](../generated/previews/connected/fractional-seams.png).

## Verification

The checks reload all three exported formats and verify palettes, Unicode mappings, metrics, geometry, and source fidelity. Connected passes **814 shaping cases per format**, including all **676 letter pairs**, repeated letters, mixed case, long runs, manual alternates, feature toggles, kerning, and color rules. Checks also cover counters, W’s regions, X’s flag, N’s diagonal, full-stroke preservation, and safe spacing.

Native rendering checks use a C compiler, `pkg-config`, and FreeType development headers:

```sh
python3 src/verify_connected_native.py
python3 src/verify_connected_seams.py
```

The join-rendering suite checks **5,655 background interfaces** and **16,965 background samples**, plus **7,400 gold-join samples** and **180 stroke-intersection samples**. It uses nine sizes from 40 to 200 pixels per em and five pixel offsets; all 676 pairs are included at sizes 52, 92, and 127. Results are in [metadata/verification.json](../generated/metadata/verification.json) and [metadata/connected/verification.json](../generated/metadata/connected/verification.json).
