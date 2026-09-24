# Putting VICAR motions into the interactive viewer

## A project that already does this

[Gauss Gym](https://escontrela.me/gauss_gym/) hosts interactive robot/scene visualizations using Viser. Its page embeds a Viser client in an iframe with a `playbackPath` pointing to a `.viser` recording. This website uses the same deployment pattern, with both the client and recordings stored in this repository.

Viser's [official embedded visualization guide](https://viser.studio/main/embedded_visualizations/) documents static and animated scene export, camera settings, iframe embedding, and GitHub Pages hosting. The supplied files use **Viser 1.1.1** so that recorder and client formats match.

## What runs on GitHub Pages

- Scene rendering, camera orbit/pan/zoom, timeline playback, speed changes, and scene-tree inspection run in the browser.
- Selecting a contact preset loads a different precomputed `.viser` recording. Record each real augmentation once, then host all of them as static files.
- Python callbacks, online motion generation, physics, and continuous optimization do **not** run in a static recording. They need a live Viser server or a separate browser implementation.

The template includes two geometric, schematic animations to test the viewer, with five presets each. They are not VICAR research results. Keep `illustrative: true` while using them. You can remove the example generation script and example recordings once you replace them.

## Export your actual robot and scene

Install the pinned version in an isolated environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements-demo.txt
```

Create your normal Viser visualization with `server.scene` (not a per-client scene). Load the real G1 model with `viser.extras.ViserUrdf` and your URDF loader, or add your reconstructed meshes directly. In your existing trajectory script:

```python
import numpy as np
import viser
from scripts.export_recording import export_recording

server = viser.ViserServer()
server.scene.set_up_direction('+z')

# Add your robot, reconstructed obstacles, contact targets, and reference ghost.
# Existing code creates `robot_visualizer`, `root_handle`, `joint_positions`,
# `root_positions`, and `root_quaternions_wxyz` from your real trajectory.

server.initial_camera.position = (2.9, -3.9, 2.4)
server.initial_camera.look_at = (0.6, 0.0, 0.7)
server.initial_camera.up = (0.0, 0.0, 1.0)

def update_frame(frame):
    root_handle.position = root_positions[frame]
    root_handle.wxyz = root_quaternions_wxyz[frame]
    robot_visualizer.update_cfg(joint_positions[frame])
    # Update object poses, contact indicators, and other animated handles here.

export_recording(server, update_frame, len(joint_positions),
                 'assets/recordings/forehand-left.viser', fps=30)
server.stop()
```

The model-specific variables above are integration points for your current visualization code. The helper records scene updates and inserts the frame timing. Confirm that joint ordering, coordinate convention, units, quaternion convention (`wxyz`), and frame rate match the source data. Never export private filesystem paths or credentials into scene labels.

For a static scene only:

```python
from pathlib import Path
Path('assets/recordings/static-scene.viser').write_bytes(
    server.get_scene_serializer().serialize()
)
```

## Register each recording

In `assets/content.js`, add or edit a scene in `viewer.scenes`:

```js
{
  "id": "forehand",
  "title": "Forehand serve",
  "description": "Retargeted VICAR trajectories at five racket–ball hit points.",
  "illustrative": false,
  "variants": [
    { "id": "original", "label": "Original", "recording": "assets/recordings/forehand-original.viser" },
    { "id": "left", "label": "Shift left", "recording": "assets/recordings/forehand-left.viser" }
  ]
}
```

The site builds the scene selector and preset buttons from this manifest. It converts recording URLs to absolute URLs at runtime, so it works at `localhost` and under `/VICAR/` on Pages.

The gray/blue/amber legend is intended for original reference, selected variant, and contact target. Use those colors in your export or update the legend in `index.html` and `assets/style.css`.

## Rebuild or regenerate the supplied viewer

The client is already committed, so visitors and routine site editing need no Python installation.

With Viser 1.1.1 installed:

```sh
viser-build-client --out-dir viser-client/
python scripts/generate_demo_recordings.py
```

`--out-dir` is the verified CLI flag for this pinned version. Keep `viser-client/LICENSE` when updating the client. If you change Viser versions, rebuild both the client and all recordings and test them together.

## Optional live Viser server

To let visitors move continuous sliders that call your Python motion generator, host your Viser application separately behind HTTPS with WebSocket support. Use a trusted host that allows iframe embedding. Set a variant's `embedUrl` instead of `recording`:

```js
{ "id": "live", "label": "Live augmentation", "embedUrl": "https://your-viser-host.example/" }
```

The site then embeds that URL. The Python server must remain running and handle multiple visitors. A public HTTPS GitHub Pages page cannot embed an insecure HTTP localhost service.

## Check before publishing real results

1. Serve the repository via HTTP and load every preset.
2. Verify scene scale, camera framing, contact colors, timing, and representative frames.
3. Check one small-screen layout, and use Open viewer for a larger 3D workspace.
4. Replace the illustrative description and set `illustrative: false` only for real research data.

References checked 2026-09-24: [Viser embedding](https://viser.studio/main/embedded_visualizations/), [Viser source](https://github.com/viser-project/viser/tree/v1.1.1), [Gauss Gym](https://escontrela.me/gauss_gym/), [GitHub Pages configuration](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).
