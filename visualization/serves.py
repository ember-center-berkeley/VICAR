"""Generate the six serve grids with TT_PLayer's general augmentation solver.

Run with --source-root /path/to/TT_PLayer --trust-pickle. Source files are read
only. Each result includes the source revision, hashes, solver diagnostics and
the motion's own ranges/hit frame. No Python server is needed on GitHub Pages.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
from .data import ROOT, JOINT_NAMES, import_motion, read_catalog

ACTIVE_NAMES = JOINT_NAMES[22:]
DISPLAY_FPS = 10
DISPLAY_LIFT = .035
TARGET_COST = .028


def grid_axes(ranges):
    return {axis: {'min': round(bounds[0] - .04, 6),
                   'max': round(bounds[1] + .04, 6),
                   'step': round((bounds[1] - bounds[0] + .08) / 8, 6),
                   'default': round((bounds[0] + bounds[1]) / 2, 6)}
            for axis, bounds in ranges.items()}


def make_grid(axes):
    values = [np.linspace(axes[a]['min'], axes[a]['max'], 9) for a in 'xyz']
    values[0] = values[0][::-1]
    return np.stack([v.flatten() for v in np.meshgrid(*values)], axis=1)


def load_solver(source):
    # Load the actual pulled solver, including its rotation utilities. Avoid
    # executing augment_serves_general_g1.py's CLI and optional Pyroki viewer.
    sys.path.insert(0, str(source / 'IsaacLab/isaac_utils'))
    spec = importlib.util.spec_from_file_location('vicar_source_spa', source / 'retarget/spa.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RacketChain:
    """Evaluate only the branch used by this serve objective; keep joint order.

    The default general-serve loss references only right_racket. Returning its
    identical transform avoids evaluating legs/left arm on every Adam step.
    Other baseline objectives must use the complete chain instead.
    """
    def __init__(self, whole, right):
        self.whole, self.right = whole, right
        self.names = right.get_joint_parameter_names()
        self.end_index = right.frame_to_idx['right_racket']

    def get_joints(self):
        return self.whole.get_joints()

    def get_links(self):
        return self.whole.get_links()

    def forward_kinematics(self, q):
        import torch
        angles = torch.stack([q[name] for name in self.names], dim=-1)
        # Tensor API avoids Python tensor.item() graph breaks in torch.compile.
        return {'right_racket': MatrixTransform(self.right.forward_kinematics_tensor(angles)[self.end_index])}


class MatrixTransform:
    def __init__(self, matrix):
        self.matrix = matrix

    def get_matrix(self):
        return self.matrix


def solve(source, task, trust_pickle, max_iters=10000, compile_cost=False):
    import torch
    import pytorch_kinematics as pk
    torch.set_num_threads(1)
    spa = load_solver(source)
    if compile_cost:
        spa.compute_cost_batch = torch.compile(spa.compute_cost_batch)
    from isaac_utils.rotations import quaternion_to_matrix
    motion_file = source / f"refined_serve_g1/{task['style']}.pkl"
    base = import_motion(motion_file, DISPLAY_FPS, str(motion_file.relative_to(source)), trust_pickle)
    urdf = (source / 'urdf/g1/g1_racket.urdf').read_text()
    whole = pk.build_chain_from_urdf(urdf)
    right = pk.build_serial_chain_from_urdf(urdf, 'right_racket')
    assert [j.name for j in whole.get_joints()] == JOINT_NAMES
    chain = RacketChain(whole, right)
    device = torch.device('cpu')
    q = torch.tensor(base.joints, dtype=torch.float32)
    trans = torch.tensor(base.positions, dtype=torch.float32)
    quats = torch.tensor(base.wxyz, dtype=torch.float32)
    rot = quaternion_to_matrix(quats)
    axes = grid_axes(base.metadata['augment_ranges'])
    shifts = torch.tensor(make_grid(axes), dtype=torch.float32)
    hit = int(base.metadata['hit_time'])
    if not 2 <= hit < len(q) - 2:
        raise ValueError('The five-frame contact window is outside the recording.')
    with torch.no_grad():
        q_dict = {name: q[:, i] for i, name in enumerate(JOINT_NAMES)}
        fk = whole.forward_kinematics(q_dict)
        reference = fk['right_racket'].get_matrix()
        torch.testing.assert_close(chain.forward_kinematics(q_dict)['right_racket'].get_matrix(), reference)
        left = torch.bmm(fk['left_ball_holder'].get_matrix()[:, :3, 3].unsqueeze(1), rot.transpose(2, 1))[:, 0] + trans
        positions = torch.bmm(reference[:, :3, 3].unsqueeze(1), rot.transpose(2, 1))[:, 0] + trans
        start, end = int(left[:, 2].argmin()), int(left[:, 2].argmax()) + 1
        if end - start <= 1:
            raise ValueError('The source toss ramp has no positive duration.')
        targets = positions.unsqueeze(0).expand(729, -1, -1).clone()
        for frame in range(start + 1, end):
            targets[:, frame:] += shifts.unsqueeze(1) / (end - start - 1)
        anchors = [(t, 'right_racket', targets[:, t].detach()) for t in range(hit - 2, hit + 3)]
        anchors.append((0, 'right_racket', targets[:, 0].detach()))
    started = time.monotonic()
    print(f"Solving {task['id']}: {axes}, hit frame {hit}, toss {start}:{end}", flush=True)
    arms, converged = spa.solve_joint_angles_batch(
        q, trans, quats, chain, ACTIVE_NAMES, ['right_racket'], anchors,
        x_axis_refs={'right_racket': reference[:, :3, 0].detach()},
        y_axis_refs={'right_racket': reference[:, :3, 1].detach()},
        target_cost=TARGET_COST, device=device, add_speed_diff_costs=True,
        max_iters=max_iters,
    )
    with torch.no_grad():
        qs = {name: q[:, i].repeat(729) for i, name in enumerate(JOINT_NAMES)}
        qs.update({name: arms[:, :, i].reshape(-1) for i, name in enumerate(ACTIVE_NAMES)})
        final = chain.forward_kinematics(qs)['right_racket'].get_matrix()
        achieved = (torch.bmm(final[:, :3, 3].unsqueeze(1), rot.repeat(729, 1, 1).transpose(2, 1))[:, 0] + trans.repeat(729, 1)).reshape(729, len(q), 3)
        distances = torch.norm(positions[1:] - positions[:-1], dim=1)[:, None]
        skip_distances = torch.norm(positions[2:] - positions[:-2], dim=1)[:, None]
        for t in range(hit - 2, hit + 2):
            distances[t] = torch.norm(targets[:, t + 1] - targets[:, t], dim=1).mean()
        for t in range(hit - 2, hit + 1):
            skip_distances[t] = torch.norm(targets[:, t + 2] - targets[:, t], dim=1).mean()
        costs, components = spa.compute_cost_batch(
            arms, trans, quats, chain, ACTIVE_NAMES, list(range(22)), q,
            ['right_racket'], distances, skip_distances, anchors,
            x_axis_refs={'right_racket': reference[:, :3, 0]},
            y_axis_refs={'right_racket': reference[:, :3, 1]}, z_axis_refs={},
            joint_names=JOINT_NAMES, add_speed_diff_costs=True,
        )
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    metadata = {
        'source_script': 'augment_serves_general_g1.py', 'source_revision': revision,
        'source_script_sha256': hashlib.sha256((source / 'augment_serves_general_g1.py').read_bytes()).hexdigest(),
        'solver_sha256': hashlib.sha256((source / 'retarget/spa.py').read_bytes()).hexdigest(),
        'urdf_sha256': hashlib.sha256(urdf.encode()).hexdigest(),
        'base_motion_sha256': base.metadata['sha256'], 'style': task['style'],
        'axes': axes, 'hit_frame': hit, 'toss_start': start, 'toss_end': end,
        'active_joints': ACTIVE_NAMES, 'display_fps': DISPLAY_FPS,
        'robot_display_lift': DISPLAY_LIFT, 'target_display_lift': 0,
        'baseline': 'ours', 'optimizer': 'Adam', 'learning_rate': .001,
        'max_steps': max_iters, 'target_cost': TARGET_COST,
        'orientation_cost_floor': float(40 * np.arccos(.999) ** 2),
        'converged': int(converged.sum()), 'torch_version': torch.__version__,
        'compiled_cost': compile_cost,
        'elapsed_seconds': round(time.monotonic() - started, 2),
        'note': 'Recomputed with the source solver; not original experiment outputs. The clamped two-axis orientation loss has a ~0.0800 floor, above the source 0.028 threshold; iteration-limit results are retained as in the source script.',
    }
    destination = ROOT / 'motions/serves'
    destination.mkdir(exist_ok=True)
    base.metadata['source_revision'] = revision
    base.save(destination / f"{task['id']}-reference.npz")
    np.savez_compressed(destination / f"{task['id']}-grid.npz", arms=arms.numpy(),
        shifts=shifts.numpy(), trajectories=targets[:, hit-2:hit+3].numpy(),
        targets=targets[:, hit].numpy(), markers=((targets[:, hit] + targets[:, hit+1]) / 2).numpy(),
        achieved=achieved[:, hit].numpy(), costs=costs.numpy(), converged=converged.numpy(),
        metadata=json.dumps(metadata), **{k: v.numpy() for k, v in components.items()})
    print(f"Saved {task['id']}: {metadata['elapsed_seconds']}s, max hit error {torch.norm(achieved[:, hit]-targets[:, hit],dim=1).max().item()*1000:.2f} mm", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--trust-pickle', action='store_true')
    parser.add_argument('--task')
    parser.add_argument('--compile', action='store_true', help='Compile the unchanged PyTorch cost for faster offline generation')
    parser.add_argument('--max-iters', type=int, default=10000, help='Source default: 10000. Smaller values are development previews only.')
    args = parser.parse_args()
    for task in read_catalog()['tasks']:
        if task['kind'] == 'serve' and (not args.task or args.task == task['id']):
            solve(args.source_root.resolve(), task, args.trust_pickle, args.max_iters, args.compile)


if __name__ == '__main__':
    main()
