# Selective background focus

The website summary uses a shallow-focus treatment on its live-action human and
robot footage. The moving subjects, table, pickup object, and contact markers
retain their original detail. The lab background is softened, with a gradual
return to sharpness on the nearby floor. Titles and Viser/simulation panels are
outside the effect. This is a composited depth-of-field effect, not a new camera
capture or a change to the underlying motions.

The edit retains 3,598 frames at 60 fps, 1920 × 1080, the existing AAC narration
bitstream, and the existing caption timing. H.264 video is re-encoded at CRF 20
with a 2.5 Mbps maximum rate and fast-start metadata for web playback.

## Reproduce the treatment

Requirements: macOS 14 or later with Vision and the Swift command-line tools,
FFmpeg, and Python with Pillow, NumPy, and SciPy. No downloaded model weights,
cloud service, or browser inference is needed.

Keep working files outside this repository. Extract the unprocessed summary
from the last website commit before this treatment (do not process the already
blurred video a second time):

```sh
mkdir -p /tmp/vicar-summary-focus
git show 43d90d7:assets/videos/summary.mp4 > /tmp/vicar-summary-focus/original.mp4
swiftc -O scripts/summary_focus_masks.swift -o /tmp/vicar-summary-focus/masks-tool
/tmp/vicar-summary-focus/masks-tool /tmp/vicar-summary-focus/original.mp4 /tmp/vicar-summary-focus
python scripts/focus_summary.py --source /tmp/vicar-summary-focus/original.mp4 --work-dir /tmp/vicar-summary-focus --output /tmp/vicar-summary-focus/summary-focused.mp4
```

Pass `--ffmpeg /absolute/path/to/ffmpeg` if it is not on PATH. Use `--preview`
instead of `--output …` to produce stills at representative motion frames.
The renderer checks the source SHA-256 because its masks and timings are
calibrated to this particular edit.

The Swift helper samples the subject mattes at 30 fps, and the renderer
interpolates them at 60 fps. It combines person and foreground-instance
segmentation for the human (to preserve the bent knee and shoes), and uses
foreground-instance segmentation for the robot. Traced table parts and
keyframed object masks supplement the tracking. These coordinates, the original
opening crop, and the fade intervals are in `scripts/focus_summary.py`.

At the 920-pixel comparison-panel width, the background blur radius is roughly
8 pixels, scaled with the opening zoom. A 7-pixel Gaussian feather (increased
from 2 pixels) produces a more gradual transition around subjects and props.
The shared `scripts/focus_composite.py` keeps background convolution weights in
floating point to avoid jagged edge pixels during normalization.
Background-only convolution prevents foreground colors from bleeding into the
blurred lab. The effect is baked into the MP4 and adds no runtime cost
on the website. Fine silhouette edges remain an approximation of lens blur.

Before publishing a revised render, inspect the opening zoom, crouch, object
lift, and hardware sequence; confirm the frame count and copied audio, regenerate
the poster, and update the media metadata and URL version in `index.html`.
The native Premiere project and original source media are separate and are not
rewritten by this website rendering script.

## Ladder hero human video

The human climb uses the same compositor, with a 6-pixel background blur at
480 × 800 and a feather scaled to that size. Separate polygons preserve the
ladder rails, rungs, and feet while leaving the openings defocused. Person and
foreground mattes follow the climber at 25 fps and interpolate at the video's
original 50 fps. The 605 frames, 12.1-second loop, white fades, and synchronization
with the Viser hero are retained.

Generate this render from the original paired clip:

```sh
mkdir -p /tmp/vicar-ladder-focus
git show fe36eb5:assets/videos/hero-ladder-human.mp4 > /tmp/vicar-ladder-focus/original.mp4
/tmp/vicar-summary-focus/masks-tool /tmp/vicar-ladder-focus/original.mp4 /tmp/vicar-ladder-focus ladder
python scripts/focus_ladder_human.py --source /tmp/vicar-ladder-focus/original.mp4 --work-dir /tmp/vicar-ladder-focus --output /tmp/vicar-ladder-focus/hero-ladder-human.mp4
```

Compile the current `summary_focus_masks.swift` with the command above first.
`prepare_hero_human.py` produces the paired clip before this focus treatment;
reapply the treatment if regenerating that original crop. Update both the MP4
and its poster, the metadata, and the URLs in `assets/content.js` when publishing.
