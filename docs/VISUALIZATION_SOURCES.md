# VICAR visualization source map

**Current serve update (b377ba95):** All six serves now use the named `refined_serve_g1/<style>.pkl` inputs, `urdf/g1/g1_racket.urdf`, and `augment_serves_general_g1.py`. Each has 729 regenerated motions. See [SERVE_AUGMENTATION.md](SERVE_AUGMENTATION.md) for ranges and diagnostics. `source_inventory.json` has current line references. The audit below describes the earlier import: its missing-file statements are historical. Newly pulled non-serve PKLs also exist; those viewers retain their previous previews in this serve-focused update.


Audited on 2026-09-28 against `ember-center-berkeley/TT_PLayer`, revision
`49ecadb2d98643075de33509b01ab467450a4661`.
The original training, refinement, and augmentation scripts are retained in that
repository. This website contains a standalone viewer/exporter in `visualization/`.

## Task entry points

Paths below are relative to the **TT_PLayer checkout**, not the website repository.
Most task scripts contain their own Viser setup and playback loop inside the
optimization program. `--vis` often also runs optimization and loads training
dependencies; it is not a lightweight playback command.

| Website task | Refinement / visualization source | Augmentation / visualization source | Available in this checkout |
| --- | --- | --- | --- |
| Simple forehand | `refine_forehand_serve_g1.py` | `augment_serves_forehand_g1.py`; `augment_serves_general_g1.py --serve_style forehand` | `refined_serve_g1/base.pkl`, 63 frames; all 729 contact augmentations now regenerated for X/Y/Z sliders. |
| Simple backhand | `refine_backhand_serve_g1.py` | `augment_serves_backhand_g1.py`; general script with `backhand` | Final robot trajectory missing. |
| Forehand chop | `refine_forehand_chop_serve_g1.py` | `augment_serves_forehand_chop_g1.py`; general script with `forehand_chop` | Final robot trajectory missing. |
| Backhand chop | `refine_backhand_chop_serve_g1.py` | `augment_serves_backhand_chop_g1.py`; general script with `backhand_chop` | Final robot trajectory missing. |
| Forehand side-spin | `refine_custom_serve_g1_2.py` (default style) | `augment_serves_custom_g1.py`; general script with `forehand_right_side_spin` | Raw racket/ball capture exists; robot trajectory missing. |
| Backhand side-spin | `refine_custom_serve_g1.py` (default style) | `augment_serves_custom_g1.py`; general script with `backhand_right_side_spin` | Raw racket/ball capture exists; robot trajectory missing. |
| Tabletop pickup | `refine_pick_motion_g1.py`, `refine_pick_motion_left_g1.py` | `augment_pick_motions_g1.py`, `augment_pick_motions_left_g1.py` | Final trajectories missing for both hand variants. |
| Under-table pickup | `refine_pick_ground_motion_left_g1.py` | `augment_ground_pick_motions_left_g1.py` | Initial `pick_under_table.csv`, 600 frames at 60 fps. Final refined/augmented trajectories missing. |
| Bimanual pick-and-place | `refine_bimanual_pick_motion_g1.py` | `augment_bimanual_pick_motions_g1.py` | Six `bimanual_pick_corrected*.csv` files, 460–480 frames. |
| Ladder climbing | `refine_climbing_motion_g1.py` | `augment_climbing_motions_g1_vis.py` | `climbing_corrected.csv`, 364 frames. |

CSV files above are in `LAFAN1_Retargeting_Dataset/g1/`. The robot is the G1
29-DOF model in `g1_29dof.urdf`, with meshes from `robots/meshes/`.
The forehand augmentation viewer instead uses the source script’s 43-joint
`robots/g1_29dof_with_hand.urdf`; see [FOREHAND_AUGMENTATION.md](FOREHAND_AUGMENTATION.md).
Using the 29-DOF model for the other task previews preserves the `left_rubber_hand` and `right_rubber_hand`
frames used by the task optimizers. No finger articulation is invented for
29-joint motions.

`visualization/tasks.json` records the per-task mapping, expected missing output
paths, explicit import selections, and frame-rate rationale. The generated
`catalog.json` lists the motions currently packaged with this website.

## Other Viser code

The search found **32 Python files** importing Viser. All paths and Viser-related
line numbers are recorded in [source_inventory.json](../visualization/source_inventory.json).
In addition to the task entry points above:

- `augment_serves_g1_vis.py`: older multi-motion serve overlay.
- `augment_climbing_motions_g1.py`: older climbing augmenter. Its output directory
  is named `refined_augmented_bimanual_pick_g1`, which conflicts with the bimanual
  task. Prefer the `_vis.py` variant with `refined_augmented_climbing_g1`.
- `coll_vis.py`, `coll_vis2.py`: collision/optimization experiments that read
  `10.pkl`; not the canonical task players.
- `generate_67_motion.py`, `generate_denae_hi_motion.py`: additional motion
  generation experiments with Viser playback; outside the ten paper tasks.
- `holosoma/src/holosoma_retargeting/viser_player.py`: reusable retargeted-motion player.
- `holosoma/src/holosoma_retargeting/data_conversion/viser_body_vel_player.py`:
  player for the body-velocity conversion format.
- `holosoma/src/holosoma_retargeting/src/viser_utils.py`: shared Viser utilities.
- `holosoma/src/holosoma_retargeting/src/interaction_mesh_retargeter.py`:
  retargeting/scene visualization integration.

## Data findings and limits

1. Many meshes and serialized motions initially contained Git LFS pointer text.
   The needed G1 meshes and `refined_serve_g1/base.pkl` were hydrated from the
   source repository. Pointer text is rejected by the new importer.
2. `pick_under_table_corrected.csv` is byte-identical to
   `bimanual_pick_corrected.csv` (SHA-256 prefix `72f65eee19e3dfdc`). It is excluded
   from the under-table task. The initial under-table motion is labeled
   **Before contact refinement** on the website.
3. Side-spin root CSVs are OptiTrack racket/ball captures, not 36-column robot
   joint trajectories. `extract_serve_racket_ball.py` processes those captures.
   They are not substituted for robot motions.
4. `refined_serve_g1/{style}.pkl`, most other `refined_*` and
   `refined_augmented_*` outputs, retargeting `demo_results`, and the relevant
   refined camera matrices are absent. Reconstructed table point clouds cannot
   be placed reliably without the corresponding alignment information.
5. The six bimanual CSVs differ, but their contact offsets and generation
   history are not embedded in the files. They are labeled **Version 1–6**, not
   “left/right/higher” or quantitative augmentation results.
6. World positions and joint trajectories are preserved. CSV quaternions are
   converted from `xyzw` to `wxyz`, normalized, and made sign-continuous. Some
   bimanual quaternion norms are approximately 0.995. CSVs and the legacy PKL
   have no timestamps; 30 fps follows the refinement/playback convention,
   except the initial under-table CSV, whose source script specifies 60 fps.
7. The translucent box is inferred from the hand midpoint using the bimanual
   script's dimensions and contact interval, not a measured object trajectory.
   Ladder rungs and contact schedules come from the climbing visualization
   script. They are schematic task context, not a reconstructed scene or
   independent evidence of achieved contacts.

Each packaged NPZ contains its source filename, full SHA-256, coordinate
convention, processing description, source revision, stage, and frame-rate
basis. Robot asset hashes and mesh reduction counts are in
`visualization/robot/provenance.json`. The imported reference trajectory values are preserved. Forehand augmentations
are newly optimized from the original reference following the source script;
their 3.5 cm visualization lift affects only the displayed scene.

## Files needed to complete the remaining scenes

Supply the final named serve PKLs, tabletop pickup PKL(s), final under-table
pickup PKL, and selected augmentation outputs for each task. Include contact
offsets, timing, and frame rates where available. For reconstructed scenes,
include both scene geometry and the camera/world alignment used by the source
viewer. Exact expected paths are listed per task in `visualization/tasks.json`.

Import/export instructions: [VISER.md](VISER.md).
