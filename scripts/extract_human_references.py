"""Extract the human panels used beside the interactive motion explorer.

Uses the website's already graded comparison videos; originals stay untouched.
Run with ffmpeg on PATH or with imageio-ffmpeg installed. Crops are in source
video pixels and contain only the human (left) panel. The ladder uses the
existing hero image and stores its contact markers separately in content.js.
"""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
# Website pairing: use the supplied top-spin clips for the two legacy '*-chop' IDs.
SPECS = [
    ('forehand', 'forehand', 3, (340, 80, 640, 640)),
    ('backhand', 'backhand', 3, (300, 20, 600, 640)),
    ('forehand-chop', 'forehand-top-spin', 3, (300, 20, 600, 640)),
    ('backhand-chop', 'backhand-top-spin', 3, (300, 20, 600, 640)),
    ('forehand-side-spin', 'forehand-side-spin', 8.45, (100, 30, 620, 660)),
    ('backhand-side-spin', 'backhand-side-spin', 7, (90, 40, 600, 660)),
    ('tabletop-pickup', 'tabletop-pickup', 6, (480, 0, 760, 670)),
    ('under-table-pickup', 'under-table-pickup', 9, (430, 130, 700, 530)),
    ('bimanual-pick-place', 'bimanual-pick-place', 8, (430, 170, 700, 490)),
]


def main():
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    destination = ROOT / 'assets/images/human-references'
    destination.mkdir(parents=True, exist_ok=True)
    manifest = []
    for scene, clip, seconds, crop in SPECS:
        source = ROOT / f'assets/videos/{clip}.mp4'
        image = destination / f'{scene}.jpg'
        x, y, width, height = crop
        subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                        '-ss', str(seconds), '-i', str(source),
                        '-vf', f'crop={width}:{height}:{x}:{y},scale=600:-2:flags=lanczos',
                        '-frames:v', '1', '-q:v', '3', str(image)], check=True)
        manifest.append(dict(scene=scene, source=str(source.relative_to(ROOT)),
                             timeSeconds=seconds, cropXYWH=list(crop),
                             image=str(image.relative_to(ROOT)), bytes=image.stat().st_size,
                             sha256=hashlib.sha256(image.read_bytes()).hexdigest()))
    (destination / 'sources.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Extracted {len(manifest)} human references; {sum(x["bytes"] for x in manifest):,} bytes total.')


if __name__ == '__main__':
    main()
