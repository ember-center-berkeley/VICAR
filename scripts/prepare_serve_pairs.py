"""Pair the four supplied human serves with their original robot recordings.

Usage: python scripts/prepare_serve_pairs.py /path/to/human_clips '/path/to/VICAR 2'
Requires ffmpeg with zscale/tonemap support (or imageio-ffmpeg).
Original files are read only. Both views retain their recorded playback speed.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


FPS = 60
HIT_FRAME = 180
FRAME_COUNT = 360
# Visually reviewed contact frames after normalizing each source with fps=60.
# These identify the nearest recorded ball/racket contact, not subframe timing.
CONTACTS = [
    ("forehand", 249, 187),
    ("backhand", 217, 232),
    ("forehand_top_spin", 307, 202),
    ("backhand_top_spin", 282, 433),
]
HUMAN_COLOR = (
    "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
    "tonemap=tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=limited,"
    "format=yuv420p"
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("human_dir", type=Path)
    parser.add_argument("robot_dir", type=Path)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    root = Path(__file__).resolve().parents[1]
    for name, *_ in CONTACTS:
        for source in [args.human_dir / f"{name}.MOV", args.robot_dir / f"{name}.mp4"]:
            if not source.is_file():
                parser.error(f"Missing video: {source}")

    def encode(entry):
        name, human_hit, robot_hit = entry
        slug = name.replace("_", "-")
        human = args.human_dir / f"{name}.MOV"
        robot = args.robot_dir / f"{name}.mp4"
        video = root / f"assets/videos/{slug}.mp4"
        poster = root / f"assets/images/{slug}-poster.jpg"
        starts = [human_hit - HIT_FRAME, robot_hit - HIT_FRAME]
        branches = []
        for index, start in enumerate(starts):
            color = HUMAN_COLOR + "," if index == 0 else ""
            branches.append(
                f"[{index}:v:0]fps={FPS},trim=start_frame={start}:end_frame={start+FRAME_COUNT},"
                f"setpts=N/({FPS}*TB),{color}scale=1280:720:flags=lanczos,setsar=1[v{index}]"
            )
        graph = ";".join(branches) + (
            ";[v0][v1]hstack=inputs=2:shortest=1,format=yuv420p,"
            "setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709[v];"
            f"[1:a:0]atrim=start={starts[1]/FPS}:duration={FRAME_COUNT/FPS},asetpts=PTS-STARTPTS[a]"
        )
        subprocess.run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(human), "-i", str(robot), "-filter_complex", graph,
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "slow",
            "-crf", "20", "-maxrate", "18M", "-bufsize", "36M", "-threads", "4",
            "-r", str(FPS), "-g", "120", "-c:a", "aac", "-b:a", "96k",
            "-t", str(FRAME_COUNT/FPS), "-movflags", "+faststart", "-map_metadata", "-1",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            str(video),
        ], check=True)
        if video.stat().st_size > 20_000_000:
            raise RuntimeError(f"{video.name} exceeds the 20 MB web budget")
        subprocess.run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(HIT_FRAME/FPS),
            "-i", str(video), "-frames:v", "1", "-vf", "scale=1920:-2",
            "-q:v", "3", str(poster),
        ], check=True)
        result = {
            "id": slug, "video": f"assets/videos/{slug}.mp4",
            "poster": f"assets/images/{slug}-poster.jpg",
            "bytes": video.stat().st_size, "width": 2560, "height": 720,
            "fps": FPS, "frames": FRAME_COUNT, "duration": FRAME_COUNT/FPS,
            "contactFrame": HIT_FRAME, "contactSeconds": HIT_FRAME/FPS,
            "sources": [
                {"file": source.name, "role": role, "bytes": source.stat().st_size,
                 "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                 "contactFrameAt60fps": contact, "trimStartFrameAt60fps": start}
                for source, role, contact, start in zip(
                    [human, robot], ["human", "robot"], [human_hit, robot_hit], starts)
            ],
            "layout": "Human left, robot right; full views without text overlays",
            "alignment": "Visually selected contact frames aligned at 3 seconds by trimming; original playback speeds preserved",
            "audio": "Robot recording, trimmed with its video",
            "color": "SDR BT.709; human HLG tone-mapped",
        }
        print(f"{slug}: {result['bytes']/1e6:.2f} MB; contact at frame {HIT_FRAME}", flush=True)
        return result

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(encode, CONTACTS))
    (root / "assets/videos/serve-pair-alignment.json").write_text(json.dumps(results, indent=2)+"\n")


if __name__ == "__main__":
    main()
