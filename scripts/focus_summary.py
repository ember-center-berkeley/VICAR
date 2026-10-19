"""Selective, temporally tracked focus treatment of the existing summary edit.

The Apple Vision mattes isolate the human; measured polygons retain the table,
object and contact graphics. Real robot footage retains its original background.
All coordinates refer to the 1080p edit.
"""
from pathlib import Path
from functools import lru_cache
import argparse, hashlib, json, shutil, subprocess
import numpy as np
from scipy.ndimage import minimum_filter, maximum_filter
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from focus_composite import soft_focus

# Working media and mattes live outside the published website.
P = None
FF = None
SOURCE = None
EXPECTED_SHA256 = '74ad3a21fc366d0461c6eb17dd78222cd817071a9006a66a9e4f41dfc1818f0a'
SIZE=(1920,1080)

HUMAN_PARTS = [
 [(640,644),(1300,644),(1300,818),(546,797),(545,744)],
 [(717,797),(757,800),(757,1080),(718,1080)],
 [(735,903),(1240,925),(1240,960),(740,931)],
 [(732,914),(863,800),(875,800),(742,923)],
 [(581,798),(677,802),(675,817),(579,812)],
 [(665,800),(684,801),(679,875),(679,884),(677,904),(672,915),(662,914),(657,900),(655,886),(660,876)],
 [(908,940),(933,942),(932,960),(926,971),(914,970),(909,961)],
 [(1095,802),(1134,804),(1134,1080),(1095,1080)],
 [(1020,815),(1050,815),(1120,915),(1100,927)],
]
# Frame, top center, bottom center, half width. Linear interpolation follows the
# small white pickup object where the subject segmenter cannot resolve it.
HUMAN_OBJECT = [
 (0,646,914,650,1010,17),(1140,646,914,650,1010,17),
 (1172,700,906,660,998,20),(1204,706,881,674,968,20),
 (1236,705,857,675,949,20),(1268,705,858,672,944,20),
 (1300,694,819,653,905,20),(1332,680,790,640,866,21),
 (1364,661,755,622,833,23),(1396,554,782,522,832,24),
 (1428,535,645,503,725,24),(1460,503,592,488,681,21),
 (1492,510,594,493,681,21),(1522,548,586,535,673,21),
 (1692,548,586,535,673,21),
]

def ease(v):
    v=max(0.,min(1.,v));return v*v*(3-2*v)

def rect(f):
    v=ease((f/60-1.1)/1.4)
    return tuple(round(a+(b-a)*v) for a,b in zip((0,0,1920,1080),(24,176,920,880)))

def mapped_human(pt,f):
    # Undo the fixed comparison crop, then apply the original opening zoom.
    v=ease((f/60-1.1)/1.4)
    x,y,w,h=rect(f)
    sx=560+(pt[0]-24)*1040/920;sy=(pt[1]-176)*996/880
    left=149+(560-149)*v;right=1920+(1600-1920)*v
    return ((sx-left)*w/(right-left),sy*h/996)

def object_poly(keys,f):
    vals=keys[-1][1:]
    for a,b in zip(keys,keys[1:]):
        if f<=b[0]:
            t=max(0,min(1,(f-a[0])/(b[0]-a[0])))
            vals=[x+(y-x)*t for x,y in zip(a[1:],b[1:])];break
    x1,y1,x2,y2,r=vals
    dx,dy=x2-x1,y2-y1;d=max(1,(dx*dx+dy*dy)**.5)
    nx,ny=-dy*r/d,dx*r/d;ex,ey=dx*6/d,dy*6/d
    return [(x1+nx-ex,y1+ny-ey),(x1-nx-ex,y1-ny-ey),
            (x2-nx+ex,y2-ny+ey),(x2+nx+ex,y2+ny+ey)]

@lru_cache(maxsize=12)
def raw_matte(f):
    result=Image.open(P/'masks'/f'{f:04d}.png').convert('L')
    if f<1644:
        foreground=Image.open(P/'foreground'/f'{f:04d}.png').convert('L').resize(result.size,Image.Resampling.BILINEAR)
        result=ImageChops.lighter(result,foreground)
    return result

def matte(f,wh):
    mf=min(1642,f//2*2)
    a=raw_matte(mf).resize(wh,Image.Resampling.BILINEAR)
    if f%2 and mf<1642:
        a=Image.blend(a,raw_matte(mf+2).resize(wh,Image.Resampling.BILINEAR),.5)
    # Eliminate low-confidence spill; retain a small safety edge around hair,
    # hands and shoes. The feather is narrow enough to avoid a cutout halo.
    a=a.point(lambda v:round(max(0,min(1,(v-160)/80))*255))
    # Remove thin background fragments misclassified beside the silhouette.
    opening=max(3,round(7*wh[0]/920)|1)
    a=Image.fromarray(maximum_filter(minimum_filter(np.asarray(a),size=opening,mode='nearest'),size=opening,mode='nearest'))
    return a

def focus(frame,f,save_mask=False):
    # Background defocus applies only while the human demonstration is visible.
    # Return the untouched source for the complete simulation/hardware section.
    if f>=1692:return frame
    x,y,w,h=rect(f);crop=frame.crop((x,y,x+w,y+h))
    a=matte(f,(w,h));manual=Image.new('L',(w,h));d=ImageDraw.Draw(manual)
    mapping=lambda pt:mapped_human(pt,f)
    for polygon in HUMAN_PARTS:
        d.polygon([mapping(pt) for pt in polygon],fill=255)
    d.polygon([mapping(pt) for pt in object_poly(HUMAN_OBJECT,f)],fill=255)
    a=ImageChops.lighter(a,manual)
    scale=w/920
    treated,alpha=soft_focus(crop,a,scale)
    # Original rounded-card antialiasing and white gutters remain untouched.
    panel=Image.new('L',(w*2,h*2));ImageDraw.Draw(panel).rounded_rectangle((0,0,w*2-1,h*2-1),radius=36*ease((f/60-1.1)/1.4),fill=255)
    panel=panel.resize((w,h),Image.Resampling.LANCZOS)
    if f<66:panel=Image.new('L',(w,h),255)
    frame.paste(treated,(x,y),panel)
    if save_mask:alpha.save(P/f'matte-{f:04}.png')
    return frame

def decode_frame(f):
    raw=subprocess.check_output([FF,'-v','error','-ss',str(f/60),'-i',str(SOURCE),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
    return Image.frombytes('RGB',SIZE,raw)

def main():
    global P, FF, SOURCE
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--work-dir',type=Path,required=True)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--ffmpeg',default=shutil.which('ffmpeg'))
    ap.add_argument('--preview',action='store_true')
    args=ap.parse_args()
    P=args.work_dir.resolve();SOURCE=args.source.resolve();FF=args.ffmpeg
    if not FF:ap.error('Pass --ffmpeg /path/to/ffmpeg or install ffmpeg.')
    if not args.preview and not args.output:ap.error('--output is required for rendering.')
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=EXPECTED_SHA256:
        ap.error('This focus map is calibrated to the 3598-frame summary at commit 43d90d7. Use that original as --source.')
    P.mkdir(parents=True,exist_ok=True)
    if args.preview:
        for f in (0,120,300,1020,1172,1236,1332,1396,1428,1460,1522,1642,2880,3000,3100,3240,3596):
            original=decode_frame(f);result=focus(original.copy(),f,True)
            result.save(P/f'after-{f:04}.jpg',quality=95)
        return
    output=args.output.resolve()
    if output==SOURCE:ap.error('Keep the input as an unmodified backup; choose another output path.')
    reader=subprocess.Popen([FF,'-v','error','-i',str(SOURCE),'-an','-pix_fmt','rgb24','-f','rawvideo','-threads','2','-'],stdout=subprocess.PIPE)
    writer=subprocess.Popen([FF,'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','60','-i','-',
        '-i',str(SOURCE),'-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','medium','-crf','20','-maxrate','2500k','-bufsize','5000k','-threads','4',
        '-pix_fmt','yuv420p','-c:a','copy','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-movflags','+faststart',str(output)],stdin=subprocess.PIPE)
    count=0
    try:
        while True:
            raw=reader.stdout.read(1920*1080*3)
            if not raw:break
            assert len(raw)==1920*1080*3
            writer.stdin.write(focus(Image.frombytes('RGB',SIZE,raw),count).tobytes())
            count+=1
            if count%300==0:print(f'Rendered {count}/3598',flush=True)
    finally:
        reader.stdout.close();writer.stdin.close()
    assert reader.wait()==0 and writer.wait()==0 and count==3598
    print(f'{output}: {count} frames; {output.stat().st_size/1e6:.2f} MB',flush=True)

if __name__=='__main__':main()
