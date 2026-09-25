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

Edit **`assets/content.js`**. All video sources, project links, authors, and demo recordings are centralized there.

- **Links:** replace `links.arxiv`, `links.paper`, and `links.video`. Unknown links intentionally point to `./`, as requested. The code button points to the actual VICAR repository.
- **Authors:** populate `authors` with `{ "name": "Author Name", "url": "https://…" }` objects and set `affiliations`. These are omitted initially because the supplied paper does not specify a byline.
- **Abstract:** copied from the supplied manuscript. Edit `abstract` to replace it.
- **Overview figure:** replace `assets/images/overview.png`. The supplied image is rendered from `figures/overview1_rebuttal.pdf` in the manuscript workspace. Keep its aspect ratio or update the image dimensions in `index.html`.
- **Citation:** set `bibtex` when the final citation is known. The citation section and copy button appear automatically.

## Add the ten videos

Place MP4 files in `assets/videos/`, then set each video's `src` in `assets/content.js`. For example:

```js
"src": "assets/videos/forehand.mp4",
"poster": "assets/images/forehand-poster.jpg",
"captions": "assets/videos/forehand.vtt"
```

`poster` and `captions` are optional. An empty `src` shows the designed “Video coming soon” placeholder without issuing a broken media request. A failed video shows “Video unavailable”. Real clips have native controls, inline mobile playback, and pause when scrolled out of view. They do not autoplay.

| Group | ID / suggested filename | Skill |
| --- | --- | --- |
| Carousel | `forehand.mp4` | Simple forehand serve |
| Carousel | `backhand.mp4` | Simple backhand serve |
| Carousel | `forehand-chop.mp4` | Forehand chop serve |
| Carousel | `backhand-chop.mp4` | Backhand chop serve |
| Carousel | `forehand-side-spin.mp4` | Forehand side-spin serve |
| Carousel | `backhand-side-spin.mp4` | Backhand side-spin serve |
| Individual | `tabletop-pickup.mp4` | Tabletop pickup |
| Individual | `under-table-pickup.mp4` | Under-table pickup |
| Individual | `bimanual-pick-place.mp4` | Bimanual box pickup and placement |
| Individual | `ladder-climbing.mp4` | Ladder climbing (simulation) |

The first six videos appear in a responsive carousel: three cards on desktop, two on tablet, and one with a peek of the next card on mobile. It supports buttons, keyboard arrows while the track is focused, six direct-selection dots, and touch scrolling. The remaining four are individually titled in a two-column grid, collapsing to one column on mobile.

Use browser-compatible H.264 MP4 with `yuv420p` and fast-start metadata. Keep individual files below GitHub's 100 MiB Git limit; for larger clips use a video/CDN URL in `src`. Do not use Git LFS pointer files as Pages media assets.

## Interactive augmentation

The page includes a **real, locally hosted Viser 1.1.1 viewer**. Click **Load 3D demo** to load it. The initial page makes no viewer or recording requests.

Two **illustrative schematic scenes** are supplied (serve and object pickup), each with five contact presets. These are geometric animations to demonstrate the website's interaction, **not VICAR outputs or measured results**. The page labels them accordingly. Visitors can orbit, zoom, play/pause, scrub time, change playback speed, and inspect the scene tree.

See [docs/VISER.md](docs/VISER.md) to replace these scenes with real motion exports or connect a live Viser server. Precomputed variants work entirely on GitHub Pages. Online optimization and Python callback controls require a separate server.

## Files

```text
index.html                    Semantic page structure
assets/content.js             Editable content and media manifest
assets/style.css              Responsive layout and visual design
assets/site.js                Carousel, media, and viewer controls
assets/images/overview.png    Paper overview figure
assets/videos/                Your ten final clips go here
assets/recordings/            Illustrative .viser exports; replace with real data
viser-client/                 Self-contained Viser 1.1.1 client and MIT license
scripts/                     Viser generation and export helpers
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

The checks exercise all six carousel selections, keyboard navigation, all ten illustrative Viser recordings, project-prefixed URLs, responsive widths, and missing-recording recovery. To use an existing Chrome installation, run `CHROME_CHANNEL=chrome npm test`.
