#!/usr/bin/env python3
"""Check saved color fonts, spacing metrics, and geometric source fidelity."""
import json
import string
from PIL import Image, ImageDraw
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

from paths import ROOT, FONTS, METADATA, PREVIEWS
SUPERSAMPLE = 4


class RasterPen(BasePen):
    def __init__(self, glyphset, scale, height, supersample):
        super().__init__(glyphset)
        self.polygons = []
        self.points = []
        self.scale, self.height, self.ss = scale, height, supersample

    def point(self, p):
        self.points.append(((p[0] - 60) / self.scale * self.ss,
                            (self.height - p[1] / self.scale) * self.ss))

    def _moveTo(self, p):
        self.points = []
        self.point(p)

    def _lineTo(self, p):
        self.point(p)

    def _qCurveToOne(self, control, end):
        start = self._getCurrentPoint()
        for step in range(1, 25):
            t = step / 24
            self.point(tuple((1-t)**2*start[i] + 2*(1-t)*t*control[i] + t*t*end[i] for i in [0, 1]))

    def _closePath(self):
        self.polygons.append(self.points)

    def _endPath(self):
        self._closePath()


def render(font, letter, palette, supersample=SUPERSAMPLE):
    width, height, scale = 190, 95, 5
    result = Image.new('RGB', (width * supersample, height * supersample), 'white')
    glyphset = font.getGlyphSet()
    for layer in font['COLR'].ColorLayers[letter]:
        pen = RasterPen(glyphset, scale, height, supersample)
        glyphset[layer.name].draw(pen)
        draw = ImageDraw.Draw(result)
        for points in pen.polygons:
            draw.polygon(points, fill=palette[layer.colorID])
    return result.resize((width, height), Image.LANCZOS)


def nearest(pixel, palette):
    return min(range(len(palette)), key=lambda i: sum((a - b) ** 2 for a, b in zip(pixel, palette[i])))


def main():
    metadata = json.loads((METADATA/'jamaican.json').read_text())
    palette = [tuple(bytes.fromhex(c[1:])) for c in metadata['palette']]
    source = Image.open(ROOT / metadata['source']).convert('RGB')
    reconstructed = Image.new('RGB', source.size, 'white')
    scores, tiles, seam_counts = {}, {}, {}
    for extension in ['ttf', 'woff', 'woff2']:
        font = TTFont(FONTS / ('JamaicanAlphabet.' + extension))
        assert font['COLR'].version == 0
        assert len(font['COLR'].ColorLayers) == 26
        assert len(font['CPAL'].palettes) == 1
        for entry, expected in zip(font['CPAL'].palettes[0], palette):
            assert (entry.red, entry.green, entry.blue, entry.alpha) == (*expected, 255)
        cmap = font.getBestCmap()
        assert font['hmtx']['space'] == (475, 0)
        assert cmap[160] == cmap[32] == 'space'
        assert metadata['letter_gap'] == 120 == 24 * metadata['units_per_pixel']
        assert font['hhea'].ascent - font['hhea'].descent + font['hhea'].lineGap == 713
        os2 = font['OS/2']
        assert os2.fsSelection & 0x80
        assert os2.sTypoAscender - os2.sTypoDescender + os2.sTypoLineGap == 713
        assert os2.usWinAscent + os2.usWinDescent == 713
        assert abs((713 - 475) - 475 / 2) <= .5
        for name in font.getGlyphOrder():
            outline = font['glyf'][name]
            assert font['hmtx'][name][1] == getattr(outline, 'xMin', 0), name
        for letter in string.ascii_uppercase:
            assert cmap[ord(letter)] == cmap[ord(letter.lower())] == letter
            record = metadata['glyphs'][letter]
            assert record['width'] == 2 * record['height'] == 190
            assert font['hmtx'][letter][0] == record['advance'] == 1070
            layers = font['COLR'].ColorLayers[letter]
            base = font['glyf'][layers[0].name]
            assert (base.xMin, base.yMin, base.xMax, base.yMax) == (60, 0, 1010, 475)
            assert all(font['hmtx'][layer.name][0] == 1070 for layer in layers)
            assert font['hmtx'][letter][0] + base.xMin - base.xMax == 120
            if letter in 'BCDGJOPQRSU':
                assert any(not flag & 1 for layer in layers for flag in font['glyf'][layer.name].flags), letter
            rendered = render(font, letter, palette)
            reference = source.crop(record['box']).resize((190, 95), Image.BICUBIC)
            expected = [[nearest(reference.getpixel((x, y)), palette) for x in range(190)] for y in range(95)]
            actual = [[nearest(rendered.getpixel((x, y)), palette) for x in range(190)] for y in range(95)]
            matches, total, seam_pixels = 0, 0, 0
            for y in range(1, 94):
                for x in range(1, 189):
                    if all(expected[yy][xx] == expected[y][x]
                           for yy in range(y - 1, y + 2) for xx in range(x - 1, x + 2)):
                        total += 1
                        matches += actual[y][x] == expected[y][x]
                    # Check color continuity along source green/gold boundaries.
                    if actual[y][x] == 0 and 4 <= x < 186 and 4 <= y < 91:
                        neighborhood = {expected[yy][xx] for yy in range(y-4, y+5) for xx in range(x-4, x+5)}
                        if neighborhood == {1, 2}:
                            seam_pixels += 1
            score = matches / total
            assert score >= .97, '%s %s geometric agreement only %.3f' % (extension, letter, score)
            assert seam_pixels == 0, '%s introduced black along green/gold boundaries' % letter
            if letter in 'EFG':
                assert all(actual[0][x] == 2 for x in range(110 if letter == 'G' else 0, 190))
            if letter in 'EG':
                assert all(actual[94][x] == 2 for x in range(110 if letter == 'G' else 0, 190))
            if extension == 'ttf':
                scores[letter] = round(score, 6)
                seam_counts[letter] = seam_pixels
                tiles[letter] = rendered
                left, top, right, bottom = record['box']
                reconstructed.paste(rendered.resize((right-left, bottom-top), Image.LANCZOS), (left, top))
        assert not font['glyf']['space'].numberOfContours
        font.close()
        print('Verified %s: colors, curves, 2:1 flags, 120-unit letter gap, 475-unit space, 713-unit line advance' % extension, flush=True)
    previews = PREVIEWS
    previews.mkdir(parents=True, exist_ok=True)
    reconstructed.save(previews / 'jamaican-alphabet.png')
    comparison = Image.new('RGB', (source.width * 2, source.height + 40), 'white')
    draw = ImageDraw.Draw(comparison)
    draw.text((26, 14), 'SOURCE IMAGE', fill='black')
    draw.text((source.width + 26, 14), 'GEOMETRIC FONT', fill='black')
    comparison.paste(source, (0, 40))
    comparison.paste(reconstructed, (source.width, 40))
    comparison.save(previews / 'source-comparison.png')
    tiled = Image.new('RGB', (190 * 7, 95 * 4), '#eee8dc')
    for i, letter in enumerate(string.ascii_uppercase):
        tiled.paste(tiles[letter], (i % 7 * 190, i // 7 * 95))
    tiled.save(previews / 'tiled-alphabet.png')
    spaced = Image.new('RGB', (7 * 214 + 24, 4 * 143 + 24), 'white')
    for i, letter in enumerate(string.ascii_uppercase):
        spaced.paste(tiles[letter], (24 + i % 7 * 214, 24 + i // 7 * 143))
    spaced.save(previews / 'spaced-alphabet.png')
    large_font = TTFont(FONTS/'JamaicanAlphabet.ttf')
    detail = Image.new('RGB', (760 * 2, 380 * 2), 'white')
    for i, letter in enumerate('GQRS'):
        canvas = Image.new('RGB', (1520, 760), 'white')
        gs = large_font.getGlyphSet()
        for layer in large_font['COLR'].ColorLayers[letter]:
            pen = RasterPen(gs, 5, 95, 8)
            gs[layer.name].draw(pen)
            draw = ImageDraw.Draw(canvas)
            for points in pen.polygons:
                draw.polygon(points, fill=palette[layer.colorID])
        detail.paste(canvas.resize((760, 380), Image.LANCZOS), (i % 2 * 760, i // 2 * 380))
    detail.save(previews / 'curve-details.png')
    report = {'interior_color_agreement': scores, 'minimum_agreement': min(scores.values()),
              'black_seam_pixels': seam_counts, 'advance_units': 1070, 'space_advance_units': 475,
              'letter_gap_units': 120, 'line_advance_units': 713, 'line_gap_between_flags_units': 238,
              'tile_bounds_units': [60, 0, 1010, 475],
              'method': 'Render saved TrueType contours; verify geometry, N-strip letter spacing, half-width spaces, and approximately half-height interline gaps.',
              'formats_verified': ['ttf', 'woff', 'woff2']}
    (METADATA/'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Minimum geometric interior agreement: %.2f%%' % (100 * min(scores.values())))


if __name__ == '__main__':
    main()
