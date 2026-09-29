"""One scene implementation shared by local playback and static web exports."""
import numpy as np
from scipy.spatial.transform import Rotation
import yourdfpy
from viser.extras import ViserUrdf
from .data import ROOT

BLUE = (62, 124, 224)
CORAL = (225, 117, 103)
AMBER = (241, 169, 52)
# Copied from augment_climbing_motions_g1_vis.py; ranges are inclusive.
CLIMB_CONTACTS = {
    'left_ankle_roll_link': [(0, 69, 0), (95, 165, 1), (206, 363, 3)],
    'right_ankle_roll_link': [(0, 115, 0), (150, 225, 2), (244, 363, 3)],
    'left_rubber_hand': [(69, 156, 4), (206, 297, 6)],
    'right_rubber_hand': [(140, 240, 5), (280, 297, 6)],
}


def joint_order(motion, names):
    if set(names) != set(motion.joint_names):
        raise ValueError('The robot and motion must have the same named actuated joints.')
    return motion.joints[:, [motion.joint_names.index(n) for n in names]]


class MotionScene:
    def __init__(self, server, motion, task):
        self.server, self.motion, self.task = server, motion, task
        server.scene.reset()
        server.scene.set_up_direction('+z')
        server.scene.world_axes.visible = False
        server.scene.add_grid('/Ground', width=6, height=6, cell_size=.25, section_size=1,
                              cell_color=(219, 226, 237), section_color=(182, 196, 216),
                              plane_color=(246, 249, 253), plane_opacity=1)
        self.root = server.scene.add_frame('/G1', show_axes=False)
        self.model = yourdfpy.URDF.load(str(ROOT / 'robot/g1.urdf'), load_collision_meshes=False)
        if len(self.model.scene.geometry) != 36:
            raise ValueError('Expected all 36 G1 visual meshes; check the robot/meshes directory.')
        self.robot = ViserUrdf(server, self.model, root_node_name='/G1')
        self.q = joint_order(motion, self.robot.get_actuated_joint_names())
        self.paths = self._compute_paths()
        self.traces = []
        for side, color in [('left', BLUE), ('right', CORAL)]:
            points = self.paths[f'{side}_rubber_hand']
            self.traces.append(server.scene.add_line_segments(
                f'/Hand_paths/{side}', np.stack((points[:-1], points[1:]), axis=1),
                colors=color, thickness=2.5, thickness_units='screen'))
        self.contact_markers = []
        self.box = None
        if task['kind'] == 'ladder':
            self._ladder()
        elif task['kind'] == 'bimanual':
            self.box_path = (self.paths['left_rubber_hand'] + self.paths['right_rubber_hand']) / 2
            self.box = server.scene.add_box('/Inferred_box', dimensions=(.3, .3, .4),
                                            color=AMBER, opacity=.35)
        center = motion.positions.mean(axis=0)
        look_at = np.array([center[0] + .15, center[1], .92 if task['kind'] == 'ladder' else .80])
        server.initial_camera.look_at = tuple(look_at)
        camera_offset = [2.7, -3.7, 1.6] if task['kind'] == 'ladder' else [2.1, -2.6, 1.2]
        server.initial_camera.position = tuple(look_at + np.array(camera_offset))
        server.initial_camera.up = (0, 0, 1)
        server.initial_camera.fov = .67
        self.update(0)

    def _compute_paths(self):
        links = ['left_rubber_hand', 'right_rubber_hand', 'left_ankle_roll_link', 'right_ankle_roll_link']
        paths = {name: [] for name in links}
        rotations = Rotation.from_quat(self.motion.wxyz[:, [1, 2, 3, 0]]).as_matrix()
        for i, q in enumerate(self.q):
            self.model.update_cfg(q)
            for name in links:
                local = self.model.get_transform(name)[:3, 3]
                paths[name].append(rotations[i] @ local + self.motion.positions[i])
        return {name: np.array(points) for name, points in paths.items()}

    def _ladder(self):
        for step in range(1, 7):
            self.server.scene.add_box(f'/Ladder/Rung_{step}', dimensions=(.076, 1., .05),
                                      position=(.4 + (step - .5) * .076, 0., .30 * step),
                                      color=(127, 149, 174), opacity=.85)
        for link, events in CLIMB_CONTACTS.items():
            y = (.25 if 'hand' in link else .15) * (1 if link.startswith('left') else -1)
            for start, end, step in events:
                position = (0., y, .03) if step == 0 else (.4 + (step - 1) * .076, y, .3 * step + .07)
                handle = self.server.scene.add_icosphere(f'/Scheduled_contacts/{link}_{start}',
                                                         radius=.025, color=AMBER, position=position)
                self.contact_markers.append((handle, start, end))

    def update(self, frame):
        frame = int(frame)
        with self.server.atomic():
            self.root.position = self.motion.positions[frame]
            self.root.wxyz = self.motion.wxyz[frame]
            self.robot.update_cfg(self.q[frame])
            for marker, start, end in self.contact_markers:
                marker.visible = start <= frame <= end
            if self.box is not None:
                # Geometric context only, inferred from the two hand trajectories.
                # Use the contact interval in augment_bimanual_pick_motions_g1.py.
                i = min(max(frame, 150), min(299, len(self.box_path) - 1))
                self.box.position = self.box_path[i]

    def show_traces(self, visible):
        for handle in self.traces:
            handle.visible = bool(visible)
