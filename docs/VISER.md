# VICAR motion explorer

The website uses **Viser 1.1.1** with a local static playback client. All ten
task categories are populated from the canonical augmentation scripts, with
both hands available for tabletop pickup. Each viewer exposes its actual
sampled ranges and scene layers. See [SERVE_AUGMENTATION.md](SERVE_AUGMENTATION.md)
and [TASK_AUGMENTATION.md](TASK_AUGMENTATION.md) for source mappings, ranges,
regeneration, and numerical diagnostics. [VISUALIZATION_SOURCES.md](VISUALIZATION_SOURCES.md)
maps the original code and retained legacy imports.

## Run the organized viewer locally

From the website checkout, with Python 3.10 or newer:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r visualization/requirements.txt
python -m visualization list
python -m visualization view --task ladder-climbing
```

Open `http://127.0.0.1:8080/`. The local players provide task-specific contact and visibility controls alongside
playback. Choose a tabletop hand with `--variant tabletop-left` or
`--variant tabletop-right`. Legacy saved-motion players also provide version selection.
It shares the renderer with the web exporter; it does not require IsaacLab,
MuJoCo, Pyroki, or the original absolute filesystem paths. Bind addresses and
ports are configurable with `--host` and `--port`.

```sh
python -m visualization view --task bimanual-pick-place --variant version-3
python -m visualization view --task forehand
python -m visualization view --task under-table-pickup
```

## Import a saved motion for local inspection

The canonical format is a pickle-free NPZ with `positions [T,3]`, `wxyz [T,4]`,
`joints [T,29]`, `joint_names [29]`, scalar `fps`, and a JSON `metadata` string.
Positions use metres, angles use radians, and the world is Z-up. The loader
validates shapes, finiteness, frame rates, quaternion norms, and joint names.
It maps robot joints by name rather than relying on incidental URDF ordering.

Robot CSV imports must use the source convention: `xyz, xyzw, 29 joint angles`
(36 columns, no header). Specify the actual frame rate:

```sh
python -m visualization import --task bimanual-pick-place \
  --input /path/to/verified_shift_left.csv --id shift-left \
  --label 'Shift left' --fps 30
python -m visualization export --task bimanual-pick-place
```

Use a meaningful label only when the motion's contact offset is known. Import
refuses to overwrite an existing variant id. Canonical NPZ imports retain the
frame rate already saved inside the file.

For original VICAR PKLs, install the migration-only dependencies and explicitly
allow trusted pickle loading:

```sh
pip install torch jax jaxlie
python -m visualization import --task backhand \
  --input /path/to/refined_serve_g1/backhand.pkl --id reference \
  --label Reference --stage 'Saved reference' --fps 30 --trust-pickle
python -m visualization export --task backhand
```

The legacy importer reads `global_pose.wxyz_xyz`, `global_position`, and `joints`,
and maps torch storage to the CPU. Only use `--trust-pickle` for files you trust:
pickle deserialization can execute code. Normal playback and export load only
the portable NPZ files and do not import torch or JAX.

The public explorer prioritizes the canonical augmentation grids. An imported
CSV/NPZ remains available locally through `view --variant <id>`; it does not
replace those grids. To publish only a task's imported variants, deliberately
remove its `augmentations` catalog entry (and, for a serve, its generated grid).

Edit a scene's description in `visualization/catalog.json` when its scope changes.
Keep stage labels accurate for reference motions, preliminary retargeting,
and actual augmentation results.

## Export and publish

```sh
python -m visualization export
python3 -m http.server 8000
```

Export writes the static Viser scenes and augmentation data packs, then regenerates
`assets/viewer-manifest.js`. The page loads this after `assets/content.js`.
The manifest includes only recordings present on disk, while keeping all ten
task entries visible. Preview at `http://localhost:8000/`, then commit and push
the website branch. GitHub Pages serves the update automatically.

The browser supports orbit/pan/zoom, timeline playback, speed, scene-tree
inspection, version switching, reset view, and opening the viewer separately.
It loads recordings on demand. Static recordings replay saved geometry and
motion; Python callbacks or continuous contact optimization require a live
server. Selecting a saved version does not run the VICAR optimizer.

Legacy CSV recordings are approximately 0.6–0.95 MB each. Augmentation scenes
also include rotation packs, object channels, and reconstructed table geometry
where applicable. The robot's visual
meshes are simplified toward 1600 triangles per mesh; constrained meshes retain
more detail (up to 8906 triangles). Kinematics are preserved.
The included URDF is for visualization and omits collision and inertial elements.

## Rebuild the initial imports from TT_PLayer

Only needed when regenerating from the original checkout. Source selection is
explicit in `visualization/tasks.json`; there is no broad data-directory glob.
From the TT_PLayer checkout, retrieve the required LFS objects:

```sh
git lfs pull --include='robots/meshes/*,refined_serve_g1/base.pkl'
```

Then, from this website checkout:

```sh
python -m visualization.prepare --source-root /path/to/TT_PLayer \
  --trust-pickle --replace-catalog
python -m visualization export
```

`--replace-catalog` explicitly recreates the catalog from the audited imports,
replacing later manual additions to it. Back up an edited catalog first. The
source checkout is read only during preparation. Relative source names and
hashes are retained; machine-specific absolute paths are not published.

## Organization and checks

```text
visualization/
  tasks.json              Per-task source map and audited import selections
  source_inventory.json   All 32 Viser source files and entry-point line numbers
  catalog.json            Current imported task/variant registry
  data.py                 Validation, joint conventions, CSV/PKL migration
  scene.py                Shared G1 renderer, hand paths, object/contact context
  __main__.py             List, import, local player, static export/manifest commands
  serves.py               General serve grid generator
  task_augmentation.py    Headless canonical pickup/bimanual/climbing generators
  export_tasks.py         Task objects, scene layers, and browser animation packs
  prepare.py              Mesh reduction and audited source import
  motions/               Portable normalized NPZ motions with provenance
  robot/                 Reduced visual-only URDF, meshes, provenance, license
```

The full Python checks also need `visualization/requirements-augmentation.txt`
for the independent kinematic gradient tests.

```sh
python -m unittest visualization.test_data visualization.test_forehand visualization.test_serves visualization.test_tasks -v
npm install
npx playwright install chromium
npm test
```

Data checks cover quaternion conversion, joint remapping, invalid inputs, LFS
pointers, and packaged robot/motion assets. Browser checks cover the video
carousel, all ten tasks and eleven viewers, actual sampled ranges, fixed axes,
hand switching, scene layers, preserved playback, standalone controls, reset,
project prefixes, responsive widths, and missing-file recovery. `CHROME_CHANNEL=chrome`
uses an existing Chrome installation.

## References and notices

[Gauss Gym](https://escontrela.me/gauss_gym/) is an example of a project website
embedding offline Viser scenes. Viser's
[official embedding guide](https://viser.studio/main/embedded_visualizations/)
describes animated scene export and static hosting. The bundled client retains
its MIT license. Rebuild the extended client with `python scripts/build_viser_client.py`.
The extension currently targets Viser 1.1.1; update and test its patch explicitly
before changing Viser versions.

G1 robot assets retain the Unitree BSD 3-Clause notice in
`visualization/robot/LICENSE`; see [Unitree's source license](https://github.com/unitreerobotics/unitree_ros/blob/master/LICENSE).
Research trajectories retain their owners' rights. Rendering is a motion
preview, not a physics simulation or an independent evaluation of feasibility.
