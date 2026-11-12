/* Optional native COLR rendering check. Build with pkg-config freetype2.
 * argv: font.ttf output.ppm [pixels_per_em]; stdin: width height count,
 * then glyph_id x top_y (positions may have fractional pixels).
 * The default 200px/em makes a flag exactly 190 by 95 pixels.
 */
#include <ft2build.h>
#include FT_FREETYPE_H
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
int main(int argc, char **argv) {
    FT_Library library;
    FT_Face face;
    int width, height, count;
    if ((argc!=3 && argc!=4) || scanf("%d %d %d", &width, &height, &count)!=3) return 1;
    if (width<=0 || height<=0 || width>10000 || height>10000 || count<0) return 2;
    if (FT_Init_FreeType(&library) || FT_New_Face(library, argv[1], 0, &face)) return 3;
    int ppem=argc==4 ? atoi(argv[3]) : 200;
    if (ppem<1 || ppem>2000 || FT_Set_Pixel_Sizes(face, 0, ppem)) return 4;
    size_t length=(size_t)width*height*3;
    unsigned char *canvas=malloc(length);
    if (!canvas) return 5;
    memset(canvas,255,length);
    for (int i=0;i<count;i++) {
        unsigned int glyph_id;
        double origin_x, origin_y;
        if (scanf("%u %lf %lf", &glyph_id, &origin_x, &origin_y)!=3) return 6;
        double baseline=origin_y+ppem*.475;
        int whole_x=(int)floor(origin_x), whole_y=(int)floor(baseline);
        FT_Vector delta={(FT_Pos)lround((origin_x-whole_x)*64),
                         (FT_Pos)-lround((baseline-whole_y)*64)};
        FT_Set_Transform(face,NULL,&delta);
        if (FT_Load_Glyph(face,glyph_id,FT_LOAD_COLOR|FT_LOAD_RENDER)) return 7;
        FT_Bitmap *bm=&face->glyph->bitmap;
        if (!bm->rows || !bm->width) continue;
        if (bm->pixel_mode!=FT_PIXEL_MODE_BGRA) return 8;
        int x0=whole_x+face->glyph->bitmap_left;
        int y0=whole_y-face->glyph->bitmap_top;
        for (unsigned int y=0;y<bm->rows;y++) for (unsigned int x=0;x<bm->width;x++) {
            int dx=x0+x,dy=y0+y;
            if (dx<0||dy<0||dx>=width||dy>=height) continue;
            unsigned char *p=bm->buffer+y*bm->pitch+x*4;
            unsigned char *d=canvas+((size_t)dy*width+dx)*3;
            for (int c=0;c<3;c++) d[c]=p[2-c]+(d[c]*(255-p[3])+127)/255;
        }
    }
    FILE *output=fopen(argv[2],"wb");
    if (!output) return 9;
    fprintf(output,"P6\n%d %d\n255\n",width,height);
    if (fwrite(canvas,1,length,output)!=length) return 10;
    fclose(output);
    free(canvas);
    FT_Done_Face(face);
    FT_Done_FreeType(library);
    return 0;
}
