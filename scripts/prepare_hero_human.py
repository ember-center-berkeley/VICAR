"""Fit the graded human climb to the existing 12.1-second Viser hero loop."""
from pathlib import Path
import hashlib,json,subprocess
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'assets/videos/ladder-climbing.mp4'
video=ROOT/'assets/videos/hero-ladder-human.mp4'
poster=ROOT/'assets/images/hero-ladder-human-video-poster.jpg'
ff=imageio_ffmpeg.get_ffmpeg_exe()
filters=('crop=480:800:6:24,setpts=(PTS-STARTPTS)*121/118,fps=50,'
         'fade=t=in:st=0:d=0.18:color=white,fade=t=out:st=11.92:d=0.18:color=white,setsar=1')
subprocess.run([ff,'-hide_banner','-loglevel','error','-y','-i',str(source),'-vf',filters,
    '-an','-frames:v','605','-c:v','libx264','-preset','slow','-crf','23','-pix_fmt','yuv420p',
    '-threads','3','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709',
    '-movflags','+faststart',str(video)],check=True)
subprocess.run([ff,'-hide_banner','-loglevel','error','-y','-ss','5','-i',str(video),
    '-frames:v','1','-q:v','3',str(poster)],check=True)
metadata=dict(source='assets/videos/ladder-climbing.mp4',
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),source_duration_seconds=11.8,
    crop_xywh=[6,24,480,800],width=480,height=800,frames=605,fps=50,duration_seconds=12.1,
    source_playback_speed=11.8/12.1,alignment='Full human climb uniformly fit to the complete Viser reference loop.',
    fade_seconds=.18,audio=False,video=str(video.relative_to(ROOT)),poster=str(poster.relative_to(ROOT)),
    video_bytes=video.stat().st_size,video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
    note='Existing SDR color grade retained. Wider vertical crop keeps the head and feet in view throughout the climb.')
(ROOT/'assets/videos/hero-ladder-human.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps(metadata,indent=2))
