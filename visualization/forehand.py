"""Reproduce augment_serves_forehand_g1.py's contact grid and right-arm solve.

Same 9x9x9 grid, toss ramp, objective, Adam settings, nearest solved warm start,
stopping threshold and 4000-step limit. Only the right-arm kinematic branch is
evaluated, since the original loss depends solely on right_rubber_hand.
"""
import argparse
import json
from pathlib import Path
import time
import numpy as np
from .data import ROOT, JOINT_NAMES, Motion

ACTIVE_NAMES = JOINT_NAMES[22:]
HIT_FRAME = 45
DISPLAY_FPS = 10  # Original visualization loop sleeps 0.1 seconds per frame.
DISPLAY_LIFT = .035
TARGET_COST = .014


def grid():
    return np.stack([a.flatten() for a in np.meshgrid(
        np.linspace(-.12, -.04, 9)[::-1], np.linspace(-.04, .04, 9),
        np.linspace(-.04, .04, 9))], axis=1)


def add_change(positions, start, end, change):
    # Keep the original iterative ramp (including its exact endpoint semantics).
    for frame in range(start + 1, end):
        positions[frame:] += change / (end - start - 1)


def solve(limit=None):
    import torch
    import pytorch_kinematics as pk
    torch.set_num_threads(1)
    motion = Motion.load(ROOT / 'motions/forehand-reference.npz')
    if not np.allclose(motion.wxyz, [1, 0, 0, 0]):
        raise ValueError('The original forehand objective assumes identity root rotations.')
    urdf = (ROOT / 'robot/g1.urdf').read_bytes()
    whole = pk.build_chain_from_urdf(urdf)
    right = pk.build_serial_chain_from_urdf(urdf, 'right_rubber_hand')
    assert right.get_joint_parameter_names() == JOINT_NAMES[12:15] + ACTIVE_NAMES
    q = torch.tensor(motion.joints, dtype=torch.float32)
    translations = torch.tensor(motion.positions, dtype=torch.float32)
    with torch.no_grad():
        fk = whole.forward_kinematics({name: q[:, i] for i, name in enumerate(JOINT_NAMES)})
        left_positions = fk['left_rubber_hand'].get_matrix()[:, :3, 3] + translations
        reference = fk['right_rubber_hand'].get_matrix()
        right_positions = reference[:, :3, 3] + translations
        right_y = reference[:, :3, 1].clone()
        serial = right.forward_kinematics(torch.cat((q[:, 12:15], q[:, 22:]), dim=1)).get_matrix()
        torch.testing.assert_close(serial, reference)
    start = int(torch.argmin(left_positions[:, 2]))
    end = int(torch.argmax(left_positions[:, 2])) + 1
    shifts = grid()[:limit]
    arms, costs, steps, targets, achieved = [], [], [], [], []
    started = time.monotonic()
    for i, shift in enumerate(shifts):
        target = right_positions.clone()
        add_change(target, start, end, torch.tensor(shift, dtype=torch.float32))
        initial = q[:, 22:].clone() if not arms else torch.tensor(
            arms[int(np.argmin(np.linalg.norm(shifts[:i] - shift, axis=1)))])
        active = torch.nn.Parameter(initial)
        optimizer = torch.optim.Adam([active], lr=.001)

        def evaluate():
            transform = right.forward_kinematics(torch.cat((q[:, 12:15], active), dim=1)).get_matrix()
            direction = transform[:, :3, 1]
            positions = transform[:, :3, 3] + translations
            orientation = .3 * torch.acos(torch.clamp((right_y * direction).sum(dim=1), -.999, .999))
            return orientation.mean() + 3 * torch.mean(torch.abs(target - positions)), positions

        for iteration in range(4000):
            optimizer.zero_grad()
            loss, _ = evaluate()
            if loss.item() < TARGET_COST:
                break
            loss.backward()
            optimizer.step()
        with torch.no_grad():
            loss, positions = evaluate()
        arms.append(active.detach().numpy().copy())
        costs.append(float(loss))
        steps.append(iteration + 1)
        targets.append(target[HIT_FRAME].numpy())
        achieved.append(positions[HIT_FRAME].numpy())
        if i % 20 == 0 or i == len(shifts) - 1:
            print(f'{i + 1}/{len(shifts)} · cost {loss:.6f} · steps {iteration + 1} · elapsed {time.monotonic() - started:.1f}s', flush=True)
    output = ROOT / 'motions/forehand-grid.npz'
    metadata = {'source_script': 'augment_serves_forehand_g1.py',
                'source_revision': '49ecadb2d98643075de33509b01ab467450a4661',
                'base_motion_sha256': motion.metadata['sha256'],
                'grid_order': 'numpy.meshgrid(x_descending, y_ascending, z_ascending).flatten()',
                'active_joints': ACTIVE_NAMES, 'toss_start': start, 'toss_end': end,
                'hit_frame': HIT_FRAME, 'display_fps': DISPLAY_FPS, 'display_lift': DISPLAY_LIFT,
                'optimizer': 'Adam', 'learning_rate': .001, 'max_steps': 4000, 'target_cost': TARGET_COST,
                'torch_version': torch.__version__,
                'note': 'Recomputed from the original base motion; not original saved experiment outputs.'}
    np.savez_compressed(output, shifts=shifts.astype(np.float32), arms=np.array(arms), costs=costs,
                        steps=steps, targets=np.array(targets), achieved=np.array(achieved),
                        metadata=json.dumps(metadata))
    print(f'Saved {output.name}; {sum(c < TARGET_COST for c in costs)}/{len(costs)} below target; max cost {max(costs):.6f}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, help='Limit solves for a quick development check')
    args = parser.parse_args()
    solve(args.limit)
