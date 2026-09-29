"""Validated, pickle-free motion interchange; legacy imports are explicit."""
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import pickle
import numpy as np

ROOT = Path(__file__).resolve().parent
JOINT_NAMES = [
    *[f"{side}_{joint}_joint" for side in ("left", "right") for joint in
      ("hip_pitch", "hip_roll", "hip_yaw", "knee", "ankle_pitch", "ankle_roll")],
    "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint",
    *[f"{side}_{joint}_joint" for side in ("left", "right") for joint in
      ("shoulder_pitch", "shoulder_roll", "shoulder_yaw", "elbow", "wrist_roll", "wrist_pitch", "wrist_yaw")],
]


def check_file(path):
    path = Path(path)
    with path.open("rb") as f:
        if f.read(80).startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise ValueError(f"{path.name} is a Git LFS pointer. Fetch and checkout its LFS object first.")
    return path


@dataclass
class Motion:
    positions: np.ndarray
    wxyz: np.ndarray
    joints: np.ndarray
    fps: float
    metadata: dict
    joint_names: tuple = tuple(JOINT_NAMES)

    def __post_init__(self):
        self.positions = np.asarray(self.positions, dtype=np.float64)
        self.wxyz = np.asarray(self.wxyz, dtype=np.float64).copy()
        self.joints = np.asarray(self.joints, dtype=np.float64)
        self.fps = float(self.fps)
        n = len(self.positions)
        if n < 2 or self.positions.shape != (n, 3) or self.wxyz.shape != (n, 4):
            raise ValueError("Expected at least two frames, positions [T,3], and quaternions [T,4].")
        if len(self.joint_names) != 29 or self.joints.shape != (n, 29) or set(self.joint_names) != set(JOINT_NAMES):
            raise ValueError("Expected the 29 named G1 joints, each exactly once.")
        if not np.isfinite(self.fps) or self.fps <= 0:
            raise ValueError("Frame rate must be finite and positive.")
        if not all(np.isfinite(a).all() for a in (self.positions, self.wxyz, self.joints)):
            raise ValueError("Motion contains non-finite values.")
        norms = np.linalg.norm(self.wxyz, axis=1)
        if np.any(abs(norms - 1) > .05):
            raise ValueError("Quaternion norms differ from 1 by more than 5%; check the source convention.")
        self.wxyz /= norms[:, None]
        # q and -q represent the same orientation; keep consecutive signs continuous.
        for i in range(1, n):
            if np.dot(self.wxyz[i - 1], self.wxyz[i]) < 0:
                self.wxyz[i] *= -1

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, positions=self.positions, wxyz=self.wxyz,
                            joints=self.joints, fps=self.fps, joint_names=self.joint_names,
                            metadata=json.dumps(self.metadata, sort_keys=True))

    @classmethod
    def load(cls, path):
        with np.load(check_file(path), allow_pickle=False) as data:
            return cls(data['positions'], data['wxyz'], data['joints'], float(data['fps']),
                       json.loads(str(data['metadata'])), tuple(data['joint_names'].tolist()))


def import_motion(path, fps, source_name=None, trust_pickle=False):
    path = check_file(path)
    if path.suffix == '.npz':
        return Motion.load(path)
    metadata = {'source': source_name or path.name,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'units': 'metres, radians', 'quaternions': 'wxyz',
                'processing': 'Unit quaternion normalization only; no joint or root trajectory edits.'}
    if path.suffix == '.csv':
        a = np.loadtxt(path, delimiter=',', ndmin=2)
        if a.shape[1] != 36:
            raise ValueError("Robot CSV must have 36 columns: xyz, xyzw, and 29 joint angles.")
        return Motion(a[:, :3], a[:, [6, 3, 4, 5]], a[:, 7:], fps, metadata)
    if path.suffix not in ('.pkl', '.pickle') or not trust_pickle:
        raise ValueError("Use a canonical NPZ or robot CSV. Legacy pickle import requires --trust-pickle.")
    # JAX/JAXLie and torch are needed only to migrate the legacy serialized objects.
    import torch

    class CPUUnpickler(pickle.Unpickler):
        def find_class(self, module, name):
            if module == 'torch.storage' and name == '_load_from_bytes':
                return lambda b: torch.load(io.BytesIO(b), map_location='cpu', weights_only=False)
            return super().find_class(module, name)

    with path.open('rb') as f:
        data = CPUUnpickler(f).load()

    def array(value):
        if hasattr(value, 'detach'):
            value = value.detach().cpu().numpy()
        return np.asarray(value)

    poses = array(data['global_pose'].wxyz_xyz)
    positions = array(data.get('global_position', poses[:, 4:]))
    if not np.allclose(positions, poses[:, 4:], atol=1e-4):
        raise ValueError("global_position and global_pose translations disagree.")
    for key in ('hit_time', 'grab_idx', 'label', 'augment_ranges', 'hit_pos_real'):
        if data.get(key) is not None:
            value = data[key]
            metadata[key] = value if isinstance(value, (str, int, float, dict)) else array(value).tolist()
    return Motion(positions, poses[:, :4], array(data['joints']), fps, metadata)


def read_catalog():
    return json.loads((ROOT / 'catalog.json').read_text())


def write_catalog(catalog):
    (ROOT / 'catalog.json').write_text(json.dumps(catalog, indent=2) + '\n')
