"""Clip background paint beneath solid gold caps for clean layer compositing.

The corner cutouts preserve the outgoing gold color through the incoming
glyph's antialiased edge."""
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.svgLib.path import parse_path
from geometry import polygon


def stroke_continuations(spec):
    """Continue both corner strokes to their natural intersection at full width."""
    corner,values=next(iter(spec['stroke_join'].items()))
    origin=190+spec['units']/5
    left,right=values['left_profile'],values['right_profile']
    lm,rm=left['slope'],right['slope']
    lb=left['height']-lm*left['anchor']
    rb=right['height']-rm*(origin+right['anchor'])
    intersection=(rb-lb)/(lm-rm) if abs(lm-rm)>1e-6 else (190+origin)/2
    # Each continuation ends where the other full stroke takes over.
    paths=[]
    for start,end,slope,intercept in [(182,max(origin,intersection),lm,lb),
                                      (min(190,intersection),origin+8,rm,rb)]:
        points=[(start,0),(end,0),(end,slope*end+intercept),(start,slope*start+intercept)]
        points=clip(clip(points,1,0,1),1,95,-1)
        if corner=='bottom': points=[(x,95-y) for x,y in reversed(points)]
        points=[(x-origin,y) for x,y in points]
        if len(points)>=3 and abs(area(points))>.001: paths.append(polygon(points))
    return paths


def clip(points,axis,edge,sign):
    result=[]
    for a,b in zip(points,points[1:]+points[:1]):
        a_in=(a[axis]-edge)*sign>=0
        b_in=(b[axis]-edge)*sign>=0
        if a_in: result.append(a)
        if a_in!=b_in:
            t=(edge-a[axis])/(b[axis]-a[axis])
            result.append(tuple(a[i]+t*(b[i]-a[i]) for i in [0,1]))
    return result


def area(points):
    return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))/2


def cut_corner(path,width,height,bottom):
    bounds=BoundsPen(None)
    parse_path(path,bounds)
    x0,y0,x1,y1=bounds.bounds
    if x0>=width or (y1<=95-height if bottom else y0>=height):
        return [path]
    recording=RecordingPen()
    parse_path(path,recording)
    contours=[]
    points=[]
    for op,args in recording.value:
        if op=='moveTo': points=[args[0]]
        elif op=='lineTo': points.append(args[0])
        elif op in ['closePath','endPath']: contours.append(points)
        else: raise ValueError('A corner knockout unexpectedly intersects a curved background')
    result=[]
    for points in contours:
        right=clip(points,0,width,1)
        left=clip(points,0,width,-1)
        left=clip(left,1,95-height if bottom else height,-1 if bottom else 1) if left else []
        for shape in [right,left]:
            if len(shape)>=3 and abs(area(shape))>.001:
                result.append(polygon(shape))
    return result


def protect_gold_caps(layers,metrics,overlap):
    result=[]
    for color,paths in layers:
        if color==2:
            result.append((color,paths))
            continue
        paths=[paths] if isinstance(paths,str) else paths
        for corner in ['top','bottom']:
            # Leave a margin underneath the gold's real antialiased inner edge.
            height=metrics['corners']['left_'+corner]-2
            if height<=0 or metrics['anchors']['left_'+corner]!=0: continue
            paths=[piece for path in paths for piece in cut_corner(path,overlap,height,corner=='bottom')]
        if paths: result.append((color,paths))
    return result


def leading_background(layers,width):
    """Share the leading field with the previous glyph while retaining gold."""
    result=[]
    for color,paths in layers:
        if color==2:
            result.append((color,paths))
            continue
        paths=[paths] if isinstance(paths,str) else paths
        clipped=[]
        for path in paths:
            bounds=BoundsPen(None)
            parse_path(path,bounds)
            if bounds.bounds[0]>=width:
                clipped.append(path)
                continue
            recording=RecordingPen()
            parse_path(path,recording)
            points=[]
            for op,args in recording.value:
                if op=='moveTo': points=[args[0]]
                elif op=='lineTo': points.append(args[0])
                elif op in ['closePath','endPath']:
                    shape=clip(points,0,width,1)
                    if len(shape)>=3 and abs(area(shape))>.001:
                        clipped.append(polygon(shape))
                else: raise ValueError('A leading overlap intersects a curved background')
        if clipped: result.append((color,clipped))
    return result
