#!/usr/bin/env python3
"""Verify contextual shaping and saved color variants with HarfBuzz."""
import hashlib
import json
import random
import string
import math
from PIL import Image, ImageDraw, ImageChops
from fontTools.ttLib import TTFont
from verify_font import RasterPen, nearest
from verify_font import render as render_original
from hb_shaping import Shaper
from connected_spacing import extension_key,STROKE_OVERLAPS

from paths import ROOT, FONTS, METADATA, PREVIEWS
LETTERS = string.ascii_uppercase
PALETTE = [(0, 0, 0), (0, 155, 57), (255, 209, 0)]
SPACING = json.loads((METADATA/'connected/spacing.json').read_text())
PAIRS = SPACING['pairs']


class ConnectedPen(RasterPen):
    def point(self, point):
        self.points.append((point[0]/self.scale*self.ss+getattr(self,'x_offset',0),
                            (self.height-point[1]/self.scale)*self.ss))


def area(points):
    return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))/2


def edge_error(pixel, expected):
    # Measure against the permitted RGB mixture, including antialiased gold.
    base, gold = PALETTE[expected], PALETTE[2]
    direction = [g-b for b,g in zip(base,gold)]
    t = max(0,min(1,sum((p-b)*d for p,b,d in zip(pixel,base,direction))/sum(d*d for d in direction)))
    return max(abs(p-(b+t*d)) for p,b,d in zip(pixel,base,direction))


def render(font, name, factor=1, transparent=False, left=0):
    ss = 4 * factor
    width=math.ceil(max(font['glyf'][layer.name].xMax for layer in font['COLR'].ColorLayers[name])/5)
    width-=left
    image = Image.new('RGBA' if transparent else 'RGB', (width*ss, 95*ss), (0,0,0,0) if transparent else 'white')
    gs = font.getGlyphSet()
    for layer in font['COLR'].ColorLayers[name]:
        pen = ConnectedPen(gs, 5, 95, ss)
        pen.x_offset=-left*ss
        gs[layer.name].draw(pen)
        mask = Image.new('L', image.size)
        draw = ImageDraw.Draw(mask)
        # Paint larger contours first and opposite-winding counters as holes.
        for points in sorted(pen.polygons, key=lambda p: abs(area(p)), reverse=True):
            draw.polygon(points, fill=255 if area(points)>0 else 0)
        image.paste(PALETTE[layer.colorID], (0,0), mask)
    return image.resize((width*factor,95*factor), Image.LANCZOS)


def validate_shape(shaper, text, calt=None, kern=None):
    result = shaper.shape(text, calt=calt, kern=kern)
    assert len(result) == len(text), (text, result)
    incoming = 'B'
    offset = 0
    for i,(char, glyph) in enumerate(zip(text, result)):
        assert glyph['cluster'] == offset, (text, glyph)
        offset += len(char.encode('utf-8'))
        if char.isascii() and char.isalpha():
            letter=char.upper()
            if letter=='X':
                state='BB'
            elif calt is False:
                state='BB' if letter=='W' else 'BG'
            else:
                state=incoming+(incoming if letter=='W' else ('G' if incoming=='B' else 'B'))
            pair=None
            if i+1<len(text) and text[i+1].isascii() and text[i+1].isalpha():
                pair=PAIRS[letter+text[i+1].upper()]
            suffix=extension_key(pair) if pair and calt is not False else None
            expected=letter+'.'+state+('.'+suffix if suffix else '')
            if i and calt is not False:
                overlap=STROKE_OVERLAPS.get(text[i-1:i+1].upper(),0)
                if overlap: expected+='.in%d'%round(overlap*5)
                elif text[i-1].isascii() and text[i-1].isalpha():
                    join=PAIRS[text[i-1:i+1].upper()].get('incoming_join')
                    if join: expected+='.'+join
            assert glyph['name'] == expected, (text, glyph, expected)
            adjusted=pair and kern is not False and (calt is not False or not pair['stroke_overlap'])
            advance=950+(pair['units'] if adjusted else 0)
            assert glyph['advance'] == advance and glyph['x_offset'] == glyph['y_offset'] == 0,(text,glyph,advance)
            incoming=state[1]
        else:
            incoming = 'B'
            if char in [' ', '\u00a0']:
                assert glyph['name']=='space' and glyph['advance']==475
    return result


def check_details(font):
    points={'A':[(95,40)],'B':[(80,28),(80,68)],'D':[(80,47)],
            'H':[(95,20),(95,75)],'M':[(95,20),(95,88)],
            'N':[(80,20),(80,80)],'O':[(95,40)],'P':[(80,32)],
            'Q':[(95,40)],'R':[(80,32)],'U':[(95,50)],
            'V':[(95,30)],'Y':[(95,10)]}
    for letter,coords in points.items():
        for state in ['BG','GB','BB','GG']:
            image=render(font,letter+'.'+state)
            for coord in coords:
                assert nearest(image.getpixel(coord),PALETTE)==(1 if state=='BB' else 0),(letter,state,coord)
    for state,left in [('BB',0),('GG',1)]:
        image=render(font,'W.'+state)
        coords=[(8,75),(48,20),(95,75),(143,20),(182,75)]
        assert [nearest(image.getpixel(p),PALETTE) for p in coords]==[left,1-left,left,1-left,left]
    original=TTFont(FONTS/'JamaicanAlphabet.ttf')
    reference=render_original(original,'X',PALETTE)
    for state in ['BG','GB','BB','GG']:
        assert render(font,'X.'+state).tobytes()==reference.tobytes(),('X must match original flag',state)
    for name in font['COLR'].ColorLayers:
        if name.startswith('X.') and '.pad' in name and '.join' not in name:
            painted=render(font,name).crop((0,0,190,95))
            assert painted.crop((0,0,187,95)).tobytes()==reference.crop((0,0,187,95)).tobytes(),('X spacer flag',name)
            # Lanczos uses the continuing spacer in its last three columns.
            diff=ImageChops.difference(painted,reference)
            assert max(max(p) for p in diff.getdata())<=16,('X spacer antialiasing',name)
    original.close()
    for state in ['BG','GB','BB','GG']:
        image=render(font,'N.'+state)
        expected=1 if state=='BB' else 0
        for y in range(5,90):
            for x in range(45,146):
                # N’s interior uses counter color and gold mixtures.
                assert edge_error(image.getpixel((x,y)),expected)<=20,('N diagonal stripe',state,x,y)
    assert (font['glyf']['I.BG'].xMin,font['glyf']['I.BG'].xMax)==(font['glyf']['H.BG'].xMin,font['glyf']['H.BG'].xMax)==(160,790)
    image=render(font,'I.BG')
    for y in [0,8,86,94]:
        assert all(nearest(image.getpixel((x,y)),PALETTE)==2 for x in [33,75,115,156])


def main():
    original = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (FONTS).glob('JamaicanAlphabet.*')}
    seed = random.Random(20261111)
    cases = [a+b for a in LETTERS for b in LETTERS]
    cases += [c*257 for c in LETTERS]
    cases += [''.join(seed.choice(LETTERS+LETTERS.lower()) for _ in range(257)) for _ in range(100)]
    cases += [LETTERS*400, 'JTL'*1000, 'JAMAICA', 'Hello World', 'A B  C D',
              'AB\u00a0CDE', 'AB.CDE', 'AB-CDE', 'AB!CDE', '', 'aBcDeF', 'OCOCONMN']
    report = {'pair_count': 676, 'cases_per_format': len(cases), 'formats': {},
              'original_font_sha256': original}
    cache = {}
    for extension in ['ttf','woff','woff2']:
        path = FONTS/('JamaicanConnected.'+extension)
        font, shaper = TTFont(path), Shaper(path)
        assert font['name'].getDebugName(1)=='Jamaican Connected'
        assert font['COLR'].version==0 and len(font['COLR'].ColorLayers)>104
        assert 'GPOS' in font
        assert font['hmtx']['space']==(475,0)
        assert font['hhea'].ascent-font['hhea'].descent+font['hhea'].lineGap==713
        for c in LETTERS:
            assert font.getBestCmap()[ord(c)]==font.getBestCmap()[ord(c.lower())]==c+('.BB' if c in 'WX' else '.BG')
        for case in cases:
            validate_shape(shaper,case)
        validate_shape(shaper,LETTERS*10,calt=False)
        validate_shape(shaper,LETTERS*10,kern=False)
        validate_shape(shaper,'AEGACGHHOOCE',calt=False,kern=False)
        check_details(font)
        for pair,spec in PAIRS.items():
            if spec['units']<0 and not spec['stroke_overlap']:
                previous_gold_right=font['glyf'][pair[0]+'.BG'].xMax
                assert 950+spec['units']>=previous_gold_right+4,(pair,spec)
            if pair[0] in 'CG': assert spec['units']==30
        assert PAIRS['AE']['units']==30 and PAIRS['GA']['joins']['bottom']>0
        for pair,spec in PAIRS.items():
            assert sum(v>0 for v in spec['joins'].values())<=1,(pair,'double connection')
            if all(spec['available_joins'].values()):
                assert spec['units']>0,(pair,'needs a break at the unchosen corner')
        for pair in ['CA','AD','CD','CE','XZ']:
            assert PAIRS[pair]['selected_corner']=='bottom',pair
        for pair in ['EF','FE','KE']:
            assert PAIRS[pair]['selected_corner']=='top',pair
        for pair,overlap in STROKE_OVERLAPS.items():
            assert PAIRS[pair]['units']==-round(overlap*5),pair
            assert PAIRS[pair]['stroke_overlap']==overlap,pair
            for text in [pair,pair.lower(),'A'+pair,'A'+pair.lower()]:
                validate_shape(shaper,text)
            for text in [pair,'LAZY']:
                validate_shape(shaper,text,kern=False)
                validate_shape(shaper,text,calt=False)
        for name in font['COLR'].ColorLayers:
            if '.join' in name:
                base=name.rsplit('.join',1)[0]
                original_layers=[(p.name,p.colorID) for p in font['COLR'].ColorLayers[base]]
                actual_layers=[(p.name,p.colorID) for p in font['COLR'].ColorLayers[name]]
                assert actual_layers[:-1]==original_layers,(name,'preserves full original strokes')
                assert actual_layers[-1][1]==2,(name,'gold continuations')
            if '.in' in name:
                base=name.rsplit('.in',1)[0]
                assert font['glyf'][name].compile(font['glyf'])==font['glyf'][base].compile(font['glyf']),name
                assert [(p.name,p.colorID) for p in font['COLR'].ColorLayers[name] if p.colorID==2]==[
                    (p.name,p.colorID) for p in font['COLR'].ColorLayers[base] if p.colorID==2],name
        for c in LETTERS:
            manual = [shaper.shape(c,calt=False,alternate=i)[0]['name'] for i in [1,2,3,4]]
            assert manual == [c+'.BG',c+'.GB',c+'.BB',c+'.GG'], manual
        for line in ['JAMAICA', 'JTL', 'ABCDEF']:
            assert validate_shape(shaper,line)[0]['name'].split('.')[1]=='BG'
        edge_pixels = 0
        for c in LETTERS:
            for state in ['BG','GB','BB','GG']:
                name = c+'.'+state
                layers = font['COLR'].ColorLayers[name]
                assert font['hmtx'][name][0]==950
                base = font['glyf'][layers[0].name]
                assert (base.xMin,base.yMin,base.xMax,base.yMax)==(0,0,950,475)
                image = render(font,name)
                for x, expected in [(0, 0 if c=='X' or state[0]=='B' else 1), (189, 0 if c=='X' or state[1]=='B' else 1)]:
                    for y in range(95):
                        pixel = image.getpixel((x,y))
                        # Allow Lanczos ringing in saturated preview channels.
                        assert edge_error(pixel,expected) <= 20, (extension,name,x,y,pixel)
                        edge_pixels += 1
                assert any(nearest(p, PALETTE)==2 for p in image.getdata()), name
                if extension=='ttf':
                    cache[name]=image
        report['formats'][extension] = {'harfbuzz_version': shaper.version,
            'shaping_cases':len(cases), 'variants_checked':104, 'edge_pixels_checked':edge_pixels,
            'default_calt':True, 'calt_off':True, 'manual_alternates':True,
            'letter_advance':950, 'space_advance':475, 'line_advance':713}
        report['formats'][extension].update({'kerning_pairs':sum(p['units']!=0 for p in PAIRS.values()),
            'spacing_alternates':len(font['COLR'].ColorLayers)-104,'dark_counters':True,
            'W_five_regions_alternate':True,'I_crossbars_match_H':True,'safe_negative_kerning':True})
        shaper.close()
        font.close()
        print('Verified %s: %d shaping cases, 104 variants, %d edge pixels' % (extension,len(cases),edge_pixels),flush=True)
    previews = PREVIEWS/'connected'
    previews.mkdir(parents=True,exist_ok=True)
    font, shaper = TTFont(FONTS/'JamaicanConnected.ttf'), Shaper(FONTS/'JamaicanConnected.ttf')
    text_cache={}

    def text_image(text, calt=True, kern=True):
        glyphs = shaper.shape(text,calt=calt,kern=kern)
        width = max(1,round(sum(g['advance'] for g in glyphs)/5))
        image = Image.new('RGB',(width,95),'white')
        x = 0
        for g in glyphs:
            if g['name'] in font['COLR'].ColorLayers:
                if g['name'] not in text_cache:
                    left=math.floor(min(font['glyf'][p.name].xMin for p in font['COLR'].ColorLayers[g['name']])/5)
                    text_cache[g['name']]=(render(font,g['name'],transparent=True,left=left),left)
                painted,left=text_cache[g['name']]
                image.paste(painted,(round(x/5)+left,0),painted)
            x += g['advance']
        return image

    samples = [('JAMAICA',True),('HELLO WORLD',True),('ABCDEFGHIJK',True),('LMNOPQRSTUV',True),
               ('WXYZ JTLJTL',True),('HHHHHH OOOO',True),('ABCDEF',False)]
    sheet = Image.new('RGB',(max(text_image(t,c).width for t,c in samples)+48, len(samples)*143+24),'#f8f6ef')
    draw = ImageDraw.Draw(sheet)
    for i,(text,calt) in enumerate(samples):
        draw.text((24,12+i*143), text+(' / CALT ON' if calt else ' / CALT OFF'),fill='black')
        sheet.paste(text_image(text,calt),(24,30+i*143))
    sheet.save(previews/'samples.png')
    pairs_text='VE LA AZ ZY CA CD XZ GA OO'
    pair_sheet=Image.new('RGB',(text_image(pairs_text).width+48,2*143+24),'#f8f6ef')
    draw=ImageDraw.Draw(pair_sheet)
    for i,kern in enumerate([True,False]):
        draw.text((24,12+i*143),'OPTICAL KERNING '+('ON' if kern else 'OFF'),fill='black')
        pair_sheet.paste(text_image(pairs_text,kern=kern),(24,30+i*143))
    pair_sheet.save(previews/'kerning-pairs.png')
    ga=text_image('GA')
    assert all(nearest(ga.getpixel((x,89)),PALETTE)==2 for x in range(188,198))
    detail_letters='BIW'
    details=Image.new('RGB',(880,3*119+24),'#f8f6ef')
    draw=ImageDraw.Draw(details)
    for row,c in enumerate(detail_letters):
        for col,state in enumerate(['BG','GB','BB','GG']):
            x,y=24+col*214,24+row*119
            draw.text((x,y-14),c+' / '+state,fill='black')
            details.paste(cache[c+'.'+state],(x,y))
    details.save(previews/'BIW-details.png')
    proof_letters = 'OCNTLJ'
    proofs = Image.new('RGB',(4*214+24,len(proof_letters)*119+24),'#f8f6ef')
    draw = ImageDraw.Draw(proofs)
    for row,c in enumerate(proof_letters):
        for col,state in enumerate(['BG','GB','BB','GG']):
            x,y=24+col*214,24+row*119
            draw.text((x,y-14),c+' / '+state[0]+' TO '+state[1],fill='black')
            proofs.paste(cache[c+'.'+state],(x,y))
    proofs.save(previews/'variant-proof.png')
    joins = text_image('JTLJTLJTL')
    joins.save(previews/'jtl-joins.png')
    for name in ['J.BG','T.GB','L.BG','O.GB','C.BG','N.GB']:
        render(font,name,factor=4).save(previews/(name+'.png'))
    shaper.close()
    font.close()
    for relative,digest in original.items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest
    (METADATA/'connected/verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Original Jamaican Alphabet font files unchanged.',flush=True)


if __name__=='__main__':
    main()
