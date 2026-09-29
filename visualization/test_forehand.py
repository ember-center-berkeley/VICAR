"""Validate the full contact grid and browser joint transforms independently."""
import gzip
import json
import unittest
import numpy as np
from scipy.spatial.transform import Rotation
import yourdfpy
from .data import ROOT, JOINT_NAMES, Motion


class ForehandTests(unittest.TestCase):
    def test_grid_targets_and_exported_joint_rotations(self):
        with np.load(ROOT / 'motions/forehand-grid.npz', allow_pickle=False) as data:
            shifts, arms, targets = data['shifts'], data['arms'], data['targets']
            achieved, costs = data['achieved'], data['costs']
        self.assertEqual(arms.shape, (729, 63, 7))
        self.assertEqual(len(np.unique(shifts, axis=0)), 729)
        np.testing.assert_allclose(shifts.min(axis=0), [-.12, -.04, -.04], atol=1e-7)
        np.testing.assert_allclose(shifts.max(axis=0), [-.04, .04, .04], atol=1e-7)
        self.assertTrue(np.isfinite(arms).all())
        self.assertLess(np.linalg.norm(achieved - targets, axis=1).max(), .002)
        # Preserve unconverged outputs just as the original script does, but
        # retain/report their actual objective values instead of hiding them.
        base = Motion.load(ROOT / 'motions/forehand-reference.npz')
        body = yourdfpy.URDF.load(str(ROOT / 'robot/g1.urdf'))
        body.update_cfg(dict(zip(JOINT_NAMES, base.joints[45])))
        original_hit = body.get_transform('right_rubber_hand')[:3, 3] + base.positions[45]
        np.testing.assert_allclose(targets, original_hit + shifts, atol=3e-7)
        meta = json.loads((ROOT.parent / 'assets/augmentation/forehand.json').read_text())
        self.assertEqual(int((costs < .014).sum()), meta['provenance']['converged'])
        rotations = np.frombuffer(gzip.decompress((ROOT.parent / 'assets/augmentation/forehand-quaternions.bin.gz').read_bytes()), dtype='<f4').reshape(meta['quaternionShape'])
        hands = yourdfpy.URDF.load(str(ROOT / 'robot-hands/g1.urdf'))
        self.assertEqual(len(hands.actuated_joint_names), 43)
        for index in [0, 8, 80, 364, 648, 728]:
            for frame in [0, 30, 45, 62]:
                cfg = dict(zip(JOINT_NAMES, base.joints[frame]))
                cfg.update(zip(JOINT_NAMES[22:], arms[index, frame]))
                hands.update_cfg(cfg)
                for j, name in enumerate(JOINT_NAMES[22:]):
                    joint = hands.joint_map[name]
                    actual = hands.get_transform(joint.child, joint.parent)[:3, :3]
                    q = rotations[index, frame, j]
                    decoded = Rotation.from_quat(q[[1, 2, 3, 0]]).as_matrix()
                    np.testing.assert_allclose(decoded, actual, atol=2e-7)


if __name__ == '__main__':
    unittest.main()
