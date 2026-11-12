"""Shape text through HarfBuzz's C API using ctypes.

fontTools decodes WOFF/WOFF2 to SFNT before shaping."""
import ctypes as C
from ctypes.util import find_library
from io import BytesIO
from fontTools.ttLib import TTFont


class Info(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in ['codepoint', 'mask', 'cluster', 'var1', 'var2']]


class Position(C.Structure):
    _fields_ = [(name, C.c_int32) for name in ['x_advance', 'y_advance', 'x_offset', 'y_offset', 'var']]


class Feature(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in ['tag', 'value', 'start', 'end']]


class Shaper:
    def __init__(self, path):
        library = find_library('harfbuzz')
        if not library:
            raise RuntimeError('HarfBuzz is required for verification: install the system libharfbuzz library.')
        self.hb = C.CDLL(library)
        signatures = {
            'hb_blob_create': (C.c_void_p, [C.c_void_p, C.c_uint, C.c_int, C.c_void_p, C.c_void_p]),
            'hb_face_create': (C.c_void_p, [C.c_void_p, C.c_uint]),
            'hb_font_create': (C.c_void_p, [C.c_void_p]),
            'hb_ot_font_set_funcs': (None, [C.c_void_p]),
            'hb_font_set_scale': (None, [C.c_void_p, C.c_int, C.c_int]),
            'hb_buffer_create': (C.c_void_p, []),
            'hb_buffer_add_utf8': (None, [C.c_void_p, C.c_char_p, C.c_int, C.c_uint, C.c_int]),
            'hb_buffer_guess_segment_properties': (None, [C.c_void_p]),
            'hb_shape': (None, [C.c_void_p, C.c_void_p, C.POINTER(Feature), C.c_uint]),
            'hb_buffer_get_glyph_infos': (C.POINTER(Info), [C.c_void_p, C.POINTER(C.c_uint)]),
            'hb_buffer_get_glyph_positions': (C.POINTER(Position), [C.c_void_p, C.POINTER(C.c_uint)]),
            'hb_version_string': (C.c_char_p, []),
        }
        for kind in ['blob', 'face', 'font', 'buffer']:
            signatures['hb_%s_destroy' % kind] = (None, [C.c_void_p])
        for name, (restype, argtypes) in signatures.items():
            method = getattr(self.hb, name)
            method.restype, method.argtypes = restype, argtypes
        tt = TTFont(path)
        self.order = tt.getGlyphOrder()
        tt.flavor = None
        tt.recalcTimestamp = False
        output = BytesIO()
        tt.save(output)
        tt.close()
        self.data = C.create_string_buffer(output.getvalue())
        self.blob = self.hb.hb_blob_create(self.data, len(output.getvalue()), 1, None, None)
        self.face = self.hb.hb_face_create(self.blob, 0)
        self.font = self.hb.hb_font_create(self.face)
        self.hb.hb_ot_font_set_funcs(self.font)
        self.hb.hb_font_set_scale(self.font, 1000, 1000)
        self.version = self.hb.hb_version_string().decode()

    def shape(self, text, calt=None, alternate=None, kern=None):
        buffer = self.hb.hb_buffer_create()
        try:
            encoded = text.encode('utf-8')
            self.hb.hb_buffer_add_utf8(buffer, encoded, len(encoded), 0, len(encoded))
            self.hb.hb_buffer_guess_segment_properties(buffer)
            features = []
            if calt is not None:
                features.append(Feature(int.from_bytes(b'calt', 'big'), int(calt), 0, 0xffffffff))
            if alternate is not None:
                features.append(Feature(int.from_bytes(b'aalt', 'big'), alternate, 0, 0xffffffff))
            if kern is not None:
                features.append(Feature(int.from_bytes(b'kern', 'big'), int(kern), 0, 0xffffffff))
            array = (Feature * len(features))(*features)
            self.hb.hb_shape(self.font, buffer, array, len(features))
            count = C.c_uint()
            infos = self.hb.hb_buffer_get_glyph_infos(buffer, C.byref(count))
            positions = self.hb.hb_buffer_get_glyph_positions(buffer, C.byref(count))
            return [{'name': self.order[infos[i].codepoint], 'cluster': infos[i].cluster,
                     'advance': positions[i].x_advance, 'x_offset': positions[i].x_offset,
                     'y_offset': positions[i].y_offset} for i in range(count.value)]
        finally:
            self.hb.hb_buffer_destroy(buffer)

    def close(self):
        self.hb.hb_font_destroy(self.font)
        self.hb.hb_face_destroy(self.face)
        self.hb.hb_blob_destroy(self.blob)
