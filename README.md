# VICAR project website

A static research project page for **VICAR: Video Imitation with Contact-Aware Retargeting for Humanoid Interactive Skills**.

The website lives on the `website` branch and is published with GitHub Pages:

**https://ember-center-berkeley.github.io/VICAR/**

## Publish on GitHub Pages

1. Open [Settings → Pages](https://github.com/ember-center-berkeley/VICAR/settings/pages).
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select **website** and **/ (root)**, then **Save**.
4. Wait for the Pages deployment in the repository's Actions tab. Open the URL above when it succeeds.

No npm build, Python server, API key, or hosting service is required for the deployed site. `.nojekyll` tells Pages to serve the files directly. Every asset uses a relative path so the `/VICAR/` project prefix works.

If you are starting from only a local copy:

```sh
git init -b website
git remote add origin https://github.com/ember-center-berkeley/VICAR.git
git add .
git commit -m "Add VICAR project website"
git push -u origin website
```

If this checkout already has its remote and branch, use `git add`, `git commit`, and `git push`; do not initialize it again. Authenticate through your own GitHub client or `gh auth login` if needed; do not paste a token into the website.

## Preview locally

From this directory:

```sh
python3 -m http.server 8000
```

Open **http://localhost:8000/**. Use a local HTTP server rather than opening `index.html` as a file; the Viser viewer fetches its recordings.

## Update the content

Edit **`assets/content.js`**. Video sources, project links, and authors are centralized there. The generated `assets/viewer-manifest.js` registers the interactive recordings.

- **Links:** replace `links.arxiv`, `links.paper`, and `links.video`. Unknown links intentionally point to `./`, as requested. The code button points to the actual VICAR repository.
- **Authors:** populate `authors` with `{ "name": "Author Name", "url": "https://…" }` objects and set `affiliations`. These are omitted initially because the supplied paper does not specify a byline.
- **Abstract:** copied from the supplied manuscript. Edit `abstract` to replace it. It sits collapsed under three cards (the gap, the idea, the result) whose text is a summary written in `index.html`; check that wording against the paper. Their images, `assets/images/idea-*.jpg`, are crops of the overview figure and can be swapped for sharper frames.
- **Overview figure:** replace `assets/images/overview.png`. The supplied image is rendered from `figures/overview1_rebuttal.pdf` in the manuscript workspace. Keep its aspect ratio or update the image dimensions in `index.html`.
- **Hero background:** set `hero.video` (muted H.264 MP4 loop) and `hero.poster` (still image, also shown with reduced motion or data saver). Keep the subject in the right third of a 16:9 frame on a white background; the left side sits under the title. `hero.source` adds the human demonstration card beside the robot (`image`, `caption`, `alt`); remove it to hide the card. If neither the loop nor the poster loads, the hero falls back to a centred text layout. The current loop is a stand-in rendered from the bimanual box-pickup recording, paired with the crate photo from the overview figure.
- **Citation:** set `bibtex` when the final citation is known. The citation section and copy button appear automatically.

## Skill videos

All ten task videos are published: six serves, three pickup comparisons, and a
human/simulation climbing comparison. Every video is below **20 MB**.
All use H.264 / AAC, 60 fps, MP4 fast-start
metadata, and JPEG posters. Videos use `preload="none"` and download on play.

The three vertically stacked pickup recordings have been rearranged with the
human demonstration on the left and robot execution on the right. Both complete
views and their original timing are preserved. Existing side-by-side serve
recordings retain their layout. Serves and pickup comparisons span the content width.

To recreate these exports from the original folder, install `imageio-ffmpeg` (or
provide `ffmpeg` on PATH), then run:

```sh
python scripts/prepare_videos.py '/path/to/VICAR 2'
```

The script reads the originals without changing them, uses two-pass compression,
and writes videos, posters, and `assets/videos/encoding-manifest.json` with source
filenames and output sizes. Regular clips are 1920 × 1080; comparisons are 2560
pixels wide at their original aspect ratio. The source files named `top_spin`
are labeled top-spin in the video gallery; the existing chop augmentation demos
remain unchanged.

After the base export, create the four paired serve videos from the supplied
human `.MOV` files and the original robot `.mp4` files:

```sh
python scripts/prepare_serve_pairs.py /path/to/human_clips '/path/to/VICAR 2'
```

These six-second clips preserve both playback speeds, trimming idle footage so
the visually selected ball-contact frames coincide at 3 seconds (frame 180 at
60 fps). Each complete view is 1280 × 720, with the human on the left and robot
on the right, without text overlays. Phone HLG colors are tone-mapped to SDR.
The robot audio is trimmed with its video. Source hashes and contact/trim frames
are recorded in `assets/videos/serve-pair-alignment.json`; this supersedes the
four single-view exports in `assets/videos/encoding-manifest.json`.

All ten comparisons use fixed human-view color grades in
`scripts/video_color.py`, with each robot view as the reference. The four phone
serves each use a calibrated 3D LUT after HLG-to-SDR conversion: separate shadow,
midtone and highlight levels, RGB white balance, and selective color corrections
match the table, walls, dark cabinet and yellow housing. Background samples at
three moments in each clip and the fitted settings are saved in
`scripts/serve_color_profiles.json`. One fixed grade per clip avoids temporal
color pumping. Physical scene differences, such as the added gray floor mat in
the robot recordings, remain intact. To rebuild the committed LUTs after changing
the profiles, install NumPy/SciPy and run `python scripts/build_serve_color_luts.py`;
ordinary video exports require only FFmpeg, as before.

Climbing and the older comparisons retain their existing color grades.
The export manifests record the settings. Grades affect only the human view;
frame counts, playback speed, contact alignment, and robot color are preserved.
Posters use the same grade as their videos. To refresh only selected base clips
without overwriting the four paired serves, pass `--only` with their gallery IDs:

```sh
python scripts/prepare_videos.py '/path/to/VICAR 2' --only forehand-side-spin backhand-side-spin tabletop-pickup under-table-pickup bimanual-pick-place
```

The climbing comparison preserves the complete human demonstration at its
original speed and pairs it with `ladder_reference_matched_1080x1920.mp4` on the
right. The complete 12-second reference is uniformly fit to the human's 11.8
seconds, after reviewing the climbing phases. Both portrait views use equal
widths without cropping or view labels; an alignment note appears in the caption.
The human's existing HLG-to-SDR conversion and color grade are preserved, while
the new SDR reference receives no additional color grading. The 984 × 864 export
uses SDR BT.709 for browser playback.

```sh
python scripts/prepare_climbing_video.py /path/to/Climbing.mp4 /path/to/ladder_reference_matched_1080x1920.mp4
```

This export's source hashes, timing landmarks, dimensions, and size are recorded
in `assets/videos/climbing-alignment.json`. It is a visual comparison with edited
timing, not a measurement of tracking latency.

To add or replace a clip:

Place MP4 files in `assets/videos/`, then set each video's `src` in `assets/content.js`. For example:

```js
"src": "assets/videos/forehand.mp4",
"poster": "assets/images/forehand-poster.jpg",
"captions": "assets/videos/forehand.vtt"
```

`poster` and `captions` are optional. An empty `src` shows the designed “Video coming soon” placeholder without issuing a broken media request. A failed video shows “Video unavailable”. Real clips have native controls, inline mobile playback, and pause when scrolled out of view. They do not autoplay.

| Group | ID / suggested filename | Skill |
| --- | --- | --- |
| Carousel | `backhand-side-spin.mp4` | Backhand side-spin serve |
| Carousel | `forehand-side-spin.mp4` | Forehand side-spin serve |
| Carousel | `forehand.mp4` | Simple forehand serve |
| Carousel | `backhand.mp4` | Simple backhand serve |
| Carousel | `backhand-top-spin.mp4` | Backhand top-spin serve |
| Carousel | `forehand-top-spin.mp4` | Forehand top-spin serve |
| Individual | `tabletop-pickup.mp4` | Tabletop pickup |
| Individual | `under-table-pickup.mp4` | Under-table pickup |
| Individual | `bimanual-pick-place.mp4` | Bimanual box pickup and placement |
| Individual | `ladder-climbing.mp4` | Ladder climbing (simulation) |

The six serves appear one at a time at full width on desktop, tablet, and mobile.
The carousel supports buttons, keyboard arrows while the track is focused, six
direct-selection dots, and touch scrolling. Its height adapts to each clip's
aspect ratio. The three pickup comparisons are individually titled, full-width
rows, followed by a centered climbing comparison at 50% width (full width on
mobile screens up to 600 px). Set each video's `width` and `height`
in `assets/content.js` so the layout reserves the correct space before playback.

Use browser-compatible H.264 MP4 with `yuv420p` and fast-start metadata. Keep individual files below GitHub's 100 MiB Git limit; for larger clips use a video/CDN URL in `src`. Do not use Git LFS pointer files as Pages media assets.

## Interactive motion explorer

All **six serve styles** use `augment_serves_general_g1.py`, with 729 motions each and X/Y/Z ranges derived from each style’s `augment_ranges` plus the script’s 4 cm padding. The G1 carries the racket and ball holder; a blue hit box, green contact spline, and orange hit marker match the source viewer. Slider changes preserve camera and playback position.

The manipulation tasks use their canonical `augment_*` scripts: left-hand tabletop pickup (306 motions), under-table pickup (250), and bimanual pick/place (50). Ladder climbing uses the supplied `ladder_scene_20261008` package: a reconstructed A-frame ladder and 605-frame reference motion at 50 Hz. Tabletop pickup shows only the left-hand motion, without a hand selector. Their viewers include the source objects, grasping fingers, reconstructed tables, contact paths, and scene-layer controls. Bimanual uses the same display robot model as ladder climbing. Its 50 motions and object paths were regenerated with the original motion URDF’s right-hand offset set to `(0.1315, 0, 0)` m; the box settles smoothly onto the reconstructed table. Bimanual Y is fixed; climbing has playback and layer controls for the ladder, contact markers, floor grid, and reference paths.

The organized `visualization/` package runs the same viewers locally and exports them for GitHub Pages. See [the serve augmentation guide](docs/SERVE_AUGMENTATION.md), [the other task guide](docs/TASK_AUGMENTATION.md), [general viewer instructions](docs/VISER.md), and [the source map](docs/VISUALIZATION_SOURCES.md).

The viewer starts loading as its section approaches the screen; with the browser's data saver on, it waits for **Load 3D demo**. Scrolling over it moves the page until the visitor clicks the scene (then the wheel zooms); touch screens show a “Tap to interact” layer instead. The browser loads geometry and the compact augmentation data once. Slider changes select actual optimized trajectories; they do not run the optimizer or reload the viewer. Other scene controls retain standard Viser playback.

## Files

```text
index.html                    Semantic page structure
assets/content.js             Editable project content and video sources
assets/viewer-manifest.js     Generated task/recording manifest
assets/style.css              Responsive layout and visual design
assets/site.js                Carousel, media, and viewer controls
assets/images/overview.png    Paper overview figure
assets/videos/                Your ten final clips go here
assets/recordings/            Real G1 trajectory exports for static playback
viser-client/                 Self-contained Viser 1.1.1 client and MIT license
visualization/               Shared renderer, importer, local player, and source map
scripts/                     Browser checks and generic export helper
docs/VISER.md                Viser integration guide and project references
```

## Design and dependencies

Original HTML/CSS/JS implementation inspired by the clean research-page layouts of [OmniRetarget](https://omniretarget.github.io/) and [LATTE-MV](https://sastry-group.github.io/LATTE-MV/). No videos, models, or scenes were copied from those projects. [Gauss Gym](https://escontrela.me/gauss_gym/) provides a concrete project-page example using Viser's offline playback pattern. [Play2Perfect](https://play2perfect.github.io/interactive/) is another reference for the interactive layout.

The page uses system fonts and no tracking, external font requests, or CDN scripts. Viser is MIT licensed; its license is included. The manuscript figure and eventual research assets retain their owners' rights.

## Browser checks

Testing is optional for content editing and is not part of the deployment:

```sh
npm install
npx playwright install chromium
npm test
```

The checks exercise playback and seeking for all ten videos, the 20 MB size
limit, no video preloading, all six carousel selections, full-width cards at
responsive sizes, keyboard navigation, all ten tasks and ten viewers, every
sampled XYZ position, left-hand tabletop pickup, fixed axes, scene layers, preserved
playback, standalone controls, project-prefixed URLs, and missing-recording
recovery. To use an existing Chrome installation, run `CHROME_CHANNEL=chrome npm test`.
