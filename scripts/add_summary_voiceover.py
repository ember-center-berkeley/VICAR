"""Generate timed neural narration and captions without re-encoding the video.

Dependencies: edge-tts, imageio-ffmpeg. Pass the original silent summary as
--source and keep --work-dir outside the published website.
"""
import argparse, asyncio, array, hashlib, json, math, re, subprocess, wave
from pathlib import Path
import edge_tts
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--work-dir',type=Path,required=True)
parser.add_argument('--output',type=Path,default=ROOT/'assets/videos/summary.mp4')
args=parser.parse_args()
args.work_dir.mkdir(parents=True,exist_ok=True)
plan=json.loads((ROOT/'docs/SUMMARY_NARRATION.json').read_text())
assert hashlib.sha256(args.source.read_bytes()).hexdigest()==plan['source_video_sha256']
ff=imageio_ffmpeg.get_ffmpeg_exe()
SR=24000

def ffmpeg(parts,**kwargs):
    return subprocess.run([ff,'-hide_banner','-loglevel','error','-nostdin','-y']+parts,check=True,**kwargs)

async def generate(cue,semaphore):
    stem=args.work_dir/cue['id']
    signature=dict(text=cue['text'],voice=plan['voice'],rate=plan['rate'])
    cache=stem.with_suffix('.json')
    if cache.exists() and json.loads(cache.read_text()).get('signature')==signature:
        return json.loads(cache.read_text())
    async with semaphore:
        stream=edge_tts.Communicate(cue['text'],voice=plan['voice'],rate=plan['rate'],boundary='WordBoundary')
        words=[]
        with stem.with_suffix('.mp3').open('wb') as file:
            async for chunk in stream.stream():
                if chunk['type']=='audio':file.write(chunk['data'])
                elif chunk['type']=='WordBoundary':words.append(chunk)
        data=dict(signature=signature,words=words)
        cache.write_text(json.dumps(data,indent=2)+'\n')
        print('Synthesized '+cue['id'],flush=True)
        return data

async def synthesize():
    semaphore=asyncio.Semaphore(3)
    return await asyncio.gather(*(generate(cue,semaphore) for cue in plan['cues']))

chunks=asyncio.run(synthesize()); prepared=[]; captions=[]
for cue,chunk in zip(plan['cues'],chunks):
    stem=args.work_dir/cue['id']
    raw=ffmpeg(['-i',str(stem.with_suffix('.mp3')),'-ac','1','-ar',str(SR),'-f','s16le','-'],stdout=subprocess.PIPE).stdout
    samples=array.array('h',raw)
    active=[i for i,s in enumerate(samples) if abs(s)>100]
    assert active, cue['id']
    first=max(0,active[0]-round(.06*SR));last=min(len(samples),active[-1]+round(.14*SR))
    duration=(last-first)/SR
    speed=max(1.,duration/(cue['deadline']-cue['start']-.06))
    assert speed<=1.18,(cue['id'],duration,speed,'Shorten the narration rather than rushing it.')
    wav=stem.with_suffix('.wav')
    with wave.open(str(wav),'wb') as file:
        file.setnchannels(1);file.setsampwidth(2);file.setframerate(SR);file.writeframes(samples[first:last].tobytes())
    end=cue['start']+duration/speed
    prepared.append(dict(**cue,audio=str(wav),trim_start_seconds=first/SR,raw_duration=duration,speed=speed,end=end))
    # Match original spelling/punctuation to synthesized word-boundary tokens.
    tokens=lambda text: re.findall(r"[a-z0-9]+",text.lower())
    boundaries=[]
    for word in chunk['words']:
        begin=max(cue['start'],cue['start']+(word['offset']/1e7-first/SR)/speed)
        finish=min(end,cue['start']+((word['offset']+word['duration'])/1e7-first/SR)/speed)
        boundaries.extend([(begin,finish)]*len(tokens(word['text'])))
    original=cue['text'].split();total=sum(len(tokens(w)) for w in original)
    assert total==len(boundaries),(cue['id'],total,len(boundaries))
    groups=cue.get('captions',[cue['text']])
    assert ' '.join(groups)==cue['text']
    token_index=0
    for text in groups:
        group_start=token_index;token_index+=len(tokens(text))
        captions.append((boundaries[group_start][0],boundaries[token_index-1][1],text))
    print(f"{cue['id']}: {cue['start']:.2f}–{end:.2f}s, rate {speed:.3f}x",flush=True)

inputs=[];filters=[]
for i,cue in enumerate(prepared):
    inputs+=['-i',cue['audio']]
    filters.append(f"[{i}:a]atempo={cue['speed']:.9f},adelay={round(cue['start']*1000)}:all=1[a{i}]")
filters.append(''.join(f'[a{i}]' for i in range(len(prepared)))+
    f"amix=inputs={len(prepared)}:normalize=0,apad,atrim=duration={plan['video_duration_seconds']},"+
    'loudnorm=I=-18:TP=-1.5:LRA=9,aresample=48000[out]')
narration=args.work_dir/'VICAR_Summary_Narration.wav'
ffmpeg(inputs+['-filter_complex',';'.join(filters),'-map','[out]','-ac','1','-c:a','pcm_s16le',str(narration)])
ffmpeg(['-i',str(args.source),'-i',str(narration),'-map','0:v:0','-map','1:a:0',
    '-c:v','copy','-c:a','aac','-b:a','128k','-ar','48000','-t',str(plan['video_duration_seconds']),
    '-metadata:s:a:0','language=eng','-metadata:s:a:0','title=AI-generated English narration',
    '-movflags','+faststart',str(args.output)])

def stamp(seconds,separator='.'):
    ms=round(seconds*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02d}:{m:02d}:{s:02d}{separator}{ms:03d}'
def wrap(text):
    if len(text)<=42:return text
    words=text.split();options=[(' '.join(words[:i]),' '.join(words[i:])) for i in range(1,len(words))]
    left,right=min(options,key=lambda p:max(len(p[0]),len(p[1])))
    return left+'\n'+right
vtt='WEBVTT\n\n';srt=''
for i,(start,end,text) in enumerate(captions):
    end=min(end+.12,captions[i+1][0]-.01 if i+1<len(captions) else plan['video_duration_seconds'])
    assert start<end and (i==0 or captions[i-1][1]<=start+.01)
    vtt+=f'{i+1}\n{stamp(start)} --> {stamp(end)}\n{wrap(text)}\n\n'
    srt+=f'{i+1}\n{stamp(start,",")} --> {stamp(end,",")}\n{wrap(text)}\n\n'
(ROOT/'assets/videos/summary.en.vtt').write_text(vtt)
(args.work_dir/'VICAR_Summary_Narration.srt').write_text(srt)
report=dict(voice=plan['voice'],engine='Microsoft neural text-to-speech via edge-tts',
    edge_tts_version=edge_tts.__version__,duration_seconds=plan['video_duration_seconds'],
    cues=prepared,caption_count=len(captions),narration_audio=str(narration),
    video=str(args.output),video_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest())
(args.work_dir/'voiceover-report.json').write_text(json.dumps(report,indent=2)+'\n')
print('Narrated summary and captions ready.',flush=True)
