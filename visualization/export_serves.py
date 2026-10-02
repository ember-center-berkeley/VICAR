"""Export all general-serve grids with the source racket, hit box and spline."""
import argparse
import gzip
import json
import time
import numpy as np
from scipy.spatial.transform import Rotation
import viser
from viser.extras import ViserUrdf
import yourdfpy
from .data import ROOT, Motion, read_catalog
from .serves import ACTIVE_NAMES, DISPLAY_FPS, DISPLAY_LIFT


def load_grid(task_id):
    base = Motion.load(ROOT / f'motions/serves/{task_id}-reference.npz')
    with np.load(ROOT / f'motions/serves/{task_id}-grid.npz', allow_pickle=False) as data:
        grid = dict(data)
    grid['metadata'] = json.loads(str(grid['metadata']))
    grid['default'] = int(np.argmin(np.linalg.norm(grid['shifts'] -
        [grid['metadata']['axes'][a]['default'] for a in 'xyz'], axis=1)))
    return base, grid


class ServeScene:
    def __init__(self, server, base, grid):
        self.server, self.base, self.grid = server, base, grid
        server.scene.reset()
        self.model = yourdfpy.URDF.load(str(ROOT / 'robot-racket/g1.urdf'))
        server.scene.set_up_direction('+z')
        server.scene.world_axes.visible = False
        server.scene.add_grid('/Ground', width=6, height=6, cell_size=.25, section_size=1,
            plane_color=(247, 249, 252), plane_opacity=1,
            cell_color=(223, 229, 238), section_color=(188, 200, 216))
        self.root = server.scene.add_frame('/base_new', show_axes=False)
        self.robot = ViserUrdf(server, self.model, root_node_name='/base_new')
        names = self.robot.get_actuated_joint_names()
        self.q = base.joints[:, [base.joint_names.index(name) for name in names]]
        self.joint_ids = [names.index(name) for name in ACTIVE_NAMES]
        self.nodes = {j.name: h.name for j, h in zip(self.robot._joint_map_values, self.robot._joint_frames)}
        self.marker = server.scene.add_icosphere('/hit_point', radius=.013, color=(255, 165, 0))
        x0, y0, z0 = grid['targets'].min(axis=0)
        x1, y1, z1 = grid['targets'].max(axis=0)
        corners = np.array([[x0,y0,z0],[x1,y0,z0],[x0,y1,z0],[x1,y1,z0],
                            [x0,y0,z1],[x1,y0,z1],[x0,y1,z1],[x1,y1,z1]], dtype=np.float32)
        edges = [(0,1),(1,3),(3,2),(2,0),(4,5),(5,7),(7,6),(6,4),(0,4),(1,5),(2,6),(3,7)]
        faces = np.array([[0,1,3],[0,3,2],[4,6,7],[4,7,5],[0,4,5],[0,5,1],
                          [2,3,7],[2,7,6],[0,2,6],[0,6,4],[1,5,7],[1,7,3]], dtype=np.uint32)
        self.box = server.scene.add_line_segments('/hit_box', points=corners[np.array(edges)],
            colors=(0, 0, 255), thickness=2, thickness_units='screen')
        self.box_mesh = server.scene.add_mesh_simple('/hit_box_mesh', vertices=corners,
            faces=faces, color=(0, 0, 255), opacity=.15, side='double')
        self.curve = server.scene.add_spline_catmull_rom('/traj_right_hand',
            points=grid['trajectories'][grid['default']], color=(0, 255, 0), thickness=3, thickness_units='screen')
        server.initial_camera.position = (2.2, -3., 1.8)
        server.initial_camera.look_at = (.05, 0., .8)
        server.initial_camera.up = (0, 0, 1)
        server.initial_camera.fov = .65
        self.update(0, grid['default'])

    def update(self, frame, index):
        pose = self.q[frame].copy()
        pose[self.joint_ids] = self.grid['arms'][index, frame]
        with self.server.atomic():
            self.root.position = self.base.positions[frame] + [0, 0, DISPLAY_LIFT]
            self.root.wxyz = self.base.wxyz[frame]
            self.robot.update_cfg(pose)
            # The source lifts the robot by 3.5 cm, but leaves overlays in the
            # unlifted target coordinates. Preserve this deliberate distinction.
            self.marker.position = self.grid['markers'][index]
            self.curve.points = self.grid['trajectories'][index]


def export_task(server, task):
    base, grid = load_grid(task['id'])
    metadata = grid['metadata']
    if metadata['max_steps'] != 10000:
        raise ValueError('Refusing to publish a shortened development solve.')
    arms = grid['arms']
    if arms.shape != (729, len(base.joints), 7):
        raise ValueError('Expected all 729 solved motions.')
    scene = ServeScene(server, base, grid)
    rotations = np.empty((*arms.shape, 4), dtype='<f4')
    for j, name in enumerate(ACTIVE_NAMES):
        joint = scene.model.joint_map[name]
        rotation = Rotation.from_matrix(joint.origin[:3, :3]) * Rotation.from_rotvec(arms[:, :, j].reshape(-1, 1) * joint.axis)
        rotations[:, :, j] = rotation.as_quat()[:, [3, 0, 1, 2]].reshape(729, len(base.joints), 4)
    recording = server.get_scene_serializer()
    for frame in range(len(base.joints)):
        scene.update(frame, grid['default'])
        recording.insert_sleep(1 / DISPLAY_FPS)
    output = ROOT.parent / 'assets/augmentation/serves'
    output.mkdir(parents=True, exist_ok=True)
    prefix = task['id']
    (output / f'{prefix}-base.viser').write_bytes(recording.serialize())
    (output / f'{prefix}-quaternions.bin.gz').write_bytes(gzip.compress(rotations.tobytes(), mtime=0))
    errors = np.linalg.norm(grid['achieved'] - grid['targets'], axis=1)
    config = {
        'version': 2, 'title': task['title'], 'frames': len(base.joints), 'fps': DISPLAY_FPS,
        'defaultIndex': grid['default'], 'hitFrame': metadata['hit_frame'],
        'quaternions': f'{prefix}-quaternions.bin.gz', 'quaternionShape': list(rotations.shape),
        'nodes': [scene.nodes[name] for name in ACTIVE_NAMES], 'owner': '',
        'targetNode': '/hit_point', 'displayLift': 0,
        'trajectoryNode': '/traj_right_hand', 'trajectories': grid['trajectories'].tolist(),
        'boxNodes': ['/hit_box', '/hit_box_mesh'], 'axes': metadata['axes'],
        'shifts': grid['shifts'].tolist(), 'targets': grid['markers'].tolist(),
        'costs': grid['costs'].tolist(), 'hitErrors': errors.tolist(),
        'provenance': {**metadata, 'total': 729,
            'median_hit_error_metres': float(np.median(errors)),
            'max_hit_error_metres': float(errors.max())},
    }
    (output / f'{prefix}.json').write_text(json.dumps(config, separators=(',', ':')) + '\n')
    print(f'{prefix}: 729 motions; median/max hit error {np.median(errors)*1000:.2f}/{errors.max()*1000:.2f} mm', flush=True)


def view_serve(task, host='127.0.0.1', port=8080):
    base, grid = load_grid(task['id'])
    server = viser.ViserServer(host=host, port=port)
    scene = ServeScene(server, base, grid)
    server.gui.add_markdown(f"## {task['title']}\nContact-point augmentation")
    axes = grid['metadata']['axes']
    controls = [server.gui.add_slider(f'{a.upper()} shift (m)', min=axes[a]['min'],
        max=axes[a]['max'], step=axes[a]['step'], initial_value=axes[a]['default']) for a in 'xyz']
    box = server.gui.add_checkbox('Show hit box', initial_value=True)
    playing = server.gui.add_checkbox('Play', initial_value=False)
    frame = server.gui.add_slider('Frame', min=0, max=len(base.joints)-1, step=1, initial_value=0)
    speed = server.gui.add_slider('Speed', min=.25, max=2, step=.25, initial_value=1.)
    deadline, previous = time.monotonic(), None
    try:
        while True:
            if playing.value and time.monotonic() >= deadline:
                frame.value = (frame.value + 1) % len(base.joints)
                deadline = time.monotonic() + 1 / (DISPLAY_FPS * speed.value)
            index = int(np.argmin(np.linalg.norm(grid['shifts'] - [c.value for c in controls], axis=1)))
            current = index, frame.value
            if current != previous:
                scene.update(frame.value, index)
                previous = current
            scene.box.visible = scene.box_mesh.visible = box.value
            time.sleep(.005)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task')
    args = parser.parse_args()
    server = viser.ViserServer(host='127.0.0.1', port=8098, verbose=False)
    try:
        for task in read_catalog()['tasks']:
            if task['kind'] == 'serve' and (not args.task or args.task == task['id']):
                export_task(server, task)
    finally:
        server.stop()


if __name__ == '__main__':
    main()
