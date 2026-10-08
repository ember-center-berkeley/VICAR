"""Encode the supplied demonstrations for Pages. Requires ffmpeg or imageio-ffmpeg.

Usage: python scripts/prepare_videos.py '/path/to/VICAR 2'
Original recordings are read only. Two-pass H.264 targets 12 MB for single views
and 16 MB for comparisons, retaining 60 fps and AAC audio. Stacked comparisons
become human-left / robot-right without cropping either view's content.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from video_color import color_profile, human_grade


VIDEOS = [
    ("forehand.mp4", "forehand", "single", 16.70),
    ("backhand.mp4", "backhand", "single", 23.95),
    ("forehand_top_spin.mp4", "forehand-top-spin", "single", 15.39),
    ("backhand_top_spin.mp4", "backhand-top-spin", "single", 20.80),
    ("forehand_side_spin.mp4", "forehand-side-spin", "wide", 17.13),
    ("backhand_side_spin.mp4", "backhand-side-spin", "wide", 15.55),
    ("pick_from_table.mp4", "tabletop-pickup", "stacked", 20.40),
    ("pick_under_table.mp4", "under-table-pickup", "stacked", 21.55),
    ("bimanual_pickmp4.mp4", "bimanual-pick-place", "stacked", 18.47),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--only", nargs="+", choices=[item[1] for item in VIDEOS],
                        help="Re-encode selected clips and preserve other manifest entries")
    args = parser.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    root = Path(__file__).resolve().parents[1]
    video_dir, image_dir = root / "assets/videos", root / "assets/images"
    video_dir.mkdir(exist_ok=True)
    image_dir.mkdir(exist_ok=True)
    selected = [entry for entry in VIDEOS if not args.only or entry[1] in args.only]
    for filename, *_ in selected:
        if not (args.input_dir / filename).is_file():
            parser.error(f"Missing input: {filename}")

    def encode(entry):
        filename, name, layout, duration = entry
        source = args.input_dir / filename
        target_mb = 12 if layout == "single" else 16
        # Reserve room for audio and MP4 overhead instead of truncating the clip.
        bitrate = int(target_mb * 1_000_000 * 8 / duration * .97 - 96_000)
        if layout == "stacked":
            graph = (
                "[0:v]split=2[top][bottom];"
                f"[top]crop=iw:ih/2:0:0,{human_grade(name)},scale=1280:720[left];"
                "[bottom]crop=iw:ih/2:0:ih/2,scale=1280:720[right];"
                "[left][right]hstack=inputs=2,fps=60,setsar=1[v]"
            )
        elif layout == "wide":
            graph = (
                "[0:v]scale=2560:-2,split=2[l][r];"
                f"[l]crop=iw/2:ih:0:0,{human_grade(name)}[left];"
                "[r]crop=iw/2:ih:iw/2:0[right];"
                "[left][right]hstack=inputs=2,fps=60,setsar=1[v]"
            )
        else:
            graph = "[0:v]scale=1920:-2,fps=60,setsar=1[v]"
        destination = video_dir / f"{name}.mp4"
        print(f"Encoding {filename} → {destination.name} ({layout}, ~{target_mb} MB)", flush=True)
        with tempfile.TemporaryDirectory(prefix=f"vicar-{name}-") as temp:
            for pass_number in (1, 2):
                command = [
                    ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(source), "-filter_complex", graph, "-map", "[v]",
                    "-c:v", "libx264", "-preset", "medium", "-threads", "4",
                    "-pix_fmt", "yuv420p", "-b:v", str(bitrate),
                    "-pass", str(pass_number), "-passlogfile", str(Path(temp) / "pass"),
                    "-g", "120", "-map_metadata", "-1",
                ]
                if pass_number == 1:
                    command += ["-an", "-f", "null", "-"]
                else:
                    command += ["-map", "0:a?", "-c:a", "aac", "-b:a", "96k",
                                "-movflags", "+faststart", str(destination)]
                subprocess.run(command, check=True)
        if destination.stat().st_size > 20_000_000:
            raise RuntimeError(f"{destination.name} exceeds 20 MB")
        poster = image_dir / f"{name}-poster.jpg"
        subprocess.run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss",
            str(duration * .4), "-i", str(destination), "-frames:v", "1",
            "-vf", "scale=1280:-2", "-q:v", "4", str(poster),
        ], check=True)
        result = {"source": filename, "video": f"assets/videos/{name}.mp4",
                  "poster": f"assets/images/{name}-poster.jpg", "layout": layout,
                  "sourceBytes": source.stat().st_size, "bytes": destination.stat().st_size}
        if layout != "single":
            result["humanGrade"] = color_profile(name)
        print(f"Finished {name}: {result['bytes'] / 1_000_000:.2f} MB", flush=True)
        return result

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(encode, selected))
    manifest_path = video_dir / "encoding-manifest.json"
    manifest = results
    if args.only and manifest_path.exists():
        previous = {item["video"]: item for item in json.loads(manifest_path.read_text())}
        previous.update({item["video"]: item for item in results})
        manifest = list(previous.values())
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Total: {sum(item['bytes'] for item in results) / 1_000_000:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
