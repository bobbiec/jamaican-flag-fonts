"""Geometric Jamaican alphabet on a 190 × 95 design grid."""
import math
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.svgLib.path import parse_path

WIDTH, HEIGHT = 190, 95
N_LEFT_GREEN_WIDTH = 24


def polygon(points):
    return 'M' + ' L'.join('%g %g' % p for p in points) + ' Z'


def rect(x, y, width, height):
    return polygon([(x, y), (x + width, y), (x + width, y + height), (x, y + height)])


def ellipse(cx, cy, rx, ry):
    return ('M%g %g A%g %g 0 1 1 %g %g A%g %g 0 1 1 %g %g Z'
            % (cx + rx, cy, rx, ry, cx - rx, cy, rx, ry, cx + rx, cy))


def reverse(path):
    pen = SVGPathPen(None)
    parse_path(path, ReverseContourPen(pen))
    return pen.getCommands()


def positive(path):
    pen = AreaPen(None)
    parse_path(path, pen)
    return reverse(path) if pen.value < 0 else path


def clip(points):
    for axis, edge, sign in [(0, 0, 1), (0, WIDTH, -1), (1, 0, 1), (1, HEIGHT, -1)]:
        output = []
        for a, b in zip(points, points[1:] + points[:1]):
            a_in = (a[axis] - edge) * sign >= 0
            b_in = (b[axis] - edge) * sign >= 0
            if a_in:
                output.append(a)
            if a_in != b_in:
                t = (edge - a[axis]) / (b[axis] - a[axis])
                output.append(tuple(a[i] + t * (b[i] - a[i]) for i in [0, 1]))
        points = output
    return points


def stroke(points, width=16):
    """Expand a polyline with miter joins and clip to the exact flag rectangle."""
    normals = []
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        normals.append((-dy / length, dx / length))
    sides = []
    for sign in [1, -1]:
        side = []
        for i, (x, y) in enumerate(points):
            if i in [0, len(points) - 1]:
                nx, ny = normals[0 if i == 0 else -1]
                factor = sign * width / 2
            else:
                a, b = normals[i - 1], normals[i]
                nx, ny = a[0] + b[0], a[1] + b[1]
                factor = sign * width / (nx * nx + ny * ny)
            side.append((x + nx * factor, y + ny * factor))
        sides.append(side)
    return polygon(clip(sides[0] + list(reversed(sides[1]))))


def alphabet():
    result = {}
    layers, gold = [], []

    def start(letter, background=0):
        nonlocal layers, gold
        layers, gold = [], []
        result[letter] = {'layers': layers, 'gold': gold}
        paint(background, rect(0, 0, WIDTH, HEIGHT))

    def paint(color, path, cut_gold=False):
        path = positive(path)
        layers.append((color, path))
        if color == 2:
            gold.append(path)
        elif cut_gold:
            gold.append(reverse(path))

    def box(color, x, y, width, height):
        paint(color, rect(x, y, width, height))

    def bowl(outer, inner):
        paint(2, outer)
        paint(1, inner, cut_gold=True)

    start('A', 1)
    paint(2, polygon([(0, 83), (83, 0), (107, 0), (190, 83), (190, 95), (0, 95)]))
    paint(0, polygon([(51, 55), (95, 11), (139, 55)]), cut_gold=True)
    paint(1, polygon([(36, 71), (154, 71), (178, 95), (12, 95)]), cut_gold=True)

    start('B')
    paint(2, 'M0 0 H118 A28 28 0 0 1 141 44 C149 48 154 57 154 67.5 '
          'C154 82.69 141.46 95 126 95 H0 V79 H32 V16 H0 Z')
    paint(1, 'M48 16 H118 A12 12 0 0 1 118 40 H48 Z', cut_gold=True)
    paint(1, 'M48 56 H126 A12 11.5 0 0 1 126 79 H48 Z', cut_gold=True)

    c_outer = 'M190 0 H102 A47.5 47.5 0 0 0 102 95 H190 Z'
    c_inner = 'M190 16 H102 A31.5 31.5 0 0 0 102 79 H190 Z'
    start('C')
    bowl(c_outer, c_inner)

    start('D')
    bowl('M0 0 H110 A47.5 47.5 0 0 1 110 95 H0 V79 H32 V16 H0 Z',
         'M48 16 H110 A31.5 31.5 0 0 1 110 79 H48 Z')

    start('E')
    box(1, 40, 8, 150, 40)
    for bounds in [(0, 0, 190, 16), (32, 8, 16, 79), (40, 40, 150, 16), (0, 79, 190, 16)]:
        box(2, *bounds)

    start('F')
    box(1, 40, 48, 150, 47)
    for bounds in [(0, 0, 190, 16), (32, 8, 16, 87), (40, 40, 150, 16)]:
        box(2, *bounds)

    start('G')
    bowl(c_outer, c_inner)
    box(2, 118, 39.5, 48, 16)
    box(2, 150, 47.5, 16, 39.5)

    start('H')
    box(1, 40, 0, 110, 48)
    for bounds in [(32, 0, 16, 95), (142, 0, 16, 95), (40, 40, 110, 16)]:
        box(2, *bounds)

    start('I')
    box(1, 0, 0, 95, 95)
    for bounds in [(87, 0, 16, 95), (55, 16, 80, 16), (55, 63, 80, 16)]:
        box(2, *bounds)

    start('J')
    paint(1, 'M126 24 H190 V95 H85 C107.64 95 126 72.64 126 50 Z')
    # Calculate the circular bowl’s intersection with the flag edge.
    intersection = math.sqrt(49 ** 2 - 46 ** 2)
    paint(2, ('M36 41 H52 V49 A33 33 0 0 0 118 49 V32 H48 V16 H190 V32 H134 V49 '
              'A49 49 0 0 1 %g 95 H%g A49 49 0 0 1 36 49 Z')
          % (85 + intersection, 85 - intersection))

    start('K')
    paint(1, polygon([(48, 0), (166, 0), (48, 48)]))
    paint(1, polygon([(48, 48), (166, 95), (48, 95)]))
    box(2, 40, 0, 16, 95)
    paint(2, polygon([(48, 40), (146, 0), (188, 0), (74, 48), (188, 95), (146, 95), (48, 56)]))

    start('L')
    box(1, 48, 0, 142, 71)
    box(2, 40, 0, 16, 79)
    box(2, 48, 63, 142, 16)

    start('M')
    paint(1, polygon([(24, 8), (95, 70), (166, 8), (166, 95), (24, 95)]))
    box(2, 16, 0, 16, 95)
    box(2, 158, 0, 16, 95)
    paint(2, polygon([(16, 0), (32, 0), (95, 59), (158, 0), (174, 0),
                      (174, 16), (95, 81), (16, 16)]))

    start('N')
    box(1, 0, 0, 32, 95)
    paint(1, polygon([(32, 0), (158, 0), (158, 88)]))
    box(2, N_LEFT_GREEN_WIDTH, 0, 16, 95)
    box(2, 150, 0, 16, 95)
    paint(2, polygon([(24, 0), (48, 0), (166, 95), (142, 95)]))

    outer, inner = ellipse(95, 47.5, 65, 47.5), ellipse(95, 47.5, 49, 31.5)
    start('O')
    bowl(outer, inner)

    p_outer = 'M0 0 H118 A32 32 0 0 1 118 64 H48 V95 H32 V16 H0 Z'
    p_inner = 'M48 16 H118 A16 16 0 0 1 118 48 H48 Z'
    start('P')
    bowl(p_outer, p_inner)

    start('Q')
    paint(1, polygon([(95, 47.5), (175, 95), (95, 95)]))
    bowl(outer, inner)
    paint(2, polygon([(118, 50), (190, 95), (160, 95), (110, 64)]))

    start('R')
    paint(1, polygon([(40, 56), (110, 56), (165, 95), (40, 95)]))
    bowl(p_outer, p_inner)
    paint(2, polygon([(110, 56), (180, 95), (150, 95), (95, 64)]))

    start('S')
    paint(1, 'M190 8 H80 A19.5 19.5 0 0 0 80 47 H111 '
          'A20 20 0 0 1 111 87 V95 H190 Z')
    paint(2, 'M190 0 H80 A27.5 27.5 0 0 0 80 55 H111 A12 12 0 0 1 111 79 '
          'H0 V95 H111 A28 28 0 0 0 111 39 H80 A11.5 11.5 0 0 1 80 16 H190 Z')

    start('T')
    box(1, 0, 0, 190, 28)
    box(2, 0, 20, 190, 16)
    box(2, 87, 28, 16, 67)

    start('U')
    intersection = math.sqrt(68 ** 2 - 55 ** 2)
    bowl(('M27 0 H163 V40 A68 68 0 0 1 %g 95 H%g A68 68 0 0 1 27 40 Z'
          % (95 + intersection, 95 - intersection)),
         'M43 0 H147 V40 A52 52 0 0 1 43 40 Z')

    start('V')
    paint(1, polygon([(0, 0), (190, 0), (95, 95)]))
    paint(2, stroke([(0, 0), (95, 95), (190, 0)]))

    start('W')
    for points in [[(0, 0), (48, 95), (0, 95)], [(48, 95), (95, 0), (143, 95)],
                   [(143, 95), (190, 0), (190, 95)]]:
        paint(1, polygon(points))
    paint(2, stroke([(0, 0), (48, 95), (95, 0), (143, 95), (190, 0)]))

    start('X')
    paint(1, polygon([(0, 0), (190, 0), (95, 47.5)]))
    paint(1, polygon([(0, 95), (190, 95), (95, 47.5)]))
    paint(2, stroke([(0, 0), (190, 95)]))
    paint(2, stroke([(0, 95), (190, 0)]))

    start('Y')
    paint(1, polygon([(0, 0), (190, 0), (95, 47.5)]))
    paint(2, stroke([(0, 0), (95, 47.5), (190, 0)]))
    box(2, 87, 47.5, 16, 47.5)

    start('Z')
    paint(1, polygon([(0, 8), (182, 8), (0, 87)]))
    box(2, 0, 0, 190, 16)
    box(2, 0, 79, 190, 16)
    paint(2, stroke([(182, 8), (8, 87)]))
    return result
