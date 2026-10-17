"""Create subject-centered website crops from the six aligned serve comparisons.

Each human/robot panel is 2:3; the side-by-side output is 4:3. Full-width inputs
remain unchanged. No retiming, trimming, or additional color processing is used.
Requires ffmpeg (or imageio-ffmpeg). Run after prepare_serve_pairs.py.
"""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


# Absolute x coordinates within each 2560-pixel paired source. Each crop retains
# the full frame height. Positions were reviewed through serve and follow-through.
CROPS = [
    ("backhand-side-spin", 60, 1360, 496, 744),
    ("forehand-side-spin", 80, 1380, 480, 720),
    ("forehand", 320, 1360, 480, 720),
    ("backhand", 200, 1290, 480, 720),
    ("backhand-top-spin", 200, 1400, 480, 720),
    ("forehand-top-spin", 200, 1440, 480, 720),
]


def main():
    root = Path(__file__).resolve().parents[1]
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    output = root / "assets/videos/serve-crops"
    posters = root / "assets/images/serve-crops"
    output.mkdir(parents=True, exist_ok=True)
    posters.mkdir(parents=True, exist_ok=True)

    def encode(entry):
        slug, human_x, robot_x, width, height = entry
        source = root / f"assets/videos/{slug}.mp4"
        video = output / f"{slug}.mp4"
        poster = posters / f"{slug}.jpg"
        graph = (
            "[0:v:0]split=2[a][b];"
            f"[a]crop={width}:{height}:{human_x}:0[human];"
            f"[b]crop={width}:{height}:{robot_x}:0[robot];"
            "[human][robot]hstack=inputs=2,setsar=1,format=yuv420p[v]"
        )
        subprocess.run([
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
            "-filter_complex", graph, "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "slow", "-crf", "19",
            "-threads", "4", "-fps_mode", "passthrough", "-g", "120",
            "-c:a", "copy", "-movflags", "+faststart", str(video),
        ], check=True)
        subprocess.run([
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-ss", "3",
            "-i", str(video), "-frames:v", "1", "-q:v", "2", str(poster),
        ], check=True)
        if video.stat().st_size > 20_000_000:
            raise RuntimeError(f"{slug} exceeds the website's 20 MB video budget")
        result = {
            "id": slug,
            "source": str(source.relative_to(root)),
            "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "video": str(video.relative_to(root)),
            "poster": str(poster.relative_to(root)),
            "width": width * 2, "height": height,
            "panelAspectRatio": "2:3", "combinedAspectRatio": "4:3",
            "humanCrop": [human_x, 0, width, height],
            "robotCrop": [robot_x, 0, width, height],
            "bytes": video.stat().st_size,
            "timing": "All source frames and timestamps preserved; audio copied",
        }
        print(f"{slug}: {width*2}x{height}, {result['bytes']/1e6:.2f} MB", flush=True)
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(encode, CROPS))
    (output / "manifest.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
