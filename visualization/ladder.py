"""Replay the supplied 2026-10-08 ladder package through the shared site player."""
import ast
import json
import xml.etree.ElementTree as ET

import numpy as np
import yourdfpy
from viser.extras import ViserUrdf

from .data import ROOT

PACKAGE = ROOT / 'ladder_scene'


def load_robot_model():
    """Shared visual model for the ladder and bimanual task players."""
    return yourdfpy.URDF.load(PACKAGE / 'main.urdf',
        filename_handler=lambda fname: str(PACKAGE / fname.removeprefix('package://unitree_description/')),
        build_collision_scene_graph=False, load_collision_meshes=False)


def load_ladder():
    with np.load(PACKAGE / 'motion.npz', allow_pickle=False) as file:
        motion = dict(file)
    mapping = json.loads((PACKAGE / 'mapping.json').read_text())
    # The motion is breadth-first/interleaved, whereas ViserUrdf uses URDF
    # articulation order. Map by name rather than reusing the other G1's order.
    names = [j.attrib['name'] for j in ET.parse(PACKAGE / 'main.urdf').findall('joint')
             if j.attrib['type'] not in ('fixed', 'floating')]
    joints = motion['joint_pos'][:, [mapping['joint_names'].index(n) for n in names]]
    constants = {}
    for statement in ast.parse((PACKAGE / 'generator_source_snapshot.py').read_text()).body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            try:
                constants[statement.targets[0].id] = ast.literal_eval(statement.value)
            except (ValueError, TypeError):
                pass
    # Match viewer.py's contact-only helpers, including its separate offset.
    # The generator snapshot is parsed as data, never imported or executed.
    contacts = []
    for prefix, color in [('LEFT_FEET', (50, 200, 50)), ('RIGHT_FEET', (200, 50, 50)),
                          ('LEFT_HAND', (50, 100, 255)), ('RIGHT_HAND', (200, 50, 255))]:
        for index, (_, _, stair) in enumerate(constants[prefix + '_CONTACTS']):
            x, z = (.3 + (stair - 1) * constants['STAIR_TREAD'], .3 * stair + .07) if stair else (0, .03)
            contacts.append(dict(node=f'/anchors/{prefix}_{index}',
                                 position=[x, constants[prefix + '_Y'], z], color=color))
    provenance = json.loads((PACKAGE / 'provenance.json').read_text())
    meta = dict(label='Ladder reference', fps=float(motion['fps'][0]), default_index=0,
                active_joints=names, lift=0, axes={axis: dict(min=0, max=0, step=.01, default=0, values=[0]) for axis in 'xyz'},
                source='ladder_scene_20261008/viewer.py', reference=provenance['reference'],
                archive_sha256=provenance['archive_sha256'], source_files=provenance['files'],
                ladder_offset=[.03, 0, 0], anchor_offset=[.04, 0, -.02],
                visual_contacts=contacts, motion_kind='Unmodified reference playback; no augmentation solve')
    return dict(joints=joints[None], poses=np.concatenate([motion['body_quat_w'][:, 0], motion['body_pos_w'][:, 0]], axis=1),
                shifts=np.zeros((1, 3)), metadata=meta, body_positions=motion['body_pos_w'], body_names=mapping['body_names'])


class LadderScene:
    """Package visuals with the same scene-layer and timeline controls as tasks."""
    def __init__(self, server, data):
        self.server, self.data, self.meta = server, data, data['metadata']
        self.joints = data['joints']
        self.N, self.T, _ = data['joints'].shape
        self.default = 0
        self.targets = self.dynamic = self.object_presentation = None
        self.curves = []
        self.box_nodes = ['/anchors']
        self.layers = [
            dict(id='ladder', label='Reconstructed ladder', nodes=['/reconstructed_ladder'], default=True),
            dict(id='floor', label='Floor grid', nodes=['/floor'], default=False),
            dict(id='paths', label='Reference paths', nodes=['/paths'], default=False),
        ]
        server.scene.reset()
        server.scene.set_up_direction('+z')
        server.scene.world_axes.visible = False
        server.scene.add_mesh_simple('/ground_plane',
            vertices=np.array([[-3, -3, 0], [3, -3, 0], [3, 3, 0], [-3, 3, 0]], dtype=np.float32),
            faces=np.array([[0, 1, 2], [0, 2, 3]], dtype=np.uint32), color=(210, 213, 216), side='double')
        server.scene.add_grid('/floor', width=6, height=6, cell_size=.1, section_size=1,
                              position=(0, 0, .0005), visible=False)
        self.model = load_robot_model()
        self.root = server.scene.add_frame('/robot', show_axes=False)
        self.robot = ViserUrdf(server, self.model, root_node_name='/robot', load_collision_meshes=False)
        self.nodes = {j.name: h.name for j, h in zip(self.robot._joint_map_values, self.robot._joint_frames)}
        # The GLB already contains the package's +3 cm Z correction.
        server.scene.add_frame('/reconstructed_ladder', show_axes=False, position=self.meta['ladder_offset'])
        server.scene.add_glb('/reconstructed_ladder/asset', (PACKAGE / 'reconstruction/ladder_reconstructed.glb').read_bytes())
        server.scene.add_frame('/anchors', show_axes=False, position=self.meta['anchor_offset'])
        for contact in self.meta['visual_contacts']:
            server.scene.add_icosphere(contact['node'], radius=.025, color=contact['color'], position=contact['position'])
        server.scene.add_frame('/paths', show_axes=False, visible=False)
        for name, color in [('pelvis', (238, 179, 46)), ('left_ankle_roll_link', (70, 170, 245)), ('right_ankle_roll_link', (68, 209, 138))]:
            points = data['body_positions'][:, data['body_names'].index(name)]
            server.scene.add_line_segments('/paths/' + name, points=np.stack([points[:-1], points[1:]], axis=1),
                                            colors=color, thickness=2, thickness_units='screen')
        server.initial_camera.position = (-1.8, -3., 2.)
        server.initial_camera.look_at = (.4, 0, 1.1)
        server.initial_camera.up = (0, 0, 1)
        # Keep the website's framing while preserving the package viewpoint.
        server.initial_camera.fov = .67
        self.update(0, 0)

    def update(self, frame, index):
        with self.server.atomic():
            pose = self.data['poses'][frame]
            self.root.position = pose[4:]
            self.root.wxyz = pose[:4] / np.linalg.norm(pose[:4])
            self.robot.update_cfg(dict(zip(self.meta['active_joints'], self.data['joints'][index, frame])))
