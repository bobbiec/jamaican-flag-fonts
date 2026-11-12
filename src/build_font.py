#!/usr/bin/env python3
"""Build the geometrically cleaned Jamaican alphabet as a vector color font."""
from collections import Counter
import hashlib
import json
import string

from PIL import Image
from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import parse_path
from geometry import WIDTH, HEIGHT, N_LEFT_GREEN_WIDTH, alphabet, rect, reverse
from font_config import VERSION, NAME_METADATA

from paths import ROOT, FONTS, REFERENCE_IMAGE, GLYPHS, METADATA
SOURCE = REFERENCE_IMAGE
SCALE = 5
LETTER_GAP = N_LEFT_GREEN_WIDTH * SCALE
SIDE_BEARING = LETTER_GAP // 2
LETTER_ADVANCE = WIDTH * SCALE + LETTER_GAP
SPACE_ADVANCE = WIDTH * SCALE // 2
# Integer OpenType metrics round the ideal 712.5-unit baseline distance.
ASCENT, DESCENT = 594, 119


def runs(values):
    result = []
    for value in values:
        if not result or value > result[-1][-1] + 1:
            result.append([value])
        else:
            result[-1].append(value)
    return [(run[0], run[-1] + 1) for run in result]


def measure(image):
    pixels = image.load()
    rows = runs(y for y in range(image.height)
                if sum(min(pixels[x, y]) < 200 for x in range(image.width)) > 100)
    boxes = []
    for top, bottom in rows:
        columns = runs(x for x in range(image.width)
                       if sum(min(pixels[x, y]) < 200 for y in range(top, bottom))
                       > (bottom - top) / 2)
        boxes.extend((left, top, right, bottom) for left, right in columns)
    if len(boxes) != 26:
        raise ValueError('Expected 26 alphabet cells; measured %d' % len(boxes))
    return dict(zip(string.ascii_uppercase, boxes))


def sample_palette(image, boxes):
    seeds = [(0, 0, 0), (0, 155, 57), (255, 209, 0)]
    counts = [Counter() for _ in seeds]
    for box in boxes.values():
        for pixel in image.crop(box).getdata():
            index = min(range(3), key=lambda i: sum((a - b) ** 2 for a, b in zip(pixel, seeds[i])))
            counts[index][pixel] += 1
    return [count.most_common(1)[0][0] for count in counts]


def glyph(paths):
    pen = TTGlyphPen(None)
    converted = TransformPen(Cu2QuPen(pen, max_err=0.5),
                             (SCALE, 0, 0, -SCALE, SIDE_BEARING, HEIGHT * SCALE))
    for path in paths:
        parse_path(path, converted)
    return pen.glyph()


def main():
    image = Image.open(SOURCE).convert('RGB')
    boxes = measure(image)
    palette = sample_palette(image, boxes)
    for directory in [FONTS, GLYPHS / 'jamaican', METADATA]:
        directory.mkdir(parents=True, exist_ok=True)
    outlines = {'.notdef': glyph([rect(0, 0, 80, 90), reverse(rect(8, 8, 64, 74))]),
                'space': TTGlyphPen(None).glyph()}
    advances = {'.notdef': 400 + LETTER_GAP, 'space': SPACE_ADVANCE}
    cmap = {32: 'space', 160: 'space'}
    colr, records = {}, {}
    for letter, design in alphabet().items():
        outlines[letter] = glyph(design['gold'])
        advances[letter] = LETTER_ADVANCE
        layers, svg_layers = [], []
        for index, (color, path) in enumerate(design['layers']):
            name = '%s.layer%d' % (letter, index)
            outlines[name] = glyph([path])
            advances[name] = LETTER_ADVANCE
            layers.append((name, color))
            svg_layers.append('<path fill="#%02x%02x%02x" d="%s"/>' % (*palette[color], path))
        colr[letter] = layers
        cmap[ord(letter)] = cmap[ord(letter.lower())] = letter
        records[letter] = {'box': list(boxes[letter]), 'width': WIDTH, 'height': HEIGHT,
                           'advance': LETTER_ADVANCE, 'layer_count': len(layers)}
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d">%s</svg>\n'
               % (WIDTH, HEIGHT, ''.join(svg_layers)))
        (GLYPHS/'jamaican' / (letter + '.svg')).write_text(svg)
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(list(outlines))
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(outlines)
    builder.setupHorizontalMetrics({name: (advances[name], getattr(outline, 'xMin', 0))
                                    for name, outline in outlines.items()})
    builder.setupHorizontalHeader(ascent=ASCENT, descent=-DESCENT, lineGap=0)
    builder.setupNameTable({**NAME_METADATA, 'familyName': 'Jamaican Alphabet', 'styleName': 'Regular',
                           'uniqueFontIdentifier': 'JamaicanAlphabet-Regular-' + VERSION,
                           'fullName': 'Jamaican Alphabet Regular',
                           'psName': 'JamaicanAlphabet-Regular', 'version': 'Version ' + VERSION,
                           'description': 'Geometric Jamaican alphabet; 2:1 flags with measured letter and word spacing.'})
    builder.setupOS2(version=4, sTypoAscender=ASCENT, sTypoDescender=-DESCENT, sTypoLineGap=0,
                     usWinAscent=ASCENT, usWinDescent=DESCENT, sxHeight=475, sCapHeight=475,
                     fsType=0, fsSelection=0x40 | 0x80)
    builder.setupPost()
    builder.setupMaxp()
    font = builder.font
    font['head'].fontRevision = float(VERSION)
    font['head'].created = font['head'].modified = 3877200000
    font.recalcTimestamp = False
    font['COLR'] = buildCOLR(colr, version=0)
    font['CPAL'] = buildCPAL([[tuple(c / 255 for c in color) + (1.0,) for color in palette]])
    for flavor, extension in [(None, 'ttf'), ('woff', 'woff'), ('woff2', 'woff2')]:
        font.flavor = flavor
        path = FONTS / ('JamaicanAlphabet.' + extension)
        font.save(path)
        print('%s (%s bytes)' % (path.relative_to(ROOT), path.stat().st_size))
    metadata = {'version': VERSION, 'source': str(SOURCE.relative_to(ROOT)), 'sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                'image_size': list(image.size), 'palette': ['#%02X%02X%02X' % c for c in palette],
                'method': 'geometric reconstruction: straight bands, circles, ellipses, square corners, overlapping color fills',
                'aspect_ratio': '2:1', 'units_per_pixel': SCALE, 'units_per_em': 1000,
                'side_bearing': SIDE_BEARING, 'letter_gap': LETTER_GAP,
                'letter_gap_reference': 'N left green strip: 24 design pixels',
                'space_advance': SPACE_ADVANCE, 'line_advance': ASCENT + DESCENT,
                'line_gap_between_flags': ASCENT + DESCENT - HEIGHT * SCALE,
                'quadratic_conversion_error_units': 0.5,
                'glyphs': records}
    (METADATA/'jamaican.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print('Embedded palette:', metadata['palette'])


if __name__ == '__main__':
    main()
