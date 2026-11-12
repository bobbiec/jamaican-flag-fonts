#!/usr/bin/env python3
"""Render blog figures with HarfBuzz, FreeType, and the project's font files."""
import hashlib
import html
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

from paths import ROOT, SRC, FONTS, REFERENCE_FONTS, BLOG
from hb_shaping import Shaper

OUT = BLOG

BG = '#f1f1e6'
INK = '#242821'
MUTED = '#62665b'
RULE = '#c9ccbd'
GREEN = '#009b39'
GOLD = '#ffd100'
W = 900
MAIN = FONTS/'JamaicanAlphabet.ttf'
CONNECTED = FONTS/'JamaicanConnected.ttf'
TAPERED = REFERENCE_FONTS / 'tapered-joins.ttf'
HAIRLINES = REFERENCE_FONTS / 'before-seam-protection.ttf'
SANS = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
MONO = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
ASSETS = []


def font(size=25, bold=False, mono=False):
    return ImageFont.truetype(MONO if mono else BOLD if bold else SANS, size)


def text(image, xy, value, size=25, color=INK, bold=False, mono=False):
    ImageDraw.Draw(image).text(xy, value, font=font(size,bold,mono), fill=color)


def canvas(title='', subtitle='', height=650):
    return Image.new('RGB',(W,height),BG)

def line(image, points, color=RULE, width=2):
    ImageDraw.Draw(image).line(points,fill=color,width=width)


def shaped(path, word):
    shaper=Shaper(path)
    result=shaper.shape(word)
    shaper.close()
    return result


def with_state(glyph,state):
    parts=glyph['name'].split('.')
    parts[1]=state
    return dict(glyph,name='.'.join(parts))


def render(path, glyphs, ppem, width, height, placements=None, phase=0, top_phase=0):
    ft=TTFont(path)
    if placements is None:
        placements=[]
        pen=phase
        for glyph in glyphs:
            placements.append((ft.getGlyphID(glyph['name']),pen,top_phase))
            pen+=glyph['advance']*ppem/1000
    data='%d %d %d\n'%(width,height,len(placements))
    data+='\n'.join('%d %.6f %.6f'%p for p in placements)
    output=TEMP/'render.ppm'
    subprocess.run([str(BINARY),str(path),str(output),str(ppem)],input=data,text=True,check=True)
    ft.close()
    return Image.open(output).convert('RGB')


def word(image, value, xy, ppem=210, path=CONNECTED, glyphs=None):
    glyphs=shaped(path,value) if glyphs is None else glyphs
    width=math.ceil(sum(g['advance'] for g in glyphs)*ppem/1000)+40
    height=math.ceil(ppem*.475)+2
    origin=(math.floor(xy[0]),math.floor(xy[1]))
    image.paste(render(path,glyphs,ppem,width,height,
                       phase=xy[0]-origin[0],top_phase=xy[1]-origin[1]),origin)
    return [xy[0]+sum(g['advance'] for g in glyphs[:i])*ppem/1000 for i in range(len(glyphs)+1)]


def glyph(image, name, xy, width=300, path=CONNECTED):
    ppem=round(width/.95)
    ft=TTFont(path)
    position=-.06*ppem if path==MAIN else 0
    placement=[(ft.getGlyphID(name),position,0)]
    image.paste(render(path,[],ppem,width,math.ceil(ppem*.475),placement),xy)
    ft.close()


def write_png(stem,image):
    image.save(OUT/(stem+'.png'),optimize=True)


def animation(stem,frames,durations=None):
    frames=[frame.convert('P',palette=Image.ADAPTIVE,colors=256) for frame in frames]
    frames[0].save(OUT/(stem+'.gif'),save_all=True,append_images=frames[1:],
                   duration=durations or [2200]*len(frames),loop=0,disposal=2,optimize=False)


def register(stem,title,caption,gif=False):
    ASSETS.append(dict(stem=stem,title=title,caption=caption,gif=gif))


def branched_arrow(image,trunk,branches):
    """Draw a shared curved stem with arrowheads at each branch tip."""
    assert all(branch[0]==trunk[-1] for branch in branches)
    ss=3
    overlay=Image.new('RGBA',(image.width*ss,image.height*ss),(0,0,0,0))
    draw=ImageDraw.Draw(overlay)
    for controls in [trunk]+branches:
        points=[]
        for i in range(65):
            t=i/64
            points.append(tuple(sum(coefficient*point[axis] for coefficient,point in zip(
                [(1-t)**3,3*(1-t)**2*t,3*(1-t)*t*t,t**3],controls))*ss for axis in [0,1]))
        draw.line(points,fill=MUTED,width=2*ss)
    for branch in branches:
        end=branch[-1]
        angle=math.atan2(end[1]-branch[-2][1],end[0]-branch[-2][0])
        points=[end]+[(end[0]-10*math.cos(angle+offset),end[1]-10*math.sin(angle+offset))
                      for offset in [-.4,.4]]
        draw.polygon([(x*ss,y*ss) for x,y in points],fill=MUTED)
    overlay=overlay.resize(image.size,Image.LANCZOS)
    image.paste(Image.alpha_composite(image.convert('RGBA'),overlay).convert('RGB'))


def stack(frames):
    image=Image.new('RGB',(W,sum(f.height for f in frames)),BG)
    y=0
    for frame in frames:
        image.paste(frame,(0,y))
        y+=frame.height
    return image


def r_definition():
    import ast
    from connected_spacing import Contours
    from fontTools.svgLib.path import parse_path
    from geometry import alphabet
    source=(SRC/'geometry.py').read_text()
    shared=source[source.index('    p_outer ='):source.index("    start('P')")]
    definition=source[source.index("    start('R')"):source.index("    start('S')")]
    code='\n'.join(row[4:] if row.startswith('    ') else row
                   for row in (shared+definition).strip('\n').splitlines())
    code=code.replace('bowl(p_outer, p_inner)',
                      'paint(2, p_outer)\npaint(1, p_inner, cut_gold=True)')
    rows=code.splitlines()
    definitions={node.targets[0].id:ast.literal_eval(node.value)
                 for node in ast.parse(code).body if isinstance(node,ast.Assign)}
    layers=alphabet()['R']['layers']
    palette=['#000000',GREEN,GOLD]
    states=[
        'Define the outer path: the bowl, stem, and top serif.',
        'Define the inner path: the enclosed counter.',
        'Start R with a black flag-sized field.',
        'Paint the lower green polygon.',
        'Paint the outer bowl gold.',
        'Paint the inner path green to form the counter.',
        'Paint the diagonal leg gold.',
    ]
    frames=[]
    for step,caption in enumerate(states):
        image=canvas(height=820)
        draw=ImageDraw.Draw(image)
        for i,row in enumerate(rows):
            y=25+i*35
            if i==step: draw.rectangle((20,y-4,880,y+29),fill='#e6deb0')
            text(image,(30,y),row,18,mono=True)
        for x,label,color in [(32,'0  black','#000000'),(300,'1  green',GREEN),(570,'2  gold',GOLD)]:
            draw.rectangle((x,300,x+20,320),fill=color)
            text(image,(x+30,297),label,19)
        # SVG contours are rendered at four times the output resolution.
        ss=4;scale=600/190
        panel=Image.new('RGB',(600*ss,300*ss),BG)
        painter=ImageDraw.Draw(panel)
        def paint_path(path,color,outline=False):
            pen=Contours();parse_path(path,pen)
            for contour in pen.contours:
                points=[(x*scale*ss,y*scale*ss) for x,y in contour]
                if outline: painter.line(points+[points[0]],fill=color,width=3*ss)
                else: painter.polygon(points,fill=color)
        if step<2:
            painter.rectangle((1,1,600*ss-2,300*ss-2),outline=RULE,width=ss)
            paint_path(definitions['p_outer'],GOLD,outline=True)
            if step==1: paint_path(definitions['p_inner'],GREEN,outline=True)
        else:
            count={2:1,3:2,4:3,5:4,6:5}[step]
            for color,path in layers[:count]: paint_path(path,palette[color])
        image.paste(panel.resize((600,300),Image.LANCZOS),(150,375))
        if step==6:
            # The final state uses the same compiled font as the other figures.
            glyph(image,'R',(150,375),width=600,path=MAIN)
        text(image,(30,730),'%d / 7  %s'%(step+1,caption),21)
        frames.append(image)
    animation('01-r-definition',frames,[2200,2200,1800,2200,1800,2200,3000])
    write_png('01-r-definition',frames[-1])
    register('01-r-definition','A letter defined by shapes',
             'R’s construction from src/geometry.py, with bowl(p_outer, p_inner) expanded into its two paint calls. Each highlighted line previews a path or applies a fill. The outer path is painted gold, then the inner path is painted green.',True)


def original_outline(image,letter,xy,width):
    """Overlay dotted red on the original gold silhouette's boundary."""
    from connected_spacing import Contours
    from fontTools.svgLib.path import parse_path
    from geometry import alphabet
    scale=width/190
    pen=Contours()
    for path in alphabet()[letter]['gold']: parse_path(path,pen)
    # The mask identifies silhouette edges where component strokes overlap.
    mask=Image.new('L',(width*3+18,round(width*1.5)+18))
    painter=ImageDraw.Draw(mask)
    for contour in pen.contours:
        painter.polygon([(9+x*scale*3,9+y*scale*3) for x,y in contour],fill=255)
    draw=ImageDraw.Draw(image)
    for contour in pen.contours:
        distance_to_dot=0
        for a,b in zip(contour,contour[1:]+contour[:1]):
            length=math.hypot(b[0]-a[0],b[1]-a[1])*scale
            if length<1e-6: continue
            while distance_to_dot<length:
                t=distance_to_dot/length
                x=(a[0]+t*(b[0]-a[0]))*scale
                y=(a[1]+t*(b[1]-a[1]))*scale
                mx,my=round(9+x*3),round(9+y*3)
                neighborhood=mask.crop((mx-5,my-5,mx+6,my+6))
                if neighborhood.getextrema()==(0,255):
                    px,py=xy[0]+x,xy[1]+y
                    draw.ellipse((px-1.5,py-1.5,px+1.5,py+1.5),fill='#dc3636')
                distance_to_dot+=7
            distance_to_dot-=length


def letter_forms():
    image=canvas(height=1090)
    labels=['Wider bars, full height','Top bar raised','Foot lowered','Top bar raised']
    for i,(c,label) in enumerate(zip('IJLT',labels)):
        x=30+(i%2)*450;y=(i//2)*520
        text(image,(x,y+8),c,27,bold=True)
        text(image,(x,y+50),'Original',19)
        glyph(image,c,(x,y+82),width=340,path=MAIN)
        text(image,(x,y+272),'Connected',19)
        glyph(image,c+'.BG',(x,y+304),width=340)
        original_outline(image,c,(x,y+304),340)
        text(image,(x,y+485),label,19)
    for x in range(30,73,7):
        ImageDraw.Draw(image).ellipse((x,1053,x+3,1056),fill='#dc3636')
    text(image,(90,1043),'Dotted red: original gold outline',19)
    write_png('02-ijlt',image)
    register('02-ijlt','Preparing the letters to connect',
             'I, J, L, and T in the Original and Connected fonts at identical flag-core dimensions. Dotted red outlines on the Connected forms mark the original gold silhouettes.')


def variants():
    image=canvas(height=285)
    for i,state in enumerate(['BG','GB']):
        x=30+(i%2)*450;y=(i//2)*285
        names={'B':'black','G':'green'}
        text(image,(x,y+22),state+' · '+names[state[0]]+' → '+names[state[1]],21,bold=True)
        glyph(image,'B.'+state,(x,y+72),width=350)
    write_png('03-color-variants',image)
    old=OUT/'03-four-variants.png'
    if old.exists(): old.unlink()
    register('03-color-variants','The two automatic color choices',
             'B in BG and GB: the two forms selected for ordinary letters by automatic color matching. The gold outline stays the same while the incoming and outgoing fields swap colors.')


def color_matching():
    glyphs=shaped(CONNECTED,'JAMAICA')
    fixed=[with_state(g,'BG') for g in glyphs]
    frames=[]
    for label,selected in [('Fixed colors',fixed),('Contextual color matching',glyphs)]:
        image=canvas(height=230)
        text(image,(30,22),label,23,bold=True)
        edges=word(image,'JAMAICA',(30,88),ppem=120,glyphs=selected)
        for edge in edges[1:-1]: line(image,[(round(edge),71),(round(edge),81)],MUTED,2)
        for i,g in enumerate(selected):
            x=round((edges[i]+edges[i+1])/2)-12
            text(image,(x,170),g['name'].split('.')[1],18,mono=True)
        frames.append(image)
    animation('04-jamaica-colors',frames)
    write_png('04-jamaica-colors',stack(frames))
    register('04-jamaica-colors','Matching the colors in JAMAICA',
             'Identical geometry and spacing in both states. Only the color choices change, matching each letter’s incoming field to its neighbor’s outgoing field.',True)


def exceptions():
    image=canvas(height=650)
    for x,name,label in [(30,'W.BB','W: black → black'),(490,'W.GG','W: green → green')]:
        text(image,(x,22),label,22)
        glyph(image,name,(x,75),width=380)
    text(image,(220,322),'X: original Jamaican flag',22)
    glyph(image,'X.BB',(220,375),width=460)
    write_png('05-w-and-x',image)
    register('05-w-and-x','Two color exceptions',
             'W alternates across five regions and returns to its incoming color. X always keeps the original flag.')


def relaxed():
    final=shaped(CONNECTED,'RELAXED')
    before=[]
    for index,glyph_data in enumerate(final):
        name=re.sub(r'\.(?:join\d+|in\d+)$','',glyph_data['name'])
        before.append(dict(glyph_data,name=name,advance=980 if index<len(final)-1 else 950))
    image=canvas(height=530)
    text(image,(30,22),'Before',23,bold=True)
    word(image,'RELAXED',(30,78),ppem=124,glyphs=before)
    text(image,(30,216),'After',23,bold=True)
    edges=word(image,'RELAXED',(30,272),ppem=124,glyphs=final)
    # All four bottom connections share one stem and label.
    la=edges[3]+5
    gap=6*124/200
    ax=edges[4]-gap/2
    xe=edges[5]-gap/2
    ed=edges[6]-gap/2
    junction=(565,420)
    branched_arrow(image,[(565,465),(550,447),(565,438),junction],[
        [junction,(510,405),(la,377),(la,333)],
        [junction,(548,397),(ax,370),(ax,333)],
        [junction,(599,397),(xe,370),(xe,333)],
        [junction,(680,420),(ed,383),(ed,333)],
    ])
    text(image,(360,485),'Bottom joins across L–A–X–E–D',20)
    top_junction=(698,230)
    branched_arrow(image,[(700,205),(704,216),(698,219),top_junction],[
        [top_junction,(670,230),(xe,243),(xe,270)],
        [top_junction,(728,230),(ed,243),(ed,270)],
    ])
    text(image,(480,174),'XE and ED: open tops for readability',19)
    write_png('06-relaxed-spacing',image)
    for filename in ['06-bedroom-spacing.png','06-bedroom-spacing.gif']:
        old=OUT/filename
        if old.exists(): old.unlink()
    register('06-relaxed-spacing','Spacing and joining RELAXED',
             'Before: uniform six-design-pixel gaps with incoming join and overlap forms omitted. After: complete contextual shaping and optical spacing. A shared curved arrow marks all bottom joins across L–A–X–E–D; the upper arrow marks the open XE and ED top corners that preserve readability. The color choices stay fixed.')


def cool():
    final=shaped(CONNECTED,'COOL')
    before=[dict(glyph_data) for glyph_data in final]
    before[1]['advance']=950
    image=canvas(height=410)
    text(image,(30,22),'Before',23,bold=True)
    before_edges=word(image,'COOL',(50,78),ppem=200,glyphs=before)
    text(image,(30,216),'After',23,bold=True)
    edges=word(image,'COOL',(50,272),ppem=200,glyphs=final)
    font_data=TTFont(CONNECTED)
    outline=font_data['glyf']['O.BG']
    ink_left,ink_right=outline.xMin*.2,outline.xMax*.2
    font_data.close()
    ss=3
    overlay=Image.new('RGBA',(image.width*ss,image.height*ss),(0,0,0,0))
    draw=ImageDraw.Draw(overlay)
    for positions,top in [(before_edges,78),(edges,272)]:
        start,end=positions[1]+ink_right,positions[2]+ink_left
        y=top+200*.475/2
        intervals=math.ceil((end-start)/7)
        for i in range(intervals+1):
            x=start+(end-start)*i/intervals
            draw.ellipse(((x-1.5)*ss,(y-1.5)*ss,(x+1.5)*ss,(y+1.5)*ss),fill='#dc3636')
    overlay=overlay.resize(image.size,Image.LANCZOS)
    image=Image.alpha_composite(image.convert('RGBA'),overlay).convert('RGB')
    write_png('06b-cool-spacing',image)
    register('06b-cool-spacing','Optical spacing in COOL',
             'Before and after the OO pair-spacing adjustment. Only the first O’s advance changes, from 950 to 830 font units: the second O moves 24 design pixels closer. Red dotted lines span the gold-to-gold gap in both rows. Colors, glyph forms, and the other pair adjustments stay fixed.')


def lazy():
    frames=[]
    for label,path in [('Earlier tapered connectors',TAPERED),('Full strokes overlapping',CONNECTED)]:
        image=canvas(height=540)
        text(image,(30,22),label,23,bold=True)
        gs=shaped(path,'LAZY')
        edges=word(image,'LAZY',(105,84),ppem=170,path=path,glyphs=gs)
        panel=render(path,gs,170,800,83)
        for i,pair in enumerate(['LA','AZ','ZY']):
            x=30+i*300
            center=round(edges[i+1]-105)
            crop=panel.crop((center-32,0,center+32,80))
            text(image,(x,206),pair,21,bold=True)
            image.paste(crop.resize((208,260),Image.NEAREST),(x,252))
        frames.append(image)
    animation('07-lazy-overlaps',frames)
    write_png('07-lazy-overlaps',stack(frames))
    register('07-lazy-overlaps','Let the strokes meet: LAZY',
             'Actual earlier tapered font versus the finished full-stroke overlaps. Enlargements show the LA, AZ, and ZY intersections.',True)


def hairlines():
    from verify_connected_seams import plane_error
    candidates=[]
    for value in ['AH','HH','OO','CA','AD','CD']:
        for phase in [.125,.375,.625,.875]:
            for ppem in [52,92,127]:
                gs=shaped(HAIRLINES,value)
                sample=render(HAIRLINES,gs,ppem,400,math.ceil(ppem*.475)+2,phase=phase)
                edge=gs[0]['advance']*ppem/1000+phase
                y=math.floor(ppem*.2375)
                error=max(plane_error(sample.getpixel((x,y))) for x in range(math.floor(edge)-1,math.floor(edge)+2))
                candidates.append((error,value,phase,ppem))
    error,value,phase,ppem=max(candidates)
    assert error>8,('historical hairline gap not reproduced',error)
    image=canvas(height=810)
    details=[]
    for i,(label,path) in enumerate([('Before join fix',HAIRLINES),('After join fix',CONNECTED)]):
        y0=i*405
        text(image,(30,y0+20),label,23,bold=True)
        gs=shaped(path,value)
        small=render(path,gs,ppem,350,math.ceil(ppem*.475)+2,phase=phase)
        edge=gs[0]['advance']*ppem/1000+phase
        y=math.floor(ppem*.2375)
        crop=small.crop((math.floor(edge)-10,y-7,math.floor(edge)+10,y+7))
        text(image,(30,y0+78),'Normal size: '+value,20)
        image.paste(small,(30,y0+125))
        text(image,(420,y0+78),'Pixel magnification',20)
        image.paste(crop.resize((420,294),Image.NEAREST),(420,y0+110))
        ImageDraw.Draw(image).rectangle((30+math.floor(edge)-10,y0+125+y-7,
                                        30+math.floor(edge)+10,y0+125+y+7),outline=MUTED,width=1)
        details.append(dict(label=label,pair=value,ppem=ppem,phase=phase,
                            plane_error=round(max(plane_error(small.getpixel((k,y))) for k in range(math.floor(edge)-1,math.floor(edge)+2)),4)))
    assert details[1]['plane_error']<=8,details
    write_png('08-hairlines',image)
    register('08-hairlines','A hairline between perfectly touching shapes',
             'Same text, %d px/em, and %.3f px horizontal origin before and after fixing the hairline gap. Nearest-neighbor enlargements preserve the individual pixels.'%(ppem,phase))
    return details


def text_demo():
    value='HELLO JAMAICA'
    ppem=120
    first_top=82
    second_top=first_top+ppem*.475*1.5
    frames=[];durations=[]
    for length in [1,2,3,5,6,7,8,9,10,11,12,13]:
        current=value[:length]
        image=canvas(height=427)
        text(image,(30,18),'Typing',23,bold=True)
        parts=current.split(' ')
        word(image,parts[0],(30,first_top),ppem=ppem)
        if len(parts)>1: word(image,parts[1],(30,second_top),ppem=ppem)
        text(image,(30,298),'Underlying characters',18,color=MUTED)
        text(image,(30,336),current,26,mono=True)
        frames.append(image);durations.append(240)
    durations[-1]=1600
    selected=frames[-1].copy()
    ImageDraw.Draw(selected).rectangle((20,10,880,56),fill=BG)
    text(selected,(30,18),'Select the text',23,bold=True)
    overlay=Image.new('RGBA',selected.size,(0,0,0,0))
    for val,y in [('HELLO',first_top),('JAMAICA',second_top)]:
        end=30+sum(g['advance'] for g in shaped(CONNECTED,val))*ppem/1000
        ImageDraw.Draw(overlay).rectangle((29,y-3,round(end),y+60),fill=(76,120,200,65))
    selected=Image.alpha_composite(selected.convert('RGBA'),overlay).convert('RGB')
    frames.append(selected);durations.append(1800)
    copied=selected.copy()
    painter=ImageDraw.Draw(copied)
    painter.rectangle((20,10,880,56),fill=BG)
    text(copied,(30,18),'Copy into ordinary text',23,bold=True)
    painter.rectangle((20,280,880,412),fill=BG)
    painter.rectangle((30,287,870,397),outline=RULE,width=2)
    text(copied,(48,302),'Copied text',18,color=MUTED)
    text(copied,(48,338),value,26,mono=True)
    frames.append(copied);durations.append(2600)
    animation('09-still-text',frames,durations)
    write_png('09-still-text',copied)
    register('09-still-text','Different glyphs. The same text.',
             'Illustrated typing, selection, and copy sequence, rendered from actual HarfBuzz-shaped text. The gap between HELLO and JAMAICA is half a flag’s height. This is an illustration rather than a browser recording.',True)


def documentation(seams):
    inputs=[MAIN,CONNECTED,TAPERED,HAIRLINES,SRC/'geometry.py']
    manifest=dict(background=BG,max_width=W,headings_and_subheadings='HTML and Markdown text outside the images',
                  typing_line_metrics={'flag_height_px':57,'top_to_top_px':85.5,'visible_gap_px':28.5},
                  renderer='HarfBuzz + FreeType; SVG contours for the R construction preview',
                  inputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                  hairline_comparison=seams,assets=ASSETS)
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    body=[]
    for asset in ASSETS:
        stem=asset['stem'];links='<a href="%s.png">PNG</a>'%stem
        if asset['gif']: links+=' · <a href="%s.gif">GIF</a>'%stem
        body.append('<section><h2>'+html.escape(asset['title'])+'</h2><p>'+html.escape(asset['caption'])+'</p><p>'+links+'</p><img loading="lazy" src="'+stem+('.gif' if asset['gif'] else '.png')+'" alt="'+html.escape(asset['caption'],quote=True)+'"></section>')
    (OUT/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Jamaican Flag Fonts — blog figures</title><style>body{background:'+BG+';color:'+INK+';font:18px/1.5 system-ui,sans-serif;margin:32px auto;max-width:900px;padding:0 20px}section{margin:56px 0}img{width:100%;height:auto;display:block}a{color:#17623a}</style><h1>Blog figures</h1><p>Each image is at most 900 pixels wide, with background '+BG+'. Headings and captions are text outside the images; embedded text labels individual states and callouts.</p>'+''.join(body)+'</html>')
    rows=['# Blog figures','', 'Open [the gallery](index.html) to review the assets. All figures are 900 pixels wide with background `'+BG+'`. Headings and subheadings are provided as text outside the images.','', '| Figure | Static comparison | Animation |','| --- | --- | --- |']
    for asset in ASSETS:
        stem=asset['stem']
        rows.append('| '+asset['title']+' | [PNG]('+stem+'.png) | '+('[GIF]('+stem+'.gif)' if asset['gif'] else '—')+' |')
    rows+=['','## Headings and captions','']
    for asset in ASSETS: rows+=['### '+asset['title'],'',asset['caption'],'']
    rows+=['## Regenerate','','From the repository root:','','```sh','python3 src/generate_blog_assets.py','```','','Uses the project’s Python dependencies, DejaVu Sans/Mono system fonts, HarfBuzz, a C compiler, `pkg-config`, and FreeType development headers. The native renderer is compiled in a temporary directory with the requested background color.','', '## Comparison sources','', 'The snapshots in [assets/reference-fonts/](../../assets/reference-fonts/) preserve the actual earlier tapered connections and the rendering before seam protection. Current font inputs come from [fonts/](../../fonts/). [manifest.json](manifest.json) records input hashes and hairline settings.','', 'R expands the bowl helper into its actual gold and green paint calls. The first two steps preview the defined paths as outlines; the subsequent frames perform each paint operation separately in source order. JAMAICA holds geometry and spacing fixed while changing colors. RELAXED holds colors fixed: the before state uses uniform six-design-pixel gaps with incoming join/overlap forms omitted, while the after state uses the complete shaping result. COOL changes only the OO pair’s advance, keeping colors, glyph forms, and the other pair adjustments fixed. LAZY compares historical and current font files. Hairlines use identical text, size, and fractional origin.','', 'The typing/selection/copy animation is an illustrated sequence rather than a browser recording.','', 'The artwork is based on [u/VelvetOnion’s alphabet](https://www.reddit.com/r/vexillologycirclejerk/s/Bqage66kXN); see the project [credits](../../README.md#credits).','']
    (OUT/'README.md').write_text('\n'.join(rows))
    thumbs=[]
    for asset in ASSETS:
        im=Image.open(OUT/(asset['stem']+'.png')).convert('RGB')
        im.thumbnail((420,560),Image.LANCZOS)
        thumbs.append(im)
    contact=Image.new('RGB',(900,math.ceil(len(thumbs)/2)*590),BG)
    for i,im in enumerate(thumbs): contact.paste(im,(15+(i%2)*450,15+(i//2)*590))
    contact.save(OUT/'overview.png',optimize=True)


def main():
    global TEMP,BINARY
    OUT.mkdir(parents=True,exist_ok=True)
    for path in [MAIN,CONNECTED,TAPERED,HAIRLINES]:
        if not path.exists(): raise FileNotFoundError(path)
    with tempfile.TemporaryDirectory(prefix='jamaican-blog-') as directory:
        TEMP=Path(directory)
        source=(SRC/'render_connected_native.c').read_text()
        source=source.replace('memset(canvas,255,length);','for (size_t i=0;i<length;i+=3) { canvas[i]=241; canvas[i+1]=241; canvas[i+2]=230; }')
        cfile=TEMP/'render.c';cfile.write_text(source)
        BINARY=TEMP/'render'
        cflags=subprocess.check_output(['pkg-config','--cflags','freetype2'],text=True).split()
        libs=subprocess.check_output(['pkg-config','--libs','freetype2'],text=True).split()
        subprocess.run(['cc',*cflags,str(cfile),'-o',str(BINARY),*libs,'-lm'],check=True)
        for fn in [r_definition,letter_forms,variants,color_matching,exceptions,relaxed,cool,lazy]:
            fn();print(fn.__name__,flush=True)
        seams=hairlines();print('hairlines',seams,flush=True)
        text_demo();documentation(seams)
    print('Wrote %d figures, animations, gallery, and manifest to %s'%(len(ASSETS),OUT),flush=True)


if __name__=='__main__': main()
