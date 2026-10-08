"""Fixed human-view grades, visually matched to the paired robot recordings.

Keep the robot view as the reference. Static grades avoid exposure/saturation
pumping over time, and never change timestamps or the contact alignment.
"""

import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SERVE_PROFILES = json.loads((SCRIPT_DIR / "serve_color_profiles.json").read_text())

HLG_TO_SDR = (
    "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
    "tonemap=tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=limited,"
    "format=yuv420p"
)

PROFILES = {
    "forehand-side-spin": {"contrast": 0.99, "brightness": -0.005, "gamma": 0.94, "saturation": 0.90},
    "backhand-side-spin": {"contrast": 1.0, "brightness": -0.004, "gamma": 0.96, "saturation": 0.95},
    # These recordings already have similar exposure to their robot views.
    "tabletop-pickup": {"contrast": 1.0, "brightness": 0.0, "gamma": 1.0, "saturation": 0.90},
    "under-table-pickup": {"contrast": 1.0, "brightness": 0.0, "gamma": 0.97, "saturation": 0.88},
    "bimanual-pick-place": {"contrast": 1.0, "brightness": 0.0, "gamma": 0.98, "saturation": 0.88},
    "ladder-climbing": {"contrast": 0.90, "brightness": -0.025, "gamma": 0.84, "saturation": 0.72},
}


def human_grade(name):
    if name in SERVE_PROFILES:
        # These LUTs include separate shadow/midtone/highlight levels, white
        # balance, and selective color correction, calibrated after HLG_TO_SDR.
        path = SCRIPT_DIR / "color_luts" / f"{name}.cube"
        # Escape both the filter-option and filter-graph parsing layers.
        escaped = str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "'\\''")
        return f"lut3d=file='{escaped}':interp=tetrahedral"
    return "eq=" + ":".join(f"{key}={value}" for key, value in PROFILES[name].items())


def color_profile(name):
    if name in SERVE_PROFILES:
        return {
            "version": "background-match-2", "target": "human view only",
            "method": "Fixed 33-point 3D LUT after HLG-to-SDR conversion",
            "calibration": "Matched table, wall, cabinet and yellow housing samples at frames 36, 180 and 288",
            **{key: value for key, value in SERVE_PROFILES[name].items() if key != "samples"},
        }
    return {"version": "robot-match-1", "target": "human view only", **PROFILES[name]}
