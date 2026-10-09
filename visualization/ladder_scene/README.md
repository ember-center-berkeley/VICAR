# Supplied ladder scene (2026-10-08)

Playback sources from `ladder_scene_20261008.zip`, copied without modification.
`provenance.json` records the archive SHA-256 and each included file's hash.
The complete archive was also extracted to `/Users/dkalaria/Downloads/ladder_scene_20261008`.
Only the 35 robot meshes referenced by `main.urdf` are included here; unused
meshes, screenshots and the reference video remain in that original directory.

The website adapter is [`../ladder.py`](../ladder.py). It reads `motion.npz`,
`mapping.json`, `main.urdf`, the reconstructed ladder GLB, and literal marker
constants from `generator_source_snapshot.py`. The optimizer is never executed.
The original `viewer.py` and reconstruction sources are retained for comparison.

Run from the website root with its `visualization/requirements.txt` environment:

```sh
python -m visualization view --task ladder-climbing
python -m visualization export --task ladder-climbing
```

The package contains `climbing_short_fs:v0`: 605 frames at 50 Hz, WXYZ root
quaternions and 29 interleaved joint columns. Map joints by `mapping.json`.
No cropping, retiming, root translation, optimization or finger animation is added.
Root quaternions are normalized for rendering. The source camera viewpoint is
retained with the website's field of view.

The GLB includes its +3 cm Z correction; the display adds +3 cm X only. Final
tread top centers are X = 0.378, 0.454, 0.530, 0.606, 0.682, 0.758 m and
Z = 0.33, 0.63, 0.93, 1.23, 1.53, 1.83 m. Contact reference markers have their
own +4 cm X / −2 cm Z offset and retain the package's colors. They are generator
guides, not measured contacts or timing annotations for the reference motion.

The shared website player supplies playback, timeline, speed, restart and camera
controls. Scene options show the ladder and contact markers by default, with
floor grid and pelvis/ankle reference paths initially hidden. The gray ground
remains visible. Collision geometry and alternative rung/slab layouts are not
loaded or exposed. The original standalone viewer's controls are retained only
in the source snapshot, not used by the website or its adapted local viewer.
