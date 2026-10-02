"""Independent kinematic and data checks for all six general-serve viewers."""
import gzip
import json
import unittest
import numpy as np
from scipy.spatial.transform import Rotation
import yourdfpy
from .data import ROOT, JOINT_NAMES, Motion

# Manually audited against each pulled PKL, including the script's ±4 cm padding.
EXPECTED = {
    'forehand': ([-.16, -.08, -.08], [0, .08, .08], 45),
    'backhand': ([-.09, -.08, -.04], [.04, .06, .08], 49),
    'forehand-chop': ([-.18, .03, -.04], [-.02, .19, .14], 45),
    'backhand-chop': ([-.09, -.10, .02], [.04, .04, .14], 49),
    'forehand-side-spin': ([-.08, -.18, -.08], [.14, .08, .08], 46),
    'backhand-side-spin': ([-.05, -.06, -.02], [.08, .08, .10], 47),
}


class ServeTests(unittest.TestCase):
    def test_all_grids_and_browser_poses(self):
        model = yourdfpy.URDF.load(str(ROOT / 'robot-racket/g1.urdf'))
        self.assertEqual(model.actuated_joint_names, JOINT_NAMES)
        self.assertIn('right_racket', model.link_map)
        self.assertIn('left_ball_holder', model.link_map)
        for task, (minimum, maximum, hit) in EXPECTED.items():
            with self.subTest(task=task):
                base = Motion.load(ROOT / f'motions/serves/{task}-reference.npz')
                with np.load(ROOT / f'motions/serves/{task}-grid.npz', allow_pickle=False) as data:
                    arms, shifts, targets, achieved = data['arms'], data['shifts'], data['targets'], data['achieved']
                    markers, trajectories = data['markers'], data['trajectories']
                    metadata = json.loads(str(data['metadata']))
                    self.assertTrue(np.isfinite(data['costs']).all())
                    self.assertEqual(int(data['converged'].sum()), 0)
                self.assertEqual(arms.shape, (729, 63, 7))
                self.assertEqual(len(np.unique(shifts, axis=0)), 729)
                self.assertEqual(metadata['max_steps'], 10000)
                self.assertEqual(metadata['hit_frame'], hit)
                self.assertEqual(metadata['source_script'], 'augment_serves_general_g1.py')
                self.assertTrue(np.isfinite(arms).all())
                np.testing.assert_allclose(shifts.min(axis=0), minimum, atol=1e-7)
                np.testing.assert_allclose(shifts.max(axis=0), maximum, atol=1e-7)
                np.testing.assert_allclose(markers, (trajectories[:, 2]+trajectories[:, 3])/2, atol=1e-7)
                directory = ROOT.parent / 'assets/augmentation/serves'
                config = json.loads((directory / f'{task}.json').read_text())
                np.testing.assert_allclose(config['targets'], markers, atol=1e-7)
                self.assertEqual(config['displayLift'], 0)
                self.assertEqual(config['hitFrame'], hit)
                self.assertEqual(config['defaultIndex'], 364)
                self.assertEqual(len(config['nodes']), 7)
                for i, axis in enumerate('xyz'):
                    settings = config['axes'][axis]
                    self.assertAlmostEqual(settings['min'], minimum[i])
                    self.assertAlmostEqual(settings['max'], maximum[i])
                    self.assertAlmostEqual(settings['step'], (maximum[i]-minimum[i])/8, places=6)
                quats = np.frombuffer(gzip.decompress((directory / config['quaternions']).read_bytes()), dtype='<f4').reshape(config['quaternionShape'])
                self.assertEqual(quats.shape, (729,63,7,4))
                np.testing.assert_allclose(np.linalg.norm(quats, axis=-1), 1, atol=1e-6)
                # Independently evaluate the portable URDF, including all eight
                # grid corners and centre, at the contact and several other frames.
                for index in [0,8,72,80,364,648,656,720,728]:
                    for frame in [0,30,hit,62]:
                        cfg = dict(zip(JOINT_NAMES, base.joints[frame]))
                        cfg.update(zip(JOINT_NAMES[22:], arms[index,frame]))
                        model.update_cfg(cfg)
                        if frame == hit:
                            world_rotation = Rotation.from_quat(base.wxyz[frame,[1,2,3,0]]).as_matrix()
                            actual = world_rotation @ model.get_transform('right_racket')[:3,3] + base.positions[frame]
                            np.testing.assert_allclose(actual, achieved[index], atol=4e-7)
                        for j,name in enumerate(JOINT_NAMES[22:]):
                            joint = model.joint_map[name]
                            actual = model.get_transform(joint.child,joint.parent)[:3,:3]
                            decoded = Rotation.from_quat(quats[index,frame,j,[1,2,3,0]]).as_matrix()
                            np.testing.assert_allclose(decoded,actual,atol=3e-7)
                # Each green contact-window point must come from that style's
                # own reference racket trajectory plus the scripted toss ramp.
                for offset in range(5):
                    frame = hit - 2 + offset
                    model.update_cfg(dict(zip(JOINT_NAMES, base.joints[frame])))
                    rotation = Rotation.from_quat(base.wxyz[frame,[1,2,3,0]]).as_matrix()
                    position = rotation @ model.get_transform('right_racket')[:3,3] + base.positions[frame]
                    ramp = np.clip((frame-metadata['toss_start'])/(metadata['toss_end']-metadata['toss_start']-1),0,1)
                    # The source accumulates the ramp in float32, while this
                    # independent formula uses one multiply and float64 FK.
                    np.testing.assert_allclose(trajectories[:,offset],position+shifts*ramp,atol=2e-6)

    def test_pruned_kinematics_and_gradients_match_whole_model(self):
        import torch
        import pytorch_kinematics as pk
        from .serves import RacketChain
        torch.set_num_threads(1)
        urdf = (ROOT / 'robot-racket/g1.urdf').read_bytes()
        whole = pk.build_chain_from_urdf(urdf)
        branch = RacketChain(whole,pk.build_serial_chain_from_urdf(urdf,'right_racket'))
        torch.manual_seed(7)
        q = torch.randn(9,29,requires_grad=True)
        values = {name:q[:,i] for i,name in enumerate(JOINT_NAMES)}
        actual = whole.forward_kinematics(values)['right_racket'].get_matrix()
        pruned = branch.forward_kinematics(values)['right_racket'].get_matrix()
        torch.testing.assert_close(actual,pruned)
        weights = torch.randn_like(actual)
        grad_actual = torch.autograd.grad((actual*weights).sum(),q)[0]
        grad_pruned = torch.autograd.grad((pruned*weights).sum(),q)[0]
        torch.testing.assert_close(grad_actual,grad_pruned,atol=3e-6,rtol=1e-5)


if __name__ == '__main__':
    unittest.main()
