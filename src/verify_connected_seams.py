#!/usr/bin/env python3
"""Verify fractional-position joins with native FreeType rendering.

RGB-plane checks measure palette purity at background joins; gold samples
measure the color of connected strokes."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile
from PIL import Image,ImageDraw
from fontTools.ttLib import TTFont
from hb_shaping import Shaper
from connected_spacing import STROKE_OVERLAPS

from paths import SRC, FONTS, METADATA, PREVIEWS
SIZES=[40,48,52,64,80,92,100,127,200]
PHASES=[0,.125,.375,.625,.875]
FOCUSED=['AB','AE','AS','WB','XB','AA','AV','WV','XY','CA','AD','CD','CE','EF','FE','KE','XZ','GA','CG','AH','FO','HH','OO','AX','XA','WX','WW','VE','LA','AZ','ZY']


def plane_error(rgb):
    r,g,b=rgb
    return abs(g-r*209/255-b*155/57)


def stroke_intersection(pair):
    origin=190-STROKE_OVERLAPS[pair]
    lines={
        'VE':((95,95),(190,0),(origin,8),(origin+190,8)),
        'LA':((48,87),(190,87),(origin+95,0),(origin,95)),
        'AZ':((95,0),(190,95),(origin+8,87),(origin+182,8)),
        'ZY':((8,87),(182,8),(origin,0),(origin+95,47.5)),
    }
    a,b,c,d=lines[pair]
    v=(b[0]-a[0],b[1]-a[1]);w=(d[0]-c[0],d[1]-c[1])
    t=((c[0]-a[0])*w[1]-(c[1]-a[1])*w[0])/(v[0]*w[1]-v[1]*w[0])
    return a[0]+t*v[0],a[1]+t*v[1]


def render_grid(binary,font_path,ppem,cases,output):
    font=TTFont(font_path)
    shaper=Shaper(font_path)
    columns=10
    cell_w=math.ceil(ppem*2.05)+32
    cell_h=math.ceil(ppem*.475)+24
    width=columns*cell_w
    height=math.ceil(len(cases)/columns)*cell_h
    placements,checks=[],[]
    for i,(text,phase) in enumerate(cases):
        origin_x=12+(i%columns)*cell_w+phase
        origin_y=10+(i//columns)*cell_h
        x=origin_x
        glyphs=shaper.shape(text)
        for index,glyph in enumerate(glyphs):
            placements.append('%d %.6f %.6f' % (font.getGlyphID(glyph['name']),x,origin_y))
            x+=glyph['advance']*ppem/1000
            if index==0:
                checks.append({'pair':text,'boundary':x,'y':origin_y+ppem*.2375,
                               'origin':[origin_x,origin_y],'phase':phase})
                overlap=STROKE_OVERLAPS.get(text,0)
                if overlap:
                    checks.append({'pair':text,'boundary':x+overlap*ppem/200,'y':origin_y+ppem*.2375,
                                   'origin':[origin_x,origin_y],'phase':phase,'handoff':True})
    data='%d %d %d\n' % (width,height,len(placements))+'\n'.join(placements)
    subprocess.run([str(binary),str(font_path),str(output),str(ppem)],input=data,text=True,check=True)
    image=Image.open(output).convert('RGB')
    shaper.close()
    font.close()
    return image,checks


def check_image(image,checks,ppem):
    samples=0
    worst=0
    for check in checks:
        y=math.floor(check['y'])
        for x in range(math.floor(check['boundary'])-1,math.floor(check['boundary'])+2):
            error=plane_error(image.getpixel((x,y)))
            worst=max(worst,error)
            assert error<=8,('background leakage',ppem,check,image.getpixel((x,y)),error)
            samples+=1
    return samples,worst


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--before-font',type=Path)
    args=parser.parse_args()
    font_path=FONTS/'JamaicanConnected.ttf'
    total,samples,worst=0,0,0
    with tempfile.TemporaryDirectory(prefix='connected-seams-') as directory:
        directory=Path(directory)
        binary,output=directory/'render',directory/'render.ppm'
        cflags=subprocess.check_output(['pkg-config','--cflags','freetype2'],text=True).split()
        libs=subprocess.check_output(['pkg-config','--libs','freetype2'],text=True).split()
        subprocess.run(['cc',*cflags,str(SRC/'render_connected_native.c'),'-o',str(binary),*libs,'-lm'],check=True)
        focused=[(pair,phase) for pair in FOCUSED for phase in PHASES]
        for size in SIZES:
            image,checks=render_grid(binary,font_path,size,focused,output)
            count,error=check_image(image,checks,size)
            samples+=count; worst=max(worst,error); total+=len(checks)
        exhaustive=[(a+b,p) for a in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                    for b in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' for p in [.125,.625]]
        for size in [52,92,127]:
            for offset in range(0,len(exhaustive),600):
                image,checks=render_grid(binary,font_path,size,exhaustive[offset:offset+600],output)
                count,error=check_image(image,checks,size)
                samples+=count; worst=max(worst,error); total+=len(checks)
        # Sample the solid interior of each incoming gold band.
        pair_specs=json.loads((METADATA/'connected/spacing.json').read_text())['pairs']
        bridge_cases=[(pair,phase) for pair,spec in pair_specs.items() if spec['stroke_join'] for phase in PHASES]
        gold_checks=0
        for size in [80,92,127,200]:
            for offset in range(0,len(bridge_cases),600):
                image,checks=render_grid(binary,font_path,size,bridge_cases[offset:offset+600],output)
                for check in checks:
                    spec=pair_specs[check['pair']]
                    corner=spec['selected_corner']
                    band=spec['stroke_join'][corner]['right_height']*size/200
                    top=check['origin'][1] if corner=='top' else check['origin'][1]+size*.475-band
                    bottom=top+band
                    rows=[y for y in range(math.ceil(top+1),math.floor(bottom-1))]
                    if not rows: continue
                    y=rows[len(rows)//2]
                    for x in range(math.floor(check['boundary']),math.floor(check['boundary'])+2):
                        error=plane_error(image.getpixel((x,y)))
                        assert error<=8,('gold seam',size,check,image.getpixel((x,y)),error)
                        assert max(abs(p-c) for p,c in zip(image.getpixel((x,y)),(255,209,0)))<=3,('gold tint',size,check,image.getpixel((x,y)))
                        gold_checks+=1
        overlap_checks=0
        overlap_cases=[(pair,phase) for pair in STROKE_OVERLAPS for phase in PHASES]
        for size in SIZES:
            image,checks=render_grid(binary,font_path,size,overlap_cases,output)
            for check in checks:
                if check.get('handoff'): continue
                ix,iy=stroke_intersection(check['pair'])
                x=math.floor(check['origin'][0]+ix*size/200)
                y=math.floor(check['origin'][1]+iy*size/200)
                pixel=image.getpixel((x,y))
                assert max(abs(p-c) for p,c in zip(pixel,(255,209,0)))<=3,('stroke intersection',size,check,pixel)
                overlap_checks+=1
        proof_cases=[(p,0) for p in ['CA','AD','CD','AH']]
        proof=Image.new('RGB',(820 if args.before_font else 410,4*110+28),'white')
        draw=ImageDraw.Draw(proof)
        before_checks=0
        for col,path in enumerate([args.before_font,font_path] if args.before_font else [font_path]):
            img,positions=render_grid(binary,path,92,proof_cases,output)
            for row,check in enumerate(positions):
                x0,y0=check['origin']
                crop=img.crop((math.floor(x0),int(y0),math.floor(x0)+194,int(y0)+45))
                x=12+col*410
                proof.paste(crop.resize((388,90),Image.NEAREST),(x,28+row*110))
                draw.text((x,12+row*110),check['pair']+' / '+('BEFORE' if args.before_font and col==0 else 'AFTER'),fill='black')
                if args.before_font and col==0:
                    pixel=img.getpixel((math.floor(check['boundary']),math.floor(check['y'])))
                    before_checks+=plane_error(pixel)>8
        if args.before_font: assert before_checks>0,'Old font did not reproduce the seam'
        (PREVIEWS/'connected').mkdir(parents=True,exist_ok=True)
        proof.save(PREVIEWS/'connected/fractional-seams.png')
    path=METADATA/'connected/verification.json'
    report=json.loads(path.read_text())
    report['fractional_seams']={'join_cases':total,'background_samples':samples,'gold_samples':gold_checks,
        'pixels_per_em':SIZES,'x_pixel_phases':PHASES,'all_676_pairs_at':[52,92,127],
        'worst_rgb_plane_error':round(worst,4),'tolerance':8,
        'stroke_intersection_samples':overlap_checks,
        'before_seam_cases_reproduced':before_checks,'result':'passed'}
    path.write_text(json.dumps(report,indent=2)+'\n')
    print('Fractional joins: %d joins, %d background samples, %d gold samples passed.' % (total,samples,gold_checks))


if __name__=='__main__': main()
