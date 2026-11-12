#!/usr/bin/env python3
"""Build Jamaican Connected font files, SVGs, and metadata."""
import hashlib
import json
import string
from collections import defaultdict
from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.svgLib.path import parse_path
from connected_geometry import STATES, SIDE_COLORS, connected_alphabet
from connected_spacing import spacing_plan, extension_key, STROKE_OVERLAPS
from connected_overlap import protect_gold_caps, leading_background, stroke_continuations
from geometry import rect, reverse, polygon
from font_config import VERSION, NAME_METADATA

from paths import ROOT, SRC, FONTS, GLYPHS, METADATA
PALETTE=[(0,0,0),(0,155,57),(255,209,0)]
OVERLAP=8  # Design pixels (40 font units); a conservative raster overlap.


def paths_glyph(paths):
    if isinstance(paths,str): paths=[paths]
    pen=TTGlyphPen(None)
    converted=TransformPen(Cu2QuPen(pen,max_err=.5),(5,0,0,-5,0,475))
    for path in paths: parse_path(path,converted)
    return pen.glyph()


def default_state(c): return 'BB' if c in 'WX' else 'BG'


def feature_code(pairs,variants):
    letters=string.ascii_uppercase
    lines=['languagesystem DFLT dflt;','languagesystem latn dflt;']
    for c in letters:
        lines.append('@base_%s = [%s];' % (c,' '.join(c+'.'+s for s in STATES)))
        lines.append('@kern_%s = [%s];' % (c,' '.join(n for n,v in variants.items() if v['letter']==c)))
    recolored=letters.replace('X','')
    lines.append('@startBlack = [%s];' % ' '.join(c+'.'+default_state(c) for c in recolored))
    lines.append('@endBlack = [%s];' % ' '.join(c+'.'+state for c in letters
                 for state in (STATES if c=='X' else ['GB','BB'])))
    lines.append('@startGreen = [%s];' % ' '.join(c+('.GG' if c=='W' else '.GB') for c in recolored))
    lines.append('@endGreen = [%s];' % ' '.join(c+'.'+s for c in recolored for s in ['BG','GG']))
    groups=defaultdict(list)
    for pair,spec in pairs.items():
        key=extension_key(spec)
        if key: groups[(pair[0],key)].append(pair[1])
    for (c,key),followers in sorted(groups.items()):
        lines.append('@%s_%s = [%s];' % (c,key,' '.join(c+'.'+s+'.'+key for s in STATES)))
    joining={pair:spec for pair,spec in pairs.items() if spec.get('incoming_join')}
    for pair,spec in joining.items():
        key=extension_key(spec)
        lines.append('@corner_out_%s = [%s];' % (pair,' '.join(n for n,v in variants.items()
                     if v['letter']==pair[0] and v['spacing_alternate']==key)))
        incoming=[n for n,v in variants.items() if v['letter']==pair[1]
                  and not v['incoming_overlap'] and not v['incoming_join']]
        lines.append('@corner_in_%s = [%s];' % (pair,' '.join(incoming)))
        lines.append('@corner_joined_%s = [%s];' % (pair,' '.join(n+'.'+spec['incoming_join'] for n in incoming)))
    for pair,width in STROKE_OVERLAPS.items():
        key=extension_key(pairs[pair])
        lines.append('@out_%s = [%s];' % (pair,' '.join(n for n,v in variants.items()
                     if v['letter']==pair[0] and v['spacing_alternate']==key)))
        incoming=[n for n,v in variants.items() if v['letter']==pair[1]
                  and not v['incoming_overlap'] and not v['incoming_join']]
        lines.append('@in_%s = [%s];' % (pair,' '.join(incoming)))
        lines.append('@joined_%s = [%s];' % (pair,' '.join(n+'.in%d'%round(width*5) for n in incoming)))
    lines += ['feature calt {','  lookup ColorChain {',
              "    sub @endGreen @startBlack' by @startGreen;",'  } ColorChain;',
              '  lookup CornerSpacing {']
    for (c,key),followers in sorted(groups.items()):
        lines.append("    sub @base_%s' [%s] by @%s_%s;" %
                     (c,' '.join('@base_'+n for n in followers),c,key))
    lines += ['  } CornerSpacing;','  lookup StrokeOverlaps {']
    for pair in STROKE_OVERLAPS:
        lines.append("    sub @out_%s @in_%s' by @joined_%s;" % (pair,pair,pair))
    for pair in joining:
        lines.append("    sub @corner_out_%s @corner_in_%s' by @corner_joined_%s;" % (pair,pair,pair))
    lines += ['  } StrokeOverlaps;','} calt;','feature aalt {']
    for c in letters:
        # Fixed indices across every letter, including W's BB default.
        lines.append('  sub %s.%s from [%s];' %
                     (c,default_state(c),' '.join(c+'.'+s for s in STATES)))
    lines += ['} aalt;','feature kern {','  lookup OpticalPairs {']
    for pair,spec in sorted(pairs.items()):
        if spec['units'] and not spec['stroke_overlap']:
            lines.append('  pos @kern_%s @kern_%s %d;' % (*pair,spec['units']))
    lines += ['  } OpticalPairs;','  lookup StrokePairs {']
    for pair in STROKE_OVERLAPS:
        lines.append('  pos @out_%s @joined_%s %d;' % (pair,pair,pairs[pair]['units']))
    lines += ['  } StrokePairs;','} kern;']
    return '\n'.join(lines)+'\n'


def main():
    for directory in [FONTS,GLYPHS/'connected',METADATA/'connected']:
        directory.mkdir(parents=True,exist_ok=True)
    for old in (GLYPHS/'connected').glob('*.pad*.svg'): old.unlink()
    for old in (GLYPHS/'connected').glob('*.in*.svg'): old.unlink()
    for old in (GLYPHS/'connected').glob('*.join*.svg'): old.unlink()
    designs=connected_alphabet()
    metrics,pairs=spacing_plan(designs)
    join_shapes={}
    for spec in pairs.values():
        if spec['stroke_join']:
            paths=tuple(stroke_continuations(spec))
            if paths not in join_shapes: join_shapes[paths]='join%d'%len(join_shapes)
            spec['incoming_join']=join_shapes[paths]
    outlines={'.notdef':paths_glyph([rect(10,10,60,75),reverse(rect(18,18,44,59))]),
              'space':TTGlyphPen(None).glyph()}
    advances={'.notdef':400,'space':475}
    cmap={32:'space',160:'space'}
    colr,variants,shared={},{},{}
    variant_layers,variant_fallbacks,variant_widths={},{},{}

    def add_variant(letter,state,layers,fallback,key=None,width=190,incoming=0,join=None):
        name=letter+'.'+state+('.'+key if key else '')
        if incoming: name+='.in%d'%round(incoming*5)
        if join: name+='.'+join
        outlines[name]=paths_glyph(fallback)
        advances[name]=950
        font_layers,svg=[],[]
        for color,paths in layers:
            paths=[paths] if isinstance(paths,str) else paths
            shape=tuple(paths)
            if shape not in shared:
                layer_name='paint.%d' % len(shared)
                shared[shape]=layer_name
                outlines[layer_name]=paths_glyph(paths)
                advances[layer_name]=950
            font_layers.append((shared[shape],color))
            svg.append('<path fill="#%02x%02x%02x" d="%s"/>' % (*PALETTE[color],' '.join(paths)))
        colr[name]=font_layers
        variants[name]={'letter':letter,'state':state,'left':'B' if letter=='X' else state[0],
                        'right':'B' if letter=='X' else state[1],'fixed_colors':letter=='X',
                        'advance':950,'spacing_alternate':key,'incoming_overlap':incoming,'incoming_join':join}
        variant_layers[name]=layers
        variant_fallbacks[name]=fallback
        variant_widths[name]=width
        bounds=BoundsPen(None)
        for path in fallback: parse_path(path,bounds)
        left=min(0,bounds.bounds[0])
        (GLYPHS/'connected'/(name+'.svg')).write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%g 0 %g 95">%s</svg>\n' % (left,width-left,''.join(svg)))

    for letter,design in designs.items():
        extensions={extension_key(spec):spec for pair,spec in pairs.items()
                    if pair[0]==letter}
        for state,layers in design['variants'].items():
            layers=protect_gold_caps(layers,metrics[letter],OVERLAP)
            add_variant(letter,state,layers,design['gold'])
            for key,spec in sorted(extensions.items()):
                extra=max(0,spec['units'])/5
                # Underlap the outgoing background beneath existing gold.
                first_gold=next(i for i,(color,_) in enumerate(layers) if color==2)
                outgoing=0 if letter=='X' else SIDE_COLORS[state[1]]
                bleed=OVERLAP+spec.get('stroke_overlap',0)
                padded=layers[:first_gold]+[(outgoing,rect(190-OVERLAP,0,extra+OVERLAP+bleed,95))]+layers[first_gold:]
                add_variant(letter,state,padded,design['gold'],key,190+extra+bleed)
        cmap[ord(letter)]=cmap[ord(letter.lower())]=letter+'.'+default_state(letter)
    for pair,width in STROKE_OVERLAPS.items():
        for name,data in list(variants.items()):
            if data['letter']!=pair[1] or data['incoming_overlap']: continue
            add_variant(data['letter'],data['state'],leading_background(variant_layers[name],width),
                        variant_fallbacks[name],data['spacing_alternate'],variant_widths[name],width)
    base_names=[n for n,v in variants.items() if not v['incoming_overlap']]
    for paths,join in join_shapes.items():
        letters={pair[1] for pair,spec in pairs.items() if spec.get('incoming_join')==join}
        for name in base_names:
            data=variants[name]
            if data['letter'] not in letters: continue
            add_variant(data['letter'],data['state'],variant_layers[name]+[(2,list(paths))],
                        variant_fallbacks[name]+list(paths),data['spacing_alternate'],variant_widths[name],join=join)
    builder=FontBuilder(1000,isTTF=True)
    builder.setupGlyphOrder(list(outlines))
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(outlines)
    builder.setupHorizontalMetrics({name:(advances[name],getattr(glyph,'xMin',0)) for name,glyph in outlines.items()})
    builder.setupHorizontalHeader(ascent=594,descent=-119,lineGap=0)
    builder.setupNameTable({**NAME_METADATA,'familyName':'Jamaican Connected','styleName':'Regular',
        'uniqueFontIdentifier':'JamaicanConnected-Regular-'+VERSION,'fullName':'Jamaican Connected Regular',
        'psName':'JamaicanConnected-Regular','version':'Version '+VERSION,
        'description':'Contextual side-color matching, alternating W, dark counters, and optical corner-joining kerning.',
        'manufacturer':'Jamaican Flag Fonts','vendorURL':'https://www.reddit.com/r/vexillologycirclejerk/s/Bqage66kXN'})
    builder.setupOS2(version=4,sTypoAscender=594,sTypoDescender=-119,sTypoLineGap=0,
        usWinAscent=594,usWinDescent=119,sxHeight=475,sCapHeight=475,fsType=0,fsSelection=0x40|0x80)
    builder.setupPost()
    builder.setupMaxp()
    font=builder.font
    font['head'].fontRevision=float(VERSION)
    font['head'].created=font['head'].modified=3877200000
    font.recalcTimestamp=False
    font['COLR']=buildCOLR(colr,version=0)
    font['CPAL']=buildCPAL([[tuple(c/255 for c in color)+(1.,) for color in PALETTE]])
    features=feature_code(pairs,variants)
    addOpenTypeFeaturesFromString(font,features)
    (METADATA/'connected/features.fea').write_text(features)
    for flavor,extension in [(None,'ttf'),('woff','woff'),('woff2','woff2')]:
        font.flavor=flavor
        path=FONTS/('JamaicanConnected.'+extension)
        font.save(path)
        print('%s (%d bytes)' % (path.relative_to(ROOT),path.stat().st_size),flush=True)
    metadata={'family':'Jamaican Connected','version':VERSION,'variant_count':104,
        'spacing_variant_count':len(variants)-104,'total_color_glyphs':len(variants),
        'palette':['#%02X%02X%02X'%c for c in PALETTE],'flag_size_units':[950,475],
        'letter_advance':950,'space_advance':475,'line_advance':713,'states':list(STATES),
        'rendering_overlap_units':OVERLAP*5,'overlap_only_before_letters':True,
        'default_state':'BG','W_default_state':'BB','X_fixed_state':'BB',
        'fixed_color_letters':['X'],'contextual_feature':'calt','spacing_feature':'kern',
        'rule':'Match incoming side; alternate outgoing except W, whose five regions alternate and retain incoming color.',
        'counter_rule':'Black except green for BB variants; W alternates all five regions.',
        'redrawn_letters':['I','J','L','T'],'variants':variants,
        'source_geometry_sha256':hashlib.sha256((SRC/'geometry.py').read_bytes()).hexdigest()}
    (METADATA/'connected/font.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (METADATA/'connected/spacing.json').write_text(json.dumps({'ink_metrics':metrics,'pairs':pairs,
        'policy':'Continue full gold strokes to their natural intersection at one selected corner. Preserve optical spacing and the open opposite corner. VE, LA, AZ, and ZY also overlap their flag cells.'},indent=2)+'\n')


if __name__=='__main__': main()
