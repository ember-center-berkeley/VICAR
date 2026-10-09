# Pickup, bimanual, and climbing augmentation

The four non-serve task categories use five canonical `augment_*` programs from
TT_PLayer revision `b377ba951d2bd12bef45e23a5e623342038121e0`. The tabletop pickup
viewer exposes only the left-hand motion; the right-hand dataset is retained
as an archive. All use the articulated 43-joint G1 visual
model from the source, with the original 29-joint body motion mapped by joint order.
The six serve viewers are described in [SERVE_AUGMENTATION.md](SERVE_AUGMENTATION.md).

## Sources and controls

All ranges below are **contact offsets in metres**. Sliders select actual solved
samples, with no interpolation. The initial selection is the lower middle sample
on an even-sized axis, so the initial displayed value always exists in the grid.

| Viewer | Canonical source | Grid / motions | X range | Y range | Z range | Frames / fps |
| --- | --- | --- | --- | --- | --- | --- |
| Tabletop, left hand | `augment_pick_motions_left_g1.py` | 9 × 17 × 2 / 306 | 0 to 0.20 | −0.30 to 0.08 | 0.058133676 to 0.078133676 | 320 / 20 |
| Tabletop, right hand (archived) | `augment_pick_motions_g1.py` | 9 × 17 × 2 / 306 | 0 to 0.20 | −0.08 to 0.30 | 0.058133676 to 0.078133676 | 220 / 10 |
| Under-table pickup | `augment_ground_pick_motions_left_g1.py` | 5 × 10 × 5 / 250 | 0 to 0.05 | 0 to 0.10 | −0.10 to 0 | 385 / 30.30303 |
| Bimanual pick/place | `augment_bimanual_pick_motions_g1.py` | 5 × 1 × 10 / 50 | 0 to 0.05 | 0, fixed | 0.57 to 0.67 | 480 / 30.30303 |
| Ladder climbing | `augment_climbing_motions_g1_vis.py` | 1 fixed contact solution | — | — | — | 364 / 30.30303 |

The site exposes **607 task motions** alongside the 4,374 serve motions, with
ten tasks and ten viewers. The 306 archived right-hand tabletop motions are
excluded from the public manifest and hand-selection controls.

Bimanual Z includes the source script's additional **+0.07 m**. Its Y slider is
disabled because `NY=1`. The climbing script declares only one shift, `[0,0,0.07]`,
but its objective uses fixed stair anchors and does not shift them with XYZ.
Consequently, climbing offers timeline and scene-layer controls without XYZ
sliders. The website now follows `augment_climbing_motions_g1_vis.py`, including
its ground contacts, revised contact schedule, toe-edge keypoints, and joint
limits. The previous export used `augment_climbing_motions_g1.py`.

The source GUIs use `(max-min)/8` even for axes with 2, 5, 10, or 17 samples. The
website uses explicit sample arrays instead, ensuring that every slider stop
maps to a generated motion. Display values are rounded to five decimals; stored
coordinates retain their original precision.

## What the scenes show

- **Tabletop:** the left-hand scene uses the source table point cloud and voxels,
  contact region/path, grasped object, and exact 15-frame finger closure starting
  at frame 100.
  The left-hand source appends a 100-frame turn: waist yaw changes by −0.8 rad
  and left shoulder pitch by −1.6 rad. The robot receives the source's 3.5 cm
  display lift; overlays retain their original coordinates.
- **Under-table:** frame-130 left-hand pickup and finger closure, the 30-frame
  contact path, right-hand support anchors, carried object, and source table.
  The detached reconstruction leg beside the object is removed from both
  displayed table layers (585 points and 15 voxels). This cleanup runs only
  when rendering/exporting; the raw reconstruction, optimization and motions
  remain in the source data.
  Contact diagnostics color and resize arm-keypoint spheres using penetration
  into the original collision box.
- **Bimanual:** source object trajectory and ±0.15 m hand paths, contact interval
  150–300, and source table. The displayed box is reduced to 0.3 × 0.3 × 0.3 m,
  so its initial 0.15 m center height puts the bottom on the ground. It follows
  the source's −0.2 m/clamped visual path while carried. After release at frame
  300, a smooth 18-frame (0.594 s) descent settles its bottom onto the visible
  voxel tabletop beneath its footprint (Z = 0.70 m), then holds it there.
  XY placement is preserved for all 50 augmentations. `objectPresentation` in
  the public JSON records the display size, surface heights and easing timing.
  This is a visual release animation, not rigid-body simulation; source contact
  targets, the original box dimensions and the solved robot motion are retained.
- **Climbing:** six rungs starting at X = 0.40 m and ten hand/foot contact markers
  (including two ground contacts). Collision geometry is omitted from both the
  scene and display controls. It remains part of the source optimization data.
  Root Y is zeroed.
  Visual markers are read from that process’s `_stair_anchor` helper: rung
  anchors use `x = origin_x + (s−1)·tread`, `z = 0.3s+0.07`; ground markers use
  X = 0, Z = 0.03. Optimizer targets separately use +0.17 m toe-edge / +0.12 m
  hand X offsets and `z = 0.3s+0.09` (ground Z = 0.05). This source distinction
  is preserved in the export. The motion optimizes 24 joints; hip yaw remains
  fixed to the input motion. Both visual and optimizer anchors are recorded
  in `visual_contacts` in the NPZ metadata and public JSON provenance.

For the pickup tasks, the captured camera and collision geometry can be toggled independently, as can
table points, voxels, paths, and contact diagnostics where relevant. Defaults
preserve the source's enabled scene layers; the camera frustum starts hidden.
Root quaternions are normalized for rendering to match the optimizer's rotation
math; raw source pose values remain in the NPZ files. Browser playback preserves
camera, time, and pause state while changing the selected augmentation.

Table reconstruction inputs are:

- `mega-sam/UniDepth/pointclouds/bimanual_pick_place/table_00000.ply`
- `holosoma/src/holosoma_retargeting/demo_data/cameras_refined/bimanual_pick_place_new.npy`

Each task's original alignment and voxelization are executed. Shared asset
hashes are recorded in
[`scene-provenance.json`](../visualization/motions/tasks/scene-provenance.json).
The source's absolute `/home/dvij/TT_Player/` prefix is remapped to the supplied
checkout only during headless loading. No source files are edited. Packaged kinematic URDF copies normalize whitespace;
the recorded hashes identify the original source files.

## Optimization and interpretation

`visualization/task_augmentation.py` executes the original script's setup and
postprocessing around `retarget/spa.py`. It selects baseline `ours`, preserves
all source anchors, obstacles, active joints, limits, weights, smoothing, speed
costs, and Adam settings, and runs the full 10,000 iterations (20,000 for right
hand tabletop). The optional Pyroki GUI/heightmap is omitted.

For CPU performance, the adapter reuses serial-chain forward transforms and
vectorizes the source's anchor sums. Before solving, it compares all cost
components and gradients against the original cost on the full task batch.
Independent tests also compare selected/full kinematics and gradients.
`torch.compile` is enabled by default; `--no-compile` runs ordinary PyTorch.
Floating-point results can vary by runtime/backend.

As with the serves, the source's clipped axis-angle terms have a nonzero floor
above its 0.028 convergence target. Outputs are retained at the iteration cap,
following the scripts; none of these runs is labeled converged. Actual final
costs, component costs, convergence flags, revision, and input/script/URDF hashes
are saved in every NPZ. Public JSON includes final cost ranges and provenance.
Some contacts retain residual errors. These are regenerated kinematic previews,
not additional physical trials or proof of collision-free feasibility.

## Replay or export the included data

```sh
pip install -r visualization/requirements.txt
python -m visualization list
python -m visualization view --task tabletop-pickup --variant tabletop-left
python -m visualization view --task under-table-pickup
python -m visualization view --task bimanual-pick-place
python -m visualization view --task ladder-climbing
```

Open the printed localhost URL. The local viewer has actual-range XYZ controls,
scene-layer toggles, timeline, play, speed, and restart. It only needs the
included NPZ data and reduced robot assets; no source checkout or torch/JAX is
needed for playback.

```sh
python -m visualization export --task tabletop-pickup
python -m visualization export --task under-table-pickup
python -m visualization export --task bimanual-pick-place
python -m visualization export --task ladder-climbing
python -m visualization manifest
python3 -m http.server 8000
```

The generic export command also refreshes the manifest. `manifest` alone is
useful after individual exports with `python -m visualization.export_tasks`.
Each task uses one static Viser scene, compressed joint rotations, and, for
manipulation, compressed object/diagnostic animation channels. GitHub Pages
needs no Python backend. The older CSV imports and their `--variant` IDs remain
available locally; the public explorer now uses these augmentation grids.

## Regenerate from TT_PLayer

Hydrate the required inputs in the original checkout first:

```sh
git lfs pull --include='refined_pick_g1/*,refined_ground_pick_g1/*,refined_bimanual_pick_g1/*,refined_climbing_pick_g1/*,mega-sam/UniDepth/pointclouds/bimanual_pick_place/table_00000.ply,holosoma/src/holosoma_retargeting/demo_data/cameras_refined/bimanual_pick_place_new.npy'
```

Then, from the website checkout:

```sh
pip install -r visualization/requirements-augmentation.txt
python -m visualization.task_augmentation --source-root /path/to/TT_PLayer \
  --task tabletop-left --trust-pickle
```

Repeat with `under-table-pickup`, `bimanual-pick-place`, and
`ladder-climbing`, then export. Input pickles are loaded only with explicit trust.
The generator executes the trusted source program's headless setup and tail;
it is not intended for untrusted Python files. A short `--max-iters` development
run writes to the ignored `visualization/motions/tasks/previews/` directory,
preserving full generated grids. The exporter also rejects shortened solves
if copied into the production data directory. The published grids were solved
on CPU with the source defaults.

## Validation

The full Python checks also need `visualization/requirements-augmentation.txt`
for the independent kinematic gradient tests.

```sh
python -m unittest visualization.test_data visualization.test_forehand \
  visualization.test_serves visualization.test_tasks -v
npm test
```

Task checks independently validate ranges and sample counts, the 29-to-43-joint
mapping, finger timelines, turn extension, browser quaternions, carried-object
transforms, and penetration overlays. Browser checks cover all ten tasks and
ten viewers, every sampled XYZ position, fixed axes, scene
layers, standalone controls, preserved playback, mobile widths, missing-file
recovery, and rapid scene changes under a `/VICAR/` project prefix.
