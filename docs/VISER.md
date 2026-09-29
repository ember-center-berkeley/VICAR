# VICAR motion explorer

The website uses **Viser 1.1.1** with a local static playback client. It now shows
the actual G1 robot and saved TT_PLayer trajectories: forehand, initial
under-table pickup, six bimanual motion versions, and ladder climbing. Six other
task entries show a deliberate coming-soon state because their motion files
are absent. The earlier schematic example recordings have been removed.

See [VISUALIZATION_SOURCES.md](VISUALIZATION_SOURCES.md) for the complete source
map, task-specific scripts, missing data, and interpretation limits.

## Run the organized viewer locally

From the website checkout, with Python 3.10 or newer:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r visualization/requirements.txt
python -m visualization list
python -m visualization view --task ladder-climbing
```

Open `http://127.0.0.1:8080/`. The local player has play/pause, frame scrubbing,
speed, motion-version selection, hand-trace visibility, and restart controls.
It shares the renderer with the web exporter; it does not require IsaacLab,
MuJoCo, Pyroki, or the original absolute filesystem paths. Bind addresses and
ports are configurable with `--host` and `--port`.

```sh
python -m visualization view --task bimanual-pick-place --variant version-3
python -m visualization view --task forehand
python -m visualization view --task under-table-pickup
```

## Add a real augmentation

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

Edit a scene's description in `visualization/catalog.json` when its scope changes.
Keep stage labels accurate for reference motions, preliminary retargeting,
and actual augmentation results.

## Export and publish

```sh
python -m visualization export
python3 -m http.server 8000
```

Export writes one self-contained `.viser` recording per variant and regenerates
`assets/viewer-manifest.js`. The page loads this after `assets/content.js`.
The manifest includes only recordings present on disk, while keeping all ten
task entries visible. Preview at `http://localhost:8000/`, then commit and push
the website branch. GitHub Pages serves the update automatically.

The browser supports orbit/pan/zoom, timeline playback, speed, scene-tree
inspection, version switching, reset view, and opening the viewer separately.
It loads recordings on demand. Static recordings replay saved geometry and
motion; Python callbacks or continuous contact optimization require a live
server. Selecting a saved version does not run the VICAR optimizer.

The generated recordings are approximately 0.6–0.95 MB each. The robot's visual
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
  __main__.py             List, import, local player, static export commands
  prepare.py              Mesh reduction and audited source import
  motions/               Portable normalized NPZ motions with provenance
  robot/                 Reduced visual-only URDF, meshes, provenance, license
```

```sh
python -m unittest visualization.test_data -v
npm install
npx playwright install chromium
npm test
```

Data checks cover quaternion conversion, joint remapping, invalid inputs, LFS
pointers, and packaged robot/motion assets. Browser checks cover the video
carousel, all nine recordings, all six missing-task states, reset, project
prefixes, responsive widths, and missing-file recovery. `CHROME_CHANNEL=chrome`
uses an existing Chrome installation.

## References and notices

[Gauss Gym](https://escontrela.me/gauss_gym/) is an example of a project website
embedding offline Viser scenes. Viser's
[official embedding guide](https://viser.studio/main/embedded_visualizations/)
describes animated scene export and static hosting. The bundled client retains
its MIT license. Rebuild it with `viser-build-client --out-dir viser-client/`
if changing Viser versions, and regenerate recordings with the same version.

G1 robot assets retain the Unitree BSD 3-Clause notice in
`visualization/robot/LICENSE`; see [Unitree's source license](https://github.com/unitreerobotics/unitree_ros/blob/master/LICENSE).
Research trajectories retain their owners' rights. Rendering is a motion
preview, not a physics simulation or an independent evaluation of feasibility.
