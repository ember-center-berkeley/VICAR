"""Apply soft background focus to the synchronized 480x800 ladder hero clip."""
from pathlib import Path
from functools import lru_cache
import argparse,hashlib,shutil,subprocess
import numpy as np
from scipy.ndimage import minimum_filter,maximum_filter
from PIL import Image,ImageDraw,ImageChops
from focus_composite import soft_focus

EXPECTED_SHA256='52eac8cee9f839ab79538d33e0174e3b15d8906f3cc44bc4dc71cdd1507114b4'
SIZE=(480,800)
P=None
# The ladder is static. Trace its rails and rungs individually so that the lab
# stays defocused through the openings instead of retaining a sharp triangle.
LADDER_PARTS=[
 [(265,255),(300,245),(327,250),(327,269),(266,275)],
 [(265,274),(282,274),(143,670),(125,667)],
 [(290,272),(311,272),(207,708),(181,706)],
 [(311,271),(326,269),(412,667),(397,671)],
 [(285,278),(293,280),(333,630),(321,634)],
 [(239,326),(275,328),(272,339),(236,338)],
 [(211,397),(259,400),(256,410),(210,407)],
 [(180,468),(238,475),(235,487),(179,480)],
 [(158,540),(218,551),(215,562),(155,550)],
 [(144,610),(199,633),(196,648),(140,624)],
 [(291,346),(335,345),(337,355),(291,356)],
 [(297,403),(348,405),(350,415),(298,413)],
 [(305,468),(364,474),(367,484),(306,478)],
 [(315,531),(379,541),(381,550),(316,541)],
 [(324,589),(395,607),(396,618),(324,600)],
 [(127,658),(147,660),(142,681),(120,687),(117,679)],
 [(182,705),(209,704),(205,736),(182,743),(174,736)],
 [(322,624),(338,624),(341,645),(330,651),(322,645)],
 [(396,663),(413,663),(423,688),(407,692),(399,686)],
]

@lru_cache(maxsize=8)
def mask(f):
    person=Image.open(P/'masks'/f'{f:04d}.png').convert('L').resize(SIZE,Image.Resampling.BILINEAR)
    foreground=Image.open(P/'foreground'/f'{f:04d}.png').convert('L').resize(SIZE,Image.Resampling.BILINEAR)
    return ImageChops.lighter(person,foreground)

def focus(frame,f):
    mf=min(594,max(10,f//2*2));a=mask(mf)
    if f%2 and 10<=f<594:a=Image.blend(a,mask(mf+2),.5)
    a=a.point(lambda value:round(max(0,min(1,(value-160)/80))*255))
    a=Image.fromarray(maximum_filter(minimum_filter(np.asarray(a),size=3,mode='nearest'),size=3,mode='nearest'))
    manual=Image.new('L',SIZE);draw=ImageDraw.Draw(manual)
    for polygon in LADDER_PARTS:draw.polygon(polygon,fill=255)
    a=ImageChops.lighter(a,manual)
    return soft_focus(frame,a,480/920,blur_radius=6,floor_start=.73)[0]

def main():
    global P
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--work-dir',type=Path,required=True)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--ffmpeg',default=shutil.which('ffmpeg'))
    ap.add_argument('--preview',action='store_true')
    args=ap.parse_args();source=args.source.resolve();P=args.work_dir.resolve();ff=args.ffmpeg
    if not ff:ap.error('Pass --ffmpeg /path/to/ffmpeg or install ffmpeg.')
    if not args.preview and not args.output:ap.error('--output is required for rendering.')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=EXPECTED_SHA256:
        ap.error('Use the original paired hero human video from commit fe36eb5 as --source.')
    P.mkdir(parents=True,exist_ok=True)
    if args.preview:
        for f in (25,100,200,300,400,500,580):
            raw=subprocess.check_output([ff,'-v','error','-ss',str(f/50),'-i',str(source),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
            focus(Image.frombytes('RGB',SIZE,raw),f).save(P/f'after-{f:04}.jpg',quality=95)
        return
    output=args.output.resolve()
    if output==source:ap.error('Choose a separate output to preserve the original.')
    reader=subprocess.Popen([ff,'-v','error','-i',str(source),'-an','-pix_fmt','rgb24','-f','rawvideo','-threads','2','-'],stdout=subprocess.PIPE)
    writer=subprocess.Popen([ff,'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','480x800','-r','50','-i','-',
        '-an','-c:v','libx264','-preset','slow','-crf','21','-pix_fmt','yuv420p','-threads','3',
        '-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-movflags','+faststart',str(output)],stdin=subprocess.PIPE)
    count=0
    try:
        while True:
            raw=reader.stdout.read(480*800*3)
            if not raw:break
            assert len(raw)==480*800*3
            writer.stdin.write(focus(Image.frombytes('RGB',SIZE,raw),count).tobytes());count+=1
            if count%150==0:print(f'Rendered {count}/605',flush=True)
    finally:
        reader.stdout.close();writer.stdin.close()
    assert reader.wait()==0 and writer.wait()==0 and count==605
    print(f'{output}: {count} frames, {output.stat().st_size/1e6:.2f} MB',flush=True)

if __name__=='__main__':main()
