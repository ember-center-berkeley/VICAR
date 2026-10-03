# General serve augmentation

All six website serves now follow TT_PLayer's `augment_serves_general_g1.py`
at revision `b377ba95` (the full revision and source hashes are included in every
generated grid). The input is `refined_serve_g1/<style>.pkl`, using that file's
`augment_ranges`, `hit_time`, root pose, and joint trajectory. The old
`augment_serves_forehand_g1.py` experiment is retained separately for historical
reproduction; it no longer supplies the live forehand viewer.

## Slider ranges

Ranges are **contact offsets in metres**, with exactly the script's 0.04 m
padding on both ends. Each axis has nine samples, giving 729 motions per serve
and 4,374 across all six. Defaults are the interval midpoints. X is stored in
descending order, Y/Z ascending, using NumPy's default `meshgrid` ordering.

| Website serve | Source style | X min/max | Y min/max | Z min/max | X/Y/Z steps | Hit frame |
| --- | --- | --- | --- | --- | --- | --- |
| Simple forehand | `forehand` | −0.16 / 0.00 | −0.08 / 0.08 | −0.08 / 0.08 | 0.02 / 0.02 / 0.02 | 45 |
| Simple backhand | `backhand` | −0.09 / 0.04 | −0.08 / 0.06 | −0.04 / 0.08 | 0.01625 / 0.0175 / 0.015 | 49 |
| Forehand chop | `forehand_chop` | −0.18 / −0.02 | 0.03 / 0.19 | −0.04 / 0.14 | 0.02 / 0.02 / 0.0225 | 45 |
| Backhand chop | `backhand_chop` | −0.09 / 0.04 | −0.10 / 0.04 | 0.02 / 0.14 | 0.01625 / 0.0175 / 0.015 | 49 |
| Forehand side-spin | `forehand_right_side_spin` | −0.08 / 0.14 | −0.18 / 0.08 | −0.08 / 0.08 | 0.0275 / 0.0325 / 0.02 | 46 |
| Backhand side-spin | `backhand_right_side_spin` | −0.05 / 0.08 | −0.06 / 0.08 | −0.02 / 0.10 | 0.01625 / 0.0175 / 0.015 | 47 |

## What matches the Python visualization

- The 29-joint `urdf/g1/g1_racket.urdf`, with **right_racket** and
  **left_ball_holder**, preserving joint origins, axes, and mesh scale.
- The toss ramp from the minimum to maximum left-ball-holder height, six
  racket anchors (frame zero plus hit−2 through hit+2), and both racket-axis
  reference trajectories.
- The actual pulled `retarget/spa.py` solver with baseline `ours`, speed
  consistency enabled, Adam learning rate 0.001, and its 10,000-iteration cap.
  Only the seven right-arm joints change; root and other joints stay fixed.
- The blue wireframe/translucent hit box bounds all prescribed hit positions.
  The green Catmull–Rom spline uses the five prescribed contact-window points.
  The orange sphere has radius 0.013 m and sits halfway between the prescribed
  hit and hit+1 positions, exactly as in the source.
- Robot display lift is 0.035 m; overlays remain at unlifted coordinates, as in
  the source. Playback uses the source loop's 10 fps and exposes all 63 frames.

Visual meshes are simplified for download speed. The browser adds an initial
camera and grid floor, timeline playback, and responsive controls. Switching a
slider preserves the camera, playback time, and pause state. The standalone
“Open viewer” and local Python player provide the same XYZ/hit-box controls.

## Solver diagnostics

The current source has a convergence-threshold inconsistency: each of its two
axis costs is bounded below by `20 * acos(0.999)^2`, so their sum is at least
approximately **0.080013**, above the default target **0.028**. Consequently,
none can satisfy that threshold. All 729 outputs per style are retained after
10,000 iterations, following the source script's behavior; these are not
reported as converged. No source solver weights or thresholds were changed.

The generator calls the original solver directly and evaluates only the right
racket branch, the sole link used by this objective. Forward transforms and
gradients are independently checked against the complete robot. Optional
`torch.compile` accelerates the same cost on CPU. Floating-point results may
vary across PyTorch versions and compiler backends.

Every grid stores actual final costs, component costs, convergence flags,
prescribed/achieved hit positions, and provenance. Public JSON files additionally
report median and maximum hit errors. These are newly recomputed kinematic
augmentations, not saved experimental or hardware results.

The exported run's racket-position residuals at each style's hit frame are:

| Serve | Median error (mm) | Maximum error (mm) | Samples above 10 mm |
| --- | ---: | ---: | ---: |
| Forehand | 0.026 | 0.706 | 0 |
| Backhand | 0.014 | 0.511 | 0 |
| Forehand chop | 0.031 | 0.687 | 0 |
| Backhand chop | 0.019 | 0.613 | 0 |
| Forehand side-spin | 0.014 | 48.342 | 115 |
| Backhand side-spin | 0.026 | 16.539 | 14 |

The side-spin extremes therefore do not all reach their prescribed targets.
Their original padded ranges and solver outputs are retained, rather than
shrinking the source grid or moving the target markers to conceal the error.

## Rebuild and preview

Already generated NPZ data, robot meshes, and browser packs are included.
Playback/export only needs `visualization/requirements.txt`:

```sh
pip install -r visualization/requirements.txt
python -m visualization view --task backhand-chop
python -m visualization export
```

To regenerate from a trusted TT_PLayer checkout, first hydrate `meshes/g1/*`
with Git LFS in that checkout if needed. Then, from this website repository:

```sh
pip install -r visualization/requirements-augmentation.txt
python -m visualization.prepare --source-root /path/to/TT_PLayer --robot-racket-only
python -m visualization.serves --source-root /path/to/TT_PLayer --trust-pickle --compile
python -m visualization export
```

Omit `--compile` to run ordinary PyTorch. Add `--task forehand`, `backhand`,
`forehand-chop`, `backhand-chop`, `forehand-side-spin`, or `backhand-side-spin`
to generate one style. Short `--max-iters` runs are development previews; the
exporter rejects them. Source files in TT_PLayer are never modified.

The client uses one scene recording plus a gzip pack of seven-joint local
quaternions for each style. Sliders select a solved grid point; there is no
interpolation or online solver. GitHub Pages serves these static assets without
a Python backend. To rebuild the pinned Viser client after extension changes:

```sh
python scripts/build_viser_client.py
```

That command requires Node 24+ and npm. Human-readable extension source is in
`viser-client-extension/AugmentationPlayback.ts`; Viser's MIT license is retained.

## Validation

```sh
python -m unittest visualization.test_data visualization.test_forehand visualization.test_serves -v
npm test
```

Checks cover every grid's ranges and unique samples, source-style hit windows,
marker midpoint, source/model provenance, independent URDF poses, normalized
browser rotations, and matching full/pruned kinematic gradients. Browser tests
exercise all nine slider values on every axis of all six styles, standalone
controls, hit-box toggling, preserved playback, scene switching, all ten tasks and eleven
viewers, and missing-file recovery under a `/VICAR/` URL prefix.
