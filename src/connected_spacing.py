"""Derive optical pair spacing and corner joins from gold geometry.

Positive adjustments carry the shared background color. Trailing margins
bound the amount of safe tightening."""
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.svgLib.path import parse_path

STROKE_OVERLAPS = {'VE': 8, 'LA': 8, 'AZ': 12, 'ZY': 14.2}
STROKE_CORNERS = {'VE': 'top', 'LA': 'bottom', 'AZ': 'bottom', 'ZY': 'top'}


class Contours(BasePen):
    def __init__(self):
        super().__init__(None)
        self.contours=[]
        self.points=[]
    def _moveTo(self,p): self.points=[p]
    def _lineTo(self,p): self.points.append(p)
    def _curveToOne(self,a,b,end):
        start=self._getCurrentPoint()
        for i in range(1,33):
            t=i/32
            self.points.append(tuple((1-t)**3*start[j]+3*(1-t)**2*t*a[j]+3*(1-t)*t*t*b[j]+t**3*end[j] for j in [0,1]))
    def _closePath(self): self.contours.append(self.points)
    def _endPath(self): self._closePath()


def inside(point,poly):
    x,y=point
    result=False
    for (ax,ay),(bx,by) in zip(poly,poly[1:]+poly[:1]):
        if (ay>y)!=(by>y) and x<(bx-ax)*(y-ay)/(by-ay)+ax:
            result=not result
    return result


def area(poly):
    return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1]))/2


def gold_metrics(paths):
    pen,bounds=Contours(),BoundsPen(None)
    for path in paths:
        parse_path(path,pen)
        parse_path(path,bounds)
    polygons=[(poly,1 if area(poly)>0 else -1) for poly in pen.contours]
    def gold(x,y):
        return sum(sign for poly,sign in polygons if inside((x,y),poly))!=0
    corners,anchors={},{}
    def band_height(x,reverse):
        count=0
        for i in range(380):
            y=94.875-i*.25 if reverse else .125+i*.25
            if not gold(x,y): break
            count+=1
        return count*.25
    for side,x in [('left',.1),('right',189.9)]:
        for corner,reverse in [('top',False),('bottom',True)]:
            height=band_height(x,reverse)
            anchor=0 if side=='left' else 190
            # Anchor pointed strokes inside the cell, where they have width.
            if height<2:
                for inset in [2,4,6,8,10]:
                    trial=x+inset if side=='left' else x-inset
                    height=band_height(trial,reverse)
                    if height>=2:
                        anchor=inset if side=='left' else 190-inset
                        break
            key=side+'_'+corner
            corners[key]=height if height>=2 else 0
            anchors[key]=anchor
    return {'bounds':list(bounds.bounds),'corners':corners,'anchors':anchors}


def corner_profile(paths,side,corner,anchor):
    """Measure the straight inner edge of a stroke entering a flag corner."""
    pen=Contours()
    for path in paths: parse_path(path,pen)
    polygons=[(poly,1 if area(poly)>0 else -1) for poly in pen.contours]
    def height(x):
        crossings=[0,95]
        for poly,_ in polygons:
            for a,b in zip(poly,poly[1:]+poly[:1]):
                if min(a[0],b[0])<x<max(a[0],b[0]):
                    crossings.append(a[1]+(x-a[0])*(b[1]-a[1])/(b[0]-a[0]))
        distances=sorted(set(round(y if corner=='top' else 95-y,6) for y in crossings if 0<=y<=95))
        for a,b in zip(distances,distances[1:]):
            y=(a+b)/2 if corner=='top' else 95-(a+b)/2
            if not sum(sign for poly,sign in polygons if inside((x,y),poly)):
                return a
        return 95
    inward=1 if side=='left' else -1
    x1,x2=anchor+inward,anchor+2*inward
    h1,h2=height(x1),height(x2)
    slope=(h2-h1)/(x2-x1)
    return {'height':round(h1+slope*(anchor-x1),6),'slope':round(slope,6),'anchor':anchor}


def spacing_plan(designs):
    metrics={c:gold_metrics(d['gold']) for c,d in designs.items()}
    for c,m in metrics.items():
        m['profiles']={key:corner_profile(designs[c]['gold'],*key.split('_'),m['anchors'][key])
                       for key,height in m['corners'].items() if height}
    pairs={}
    for left,l in metrics.items():
        trailing=max(0,190-l['bounds'][2])
        for right,r in metrics.items():
            available={corner:min(l['corners']['right_'+corner],r['corners']['left_'+corner])
                   for corner in ['top','bottom']}
            chosen=('top' if left=='K' and available['top'] else
                    'bottom' if available['bottom'] else 'top' if available['top'] else None)
            overlap=STROKE_OVERLAPS.get(left+right,0)
            if overlap:
                chosen=STROKE_CORNERS[left+right]
            joins={corner:available[corner] if corner==chosen else 0 for corner in ['top','bottom']}
            stroke_join={corner: {'left_height':l['corners']['right_'+corner],
                            'right_height':r['corners']['left_'+corner],
                            'left_anchor':l['anchors']['right_'+corner],
                            'right_anchor':r['anchors']['left_'+corner],
                            'left_profile':l['profiles']['right_'+corner],
                            'right_profile':r['profiles']['left_'+corner]}
                   for corner in ['top','bottom'] if joins[corner]}
            if overlap:
                stroke_join={}
            gap=trailing+r['bounds'][0]
            if overlap:
                adjustment=-overlap
            elif any(joins.values()):
                # Six pixels open the other corner while full strokes connect.
                adjustment=6
            elif left in 'CG':
                adjustment=6
            else:
                adjustment=max(-min(24,max(0,trailing-1)), min(10,28-gap))
            units=round(adjustment*5)
            if units<0 and not overlap:
                units=max(units,-int(max(0,trailing-1)*5))
            pairs[left+right]={'units':units,'joins':joins,'available_joins':available,
                               'selected_corner':chosen,'stroke_join':stroke_join,'stroke_overlap':overlap}
    return metrics,pairs


def extension_key(pair):
    if pair.get('stroke_overlap'):
        return 'pad0_overlap%d' % round(pair['stroke_overlap']*5)
    # Every adjacent pair receives a rendering overlap.
    return 'pad%d_plain' % max(0,pair['units'])
