# Blog figures

Open [the gallery](index.html) to review the assets. All figures are 900 pixels wide with background `#f1f1e6`. Headings and subheadings are provided as text outside the images.

| Figure | Static comparison | Animation |
| --- | --- | --- |
| A letter defined by shapes | [PNG](01-r-definition.png) | [GIF](01-r-definition.gif) |
| Preparing the letters to connect | [PNG](02-ijlt.png) | — |
| The two automatic color choices | [PNG](03-color-variants.png) | — |
| Matching the colors in JAMAICA | [PNG](04-jamaica-colors.png) | [GIF](04-jamaica-colors.gif) |
| Two color exceptions | [PNG](05-w-and-x.png) | — |
| Spacing and joining RELAXED | [PNG](06-relaxed-spacing.png) | — |
| Optical spacing in COOL | [PNG](06b-cool-spacing.png) | — |
| Let the strokes meet: LAZY | [PNG](07-lazy-overlaps.png) | [GIF](07-lazy-overlaps.gif) |
| A hairline between perfectly touching shapes | [PNG](08-hairlines.png) | — |
| Different glyphs. The same text. | [PNG](09-still-text.png) | [GIF](09-still-text.gif) |

## Headings and captions

### A letter defined by shapes

R’s construction from src/geometry.py, with bowl(p_outer, p_inner) expanded into its two paint calls. Each highlighted line previews a path or applies a fill. The outer path is painted gold, then the inner path is painted green.

### Preparing the letters to connect

I, J, L, and T in the Original and Connected fonts at identical flag-core dimensions. Dotted red outlines on the Connected forms mark the original gold silhouettes.

### The two automatic color choices

B in BG and GB: the two forms selected for ordinary letters by automatic color matching. The gold outline stays the same while the incoming and outgoing fields swap colors.

### Matching the colors in JAMAICA

Identical geometry and spacing in both states. Only the color choices change, matching each letter’s incoming field to its neighbor’s outgoing field.

### Two color exceptions

W alternates across five regions and returns to its incoming color. X always keeps the original flag.

### Spacing and joining RELAXED

Before: uniform six-design-pixel gaps with incoming join and overlap forms omitted. After: complete contextual shaping and optical spacing. A shared curved arrow marks all bottom joins across L–A–X–E–D; the upper arrow marks the open XE and ED top corners that preserve readability. The color choices stay fixed.

### Optical spacing in COOL

Before and after the OO pair-spacing adjustment. Only the first O’s advance changes, from 950 to 830 font units: the second O moves 24 design pixels closer. Red dotted lines span the gold-to-gold gap in both rows. Colors, glyph forms, and the other pair adjustments stay fixed.

### Let the strokes meet: LAZY

Actual earlier tapered font versus the finished full-stroke overlaps. Enlargements show the LA, AZ, and ZY intersections.

### A hairline between perfectly touching shapes

Same text, 127 px/em, and 0.125 px horizontal origin before and after fixing the hairline gap. Nearest-neighbor enlargements preserve the individual pixels.

### Different glyphs. The same text.

Illustrated typing, selection, and copy sequence, rendered from actual HarfBuzz-shaped text. The gap between HELLO and JAMAICA is half a flag’s height. This is an illustration rather than a browser recording.

## Regenerate

From the repository root:

```sh
python3 src/generate_blog_assets.py
```

Uses the project’s Python dependencies, DejaVu Sans/Mono system fonts, HarfBuzz, a C compiler, `pkg-config`, and FreeType development headers. The native renderer is compiled in a temporary directory with the requested background color.

## Comparison sources

The snapshots in [assets/reference-fonts/](../../assets/reference-fonts/) preserve the actual earlier tapered connections and the rendering before seam protection. Current font inputs come from [fonts/](../../fonts/). [manifest.json](manifest.json) records input hashes and hairline settings.

R expands the bowl helper into its actual gold and green paint calls. The first two steps preview the defined paths as outlines; the subsequent frames perform each paint operation separately in source order. JAMAICA holds geometry and spacing fixed while changing colors. RELAXED holds colors fixed: the before state uses uniform six-design-pixel gaps with incoming join/overlap forms omitted, while the after state uses the complete shaping result. COOL changes only the OO pair’s advance, keeping colors, glyph forms, and the other pair adjustments fixed. LAZY compares historical and current font files. Hairlines use identical text, size, and fractional origin.

The typing/selection/copy animation is an illustrated sequence rather than a browser recording.

The artwork is based on [u/VelvetOnion’s alphabet](https://www.reddit.com/r/vexillologycirclejerk/s/Bqage66kXN); see the project [credits](../../README.md#credits).
