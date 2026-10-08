"""Rebuild the four fixed phone-to-robot color LUTs (requires numpy and scipy).

Run this after editing serve_color_profiles.json. Normal video encoding reads
the committed LUTs directly and needs neither numpy nor scipy. Sample ROIs in
the JSON use local coordinates in each 1280x720 view, after SDR conversion.
"""

import json
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator


ROOT = Path(__file__).resolve().parent


def transform(rgb, profile):
    luma = rgb @ np.array([0.2126, 0.7152, 0.0722])
    chroma = np.max(rgb, axis=-1) - np.min(rgb, axis=-1)
    # Smoothly correct the cool table/tile colors without desaturating the
    # yellow equipment. No spatial masks or frame-dependent adjustments.
    cool = np.clip((rgb[..., 2] - rgb[..., 0]) / np.maximum(chroma, 0.03), 0, 1)
    saturation = 1 - (1 - profile["coolSaturation"]) * cool
    balanced = luma[..., None] + saturation[..., None] * (rgb - luma[..., None])
    yellow = np.clip(
        (np.minimum(rgb[..., 0], rgb[..., 1]) - rgb[..., 2])
        / np.maximum(np.max(rgb, axis=-1), 0.03), 0, 1,
    ) ** 2
    # Monotone, shape-preserving curves retain black and avoid tone reversals.
    curve = PchipInterpolator([0, 0.32, 0.75, 1], [0, *profile["tone"]])
    exposure = curve(luma) / np.maximum(luma, 0.000001)
    balanced *= exposure[..., None] * np.array(profile["whiteBalance"])
    balanced *= (1 + (profile["yellowGain"] - 1) * yellow)[..., None]
    return np.clip(balanced, 0, 1)


def main():
    profiles = json.loads((ROOT / "serve_color_profiles.json").read_text())
    output = ROOT / "color_luts"
    output.mkdir(exist_ok=True)
    values = np.linspace(0, 1, 33)
    # .cube order: red varies fastest, then green, then blue.
    blue, green, red = np.meshgrid(values, values, values, indexing="ij")
    rgb = np.stack([red, green, blue], axis=-1).reshape(-1, 3)
    for name, profile in profiles.items():
        assert 0 < profile["tone"][0] < profile["tone"][1] < profile["tone"][2] <= 1
        result = transform(rgb, profile)
        path = output / f"{name}.cube"
        with path.open("w") as stream:
            stream.write(f'TITLE "VICAR {name} background-match-2"\n')
            stream.write("LUT_3D_SIZE 33\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n")
            np.savetxt(stream, result, fmt="%.6f")
        print(path.name)


if __name__ == "__main__":
    main()
