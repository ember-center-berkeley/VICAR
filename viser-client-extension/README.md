# Viser offline augmentation extension

`AugmentationPlayback.ts` is compiled into the pinned Viser 1.1.1 client using
`python scripts/build_viser_client.py`. Each ordinary playback batch receives
selected joint rotations, contact targets/paths, object animations, and layer
visibility updates. The source patch fails if its anchors no longer match Viser.

`?augmentationPath=…` loads grid metadata and compressed float32 quaternion data.
Version 3 also supports a variable number of optimized joints, one-point and
nonuniform-size grids, fixed axes, multiple paths, and dynamic channels for
object position/orientation and contact-diagnostic color/scale. Existing serve
grids remain compatible.

Embedded mode uses same-origin parent messages and `controls=external`;
standalone mode displays its own actual-range XYZ sliders and scene toggles.
The fixed ladder solution has no XYZ sliders. Neither mode resets the Viser
camera, timeline, pause, or speed when a slider changes. Updates are appended
after baseline recording messages so seeks cannot restore a different sample
or override a hidden layer.

Full provenance, rebuild commands, and validation:
[SERVE_AUGMENTATION.md](../docs/SERVE_AUGMENTATION.md) and
[TASK_AUGMENTATION.md](../docs/TASK_AUGMENTATION.md).
