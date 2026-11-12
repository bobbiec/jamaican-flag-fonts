#!/usr/bin/env python3
"""Verify COLR rendering with FreeType."""
import json
import argparse
from pathlib import Path
import subprocess
import tempfile
from PIL import Image, ImageDraw
from fontTools.ttLib import TTFont
from verify_connected import edge_error,SPACING
from hb_shaping import Shaper
from connected_spacing import STROKE_OVERLAPS

from paths import SRC, FONTS, METADATA, PREVIEWS


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--before-font',type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='connected-native-') as directory:
        binary=Path(directory)/'render'
        output=Path(directory)/'preview.ppm'
        cflags=subprocess.check_output(['pkg-config','--cflags','freetype2'],text=True).split()
        libs=subprocess.check_output(['pkg-config','--libs','freetype2'],text=True).split()
        subprocess.run(['cc',*cflags,str(SRC/'render_connected_native.c'),'-o',str(binary),*libs,'-lm'],check=True)
        font=TTFont(FONTS/'JamaicanConnected.ttf')
        names=[c+'.'+state for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' for state in ['BG','GB','BB','GG']]
        layout=['880 3118 104']
        for i,name in enumerate(names):
            layout.append('%d %d %d' % (font.getGlyphID(name),24+(i%4)*214,24+(i//4)*119))
        subprocess.run([str(binary),str(FONTS/'JamaicanConnected.ttf'),str(output)],
                       input='\n'.join(layout),text=True,check=True)
        image=Image.open(output).convert('RGB')
        count=0
        for i,name in enumerate(names):
            x0,y0=24+(i%4)*214,24+(i//4)*119
            for x,expected in [(0,0 if name[0]=='X' or name[-2]=='B' else 1),(189,0 if name[0]=='X' or name[-1]=='B' else 1)]:
                for y in range(95):
                    pixel=image.getpixel((x0+x,y0+y))
                    if edge_error(pixel,expected)>4:
                        # Permit outer-edge gold/page antialiasing while
                        # checking the adjacent interior pixel’s opacity.
                        c=SPACING['ink_metrics'][name[0]]['corners']
                        gold_cap=x==0 and (y<c['left_top'] or y>=95-c['left_bottom'])
                        white_gold=(abs(pixel[0]-255)<=4 and abs(pixel[1]-(209+46*pixel[2]/255))<=4)
                        assert gold_cap and white_gold,(name,x,y,pixel)
                        assert edge_error(image.getpixel((x0+1,y0+y)),expected)<=4,(name,'interior',y)
                    count+=1
        proof_letters='XBIWOCNTLJ'
        proof=Image.new('RGB',(880,len(proof_letters)*119+24),'#f8f6ef')
        draw=ImageDraw.Draw(proof)
        for row,c in enumerate(proof_letters):
            source_row='ABCDEFGHIJKLMNOPQRSTUVWXYZ'.index(c)
            for col,state in enumerate(['BG','GB','BB','GG']):
                x,y=24+col*214,24+row*119
                proof.paste(image.crop((x,24+source_row*119,x+190,119+source_row*119)),(x,y))
                draw.text((x,y-14),c+' / '+state[0]+' TO '+state[1],fill='black')
        proof.save(PREVIEWS/'connected/native-variant-proof.png')
        def color_at(c,state,point):
            col=['BG','GB','BB','GG'].index(state)
            row='ABCDEFGHIJKLMNOPQRSTUVWXYZ'.index(c)
            return image.getpixel((24+col*214+point[0],24+row*119+point[1]))
        for state in ['BG','GB','BB','GG']:
            for point in [(95,10),(95,85)]:
                assert color_at('X',state,point)==(0,155,57),('X green',state,point)
            for point in [(8,47),(182,47)]:
                assert color_at('X',state,point)==(0,0,0),('X black',state,point)
            expected=(0,155,57) if state=='BB' else (0,0,0)
            for c,point in [('B',(80,28)),('B',(80,68)),('O',(95,47)),('P',(80,32))]:
                assert color_at(c,state,point)==expected,(c,state,point)
            for point in [(33,8),(156,8),(33,86),(156,86)]:
                assert color_at('I',state,point)==(255,209,0)
            for y in range(5,90):
                for x in range(45,146):
                    assert edge_error(color_at('N',state,(x,y)),1 if state=='BB' else 0)<=4,('N stripe',state,x,y)
        for state,colors in [('BB',[0,1,0,1,0]),('GG',[1,0,1,0,1])]:
            coords=[(8,75),(48,20),(95,75),(143,20),(182,75)]
            palette=[(0,0,0),(0,155,57)]
            assert [color_at('W',state,p) for p in coords]==[palette[i] for i in colors]
        shaper=Shaper(FONTS/'JamaicanConnected.ttf')
        pairs=['CA','AD','CD','CE','EF','FE','KE','XZ','GA','CG','HH','OO','BIW','WAW']
        placements=[]
        labels=[]
        for row,text in enumerate(pairs):
            for col,kern in enumerate([True,False]):
                x,y=24+col*650,24+row*119
                labels.append((x,y-14,text+' / KERN '+('ON' if kern else 'OFF')))
                pen=x*5
                for g in shaper.shape(text,kern=kern):
                    placements.append('%d %d %d' % (font.getGlyphID(g['name']),round(pen/5),y))
                    pen+=g['advance']
        layout=['1300 %d %d' % (len(pairs)*119+24,len(placements))]+placements
        subprocess.run([str(binary),str(FONTS/'JamaicanConnected.ttf'),str(output)],
                       input='\n'.join(layout),text=True,check=True)
        kern_image=Image.open(output).convert('RGB')
        # Verify the selected gold join and the open opposite corner.
        for pair in ['CA','AD','CD','CE','XZ','GA']:
            y=24+pairs.index(pair)*119
            assert all(kern_image.getpixel((x,y+92))==(255,209,0) for x in range(215,219)),pair
        for pair in ['CD','CE','XZ']:
            y=24+pairs.index(pair)*119
            background=(0,0,0) if pair[0]=='X' else (0,155,57)
            assert all(kern_image.getpixel((x,y+3))==background for x in range(216,219)),(pair,'top must stay open')
        for pair in ['EF','FE','KE']:
            y=24+pairs.index(pair)*119
            assert all(kern_image.getpixel((x,y+1))==(255,209,0) for x in range(215,219)),pair
            assert all(kern_image.getpixel((x,y+92))==(0,155,57) for x in range(216,219)),(pair,'bottom must stay open')
        # Continued strokes retain their full thickness at the join.
        assert kern_image.getpixel((214,24+81))==(255,209,0),'CA stroke'
        assert kern_image.getpixel((219,24+119+81))==(255,209,0),'AD stroke'
        # C/G spacers retain the outgoing background color.
        for row in [pairs.index(pair) for pair in ['CA','CD','CE','GA','CG']]:
            assert all(kern_image.getpixel((x,24+row*119+45))==(0,155,57)
                       for x in range(214,220)),('C/G spacer',row)
        draw=ImageDraw.Draw(kern_image)
        for x,y,label in labels: draw.text((x,y),label,fill='black')
        kern_image.save(PREVIEWS/'connected/native-kerning-proof.png')
        shaper.close()
        examples=['VE','LAZY','AB','AD','AE','AS','WB','XB','CA','AV','WV','AA','KE','XZ']
        sources=[args.before_font,FONTS/'JamaicanConnected.ttf'] if args.before_font else [FONTS/'JamaicanConnected.ttf']
        height=len(examples)*119+24
        comparison=Image.new('RGB',(900*len(sources),height),'white')
        captions=[]
        for col,source in enumerate(sources):
            example_font=TTFont(source)
            example_shaper=Shaper(source)
            placements=[]
            for row,text in enumerate(examples):
                x,y=24,24+row*119
                captions.append((24+col*900,y-14,text+' / '+('BEFORE' if args.before_font and col==0 else 'AFTER')))
                pen=x*5
                for glyph in example_shaper.shape(text):
                    placements.append('%d %.6f %.6f' % (example_font.getGlyphID(glyph['name']),pen/5,y))
                    pen+=glyph['advance']
            layout=['900 %d %d'%(height,len(placements))]+placements
            subprocess.run([str(binary),str(source),str(output)],input='\n'.join(layout),text=True,check=True)
            panel=Image.open(output).convert('RGB')
            if col==len(sources)-1:
                gold=(255,209,0)
                assert panel.getpixel((24+182,24+17))==gold,'VE retains V below E’s bar'
                assert panel.getpixel((24+184,143+80))==gold,'LA retains L’s foot in A’s cell'
                assert panel.getpixel((24+362,143+75))==gold,'AZ retains A’s diagonal in Z’s cell'
                assert panel.getpixel((24+538,143+16))==gold,'ZY retains Z’s diagonal in Y’s cell'
            comparison.paste(panel,(col*900,0))
            example_font.close()
            example_shaper.close()
        draw=ImageDraw.Draw(comparison)
        for x,y,label in captions: draw.text((x,y),label,fill='black')
        comparison.crop((0,0,comparison.width,262)).save(PREVIEWS/'connected/pair-refinements.png')
        corners=Image.new('RGB',(425*len(sources),height-238),'white')
        for col in range(len(sources)):
            corners.paste(comparison.crop((col*900,238,col*900+425,height)),(col*425,0))
        corners.save(PREVIEWS/'connected/corner-overlaps.png')
        path=METADATA/'connected/verification.json'
        report=json.loads(path.read_text())
        report['native_freetype']={'variants_checked':104,'edge_pixels_checked':count,
            'pixel_mode':'BGRA','pixels_per_em':200,'result':'passed',
            'dark_counters':True,'I_crossbars':True,'W_alternation':True,
            'kerning_comparisons':len(pairs),'GA_corner_bridge':True,'C_G_spacers_clean':True,
            'CA_AD_full_strokes':True,'single_corner_only':True,'K_upper_arm_join':True,
            'stroke_overlaps':STROKE_OVERLAPS,'full_gold_strokes':True}
        path.write_text(json.dumps(report,indent=2)+'\n')
        print('Native FreeType: verified 104 COLR variants and %d side-edge pixels.' % count)


if __name__=='__main__':
    main()
