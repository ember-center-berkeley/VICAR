# VICAR visualization source map

Current audit: TT_PLayer revision `b377ba951d2bd12bef45e23a5e623342038121e0`.
Nine task categories use the canonical augmentation scripts; ladder climbing
uses the supplied `ladder_scene_20261008` standalone reference package.
Paths below are relative to the TT_PLayer checkout. The original training,
refinement, and augmentation code remains there; `visualization/` contains the
portable data preparation, renderer, local player, and static web exporter.

## Current task entry points

| Website task | Augmentation source | Input | Published motions |
| --- | --- | --- | --- |
| Simple forehand | `augment_serves_general_g1.py --serve_style forehand` | `refined_serve_g1/forehand.pkl` | 729 |
| Simple backhand | General script, `backhand` | `refined_serve_g1/backhand.pkl` | 729 |
| Forehand chop | General script, `forehand_chop` | `refined_serve_g1/forehand_chop.pkl` | 729 |
| Backhand chop | General script, `backhand_chop` | `refined_serve_g1/backhand_chop.pkl` | 729 |
| Forehand side-spin | General script, `forehand_right_side_spin` | `refined_serve_g1/forehand_right_side_spin.pkl` | 729 |
| Backhand side-spin | General script, `backhand_right_side_spin` | `refined_serve_g1/backhand_right_side_spin.pkl` | 729 |
| Tabletop, left hand | `augment_pick_motions_left_g1.py` | `refined_pick_g1/pick_left.pkl` | 306 |
| Tabletop, right hand | `augment_pick_motions_g1.py` | `refined_pick_g1/pick.pkl` | 306 |
| Under-table pickup | `augment_ground_pick_motions_left_g1.py` | `refined_ground_pick_g1/ground_pick_left.pkl` | 250 |
| Bimanual pick/place | `augment_bimanual_pick_motions_g1.py` | `refined_bimanual_pick_g1/bimanual_pick.pkl` | 50 |
| Ladder climbing | `ladder_scene_20261008/viewer.py` | `climbing_short_fs:v0` (`motion.npz`) | 1 reference, 605 frames at 50 Hz |

Most source scripts contain their Viser setup and replay loop inside the
optimization program. `--vis` also runs optimization and loads optional
training dependencies. For lightweight playback use `python -m visualization
view --task <id>` from this website checkout.

The serve model is `urdf/g1/g1_racket.urdf`, with a right racket and left ball
holder. Pickup tasks display `g1_29dof_with_hand.urdf`, using the source's
43-joint mapping and finger timelines. Bimanual and ladder share the ladder
package's exact 29-joint visual model; bimanual maps its solved body joint
angles by name. Manipulation tasks optimize with `g1_29dof.urdf`, or
`g1_29dof_feet_edge.urdf` for the archived climbing solve. The current ladder
replays the package's `main.urdf`, all 35 referenced visual meshes, and reconstructed
ladder GLB; checksums are in `visualization/ladder_scene/provenance.json`. See
[SERVE_AUGMENTATION.md](SERVE_AUGMENTATION.md) and
[TASK_AUGMENTATION.md](TASK_AUGMENTATION.md) for exact ranges, geometry,
rendering adaptations, regeneration, and solver diagnostics.

`visualization/tasks.json` keeps the source map and initial import selections;
`catalog.json` includes those retained imports plus the current `augmentations`
registry. Input/script/solver/URDF hashes are stored in each generated NPZ and
public JSON. The reconstructed table and camera hashes are recorded in
[`scene-provenance.json`](../visualization/motions/tasks/scene-provenance.json).

## Other Viser code

The indexed Viser-related files and source line numbers are recorded in
[source_inventory.json](../visualization/source_inventory.json). Other entries
include:

- `augment_serves_forehand_g1.py` and the other style-specific scripts:
  earlier per-style augmenters. The old forehand export is retained for
  reproduction; it does not replace the live general-script forehand.
- `augment_pick_motions_left_g1_.py`: an earlier left-pick variant. The current
  canonical filename has no trailing underscore.
- `augment_climbing_motions_g1.py`: the previous climbing source, replaced by
  `augment_climbing_motions_g1_vis.py` for its revised contact schedule, toe-edge
  constraints, joint limits, and visualization geometry. Both solves are now
  superseded on the website by the standalone reference package. The headless exporter
  disables source saving and writes uniquely named website NPZs.
- `augment_serves_g1_vis.py`: older multi-motion serve overlay.
- `coll_vis.py`, `coll_vis2.py`: collision/optimization experiments reading
  `10.pkl`, outside the ten task players.
- `generate_67_motion.py`, `generate_denae_hi_motion.py`: additional generation
  experiments outside the ten paper tasks.
- `holosoma/src/holosoma_retargeting/viser_player.py` and
  `data_conversion/viser_body_vel_player.py`: general retargeted-motion players.
- `holosoma/src/holosoma_retargeting/src/viser_utils.py` and
  `interaction_mesh_retargeter.py`: shared visualization and scene integration.

## Retained legacy imports

The first website import used revision
`49ecadb2d98643075de33509b01ab467450a4661`, before the final named PKLs and table
alignment were available. Those previews remain in the repository for local
inspection, but no longer supply the public task explorer.

- Initial under-table pickup: `LAFAN1_Retargeting_Dataset/g1/pick_under_table.csv`,
  600 frames at the source's 60 fps, labeled **Before contact refinement**.
- Bimanual: six `bimanual_pick_corrected*.csv` motions, 460–480 frames, labeled
  **Version 1–6** because their generation offsets are not recorded in the CSVs.
- Climbing: `climbing_corrected.csv`, 364 frames.
- Historical forehand: `refined_serve_g1/base.pkl` and its earlier augmentation.

`pick_under_table_corrected.csv` is byte-identical to
`bimanual_pick_corrected.csv` (SHA-256 prefix `72f65eee19e3dfdc`), so it was not
used for under-table pickup. Side-spin root CSVs are OptiTrack racket/ball
captures rather than 36-column robot trajectories and were not substituted for
robot motions. CSV imports convert `xyzw` to normalized, sign-continuous `wxyz`.

Many original assets use Git LFS. The importer rejects pointer text, and the
required motion and reconstruction assets have now been hydrated. The website
serves actual meshes, motion data, and Viser recordings directly from GitHub
Pages. It does not depend on LFS downloads at runtime.

Rendering remains a kinematic motion preview. Original solver convergence flags
and contact residuals are retained, rather than inferred from an attractive
render. Detailed limitations are in the two augmentation guides above.

Playback, import, export, and publishing: [VISER.md](VISER.md).
