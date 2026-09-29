# Viser offline augmentation extension

`AugmentationPlayback.ts` is compiled into the pinned Viser 1.1.1 client using
`python scripts/build_viser_client.py`. It adds seven selected joint orientation
updates and a hit-target position update to each ordinary playback batch.
The source patch is explicit and fails if its anchors no longer match Viser.

`?augmentationPath=…` loads the grid metadata and compressed float32 quaternion
array. Embedded mode uses same-origin parent messages and `controls=external`;
standalone mode displays its own X/Y/Z sliders. Neither mode resets the Viser
camera, timeline, or scene when a slider changes.

Full data provenance, rebuild commands, and validation:
[FOREHAND_AUGMENTATION.md](../docs/FOREHAND_AUGMENTATION.md).
