"""Combine the supplied human and rendered reference climbs for the project page.

Usage: python scripts/prepare_climbing_video.py Climbing.mp4 ladder_reference_matched_1080x1920.mp4
Requires ffmpeg (or imageio-ffmpeg). Original recordings are read only.
The human retains its original speed. The 12-second reference is uniformly fit
to the 11.8-second human clip; this is an editorial comparison, not a measurement
of real-time tracking latency. Both portrait views are preserved without crops.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from video_color import HLG_TO_SDR, color_profile, human_grade


# (human/output time, reference source time, alignment landmark).
# Climbing phases were visually reviewed; the supplied reference already follows
# the human timing closely, so only the total duration is matched.
ALIGNMENT = [
    (0.0, 0.0, "Start"),
    (11.80, 12.00, "End"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("human", type=Path)
    parser.add_argument("reference", type=Path)
    args = parser.parse_args()
    for source in [args.human, args.reference]:
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
    # playback. The new reference is already SDR; preserve its encoded colors.
    human_color = HLG_TO_SDR + "," + human_grade("ladder-climbing")
    reference_color = "format=yuv420p"
    graph = (
        f"[0:v]setpts=PTS-STARTPTS,{human_color},scale=486:864:flags=lanczos,setsar=1,fps=60,"
        "pad=498:864:0:0:color=0x111827[left];"
        f"[1:v]setpts=PTS-STARTPTS,setpts='({timing})/TB',{reference_color},scale=486:864:flags=lanczos,setsar=1,fps=60,"
        "null[right];"
        "[left][right]hstack=inputs=2:shortest=1,tpad=stop_mode=clone:stop_duration=0.1,format=yuv420p,"
        "setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709[v]"
    )
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(args.human), "-i", str(args.reference),
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
        "bytes": video.stat().st_size, "width": 984, "height": 864,
        "fps": 60, "duration": 11.8,
        "sources": [{"file": p.name, "bytes": p.stat().st_size,
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in [args.human, args.reference]],
        "alignment": [{"outputSeconds": h, "referenceSeconds": s, "phase": phase}
                      for h, s, phase in ALIGNMENT],
        "note": "Human at original speed; complete 12-second reference uniformly fit to 11.8 seconds for comparison.",
        "color": "SDR BT.709 output; human HLG tone-mapped, SDR reference retained without additional grading",
        "humanGrade": color_profile("ladder-climbing"),
    }
    (video.parent / "climbing-alignment.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(f"Climbing comparison: {video.stat().st_size/1e6:.2f} MB, 984 × 864, 11.8 s", flush=True)


if __name__ == "__main__":
    main()
