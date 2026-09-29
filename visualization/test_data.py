"""Checks for errors that silently corrupt robot playback."""
from pathlib import Path
import tempfile
import unittest
import numpy as np
import yourdfpy
from .data import JOINT_NAMES, ROOT, Motion, check_file, import_motion, read_catalog
from .scene import joint_order


class MotionTests(unittest.TestCase):
    def test_csv_quaternion_convention_and_joint_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'motion.csv'
            # A 90-degree yaw in the CSV's xyzw convention.
            row = np.r_[[1., 2., 3.], [0., 0., np.sqrt(.5), np.sqrt(.5)], np.arange(29) / 10]
            np.savetxt(path, np.tile(row, (2, 1)), delimiter=',')
            motion = import_motion(path, 60)
            np.testing.assert_allclose(motion.wxyz[0], [np.sqrt(.5), 0., 0., np.sqrt(.5)])
            np.testing.assert_allclose(motion.positions[0], [1., 2., 3.])
            np.testing.assert_allclose(joint_order(motion, list(reversed(JOINT_NAMES)))[0], row[7:][::-1])
            motion.save(Path(directory) / 'motion.npz')
            restored = Motion.load(Path(directory) / 'motion.npz')
            np.testing.assert_array_equal(restored.joints, motion.joints)
            self.assertEqual(restored.metadata['sha256'], motion.metadata['sha256'])
            self.assertEqual(restored.fps, 60)

    def test_reject_invalid_motion_and_untrusted_pickle(self):
        for fps in (0, -1, float('nan')):
            with self.assertRaises(ValueError):
                Motion(np.zeros((2, 3)), np.tile([1, 0, 0, 0], (2, 1)), np.zeros((2, 29)), fps, {})
        with self.assertRaises(ValueError):
            Motion(np.zeros((2, 3)), np.zeros((2, 4)), np.zeros((2, 29)), 30, {})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'motion.pkl'
            path.write_bytes(b'not a pickle')
            with self.assertRaisesRegex(ValueError, 'trust-pickle'):
                import_motion(path, 30)
            path.write_text('version https://git-lfs.github.com/spec/v1\noid sha256:example\nsize 100\n')
            with self.assertRaisesRegex(ValueError, 'Git LFS pointer'):
                check_file(path)

    def test_all_packaged_motions_and_meshes(self):
        model = yourdfpy.URDF.load(str(ROOT / 'robot/g1.urdf'))
        self.assertEqual(len(model.scene.geometry), 36)
        catalog = read_catalog()
        self.assertEqual(len(catalog['tasks']), 10)
        for task in catalog['tasks']:
            ids = [v['id'] for v in task['variants']]
            self.assertEqual(len(set(ids)), len(ids))
            for variant in task['variants']:
                motion = Motion.load(ROOT / variant['file'])
                q = joint_order(motion, model.actuated_joint_names)
                self.assertTrue(np.isfinite(q).all())
                np.testing.assert_allclose(np.linalg.norm(motion.wxyz, axis=1), 1, atol=1e-6)
                self.assertFalse(Path(motion.metadata['source']).is_absolute())


if __name__ == '__main__':
    unittest.main()
