# Historical forehand augmentation

**Superseded:** the live website now uses `augment_serves_general_g1.py` for all six serves. See [SERVE_AUGMENTATION.md](SERVE_AUGMENTATION.md). This document and the older forehand files are retained for reproducibility; the commands below rebuild the historical experiment only.

The forehand scene follows **`augment_serves_forehand_g1.py`** from TT_PLayer
revision `49ecadb2d98643075de33509b01ab467450a4661`. It replaces the previous
reference-only website preview with the script's optimized contact grid.

## What matches the original script

- The real `refined_serve_g1/base.pkl` trajectory: 63 frames and 29 body joints.
- 729 shifts: nine samples per axis, with X from −0.12 to −0.04 m and Y/Z
  from −0.04 to +0.04 m. Slider increments are 0.01 m, matching the source grid.
- The original `add_change` ramp from the left-hand toss minimum to maximum.
- Only the seven right-arm joints are optimized; the other body joints and
  root trajectory remain unchanged.
- The same right-hand position/orientation loss, Adam learning rate 0.001,
  nearest previously solved warm start, 0.014 cost threshold, and 4000-step cap.
- The **43-joint G1 with hands** from `robots/g1_29dof_with_hand.urdf`. The 29
  body joints map by name into it, with all 14 finger joints held at zero, as in
  the original script.
- The original 0.035 m visualization lift and 10 fps preview timing from the
  script's 0.1-second playback delay. All 63 frames are accessible.

The loss is evaluated on the right-arm kinematic branch for speed. Its forward
kinematics is checked against the full source model before solving. Joint
geometry is unchanged; visual meshes are simplified. Numerical results can
vary slightly across torch/kinematics versions. These are newly computed
augmentations, not previously saved experimental outputs.

The website adds a small amber marker at the prescribed hit target, a grid
floor, and a centered starting camera. It omits the earlier hand-path overlays
in this scene. Sliders preserve camera orientation, playback time, and pause
state. Open viewer provides the same three sliders in a standalone Viser view.

## Static hosting implementation

One `.viser` file loads the robot, ground, and baseline animation. A compact
binary pack contains the local joint quaternions for all 729 augmented motions
(approximately 1.7 MB compressed). A small Viser client extension substitutes
the selected right-arm poses during ordinary playback. The geometry is loaded
once; slider changes do not reload the iframe or download another recording.

Each slider selects an actual optimized grid motion. There is no interpolation
between grid points or online optimization in the browser. Python callbacks
are not required on GitHub Pages.

Only same-origin messages from the parent window can change the selected grid
point. Bounds and data dimensions are checked; the UI displays a load error if
the motion pack is unavailable. Other scenes use standard Viser playback.

## Generate, preview, export

With the website virtual environment activated:

```sh
pip install -r visualization/requirements-augmentation.txt
python -m visualization.forehand
python -m visualization.export_forehand
python -m visualization export --task forehand
python -m visualization view --task forehand
```

The local Viser player opens at `http://127.0.0.1:8080/` with X/Y/Z sliders,
frame scrubbing, play/pause and speed. Already generated motion data is included,
so playback alone needs only `visualization/requirements.txt`. To inspect the
unaugmented historical reference with the older generic player, pass
`--variant reference` explicitly.

To rebuild the hand-model meshes from the original checkout:

```sh
python -m visualization.prepare --source-root /path/to/TT_PLayer --robot-hands-only
```

To rebuild the browser client, install Node 24+ and npm, then run:

```sh
python scripts/build_viser_client.py
```

This copies the pinned Viser 1.1.1 sources into a temporary directory, applies
the readable extension from `viser-client-extension/AugmentationPlayback.ts`,
checks TypeScript, and rebuilds `viser-client/index.html`. It retains the Viser
MIT license. It does not modify the installed Viser package.

## Validation and numerical limits

The complete grid was generated and checked against the source kinematics.
724 of 729 solves reached the source objective threshold; five reached its
4000-step cap. As in the original script, all outputs are retained, with their
actual costs recorded in the metadata. The right-hand position error at hit
frame 45 is approximately 0.21 mm median and 1.07 mm maximum. This is a
kinematic fit check, not a hardware or physics validation.

`forehand-grid.npz` retains the shifts, seven-joint trajectories, prescribed and
achieved targets, costs, iteration counts, and generation settings. Browser
quaternions are checked against independent URDF forward kinematics at sampled
frames and grid extremes. Source data hashes and revision are retained.

```sh
python -m unittest visualization.test_data visualization.test_forehand -v
npm test
```

Browser checks exercise all nine positions on each X/Y/Z axis, slider reset,
preservation of paused playback time, standalone controls, responsive layouts,
all other recordings, and missing-data recovery.
