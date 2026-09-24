"""Generate small, explicitly illustrative Viser recordings for the website.

These are geometric animations, NOT VICAR predictions, robot trajectories, or
experimental results. Replace them with exported research scenes before release.
Run with Python 3.10+ and the versions in requirements-demo.txt.
"""
from pathlib import Path
import math
import numpy as np
import trimesh
import viser

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "recordings"
BLUE = (53, 112, 222)
GREY = (165, 181, 202)
AMBER = (239, 166, 61)
OFFSETS = {
    "original": (0, 0, 0),
    "left": (0, 0.22, 0),
    "right": (0, -0.22, 0),
    "forward": (0.18, 0, 0),
    "higher": (0, 0, 0.18),
}


def quaternion_between_z(direction):
    direction = np.array(direction, dtype=float, copy=True)
    direction /= np.linalg.norm(direction)
    if direction[2] < -0.99999:
        return np.array([0.0, 1.0, 0.0, 0.0])
    q = np.r_[1.0 + direction[2], -direction[1], direction[0], 0.0]
    return q / np.linalg.norm(q)


class Robot:
    """A deliberately schematic humanoid, drawn from geometric primitives."""
    def __init__(self, scene, name, color, opacity=1.0):
        self.name = name
        self.parts = {}
        self.bones = {}
        for part, size in {"torso": (.19, .31, .34), "pelvis": (.18, .27, .16),
                           "head": (.18, .20, .23), "visor": (.035, .17, .07),
                           "left_foot": (.28, .13, .08), "right_foot": (.28, .13, .08)}.items():
            shade = (38, 50, 66) if part == "visor" else color
            self.parts[part] = scene.add_box(f"/{name}/{part}", color=shade,
                                            dimensions=size, opacity=opacity)
        for joint in ["left_hip", "right_hip", "left_knee", "right_knee", "left_ankle",
                      "right_ankle", "left_shoulder", "right_shoulder", "left_elbow",
                      "right_elbow", "left_hand", "right_hand"]:
            self.parts[joint] = scene.add_icosphere(f"/{name}/{joint}", radius=.052,
                                                    color=color, opacity=opacity, subdivisions=2)
        self.connections = [(side + '_' + a, side + '_' + b) for side in ['left', 'right']
                            for a, b in [('hip', 'knee'), ('knee', 'ankle'),
                                         ('shoulder', 'elbow'), ('elbow', 'hand')]]
        cylinder = trimesh.creation.cylinder(radius=.037, height=1, sections=12)
        for a, b in self.connections:
            self.bones[(a, b)] = scene.add_mesh_simple(f"/{name}/{a}-{b}",
                cylinder.vertices.astype(np.float32), cylinder.faces.astype(np.uint32),
                color=color, opacity=opacity)

    def pose(self, target, phase):
        # A smooth reach and return, for showing viewer controls only.
        reach = (1 - math.cos(2 * math.pi * phase)) / 2
        lean = .05 * reach
        points = {
            'pelvis': np.array([lean, 0, .73]), 'torso': np.array([lean+.02, 0, .98]),
            'head': np.array([lean+.03, 0, 1.30]), 'visor': np.array([lean+.126, 0, 1.32]),
            'left_foot': np.array([.07, .15, .045]), 'right_foot': np.array([.02, -.15, .045]),
        }
        for side, sign in [('left', 1), ('right', -1)]:
            points[f'{side}_hip'] = np.array([lean, sign*.13, .73])
            points[f'{side}_knee'] = np.array([.06, sign*.15, .40])
            points[f'{side}_ankle'] = np.array([.0, sign*.15, .11])
            points[f'{side}_shoulder'] = np.array([lean+.02, sign*.22, 1.10])
        points['left_hand'] = np.array([.28, .26, .97])
        points['left_elbow'] = np.array([.12, .30, .88])
        start = np.array([.16, -.32, .79])
        hand = start * (1-reach) + target * reach
        hand[2] += .10 * math.sin(math.pi * reach)
        points['right_hand'] = hand
        points['right_elbow'] = (points['right_shoulder']+hand)/2 + np.array([-.08, -.11, -.14])
        for name, position in points.items():
            self.parts[name].position = position
        for (a, b), bone in self.bones.items():
            direction = points[b]-points[a]
            bone.position = (points[a]+points[b])/2
            bone.wxyz = quaternion_between_z(direction)
            bone.scale = (1.0, 1.0, float(np.linalg.norm(direction)))
        return hand


def record(server, task, variant, delta):
    server.scene.reset()
    scene = server.scene
    scene.set_up_direction('+z')
    scene.world_axes.visible = False
    scene.add_grid('/floor', width=6, height=6, cell_size=.25, section_size=1,
                   cell_color=(218, 226, 237), section_color=(180, 196, 217),
                   plane_color=(247, 249, 252), plane_opacity=1)
    # A table and legs define a stable spatial reference for the contact changes.
    scene.add_box('/table/top', color=(98, 137, 170), dimensions=(1.20, 1.18, .05), position=(1.18, 0, .70))
    for i, (x, y) in enumerate([(0.68, -.48), (0.68, .48), (1.68, -.48), (1.68, .48)]):
        scene.add_box(f'/table/leg{i}', color=(149, 164, 184), dimensions=(.045, .045, .67), position=(x, y, .335))
    if task == 'serve':
        scene.add_box('/table/net', color=(217, 230, 246), dimensions=(.012, 1.19, .12), opacity=.75, position=(1.20, 0, .785))
        base = np.array([.65, -.12, 1.00])
    else:
        base = np.array([.70, -.10, .79])
    target = base + np.array(delta)
    ghost = Robot(scene, 'Original_reference', GREY, .25)
    ghost.pose(base, .5)
    robot = Robot(scene, 'Selected_variation', BLUE)
    scene.add_icosphere('/Contact_target', radius=.042, position=target, color=AMBER)
    scene.add_icosphere('/Original_contact', radius=.029, position=base, color=GREY, opacity=.45)
    # Dotted connector between the reference and new target.
    if np.linalg.norm(target-base) > 0:
        ticks = np.linspace(base, target, 13)
        scene.add_line_segments('/Contact_offset', np.stack([ticks[:-1:2], ticks[1::2]], axis=1),
                                 colors=AMBER, thickness=.009)
    phases = np.linspace(0, .5, 35)
    path = np.array([robot.pose(target, float(p)) for p in phases])
    scene.add_line_segments('/Reach_path', np.stack([path[:-1], path[1:]], axis=1),
                            colors=BLUE, thickness=.008)
    obj = None
    if task == 'pickup':
        obj = scene.add_box('/Object', color=AMBER, dimensions=(.09, .09, .09), position=target)
    else:
        racket = trimesh.creation.cylinder(radius=.082, height=.015, sections=24)
        obj = scene.add_mesh_simple('/Racket', racket.vertices.astype(np.float32), racket.faces.astype(np.uint32), color=(235, 122, 107))
    server.initial_camera.position = (2.9, -3.9, 2.4)
    server.initial_camera.look_at = (.60, 0.0, .68)
    server.initial_camera.up = (0.0, 0.0, 1.0)
    server.initial_camera.fov = .78
    robot.pose(target, 0)
    recording = server.get_scene_serializer()
    for phase in np.linspace(0, 1, 100):
        hand = robot.pose(target, float(phase))
        if task == 'serve':
            obj.position = hand
            obj.wxyz = quaternion_between_z([1, 0, .3])
        recording.insert_sleep(1 / 30)
    output = OUT / f'{task}-{variant}.viser'
    output.write_bytes(recording.serialize())
    print(f'Wrote {output.name} ({output.stat().st_size // 1024} KB)')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    server = viser.ViserServer(host='127.0.0.1', port=8098)
    try:
        for task in ['serve', 'pickup']:
            for variant, delta in OFFSETS.items():
                record(server, task, variant, delta)
    finally:
        server.stop()


if __name__ == '__main__':
    main()
