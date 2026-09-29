"""Export the script-faithful 43-joint scene and a shared augmentation grid."""
import gzip
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
import viser
from viser.extras import ViserUrdf
import yourdfpy
from .data import ROOT, Motion, JOINT_NAMES
from .forehand import ACTIVE_NAMES, DISPLAY_LIFT, DISPLAY_FPS, HIT_FRAME, TARGET_COST


def make_scene(server, base):
    model = yourdfpy.URDF.load(str(ROOT / 'robot-hands/g1.urdf'))
    if len(model.actuated_joint_names) != 43 or len(model.scene.geometry) != 50:
        raise ValueError('Expected the source script\'s 43-joint G1 model with 50 visual meshes.')
    server.scene.set_up_direction('+z')
    server.scene.world_axes.visible = False
    server.scene.add_grid('/Ground', width=6, height=6, cell_size=.25, section_size=1,
                          plane_color=(247, 249, 252), plane_opacity=1,
                          cell_color=(223, 229, 238), section_color=(188, 200, 216))
    root = server.scene.add_frame('/base_new', show_axes=False)
    robot = ViserUrdf(server, model, root_node_name='/base_new')
    marker = server.scene.add_icosphere('/Hit_target', radius=.018, color=(239, 168, 51))
    # The source maps the 29 body joints into 43, leaving 14 fingers at zero.
    q = np.zeros((len(base.joints), 43))
    for i, name in enumerate(robot.get_actuated_joint_names()):
        if name in JOINT_NAMES:
            q[:, i] = base.joints[:, JOINT_NAMES.index(name)]
    server.initial_camera.position = (2.2, -3., 1.8)
    server.initial_camera.look_at = (.05, 0., .8)
    server.initial_camera.up = (0, 0, 1)
    server.initial_camera.fov = .65
    nodes = {j.name: h.name for j, h in zip(robot._joint_map_values, robot._joint_frames)}
    return model, robot, root, marker, q, nodes


def main():
    base = Motion.load(ROOT / 'motions/forehand-reference.npz')
    with np.load(ROOT / 'motions/forehand-grid.npz', allow_pickle=False) as data:
        arms, shifts, targets = data['arms'], data['shifts'], data['targets']
        costs, achieved = data['costs'], data['achieved']
        metadata = json.loads(str(data['metadata']))
    if arms.shape != (729, len(base.joints), 7):
        raise ValueError('Export requires the complete 9x9x9 forehand grid.')
    server = viser.ViserServer(host='127.0.0.1', port=8098)
    try:
        model, robot, root, marker, q, nodes = make_scene(server, base)
        owner = ''  # Viser server scene's default owner.
        # Local joint rotation = URDF origin rotation * rotation(axis, angle).
        quaternions = np.empty((*arms.shape, 4), dtype='<f4')
        for j, name in enumerate(ACTIVE_NAMES):
            joint = model.joint_map[name]
            origin = Rotation.from_matrix(joint.origin[:3, :3])
            rotations = origin * Rotation.from_rotvec(arms[:, :, j].reshape(-1, 1) * joint.axis)
            quaternions[:, :, j] = rotations.as_quat()[:, [3, 0, 1, 2]].reshape(729, len(q), 4)
        default = int(np.argmin(np.linalg.norm(shifts - [-.08, 0, 0], axis=1)))
        marker.position = targets[default] + [0, 0, DISPLAY_LIFT]
        root.position = base.positions[0] + [0, 0, DISPLAY_LIFT]
        root.wxyz = base.wxyz[0]
        robot.update_cfg(q[0])
        serializer = server.get_scene_serializer()
        for frame in range(len(q)):
            root.position = base.positions[frame] + [0, 0, DISPLAY_LIFT]
            root.wxyz = base.wxyz[frame]
            robot.update_cfg(q[frame])
            serializer.insert_sleep(1 / DISPLAY_FPS)
        output = ROOT.parent / 'assets/augmentation'
        output.mkdir(parents=True, exist_ok=True)
        (output / 'forehand-base.viser').write_bytes(serializer.serialize())
        (output / 'forehand-quaternions.bin.gz').write_bytes(gzip.compress(quaternions.tobytes(), mtime=0))
        errors = np.linalg.norm(achieved - targets, axis=1)
        config = {
            'version': 1, 'frames': len(q), 'fps': DISPLAY_FPS, 'defaultIndex': default,
            'quaternions': 'forehand-quaternions.bin.gz', 'quaternionShape': list(quaternions.shape),
            'nodes': [nodes[name] for name in ACTIVE_NAMES], 'owner': owner,
            'targetNode': '/Hit_target', 'displayLift': DISPLAY_LIFT,
            'axes': {'x': {'min': -.12, 'max': -.04, 'step': .01, 'default': -.08},
                     'y': {'min': -.04, 'max': .04, 'step': .01, 'default': 0},
                     'z': {'min': -.04, 'max': .04, 'step': .01, 'default': 0}},
            'shifts': shifts.round(5).tolist(), 'targets': targets.tolist(),
            'costs': costs.tolist(), 'hitErrors': errors.tolist(),
            'provenance': {**metadata, 'converged': int((costs < TARGET_COST).sum()),
                           'total': len(costs), 'max_hit_error_metres': float(errors.max())},
        }
        (output / 'forehand.json').write_text(json.dumps(config, separators=(',', ':')) + '\n')
        print(f'Exported {len(shifts)} shifts; compressed rotations {(output / "forehand-quaternions.bin.gz").stat().st_size / 1e6:.2f} MB')
        print(f'Hit error: median {np.median(errors)*1000:.2f} mm, maximum {errors.max()*1000:.2f} mm')
    finally:
        server.stop()


if __name__ == '__main__':
    main()
