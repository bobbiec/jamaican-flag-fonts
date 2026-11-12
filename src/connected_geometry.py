"""Construct color variants with gold strokes separating the side fields."""
import math
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path
from geometry import alphabet, polygon, rect, positive

STATES = ('BG', 'GB', 'BB', 'GG')
SIDE_COLORS = {'B': 0, 'G': 1}


def right_fields():
    vertical = lambda x: rect(x, 0, 190-x, 95)
    c = 'M190 0 H150 V8 H102 A39.5 39.5 0 0 0 102 87 H150 V95 H190 Z'
    o = 'M190 0 H95 V8 A57 39.5 0 0 0 95 87 V95 H190 Z'
    fields = {
        'A': polygon([(101, 0), (190, 0), (190, 95), (6, 95)]),
        'B': vertical(40), 'C': c, 'D': vertical(40),
        'E': vertical(40), 'F': vertical(40), 'G': c,
        'H': vertical(40), 'I': vertical(95),
        'J': 'M190 0 H126 V49 A41 41 0 0 1 85 90 V95 H190 Z',
        'K': vertical(48), 'L': vertical(48), 'M': vertical(24),
        'N': vertical(32), 'O': o, 'P': vertical(40), 'Q': o,
        'R': vertical(40),
        'S': 'M190 0 H150 V8 H80 A19.5 19.5 0 0 0 80 47 H111 '
             'A20 20 0 0 1 111 87 H40 V95 H190 Z',
        'T': vertical(95),
        'U': ('M190 0 H35 V40 A60 60 0 0 0 %g 95 H190 Z'
              % (95-math.sqrt(60**2-55**2))),
        'V': polygon([(0, 0), (190, 0), (190, 95), (95, 95)]),
        'W': polygon([(0, 0), (190, 0), (190, 95), (48, 95)]),
        'X': polygon([(0, 0), (190, 0), (190, 95)]),
        'Y': polygon([(0, 0), (190, 0), (190, 95), (95, 95), (95, 47.5)]),
        'Z': 'M190 0 H182 V8 L8 87 V95 H190 Z',
    }
    return {letter: positive(path) for letter, path in fields.items()}


def bounded_interiors(layers):
    """Retain enclosed source details, with a little underlap beneath the gold."""
    result = []
    for color, path in layers[1:]:
        if color == 2:
            continue
        bounds = BoundsPen(None)
        parse_path(path, bounds)
        x0, y0, x1, y1 = bounds.bounds
        if x0 <= 0 or x1 >= 190:
            continue
        sx = (x1-x0+2)/(x1-x0)
        sy = (y1-y0+2)/(y1-y0) if y0 > 0 and y1 < 95 else 1
        cx, cy = (x0+x1)/2, (y0+y1)/2
        pen = SVGPathPen(None)
        parse_path(path, TransformPen(pen, (sx, 0, 0, sy, cx*(1-sx), cy*(1-sy))))
        result.append((color, positive(pen.getCommands())))
    return result


def connected_alphabet():
    source = alphabet()
    fields = right_fields()
    result = {}
    for letter, design in source.items():
        gold = list(design['gold'])
        interiors = bounded_interiors(design['layers'])
        # Preserve enclosed regions independently of the side colors.
        enclosed = {
            'H': [(0, rect(48, 56, 94, 39))],
            'M': [(0, polygon([(32, 0), (158, 0), (95, 59)]))],
            'V': [(1, polygon([(12, 0), (178, 0), (95, 83)]))],
            'X': [(1, polygon([(18, 0), (172, 0), (95, 38.5)])),
                  (1, polygon([(18, 95), (172, 95), (95, 56.5)]))],
            'Y': [(1, polygon([(18, 0), (172, 0), (95, 38.5)]))],
        }
        interiors += bounded_interiors([(0, rect(0, 0, 190, 95))] + enclosed.get(letter, []))
        if letter in 'CG':
            # A single open band gives C/G a clean right edge.
            gold = [positive('M190 0 H102 A47.5 47.5 0 0 0 102 95 H190 V79 '
                             'H102 A31.5 31.5 0 0 1 102 16 H190 Z')]
            if letter == 'G':
                gold += [rect(118,39.5,48,16),rect(150,47.5,16,39.5)]
        elif letter == 'T':
            gold = [rect(0, 0, 190, 16), rect(87, 8, 16, 87)]
            interiors = []
        elif letter == 'L':
            gold = [rect(40, 0, 16, 95), rect(48, 79, 142, 16)]
            interiors = []
        elif letter == 'J':
            intersection = math.sqrt(49**2-46**2)
            gold = [('M36 41 H52 V49 A33 33 0 0 0 118 49 V16 H48 V0 H190 V16 H134 V49 '
                     'A49 49 0 0 1 %g 95 H%g A49 49 0 0 1 36 49 Z')
                    % (85+intersection, 85-intersection)]
            interiors = []
        elif letter == 'I':
            # Match H’s width with full-height crossbars.
            gold = [rect(32, 0, 126, 16), rect(87, 8, 16, 79), rect(32, 79, 126, 16)]
            interiors = []
        elif letter == 'N':
            # One underlapping field supplies both N counters.
            interiors = [(0, rect(32, 0, 126, 95))]
        result[letter] = {'gold': gold, 'variants': {}}
        for state in STATES:
            left, right = [SIDE_COLORS[c] for c in state]
            layers = [(left, rect(0, 0, 190, 95)), (right, fields[letter])]
            counter_color = 1 if state == 'BB' else 0
            layers.extend((counter_color, path) for _, path in interiors)
            if letter == 'W':
                # Four strokes divide five regions, so full alternation
                # returns to the incoming color: BB or GG.
                layers = [(left, rect(0, 0, 190, 95)), (right, fields[letter])]
                for color, points in [
                    (1-left, [(0, 0), (95, 0), (48, 95)]),
                    (left, [(48, 95), (95, 0), (143, 95)]),
                    (1-left, [(95, 0), (190, 0), (143, 95)]),
                ]:
                    layers.append((color, polygon(points)))
            layers.append((2, gold))
            if letter == 'X':
                # All X aliases retain the original Jamaican flag.
                layers = list(design['layers'])
            result[letter]['variants'][state] = layers
    return result
