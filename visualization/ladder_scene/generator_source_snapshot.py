import argparse
import numpy as np
import os
import viser
from viser.extras import ViserUrdf
import torch
import multiprocessing as mp
from multiprocessing.shared_memory import SharedMemory
from isaac_utils.rotations import(
    quat_conjugate,
    quaternion_to_matrix,
    slerp
)
import pytorch_kinematics as pk
import pyroki as pk2
import jax.numpy as jnp
import jaxlie
import pickle
import yourdfpy
import time
from retarget.spa import solve_joint_angles_batch
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# import pdb; pdb.set_trace()

START_FROM = 0

SAVE_DIR = "refined_augmented_climbing_g1"

parser = argparse.ArgumentParser()
parser.add_argument('--vis', action='store_true', help='Enable visualization')
parser.add_argument('--save', action='store_true', help='Whether to save the results')
parser.add_argument('--target_cost', type=float, default=0.028, help='Convergence cost threshold')
args = parser.parse_args()
VIS = args.vis
TARGET_COST = args.target_cost
SAVE = args.save
TABLE_HEIGHT = 0.8
TABLE_VOXEL_RESOLUTION = 0.05  # metres per voxel side
FEET_ALIGN_START = 0
FEET_ALIGN_END = 10

CONTACT_START_FRAME = 150
CONTACT_END_FRAME = 300
OBJECT_DIMS = [0.3, 0.3, 0.4]
LEAVE_FRAMES = 15
HAND_ROT_INDICES = [20,69,320,340]
N_STAIRS = 6
STAIR_TREAD = 0.076    # tread depth per step (x), metres
STAIR_DEPTH = 1.0     # extent in y, metres
STAIR_ORIGIN = np.array([0.3, 0.0, 0.0])  # front-left corner of step 1
LEFT_FEET_Y = 0.13
RIGHT_FEET_Y = -0.13
LEFT_HAND_Y = 0.11
RIGHT_HAND_Y = -0.11


# Tuples are of form[start index, end index, stair number]
LEFT_FEET_CONTACTS = [
                      [0,  69,  0],
                      [95, 165, 1],
                      [206, 363, 3]]
RIGHT_FEET_CONTACTS = [
                      [0,  115,  0],
                      [150, 225, 2],
                      [244, 363, 3]]

LEFT_HAND_CONTACTS = [[69, 156, 4],
                      [206, 297, 6]]
RIGHT_HAND_CONTACTS = [[140, 240, 5],
                      [280, 297, 6]]



PLATFORM_POSITION = [1.2, 0, TABLE_HEIGHT/2.]
PLATFORM_DIMENSIONS = [0.7, 1.0, TABLE_HEIGHT]
RIGHT_HAND_CONTACT_POINT = [0.45, -0.2, TABLE_HEIGHT]

heightmap = np.zeros((1000, 1000), dtype=np.float32)  # Dummy heightmap for visualization
heightmap = pk2.collision.Heightmap(
    pose=jaxlie.SE3.identity(),
    size=jnp.array([0.01, 0.01, 1.0]),
    height_data=heightmap,
)


def _stair_anchor(stair_no, y, offset=0.0):
    """Fixed-world anchor position on top of stair stair_no at lateral offset y."""
    x = STAIR_ORIGIN[0] + (stair_no - 1.) * STAIR_TREAD + offset
    z = 0.30 * stair_no + 0.07 
    if stair_no == 0:
        x = offset
        z = 0.03
    return torch.tensor([x, y, z], device=DEVICE, dtype=torch.float32).unsqueeze(0).expand(N_shifts, -1).clone()



def build_personal_mesh(center, side_lengths):
    """Return (vertices [8,3], faces [12,3]) for an axis-aligned cuboid."""
    cx, cy, cz = center
    hx, hy, hz = side_lengths[0] / 2, side_lengths[1] / 2, side_lengths[2] / 2
    verts = np.array([
        [cx - hx, cy - hy, cz - hz], [cx + hx, cy - hy, cz - hz],
        [cx - hx, cy + hy, cz - hz], [cx + hx, cy + hy, cz - hz],
        [cx - hx, cy - hy, cz + hz ], [cx + hx, cy - hy, cz + hz],
        [cx - hx, cy + hy, cz + hz ], [cx + hx, cy + hy, cz + hz],
    ], dtype=np.float32)
    faces = np.array([
        # [0, 1, 3], [0, 3, 2],
        [4, 6, 7], [4, 7, 5],
        [1, 4, 5], #[0, 5, 1],
        [6, 3, 7], #[2, 7, 6],
        # [0, 2, 6], [0, 6, 4],
        [1, 5, 7], [1, 7, 3],
        [1, 6, 4], [1, 3, 6]
    ], dtype=np.uint32)
    faces_reverse = faces.copy()
    faces_reverse[:, [0, 1]] = faces_reverse[:, [1, 0]]
    return verts, faces_reverse

def build_cuboid_mesh(center, side_lengths):
    """Return (vertices [8,3], faces [12,3]) for an axis-aligned cuboid."""
    cx, cy, cz = center
    hx, hy, hz = side_lengths[0] / 2, side_lengths[1] / 2, side_lengths[2] / 2
    verts = np.array([
        [cx - hx, cy - hy, cz - hz], [cx + hx, cy - hy, cz - hz],
        [cx - hx, cy + hy, cz - hz], [cx + hx, cy + hy, cz - hz],
        [cx - hx, cy - hy, cz + hz], [cx + hx, cy - hy, cz + hz],
        [cx - hx, cy + hy, cz + hz], [cx + hx, cy + hy, cz + hz],
    ], dtype=np.float32)
    faces = np.array([
        [0, 1, 3], [0, 3, 2],
        [4, 6, 7], [4, 7, 5],
        [0, 4, 5], [0, 5, 1],
        [2, 3, 7], [2, 7, 6],
        [0, 2, 6], [0, 6, 4],
        [1, 5, 7], [1, 7, 3],
    ], dtype=np.uint32)
    faces_reverse = faces.copy()
    faces_reverse[:, [0, 1]] = faces_reverse[:, [1, 0]]
    return verts, faces_reverse


def _vis_process_main(shm_ja_name, shm_meta_name, T, setup_data, port=8091):
    """Child process: serves viser, reads joint angles from shared memory."""
    import numpy as np
    import viser
    from viser.extras import ViserUrdf
    import yourdfpy
    import xml.etree.ElementTree as ET
    import io
    import time
    from multiprocessing.shared_memory import SharedMemory

    shm_ja   = SharedMemory(name=shm_ja_name)
    shm_meta = SharedMemory(name=shm_meta_name)
    ja_np  = np.ndarray((T, 43), dtype=np.float32, buffer=shm_ja.buf)
    _meta  = np.ndarray((2,),    dtype=np.int32,   buffer=shm_meta.buf)

    _tree = ET.parse(setup_data['urdf_path'])
    for _link in _tree.getroot().iter('link'):
        for _col in _link.findall('collision'):
            _geom = _col.find('geometry')
            if _geom is not None and len(_geom) and _geom[0].tag == 'capsule':
                _link.remove(_col)
    _buf = io.BytesIO()
    _tree.write(_buf)
    urdf = yourdfpy.URDF.load(io.BytesIO(_buf.getvalue()))

    server = viser.ViserServer(port=port)
    server.scene.add_frame("/base", show_axes=False)
    base_frame_new = server.scene.add_frame("/base_new", show_axes=False)
    urdf_vis = ViserUrdf(server, urdf, root_node_name="/base_new")
    playing = server.gui.add_checkbox("playing", False)
    timestep_slider = server.gui.add_slider("timestep", 0, T - 2, 1, 0)
    show_obstacles = server.gui.add_checkbox("show obstacles", True)

    sc = setup_data['stair_constants']
    N_STAIRS_    = sc['N_STAIRS']
    STAIR_TREAD_ = sc['STAIR_TREAD']
    STAIR_DEPTH_ = sc['STAIR_DEPTH']
    STAIR_ORIGIN_= np.array(sc['STAIR_ORIGIN'])

    def _stair_anchor(stair_no, y, offset=0.0):
        """Fixed-world anchor position on top of stair stair_no at lateral offset y."""
        x = STAIR_ORIGIN[0] + (stair_no - 1.) * STAIR_TREAD + offset
        z = 0.30 * stair_no + 0.07 
        if stair_no == 0:
            x = 0
            z = 0.03
        return np.array([x, y, z], dtype=np.float32)

    def _bcm(center, side_lengths):
        cx, cy, cz = center
        hx, hy, hz = [s / 2 for s in side_lengths]
        verts = np.array([
            [cx-hx,cy-hy,cz-hz],[cx+hx,cy-hy,cz-hz],[cx-hx,cy+hy,cz-hz],[cx+hx,cy+hy,cz-hz],
            [cx-hx,cy-hy,cz+hz],[cx+hx,cy-hy,cz+hz],[cx-hx,cy+hy,cz+hz],[cx+hx,cy+hy,cz+hz],
        ], dtype=np.float32)
        faces = np.array([[0,1,3],[0,3,2],[4,6,7],[4,7,5],[0,4,5],[0,5,1],
                          [2,3,7],[2,7,6],[0,2,6],[0,6,4],[1,5,7],[1,7,3]], dtype=np.uint32)
        fr = faces.copy(); fr[:, [0, 1]] = fr[:, [1, 0]]
        return verts, fr

    for _s in range(1, N_STAIRS_ + 1):
        _h = 0.30 * _s
        _sc = STAIR_ORIGIN_ + np.array([(_s - 0.5) * STAIR_TREAD_, 0., _h])
        _sv, _sf = _bcm(_sc, [STAIR_TREAD_, STAIR_DEPTH_,0.05])
        server.scene.add_mesh_simple(f"/stairs/step_{_s}", vertices=_sv, faces=_sf,
                                     color=(180, 160, 140), opacity=1.0, flat_shading=False)

    contacts = setup_data['contacts']
    for _cl, _y, _lbl, _col in [
        (contacts['LEFT_FEET_CONTACTS'],  contacts['LEFT_FEET_Y'],  "lfoot", ( 50, 200,  50)),
        (contacts['RIGHT_FEET_CONTACTS'], contacts['RIGHT_FEET_Y'], "rfoot", (200,  50,  50)),
        (contacts['LEFT_HAND_CONTACTS'],  contacts['LEFT_HAND_Y'],  "lhand", ( 50, 100, 255)),
        (contacts['RIGHT_HAND_CONTACTS'], contacts['RIGHT_HAND_Y'], "rhand", (200,  50, 255)),
    ]:
        for _ci, (_s, _e, _stair) in enumerate(_cl):
            _pos = _stair_anchor(_stair, _y)
            _pos_before = _pos.copy()
            _pos_before[2] += 0.05
            _pos_before[0] -= 0.10
            _ax_before = _pos_before[0]
            _az_before = _pos_before[2]
            _ax = _pos[0]
            _az = _pos[2]
            server.scene.add_icosphere(f"/anchors/{_lbl}_{_ci}", radius=0.025,
                                       color=_col, position=np.array([_ax, _y, _az]))
            server.scene.add_icosphere(f"/anchors/{_lbl}_{_ci}_before", radius=0.025,
                                       color=_col, position=np.array([_ax_before, _y, _az_before]))

    obs_handles = []
    for _oi, (_ov, _of) in enumerate(setup_data.get('obstacles', [])):
        obs_handles.append(server.scene.add_mesh_simple(
            f"/obstacles/obs_{_oi}", vertices=_ov, faces=_of,
            color=(255, 80, 0), opacity=0.35, side="double"))

    trans_np = setup_data['trans_np']
    quats_np = setup_data['quats_np']
    prev_show_obs = True

    while True:
        with server.atomic():
            if playing.value:
                timestep_slider.value = (timestep_slider.value + 1) % T
            t = timestep_slider.value
            base_frame_new.wxyz     = quats_np[t]
            base_frame_new.position = trans_np[t]
            urdf_vis.update_cfg(ja_np[t].copy())
            cur_show_obs = show_obstacles.value
            if cur_show_obs != prev_show_obs:
                for _h in obs_handles:
                    _h.visible = cur_show_obs
                prev_show_obs = cur_show_obs
        time.sleep(0.033)


def cuboid_penetration_depth(pos, center, side_lengths):
    """
    Penetration depth of a point into an axis-aligned cuboid.
    Returns 0.0 if the point is outside, else the distance to the nearest face
    (minimum across axes), i.e. how far the point needs to move to exit.
    """
    half = np.array([s / 2.0 for s in side_lengths])
    diff = half - np.abs(np.asarray(pos) - np.asarray(center))
    if np.all(diff > 0):
        return float(diff.min())
    return 0.0


def voxelize_to_mesh(pts, resolution, min_points=5):
    """Return (vertices, faces, point_mask) — point_mask selects pts belonging to valid voxels."""
    voxel_idx = np.floor(pts / resolution).astype(np.int32)
    unique_voxels, inverse, counts = np.unique(voxel_idx, axis=0, return_inverse=True, return_counts=True)
    valid = counts >= min_points
    point_mask = valid[inverse]                            # (N,) bool
    unique_voxels = unique_voxels[valid]                   # (M, 3)
    centers = (unique_voxels + 0.5) * resolution           # (M, 3)
    h = resolution / 2.0
    # 8 corner offsets, vectorised over M voxels
    corners = np.array([[-1,-1,-1],[+1,-1,-1],[-1,+1,-1],[+1,+1,-1],
                        [-1,-1,+1],[+1,-1,+1],[-1,+1,+1],[+1,+1,+1]],
                       dtype=np.float32) * h               # (8, 3)
    verts = (centers[:, None, :] + corners[None, :, :]).reshape(-1, 3)  # (M*8, 3)
    cube_faces = np.array([[0,1,3],[0,3,2],[4,6,7],[4,7,5],
                           [0,4,5],[0,5,1],[2,3,7],[2,7,6],
                           [0,2,6],[0,6,4],[1,5,7],[1,7,3]], dtype=np.uint32)
    M = len(unique_voxels)
    offsets = (np.arange(M, dtype=np.uint32) * 8)[:, None, None]  # (M,1,1)
    faces = (cube_faces[None] + offsets).reshape(-1, 3)    # (M*12, 3)
    return verts, faces, point_mask


def load_ply_xyz_rgb(path):
    """Read a binary-little-endian PLY with float xyz + uchar rgb."""
    import re
    with open(path, 'rb') as f:
        header = b''
        while True:
            line = f.readline()
            header += line
            if line.strip() == b'end_header':
                break
        n = int(re.search(rb'element vertex (\d+)', header).group(1))
        dt = np.dtype([('x','f4'),('y','f4'),('z','f4'),('r','u1'),('g','u1'),('b','u1')])
        data = np.frombuffer(f.read(n * dt.itemsize), dtype=dt)
    pts  = np.column_stack([data['x'], data['y'], data['z']]).astype(np.float32)
    cols = np.column_stack([data['r'], data['g'], data['b']]).astype(np.uint8)
    return pts, cols


def add_change(pos, ind_start_toss, ind_end_toss, change=np.array([0., 0., 0.])):
    for ind_current in range(ind_start_toss+1, ind_end_toss):
        pos[ind_current:,:] += change[None,:]/(ind_end_toss-ind_start_toss-1)


# Load URDF and create kinematic chain
urdf_path = 'g1_29dof_feet_edge.urdf'
chain = pk.build_chain_from_urdf(open(urdf_path).read())
chain = chain.to(device=DEVICE)

joint_names = []
for joint in chain.get_joints():
    joint_names.append(joint.name)

# import pdb; pdb.set_trace()
active_joint_names = ['left_hip_pitch_joint', 'left_hip_roll_joint', 'left_knee_joint', 'left_ankle_pitch_joint', 'left_ankle_roll_joint', \
    'right_hip_pitch_joint', 'right_hip_roll_joint', 'right_knee_joint', 'right_ankle_pitch_joint', 'right_ankle_roll_joint', \
    # 'waist_yaw_joint', 'waist_roll_joint', 'waist_pitch_joint', \
    'left_shoulder_pitch_joint', 'left_shoulder_roll_joint', 'left_shoulder_yaw_joint', 'left_elbow_joint', 'left_wrist_roll_joint', 'left_wrist_pitch_joint', 'left_wrist_yaw_joint', \
    'right_shoulder_pitch_joint', 'right_shoulder_roll_joint', 'right_shoulder_yaw_joint', 'right_elbow_joint', 'right_wrist_roll_joint', 'right_wrist_pitch_joint', 'right_wrist_yaw_joint']
active_joint_ids = [joint_names.index(name) for name in active_joint_names]

joint_limit_constraints = {
    "left_hip_pitch_joint":       [-2.5307,       2.8798],
    "left_hip_roll_joint":        [-0.5236,        2.9671],
    "left_hip_yaw_joint":         [-2.7576,        2.7576],
    "left_knee_joint":            [-0.087267,      2.8798],
    "left_ankle_pitch_joint":     [-0.87267,       0.5236],
    "left_ankle_roll_joint":      [-0.2618,        0.2618],
    "right_hip_pitch_joint":      [-2.5307,        2.8798],
    "right_hip_roll_joint":       [-2.9671,        0.5236],
    "right_hip_yaw_joint":        [-2.7576,        2.7576],
    "right_knee_joint":           [-0.087267,      2.8798],
    "right_ankle_pitch_joint":    [-0.87267,       0.5236],
    "right_ankle_roll_joint":     [-0.2618,        0.2618],
    "left_shoulder_pitch_joint":  [-3.0892,        2.6704],
    "left_shoulder_roll_joint":   [0.2,        2.2515],
    "left_shoulder_yaw_joint":    [-2.618,         2.618],
    "left_elbow_joint":           [-1.0472,        2.0944],
    "left_wrist_roll_joint":      [-1.972222054,   1.972222054],
    "left_wrist_pitch_joint":     [-1.614429558,   1.614429558],
    "left_wrist_yaw_joint":       [-1.614429558,   1.614429558],
    "right_shoulder_pitch_joint": [-3.0892,        2.6704],
    "right_shoulder_roll_joint":  [-2.2515,        -0.2],
    "right_shoulder_yaw_joint":   [-2.618,         2.618],
    "right_elbow_joint":          [-1.0472,        2.0944],
    "right_wrist_roll_joint":     [-1.972222054,   1.972222054],
    "right_wrist_pitch_joint":    [-1.614429558,   1.614429558],
    "right_wrist_yaw_joint":      [-1.614429558,   1.614429558],
}
# read npz file
path = f"refined_climbing_pick_g1/climbing.pkl"
with open(path, 'rb') as f:
    data = pickle.load(f)

X_MIN = data["augment_ranges"]["x"][0]
X_MAX = data["augment_ranges"]["x"][1]
Y_MIN = data["augment_ranges"]["y"][0]
Y_MAX = data["augment_ranges"]["y"][1]
Z_MIN = data["augment_ranges"]["z"][0] + 0.07
Z_MAX = data["augment_ranges"]["z"][1] + 0.07

LABEL = data["label"]

# Generate normalized grid
x = np.linspace(X_MIN, X_MAX, data["augment_ranges"]["NX"])[::-1]
y = np.linspace(Y_MIN, Y_MAX, data["augment_ranges"]["NY"])
z = np.linspace(Z_MIN, Z_MAX, data["augment_ranges"]["NZ"])
SHIFT_Xs, SHIFT_Ys, SHIFT_Zs = np.meshgrid(x, y, z)
SHIFT_Xs = SHIFT_Xs.flatten()
SHIFT_Ys = SHIFT_Ys.flatten()
SHIFT_Zs = SHIFT_Zs.flatten()

init_joint_angles = [-0.2, 0., 0., 0.42, -0.23, 0., -0.2, 0., 0., 0.42, -0.23, 0., 0., 0., 0., 0.35, 0.16, 0., 0.87, 0., 0., 0., 0.35, -0.16, 0., 0.87, 0., 0., 0.]

path = 'climbing_new.npy'
cam_matrix = np.load(path)

# Load table point cloud (camera space, frame 0) and transform to world space.
# cam_matrix[0] is T_w2c: p_world = R^T @ (p_cam - t)
# _pts_cam, _pts_colors = load_ply_xyz_rgb(
#     '/home/dvij/TT_Player/mega-sam/UniDepth/pointclouds/bimanual_pick_place/table_00000.ply'
# )

# All tensors to DEVICE:
target_trans = torch.tensor(np.array(data['global_position']), device=DEVICE).clone()[START_FROM:,:3].float()
target_quats = torch.tensor(np.array(data['global_pose'].wxyz_xyz), device=DEVICE).clone()[START_FROM:,:4].float()
target_joint_angles = torch.tensor(np.array(data['joints']), device=DEVICE).clone()[START_FROM:,:].float()
target_joint_angles[340:] = target_joint_angles[340]
target_trans[:,1] *= 0.
# import pdb; pdb.set_trace()
num_timesteps = target_trans.shape[0]
if VIS:
    _jvis_init = torch.zeros(num_timesteps, 43)
    _jvis_init[:, :22]   = target_joint_angles.cpu()[:, :22]
    _jvis_init[:, 29:36] = target_joint_angles.cpu()[:, 22:]

    _shm_ja   = SharedMemory(create=True, size=num_timesteps * 43 * 4)
    _shm_meta = SharedMemory(create=True, size=2 * 4)
    _ja_np   = np.ndarray((num_timesteps, 43), dtype=np.float32, buffer=_shm_ja.buf)
    _meta_np = np.ndarray((2,),               dtype=np.int32,   buffer=_shm_meta.buf)
    _ja_np[:]   = _jvis_init.numpy()
    _meta_np[:] = 0

    _setup_data = {
        'urdf_path': 'g1_29dof_with_hand.urdf',
        'trans_np':  target_trans.cpu().numpy().copy(),
        'quats_np':  target_quats.cpu().numpy().copy(),
        'stair_constants': {
            'N_STAIRS': N_STAIRS, 'STAIR_TREAD': STAIR_TREAD,
            'STAIR_DEPTH': STAIR_DEPTH, 'STAIR_ORIGIN': STAIR_ORIGIN.tolist(),
        },
        'contacts': {
            'LEFT_FEET_CONTACTS':  LEFT_FEET_CONTACTS,  'LEFT_FEET_Y':  LEFT_FEET_Y,
            'RIGHT_FEET_CONTACTS': RIGHT_FEET_CONTACTS, 'RIGHT_FEET_Y': RIGHT_FEET_Y,
            'LEFT_HAND_CONTACTS':  LEFT_HAND_CONTACTS,  'LEFT_HAND_Y':  LEFT_HAND_Y,
            'RIGHT_HAND_CONTACTS': RIGHT_HAND_CONTACTS, 'RIGHT_HAND_Y': RIGHT_HAND_Y,
        },
    }
    # obstacles not yet built here; will be added before vis_proc.start()
    


q_dict = {name: target_joint_angles[:, i] for i, name in enumerate( joint_names ) }
rot_matrix = quaternion_to_matrix(target_quats)
fk_results = chain.forward_kinematics(q_dict)

left_arm_keypt_names = ["left_shoulder_pitch_link", "left_shoulder_roll_link", "left_shoulder_yaw_link", "left_elbow_link", "left_wrist_roll_link", "left_wrist_pitch_link", "left_wrist_yaw_link", "left_rubber_hand"]

left_arm_keypts = []
for keypt in left_arm_keypt_names:
    pos_left_arm_keypt = fk_results[keypt].get_matrix()[:,:3,3]
    pos_left_arm_keypt = torch.bmm(pos_left_arm_keypt.unsqueeze(1), rot_matrix.transpose(2, 1))[:,0] + target_trans
    left_arm_keypts.append(pos_left_arm_keypt)
left_arm_keypts = torch.stack(left_arm_keypts, dim=1)
pos_left_hand = left_arm_keypts[:, -1]

left_hand_rot_mat = fk_results["left_rubber_hand"].get_matrix()[:,:3,:3]
left_hand_rot_mat = torch.bmm(rot_matrix, left_hand_rot_mat)
x_axis_left_hand = left_hand_rot_mat[:, :3, 0]
y_axis_left_hand = left_hand_rot_mat[:, :3, 1]
z_axis_left_hand = left_hand_rot_mat[:, :3, 2]

ref_z_axis_left_hand = torch.tensor([0., -1., 0.], device=DEVICE)
ref_x_axis_left_hand = torch.tensor([1., 0., 0.], device=DEVICE) / torch.norm(torch.tensor([1., 0., 0.], device=DEVICE))

for i in range(len(z_axis_left_hand)):
    factor1 = max(0.,min(HAND_ROT_INDICES[1]-HAND_ROT_INDICES[0],i-HAND_ROT_INDICES[0])/(HAND_ROT_INDICES[1]-HAND_ROT_INDICES[0]))
    factor2 = 1. - max(0.,min(HAND_ROT_INDICES[3]-HAND_ROT_INDICES[2],i-HAND_ROT_INDICES[2])/(HAND_ROT_INDICES[3]-HAND_ROT_INDICES[2]))
    factor = min(factor1, factor2)
    z_axis_left_hand[i:i+1] = z_axis_left_hand[i:i+1] + (ref_z_axis_left_hand[None,:] - z_axis_left_hand[i:i+1]) * factor
    z_axis_left_hand[i:i+1] /= torch.norm(z_axis_left_hand[i:i+1])
    x_axis_left_hand[i:i+1] = x_axis_left_hand[i:i+1] + (ref_x_axis_left_hand[None,:] - x_axis_left_hand[i:i+1]) * factor
    x_axis_left_hand[i:i+1] /= torch.norm(x_axis_left_hand[i:i+1])


right_arm_keypt_names = ["right_shoulder_pitch_link", "right_shoulder_roll_link", "right_shoulder_yaw_link", "right_elbow_link", "right_wrist_roll_link", "right_wrist_pitch_link", "right_wrist_yaw_link", "right_rubber_hand"]
right_arm_keypts = []
for keypt in right_arm_keypt_names:
    pos_right_arm_keypt = fk_results[keypt].get_matrix()[:,:3,3]
    pos_right_arm_keypt = torch.bmm(pos_right_arm_keypt.unsqueeze(1), rot_matrix.transpose(2, 1))[:,0] + target_trans
    right_arm_keypts.append(pos_right_arm_keypt)
right_arm_keypts = torch.stack(right_arm_keypts, dim=1)
pos_right_hand = right_arm_keypts[:, -1]
right_hand_rot_mat = fk_results["right_rubber_hand"].get_matrix()[:,:3,:3]
right_hand_rot_mat = torch.bmm(rot_matrix, right_hand_rot_mat)
x_axis_right_hand = right_hand_rot_mat[:, :3, 0]
y_axis_right_hand = right_hand_rot_mat[:, :3, 1]
z_axis_right_hand = right_hand_rot_mat[:, :3, 2]
ref_z_axis_right_hand = torch.tensor([0., 1., 0.], device=DEVICE)
ref_x_axis_right_hand = torch.tensor([1., 0., 0.], device=DEVICE) / torch.norm(torch.tensor([1., 0., 0.], device=DEVICE))

for i in range(len(z_axis_right_hand)):
    factor1 = max(0.,min(HAND_ROT_INDICES[1]-HAND_ROT_INDICES[0],i-HAND_ROT_INDICES[0])/(HAND_ROT_INDICES[1]-HAND_ROT_INDICES[0]))
    factor2 = 1. - max(0.,min(HAND_ROT_INDICES[3]-HAND_ROT_INDICES[2],i-HAND_ROT_INDICES[2])/(HAND_ROT_INDICES[3]-HAND_ROT_INDICES[2]))
    factor = min(factor1, factor2)
    z_axis_right_hand[i:i+1] = z_axis_right_hand[i:i+1] + (ref_z_axis_right_hand[None,:] - z_axis_right_hand[i:i+1]) * factor
    z_axis_right_hand[i:i+1] /= torch.norm(z_axis_right_hand[i:i+1])
    x_axis_right_hand[i:i+1] = x_axis_right_hand[i:i+1] + (ref_x_axis_right_hand[None,:] - x_axis_right_hand[i:i+1]) * factor
    x_axis_right_hand[i:i+1] /= torch.norm(x_axis_right_hand[i:i+1])

object_traj = (pos_left_hand + pos_right_hand) / 2.

left_feet_keypt_names = ["left_feet_edge"]
left_feet_keypts = []
for keypt in left_feet_keypt_names:
    pos_left_feet_keypt = fk_results[keypt].get_matrix()[:,:3,3]
    pos_left_feet_keypt = torch.bmm(pos_left_feet_keypt.unsqueeze(1), rot_matrix.transpose(2, 1))[:,0] + target_trans
    left_feet_keypts.append(pos_left_feet_keypt)
left_feet_keypts = torch.stack(left_feet_keypts, dim=1)
pos_left_ankle = left_feet_keypts[:, -1]

right_feet_keypt_names = ["right_feet_edge"]
right_feet_keypts = []
for keypt in right_feet_keypt_names:
    pos_right_feet_keypt = fk_results[keypt].get_matrix()[:,:3,3]
    pos_right_feet_keypt = torch.bmm(pos_right_feet_keypt.unsqueeze(1), rot_matrix.transpose(2, 1))[:,0] + target_trans
    right_feet_keypts.append(pos_right_feet_keypt)
right_feet_keypts = torch.stack(right_feet_keypts, dim=1)
pos_right_ankle = right_feet_keypts[:, -1]

_R0 = cam_matrix[0, :3, :3]*0.
_t0 = cam_matrix[0, :3, 3]
# import pdb; pdb.set_trace()
_R0[1,2] = 1.
_R0[0,0] = 1.
_R0[2,1] = -1.
yaw = np.pi/5.
_cy, _sy = np.cos(yaw), np.sin(yaw)
_R_yaw = np.array([[_cy, -_sy, 0.],
                   [_sy,  _cy, 0.],
                   [0.,   0.,  1.]], dtype=np.float32)
_R0 = _R_yaw @ _R0
roll = -np.pi/18.
_cr, _sr = np.cos(roll), np.sin(roll)
_R_roll = np.array([[1.,  0.,   0.],
                    [0.,  _cr, -_sr],
                    [0.,  _sr,  _cr]], dtype=np.float32)
_R0 = _R_roll @ _R0
pitch = np.pi/40.
_cp, _sp = np.cos(pitch), np.sin(pitch)
_R_pitch = np.array([[_cp, 0., -_sp],
                    [0.,  1.,  0.],
                    [_sp, 0.,  _cp]], dtype=np.float32)
_R0 = _R_pitch @ _R0
# import pdb; pdb.set_trace()
# dists = np.linalg.norm(_pts_cam[:,:2], axis=1)
# min_i = np.argmin(dists)

# table_pts_world  = (_R0 @ _pts_cam.T).T   # (N, 3)
# _t0 = object_traj[275:276, :].cpu().numpy() - table_pts_world[min_i:min_i+1, :] + np.array([0.1, -0.5, 0.07]).reshape(1,3)
# table_pts_world = table_pts_world + _t0
# table_pts_colors = _pts_colors               # (N, 3) uint8
# _mask = table_pts_world[:, 1] <= 1.0
# table_pts_world  = table_pts_world[_mask]
# table_pts_colors = table_pts_colors[_mask]

# _mask = table_pts_world[:, 0] >= object_traj[275, 0].cpu().numpy() + 0.1
# table_pts_world  = table_pts_world[_mask]
# table_pts_colors = table_pts_colors[_mask]

# table_vox_verts, table_vox_faces, _vox_mask = voxelize_to_mesh(table_pts_world, TABLE_VOXEL_RESOLUTION)
# table_pts_world = table_pts_world[_vox_mask]
# table_pts_colors = table_pts_colors[_vox_mask]


left_ankle_rot_mat = fk_results["left_ankle_roll_link"].get_matrix()[:,:3,:3]
left_ankle_rot_mat = torch.bmm(rot_matrix, left_ankle_rot_mat)
z_axis_left_ankle = left_ankle_rot_mat[:, :3, 2]

right_ankle_rot_mat = fk_results["right_ankle_roll_link"].get_matrix()[:,:3,:3]
right_ankle_rot_mat = torch.bmm(rot_matrix, right_ankle_rot_mat)
z_axis_right_ankle = right_ankle_rot_mat[:, :3, 2]

feet_z_axis = torch.tensor([0., 0., 1.], device=DEVICE)
for i in range(len(z_axis_left_ankle)):
    factor = max(0.,min(FEET_ALIGN_END-FEET_ALIGN_START,i-FEET_ALIGN_START)/(FEET_ALIGN_END-FEET_ALIGN_START))
    z_axis_left_ankle[i:i+1] = z_axis_left_ankle[i:i+1] + (feet_z_axis[None,:] - z_axis_left_ankle[i:i+1]) * factor
    z_axis_right_ankle[i:i+1] = z_axis_right_ankle[i:i+1] + (feet_z_axis[None,:] - z_axis_right_ankle[i:i+1]) * factor
    z_axis_left_ankle[i:i+1] /= torch.norm(z_axis_left_ankle[i:i+1])
    z_axis_right_ankle[i:i+1] /= torch.norm(z_axis_right_ankle[i:i+1])


hit_pos_reals = []
Ts_world_roots = []

N_shifts = len(SHIFT_Xs)
shifts = torch.tensor(np.stack([SHIFT_Xs, SHIFT_Ys, SHIFT_Zs], axis=1), device=DEVICE).float()  # [N, 3]

ind_start = CONTACT_START_FRAME
ind_end = CONTACT_END_FRAME
# Pre-compute all N target hand trajectories at once: [N, T, 3]
object_traj_batch = object_traj.unsqueeze(0).expand(N_shifts, -1, -1).clone()
object_traj_batch[:,:,2] += 0.05
object_traj_batch[:,:,0] += 0.1
divisor = ind_end - ind_start - 1
for ind_current in range(ind_start + 1, ind_end):
    object_traj_batch[:, ind_current:, :] += shifts.unsqueeze(1) / divisor

pos_left_hand_batch = pos_left_hand.unsqueeze(0).expand(N_shifts, -1, -1).clone()
pos_right_hand_batch = pos_right_hand.unsqueeze(0).expand(N_shifts, -1, -1).clone()
pos_left_ankle_batch = pos_left_ankle.unsqueeze(0).expand(N_shifts, -1, -1).clone()
pos_right_ankle_batch = pos_right_ankle.unsqueeze(0).expand(N_shifts, -1, -1).clone()
trans = target_trans.to(DEVICE)
quats = target_quats.to(DEVICE)

keypt_names = ["left_rubber_hand", "right_rubber_hand", "left_feet_edge", "right_feet_edge"]

def _cuboid_mesh_obstacle(center, dims):
    """Build a mesh obstacle with inward normals from a cuboid definition."""
    _verts_np, _faces_out = build_cuboid_mesh(center, dims)
    # build_cuboid_mesh returns outward normals; reverse winding → inward normals
    _faces_in = _faces_out.copy()
    _faces_in[:, [0, 1]] = _faces_in[:, [1, 0]]
    _verts_t = torch.tensor(_verts_np, dtype=torch.float32, device=DEVICE)
    _faces_t = torch.tensor(_faces_in.astype(np.int64), dtype=torch.long, device=DEVICE)
    return ("mesh", _verts_t, _faces_t)

def _personal_mesh_obstacle(center, dims):
    """Build a mesh obstacle with inward normals from a personal definition."""
    _verts_np, _faces_out = build_personal_mesh(center, dims)
    _faces_in = _faces_out.copy()
    _faces_in[:, [0, 1]] = _faces_in[:, [1, 0]]
    _verts_t = torch.tensor(_verts_np, dtype=torch.float32, device=DEVICE)
    _faces_t = torch.tensor(_faces_in.astype(np.int64), dtype=torch.long, device=DEVICE)
    return ("mesh", _verts_t, _faces_t)

obstacles = []
for _s in range(1, 8):
    _cx = STAIR_ORIGIN[0] + (_s - 0.5) * STAIR_TREAD + 0.5
    _cy = STAIR_ORIGIN[1]
    _cz = 0.3 * _s - 0.09 + 0.05
    if _s == 7:
        _cz = 0.15 * 20.
        _cx += 2.
        obstacles.append(_cuboid_mesh_obstacle([_cx, _cy, _cz], [STAIR_TREAD * 4. + 4., STAIR_DEPTH, 0.30 * 20.]))
    else:
        # obstacles.append(_personal_mesh_obstacle([_cx, _cy, _cz], [STAIR_TREAD * 4.+1., STAIR_DEPTH, 0.30+3.]))
        obstacles.append(("cuboid_bottom_open", [_cx, _cy, _cz], [STAIR_TREAD * 3.+1., STAIR_DEPTH, 0.18]))

if VIS:
    _setup_data['obstacles'] = []#[(v.cpu().numpy().copy(), f.cpu().numpy().copy())
                                #for (_, v, f) in obstacles]
    vis_proc = mp.Process(target=_vis_process_main,
                          args=(_shm_ja.name, _shm_meta.name, num_timesteps, _setup_data),
                          daemon=True)
    vis_proc.start()


anchor_points = []
for _start, _end, _stair in LEFT_FEET_CONTACTS:
    _pos = _stair_anchor(_stair, LEFT_FEET_Y, offset=0.15)
    _pos_before = _pos.clone()
    _pos_before[:, 2] += 0.05
    _pos_before[:, 0] -= 0.10
    if _start-7 >= 0:
        anchor_points.extend([(_start-7, "left_feet_edge", _pos_before)])
    # print(_start)
    # import pdb; pdb.set_trace()
    anchor_points.extend([(t, "left_feet_edge", _pos) for t in range(_start, _end + 1)])

# import pdb; pdb.set_trace()

for _start, _end, _stair in RIGHT_FEET_CONTACTS:
    _pos = _stair_anchor(_stair, RIGHT_FEET_Y, offset=0.15)
    _pos_before = _pos.clone()
    _pos_before[:, 2] += 0.05
    _pos_before[:, 0] -= 0.10
    if _start-7 >= 0:
        anchor_points.extend([(_start-7, "right_feet_edge", _pos_before)])
    anchor_points.extend([(t, "right_feet_edge", _pos) for t in range(_start, _end + 1)])
for _start, _end, _stair in LEFT_HAND_CONTACTS:
    _pos = _stair_anchor(_stair, LEFT_HAND_Y,offset=0.14)
    _pos_before = _pos.clone()
    _pos_before[:, 2] += 0.05
    _pos_before[:, 0] -= 0.10
    if _start-7 >= 0:
        anchor_points.extend([(_start-7, "left_rubber_hand", _pos_before)])
    anchor_points.extend([(t, "left_rubber_hand", _pos) for t in range(_start, _end + 1)])
for _start, _end, _stair in RIGHT_HAND_CONTACTS:
    _pos = _stair_anchor(_stair, RIGHT_HAND_Y,offset=0.14)
    _pos_before = _pos.clone()
    _pos_before[:, 2] += 0.05
    _pos_before[:, 0] -= 0.10
    if _start-7 >= 0:
        anchor_points.extend([(_start-7, "right_rubber_hand", _pos_before)])
    anchor_points.extend([(t, "right_rubber_hand", _pos) for t in range(_start, _end + 1)])

# Add anchor points for 0th and last step
anchor_points.append((0, "left_rubber_hand", pos_left_hand_batch[:, 0].detach()))
anchor_points.append((num_timesteps-1, "left_rubber_hand", pos_left_hand_batch[:, num_timesteps-1].detach()))
anchor_points.append((0, "right_rubber_hand", pos_right_hand_batch[:, 0].detach()))
anchor_points.append((num_timesteps-1, "right_rubber_hand", pos_right_hand_batch[:, num_timesteps-1].detach()))

# anchor_points.append((0, "left_feet_edge", pos_left_ankle_batch[:, 0].detach()))
# anchor_points.append((num_timesteps-1, "left_feet_edge", pos_left_ankle_batch[:, num_timesteps-1].detach()))
# anchor_points.append((0, "right_feet_edge", pos_right_ankle_batch[:, 0].detach()))
# anchor_points.append((num_timesteps-1, "right_feet_edge", pos_right_ankle_batch[:, num_timesteps-1].detach()))

if VIS:
    def _vis_callback(ja_batch, _step, _costs):
        _ja = ja_batch[0].cpu()
        _jfull = target_joint_angles.cpu().clone()
        _jfull[:, active_joint_ids] = _ja
        _jvis = torch.zeros(num_timesteps, 43)
        _jvis[:, :22]   = _jfull[:, :22]
        _jvis[:, 29:36] = _jfull[:, 22:]
        _ja_np[:] = _jvis.numpy()
else:
    _vis_callback = None
for _anchor_point in anchor_points:
    t,a,b = _anchor_point
    if t > 340:
        print(t,a,b)
# import pdb; pdb.set_trace()
joint_angles_batch, converged = solve_joint_angles_batch(
    target_joint_angles, trans, quats,
    chain, active_joint_names,
    keypt_names, anchor_points,
    x_axis_refs={"left_rubber_hand": x_axis_left_hand.detach(), "right_rubber_hand": x_axis_right_hand.detach()},
    y_axis_refs={},#"left_rubber_hand": y_axis_left_hand.detach(), "right_rubber_hand": y_axis_right_hand.detach()},
    z_axis_refs={"left_rubber_hand": z_axis_left_hand.detach(), "right_rubber_hand": z_axis_right_hand.detach(), "left_ankle_roll_link": z_axis_left_ankle.detach(), "right_ankle_roll_link": z_axis_right_ankle.detach()},
    target_cost=TARGET_COST,
    device=DEVICE,
    obstacles=obstacles,
    joint_limit_constraints=joint_limit_constraints,
    max_iters=10000,
    smoothening_joint_names=active_joint_names,
    vis_callback=_vis_callback,
    vis_interval=50,
    pose_optimizable=[]
)

print(f"All converged: {converged.all().item()}, remaining: {(~converged).sum().item()}")

if VIS:
    _jfinal = target_joint_angles.cpu().clone()
    _jfinal[:, active_joint_ids] = joint_angles_batch[0].detach().cpu()
    _jvis_final = torch.zeros(num_timesteps, 43)
    _jvis_final[:, :22]   = _jfinal[:, :22]
    _jvis_final[:, 29:36] = _jfinal[:, 22:]
    _ja_np[:] = _jvis_final.numpy()
    _meta_np[1] = 1

# Extract per-sample results
num_timesteps = target_joint_angles.shape[0]
trans_new = target_trans.clone()
quats_new = target_quats.clone()
Ts_world_root = jaxlie.SE3.from_rotation_and_translation(
    jaxlie.SO3(jnp.array(quats_new.cpu())), jnp.array(trans_new.cpu())
)

if SAVE and not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

joints_new_augs = []
joint_new_s = []
for i in range(N_shifts):
    joints_new_ = target_joint_angles.cpu().clone()
    joints_new_[:, active_joint_ids] = joint_angles_batch[i].detach().cpu()

    joints_new = torch.zeros((num_timesteps, 43))
    joints_new[:,:22] = joints_new_[:,:22].cpu().clone()
    joints_new[:, 29:36] = joints_new_[:, 22:].cpu().clone()
    
    joints_new_augs.append(joints_new.cpu().numpy())
    joint_new_s.append(joints_new_.cpu().clone())
    Ts_world_roots.append(Ts_world_root)
    hit_pos_reals.append(object_traj_batch[i, CONTACT_END_FRAME].cpu().numpy())
    if SAVE:
        with open(SAVE_DIR + "/" + f"t_{i}.pkl","wb") as f:
            pickle.dump({"global_pose": Ts_world_root , "joints": joints_new_.cpu(), "global_position": trans_new.cpu(), "pick_pos_real": hit_pos_reals[-1], "label": LABEL, "CONTACT_START_FRAME": CONTACT_START_FRAME, "CONTACT_END_FRAME": CONTACT_END_FRAME}, f)
target_positions_np = np.stack([SHIFT_Xs, SHIFT_Ys, SHIFT_Zs], axis=1)  # [N, 3]


if VIS:
    print("Optimization done. Visualization running in background — press Ctrl+C to stop.")
    try:
        vis_proc.join()
    except KeyboardInterrupt:
        vis_proc.terminate()
        vis_proc.join()
    finally:
        _shm_ja.close();   _shm_ja.unlink()
        _shm_meta.close(); _shm_meta.unlink()

# python scripts/batch_osmo_run.py   \
# --eval_gpus 1 -ef 2000    --nodes 1     -group "zen_heading_0223" \
# --exp_var thor   \
# --cfg_query manager/universal_token/all_modes/sonic_release_3pt_heading   $OSMO  \
# -ag \ "manager_env.commands.motion.motion_lib_cfg.motion_file=${shared_dir}/wbc_data/training_mixes/train_pyroki_0213_26/" "manager_env.commands.motion.motion_lib_cfg.smpl_motion_file=${shared_dir}/wbc_data/smpl_retarget/1215/" "manager_env/rewards=tracking/local_feet_acc_energy_5pt" "num_envs=8192"  -ea "+eval_datasets=[${shared_dir}/wbc_data/pyroki/pyroki_v0.8.0_splits/v0.8.0_test_content,${shared_dir}/wbc_data/pyroki/pyroki_v0.8.0_splits/v0.8.0_test_repetition] " "+eval_modes=[g1,smpl,teleop]" 