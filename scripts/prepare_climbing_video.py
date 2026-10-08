"""Combine the supplied human and simulation climbs for the project page.

Usage: python scripts/prepare_climbing_video.py Climbing.mp4 climbing_in_sim_new.mov
Requires ffmpeg (or imageio-ffmpeg). Original recordings are read only.
The human retains its original speed. The simulation receives small, continuous
timing adjustments at visually reviewed climbing phases; this is an editorial
comparison, not a measurement of real-time tracking latency.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


# (human/output time, simulation source time, visual alignment landmark).
# Seconds were reviewed in the supplied clips, including intermediate frames.
ALIGNMENT = [
    (0.0, 0.0, "Start"),
    (2.60, 2.85, "First foot lift"),
    (4.60, 4.70, "Next raised-knee phase"),
    (6.30, 6.30, "Upper-rung transfer"),
    (7.80, 7.85, "Trailing foot joins upper rung"),
    (8.70, 8.65, "Stand upright"),
    (11.80, 11.80, "End"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("human", type=Path)
    parser.add_argument("simulation", type=Path)
    parser.add_argument("--font", default="/System/Library/Fonts/Helvetica.ttc")
    args = parser.parse_args()
    for source in [args.human, args.simulation]:
        if not source.is_file():
            parser.error(f"Missing video: {source}")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    root = Path(__file__).resolve().parents[1]
    video = root / "assets/videos/ladder-climbing.mp4"
    poster = root / "assets/images/ladder-climbing-poster.jpg"
    # Remap timestamps continuously; no cuts, reversed frames, or generated poses.
    segments = []
    for (out_start, src_start, _), (out_end, src_end, _) in zip(ALIGNMENT, ALIGNMENT[1:]):
        segments.append((src_end, f"{out_start}+(T-{src_start})*{out_end-out_start}/{src_end-src_start}"))
    timing = segments[-1][1]
    for end, expression in reversed(segments[:-1]):
        timing = f"if(lt(T,{end}),{expression},{timing})"
    # The phone clip is BT.2020 HLG; tone-map it to SDR for consistent browser
    # playback. The screen recording is full-range Display P3 with BT.709 gamma.
    human_color = "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=limited,format=yuv420p"
    sim_color = "zscale=p=bt709:t=bt709:m=bt709:r=limited,format=yuv420p"
    graph = (
        f"[0:v]setpts=PTS-STARTPTS,{human_color},scale=486:864:flags=lanczos,setsar=1,fps=60,"
        f"pad=498:912:0:48:color=0x111827,drawtext=fontfile='{args.font}':text='Human demonstration':fontsize=23:fontcolor=white:x=(486-tw)/2:y=12[left];"
        f"[1:v]setpts=PTS-STARTPTS,setpts='({timing})/TB',{sim_color},scale=668:864:flags=lanczos,setsar=1,fps=60,"
        f"pad=668:912:0:48:color=0x111827,drawtext=fontfile='{args.font}':text='Robot simulation':fontsize=23:fontcolor=white:x=(w-tw)/2:y=12[right];"
        "[left][right]hstack=inputs=2:shortest=1,format=yuv420p,"
        "setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709[v]"
    )
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(args.human), "-i", str(args.simulation),
        "-filter_complex", graph, "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "slow", "-crf", "20",
        "-maxrate", "10M", "-bufsize", "20M", "-threads", "4", "-g", "120",
        "-c:a", "aac", "-b:a", "96k", "-t", "11.8", "-movflags", "+faststart",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-map_metadata", "-1", str(video),
    ], check=True)
    if video.stat().st_size > 20_000_000:
        raise RuntimeError("Climbing comparison exceeds the 20 MB web budget")
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", "6.3",
        "-i", str(video), "-frames:v", "1", "-q:v", "4", str(poster),
    ], check=True)
    manifest = {
        "video": "assets/videos/ladder-climbing.mp4",
        "poster": "assets/images/ladder-climbing-poster.jpg",
        "bytes": video.stat().st_size, "width": 1166, "height": 912,
        "fps": 60, "duration": 11.8,
        "sources": [{"file": p.name, "bytes": p.stat().st_size,
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in [args.human, args.simulation]],
        "alignment": [{"outputSeconds": h, "simulationSeconds": s, "phase": phase}
                      for h, s, phase in ALIGNMENT],
        "note": "Human at original speed; simulation timing aligned by climbing phase for comparison.",
        "color": "SDR BT.709; human HLG tone-mapped, simulation converted from Display P3",
    }
    (video.parent / "climbing-alignment.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(f"Climbing comparison: {video.stat().st_size/1e6:.2f} MB, 1166 × 912, 11.8 s", flush=True)


if __name__ == "__main__":
    main()
