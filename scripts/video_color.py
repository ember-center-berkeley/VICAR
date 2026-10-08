"""Fixed human-view grades, visually matched to the paired robot recordings.

Keep the robot view as the reference. Static grades avoid exposure/saturation
pumping over time, and never change timestamps or the contact alignment.
"""

HLG_TO_SDR = (
    "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
    "tonemap=tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=limited,"
    "format=yuv420p"
)

PHONE_SERVE = {"contrast": 0.90, "brightness": -0.03, "gamma": 0.82, "saturation": 0.72}
PROFILES = {
    "forehand": PHONE_SERVE,
    "backhand": PHONE_SERVE,
    "forehand-top-spin": PHONE_SERVE,
    "backhand-top-spin": PHONE_SERVE,
    "forehand-side-spin": {"contrast": 0.99, "brightness": -0.005, "gamma": 0.94, "saturation": 0.90},
    "backhand-side-spin": {"contrast": 1.0, "brightness": -0.004, "gamma": 0.96, "saturation": 0.95},
    # These recordings already have similar exposure to their robot views.
    "tabletop-pickup": {"contrast": 1.0, "brightness": 0.0, "gamma": 1.0, "saturation": 0.90},
    "under-table-pickup": {"contrast": 1.0, "brightness": 0.0, "gamma": 0.97, "saturation": 0.88},
    "bimanual-pick-place": {"contrast": 1.0, "brightness": 0.0, "gamma": 0.98, "saturation": 0.88},
    "ladder-climbing": {"contrast": 0.90, "brightness": -0.025, "gamma": 0.84, "saturation": 0.72},
}


def human_grade(name):
    return "eq=" + ":".join(f"{key}={value}" for key, value in PROFILES[name].items())


def color_profile(name):
    return {"version": "robot-match-1", "target": "human view only", **PROFILES[name]}
