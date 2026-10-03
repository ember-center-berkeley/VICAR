"""Run the other TT_PLayer augment_* scripts headlessly and export their data.

The source constructs every target, constraint, range and scene. Only its
optional GUI/heightmap and machine-specific paths are adapted. Pickles require
explicit trust. Source scripts and assets are never modified.
"""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import time
import numpy as np
from .data import ROOT, JOINT_NAMES, check_file
from .serves import MatrixTransform

TASKS = {
    'tabletop-left': dict(task='tabletop-pickup', label='Left hand', script='augment_pick_motions_left_g1.py', fps=20, lift=.035),
    'tabletop-right': dict(task='tabletop-pickup', label='Right hand', script='augment_pick_motions_g1.py', fps=10, lift=.035),
    'under-table-pickup': dict(task='under-table-pickup', label='Contact augmentation', script='augment_ground_pick_motions_left_g1.py', fps=1/.033, lift=0),
    'bimanual-pick-place': dict(task='bimanual-pick-place', label='Contact augmentation', script='augment_bimanual_pick_motions_g1.py', fps=1/.033, lift=0),
    'ladder-climbing': dict(task='ladder-climbing', label='Contact solution', script='augment_climbing_motions_g1.py', fps=1/.033, lift=0),
}
DATA_DIR = ROOT / 'motions/tasks'


def trusted_load(file):
    import torch
    class CPUUnpickler(pickle.Unpickler):
        def find_class(self, module, name):
            if module == 'torch.storage' and name == '_load_from_bytes':
                return lambda b: torch.load(io.BytesIO(b), map_location='cpu', weights_only=False)
            return super().find_class(module, name)
    return CPUUnpickler(file).load()


class HeadlessSource(ast.NodeTransformer):
    def __init__(self, source):
        self.source = source

    def visit_Import(self, node):
        node.names = [n for n in node.names if n.name != 'pyroki']
        return node if node.names else None

    def visit_Assign(self, node):
        if any(isinstance(t, ast.Name) and t.id == 'heightmap' for t in node.targets):
            return None
        return self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == 'pickle' and node.func.attr == 'load':
                node.func = ast.Name(id='_trusted_load', ctx=ast.Load())
            elif node.func.attr == 'parse_args':
                node.args = [ast.List(elts=[], ctx=ast.Load())]
        return self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str) and node.value.startswith('/home/dvij/TT_Player/'):
            node.value = str(self.source / node.value.removeprefix('/home/dvij/TT_Player/'))
        return node


def read_source(source, key):
    import torch
    torch.set_num_threads(1)
    sys.path[:0] = [str(source), str(source / 'IsaacLab/isaac_utils')]
    from retarget import spa
    spec = TASKS[key]
    text = (source / spec['script']).read_text()
    tree = ast.fix_missing_locations(HeadlessSource(source).visit(ast.parse(text)))
    # Prevent the source PLY reader waiting forever on an unhydrated LFS pointer.
    if 'load_ply_xyz_rgb(' in text:
        check_file(source / 'mega-sam/UniDepth/pointclouds/bimanual_pick_place/table_00000.ply')
        check_file(source / 'holosoma/src/holosoma_retargeting/demo_data/cameras_refined/bimanual_pick_place_new.npy')
    for index, statement in enumerate(tree.body):
        if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call) and isinstance(statement.value.func, ast.Name) and statement.value.func.id == 'solve_joint_angles_batch':
            break
    else:
        raise ValueError('Source solver entry point has changed.')
    env = {'__name__': 'vicar_headless_source', '_trusted_load': trusted_load}
    cwd = Path.cwd()
    try:
        os.chdir(source)
        exec(compile(ast.Module(body=tree.body[:index], type_ignores=[]), spec['script'], 'exec'), env)
        env['solve_joint_angles_batch'] = lambda *a, **kw: (a, kw)
        args, kwargs = eval(compile(ast.Expression(statement.value), spec['script'], 'eval'), env)
    finally:
        os.chdir(cwd)
    return env, args, kwargs, tree.body[index+1:], spa


class SelectedChain:
    """Identical FK for the branches actually referenced by a task's loss."""
    def __init__(self, whole, urdf, names):
        import pytorch_kinematics as pk
        self.whole = whole
        self.branches = []
        self.indices = {}
        self.order = [name for name in whole.frame_to_idx if name in names]
        # A hand's serial chain also contains its elbow and shoulder. Evaluate
        # that chain once, then reuse its intermediate transforms.
        for name in reversed(self.order):
            if name in self.indices:
                continue
            branch = pk.build_serial_chain_from_urdf(urdf, name).to(device=whole.device)
            index = len(self.branches)
            self.branches.append((branch, branch.get_joint_parameter_names()))
            for frame, frame_index in branch.frame_to_idx.items():
                if frame in names and frame not in self.indices:
                    self.indices[frame] = (index, frame_index)

    def get_joints(self):
        return self.whole.get_joints()

    def get_links(self):
        return self.whole.get_links()

    def forward_kinematics(self, q):
        import torch
        matrices = [branch.forward_kinematics_tensor(torch.stack([q[n] for n in names], dim=-1)) for branch, names in self.branches]
        return {name: MatrixTransform(matrices[self.indices[name][0]][self.indices[name][1]]) for name in self.order}


class VectorizedCost:
    """Vectorize the source's anchor sum, retaining its costs and gradients.

    Source Adam, reference-speed construction, thresholds, masks, limits and
    iteration caps are unchanged. Validate against the original on first call.
    Only baseline 'ours', fixed-root tasks are accepted.
    """
    def __init__(self, original, obstacle_cost, compile_cost=True):
        self.original, self.obstacle_cost = original, obstacle_cost
        self.compile_cost = compile_cost
        self.evaluate = None

    def __call__(self, active, trans, quats, chain, active_names, inactive_ids, q_ref,
                 keypoints, distances, skip_distances, anchors, **kw):
        import torch
        from isaac_utils.rotations import quaternion_to_matrix
        if self.evaluate is None:
            if kw.get('laplacian_weight', 0) or kw.get('motion_transfer_weight', 0) or trans.ndim != 2:
                raise ValueError('This adapter supports only the requested default fixed-root objective.')
            N, T, _ = active.shape
            names = kw['joint_names']
            grouped = {}
            for t, name, position in anchors:
                grouped.setdefault(name, []).append((t, position))
            packed = {name: (torch.tensor([t for t,_ in items], dtype=torch.long, device=active.device),
                             torch.stack([p for _,p in items], dim=1)) for name,items in grouped.items()}
            rotation = quaternion_to_matrix(quats).repeat(N, 1, 1)
            translation = trans.repeat(N, 1)
            inactive = {names[i]: q_ref[:,i].repeat(N) for i in inactive_ids}
            def evaluate(angles):
                q = {name: angles[:,:,i].reshape(N*T) for i,name in enumerate(active_names)}
                q.update(inactive)
                fk = chain.forward_kinematics(q)
                zero = torch.zeros(N, dtype=angles.dtype, device=angles.device)
                total, smooth, axis_cost, anchor_cost, obstacle, dist_cost = [zero.clone() for _ in range(6)]
                ids = kw.get('smoothening_ids')
                if ids is not None:
                    smooth = kw.get('smoothening_k',30.) * (angles[:,1:,ids]-angles[:,:-1,ids]).square().sum(dim=2).mean(dim=1)
                    total = total + smooth
                for name, transform in fk.items():
                    matrix = transform.get_matrix()
                    position = (torch.bmm(matrix[:,:3,3].unsqueeze(1), rotation.transpose(2,1))[:,0]+translation).reshape(N,T,3)
                    if name in keypoints:
                        i = keypoints.index(name)
                        one = (distances[:,i]-torch.norm(position[:,1:]-position[:,:-1],dim=2)).square().sum(dim=1)
                        two = (skip_distances[:,i]-torch.norm(position[:,2:]-position[:,:-2],dim=2)).square().sum(dim=1)
                        if kw.get('add_speed_diff_costs',True):
                            total = total + 10*one + 10*two
                        dist_cost = dist_cost + one
                        if kw.get('obstacles'):
                            value = self.obstacle_cost(position, kw['obstacles'], kw.get('obstacle_avoidance_k',100.))
                            total, obstacle = total+value, obstacle+value
                    for axis, field, weight in [(1,'y_axis_refs',20.),(0,'x_axis_refs',20.),(2,'z_axis_refs',200.)]:
                        refs = kw.get(field) or {}
                        if name in refs:
                            direction = torch.bmm(rotation,matrix[:,:3,:3])[:,:,axis].reshape(N,T,3)
                            value = weight * torch.acos(torch.clamp((refs[name]*direction).sum(dim=2),-.999,.999)).square().sum(dim=1)/T
                            total, axis_cost = total+value, axis_cost+value
                    if name in packed:
                        times, expected = packed[name]
                        value = 10*(expected-position[:,times]).square().sum(dim=(1,2))
                        total, anchor_cost = total+value, anchor_cost+value
                return total, dict(obstacle_costs=obstacle, axis_ref_costs=axis_cost, anchor_costs=anchor_cost,
                    smoothening_costs=smooth, dist_costs=dist_cost, laplacian_costs=zero, motion_transfer_costs=zero)
            # This check covers the full task batch, including all anchors and
            # geometry, before permitting compiled optimization.
            probe = (active.detach()+.013).requires_grad_()
            original, original_parts = self.original(probe,trans,quats,chain,active_names,inactive_ids,q_ref,
                keypoints,distances,skip_distances,anchors,**kw)
            candidate, candidate_parts = evaluate(probe)
            torch.testing.assert_close(candidate, original, rtol=2e-5, atol=2e-5)
            for name in original_parts:
                torch.testing.assert_close(candidate_parts[name],original_parts[name],rtol=2e-5,atol=2e-5)
            g1 = torch.autograd.grad(original.sum(),probe)[0]
            g2 = torch.autograd.grad(candidate.sum(),probe)[0]
            torch.testing.assert_close(g2,g1,rtol=1e-4,atol=2e-5)
            print('PASS: vectorized source cost, every component, and gradients.',flush=True)
            self.evaluate = torch.compile(evaluate) if self.compile_cost else evaluate
        return self.evaluate(active)


def generate(source, key, compile_cost=True, max_iters=None):
    import torch
    env, args, kwargs, tail, spa = read_source(source,key)
    spec = TASKS[key]
    args = list(args)
    if env['joint_names'] != JOINT_NAMES:
        raise ValueError('Source joint order has changed; audit the 29-to-43-joint mapping before exporting.')
    names = set(args[5]) | {a[1] for a in args[6]}
    for field in ('x_axis_refs','y_axis_refs','z_axis_refs'):
        names.update(kwargs.get(field,{}))
    urdf = (source/env['urdf_path']).read_bytes()
    selected = SelectedChain(args[3],urdf,names)
    sample = {name:args[0][:,i] for i,name in enumerate(env['joint_names'])}
    original_fk = args[3].forward_kinematics(sample)
    for name,transform in selected.forward_kinematics(sample).items():
        torch.testing.assert_close(transform.get_matrix(),original_fk[name].get_matrix())
    args[3] = selected
    source_iters = kwargs.get('max_iters',10000)
    if max_iters is not None:
        kwargs['max_iters'] = max_iters
    adapter = VectorizedCost(spa.compute_cost_batch,spa.compute_obstacle_avoidance_cost,compile_cost)
    spa.compute_cost_batch = adapter
    started = time.monotonic()
    print(f"{key}: {env['N_shifts']} motions, {env['num_timesteps']} frames, {len(env['active_joint_names'])} optimized joints, {kwargs.get('max_iters',10000)} iterations",flush=True)
    try:
        solved, converged = spa.solve_joint_angles_batch(*args,**kwargs)
        with torch.no_grad():
            costs, components = adapter.evaluate(solved)
    finally:
        spa.compute_cost_batch = adapter.original
    env.update(joint_angles_batch=solved.cpu(),converged=converged.cpu(),solver_device=str(args[0].device))
    env['chain'] = env['chain'].to(device=torch.device('cpu'))
    cwd = Path.cwd()
    try:
        os.chdir(source)
        exec(compile(ast.Module(body=tail,type_ignores=[]),spec['script'],'exec'),env)
    finally:
        os.chdir(cwd)
    export_data(source,key,env,costs.cpu(),{k:v.cpu() for k,v in components.items()},converged.cpu(),source_iters,kwargs.get('max_iters',10000),time.monotonic()-started,
        DATA_DIR/'previews' if max_iters is not None else DATA_DIR)


def export_data(source,key,env,costs,components,converged,source_iters,iterations,elapsed,destination=DATA_DIR):
    import torch
    from isaac_utils.rotations import quaternion_to_matrix
    spec = TASKS[key]
    q = np.stack(env['joints_new_augs']).astype(np.float32)
    body = np.stack([x.numpy() for x in env['joint_new_s']]).astype(np.float32)
    poses = np.array(env['Ts_world_roots'][0].wxyz_xyz)
    shifts = np.stack([env['SHIFT_Xs'],env['SHIFT_Ys'],env['SHIFT_Zs']],axis=1)
    axes = {}
    default_query = []
    for i,axis in enumerate('xyz'):
        values = np.unique(shifts[:,i])
        # Controls select actual samples, including even-sized and fixed axes.
        default = float(values[(len(values)-1)//2])
        axes[axis] = dict(min=float(values[0]),max=float(values[-1]),step=float(values[1]-values[0]) if len(values)>1 else 1.,default=default,values=values.tolist())
        default_query.append(default)
    default_index = int(np.linalg.norm(shifts-default_query,axis=1).argmin())
    revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    metadata = {**spec,'key':key,'source_revision':revision,'axes':axes,'default_index':default_index,
        'source_script_sha256':hashlib.sha256((source/spec['script']).read_bytes()).hexdigest(),
        'solver_sha256':hashlib.sha256((source/'retarget/spa.py').read_bytes()).hexdigest(),
        'kinematic_urdf':env['urdf_path'],'kinematic_urdf_sha256':hashlib.sha256((source/env['urdf_path']).read_bytes()).hexdigest(),
        'active_joints':env['active_joint_names'],'source_iterations':source_iters,'iterations':iterations,
        'converged':int(converged.sum()),'target_cost':env['TARGET_COST'],'baseline':env.get('BASELINE','ours'),'elapsed_seconds':round(elapsed,2),
        'torch_version':torch.__version__,'root_y_zeroed':key=='ladder-climbing',
        'solver_device':env.get('solver_device','cpu'),
        'source_adaptations':['CPU-safe trusted pickle import','Resolve original absolute paths in supplied checkout','Omit GUI-only Pyroki heightmap','Vectorized equivalent anchor sums and selected FK branches, validated against source cost and gradients']}
    for field in ['PICK_TIME','CONTACT_START_FRAME','CONTACT_END_FRAME','TURN_AROUND_FRAMES','N_STAIRS','STAIR_TREAD','STAIR_DEPTH','LEFT_FEET_Y','RIGHT_FEET_Y','LEFT_HAND_Y','RIGHT_HAND_Y','LEFT_FEET_CONTACTS','RIGHT_FEET_CONTACTS','LEFT_HAND_CONTACTS','RIGHT_HAND_CONTACTS','OBJECT_DIMS','PLATFORM_POSITION','PLATFORM_DIMENSIONS','RIGHT_HAND_CONTACT_POINT']:
        if field in env:metadata[field]=env[field]
    # The actual input pickles are a fixed, reviewed mapping, not filename guesses.
    inputs={'tabletop-left':'refined_pick_g1/pick_left.pkl','tabletop-right':'refined_pick_g1/pick.pkl',
        'under-table-pickup':'refined_ground_pick_g1/ground_pick_left.pkl','bimanual-pick-place':'refined_bimanual_pick_g1/bimanual_pick.pkl','ladder-climbing':'refined_climbing_pick_g1/climbing.pkl'}
    metadata['source_motion']=inputs[key]
    metadata['source_motion_sha256']=hashlib.sha256((source/inputs[key]).read_bytes()).hexdigest()
    arrays={name:np.asarray(env[name]) for name in ['table_pts_world','table_pts_colors','table_vox_verts','table_vox_faces','_R0','_t0','STAIR_ORIGIN'] if name in env}
    for name in ['pos_left_hand_batch','pos_right_hand_batch','object_traj_batch']:
        if name in env:arrays[name]=env[name].cpu().numpy()
    N,T,_=q.shape
    # FK is used for the carried objects and the source penetration overlays.
    with torch.no_grad():
        q_dict={name:torch.tensor(body[:,:,i].reshape(-1)) for i,name in enumerate(JOINT_NAMES)}
        fk=env['chain'].forward_kinematics(q_dict)
        rot=quaternion_to_matrix(torch.tensor(poses[:,:4])).repeat(N,1,1)
        trans=torch.tensor(poses[:,4:]).repeat(N,1)
        for name in set(env.get('left_arm_keypt_names',[])+env.get('right_arm_keypt_names',[])+['left_ankle_roll_link','right_ankle_roll_link']):
            matrix=fk[name].get_matrix()
            arrays[f'world_{name}']=(torch.bmm(matrix[:,:3,3].unsqueeze(1),rot.transpose(2,1))[:,0]+trans).reshape(N,T,3).numpy()
            if name.endswith('rubber_hand'):
                arrays[f'rotation_{name}']=torch.bmm(rot,matrix[:,:3,:3]).reshape(N,T,3,3).numpy()
    # Preserve exact source obstacle meshes for the optional collision overlay.
    for i,(shape,p1,p2) in enumerate(env['obstacles']):
        if shape=='mesh':
            arrays[f'obstacle_{i}_vertices']=p1.cpu().numpy()
            arrays[f'obstacle_{i}_faces']=p2.cpu().numpy()
    destination.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(destination/f'{key}.npz',joints=q,body_joints=body,poses=poses,shifts=shifts,
        costs=costs.numpy(),converged=converged.numpy(),metadata=json.dumps(metadata),
        **{k:v.numpy() for k,v in components.items()},**arrays)
    urdf_text=(source/env['urdf_path']).read_text()
    (destination/env['urdf_path']).write_text('\n'.join(line.rstrip() for line in urdf_text.splitlines())+'\n')
    print(f'Saved {key}: {N} motions; costs {costs.min():.5f}–{costs.max():.5f}; converged {int(converged.sum())}; {elapsed:.1f}s',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',required=True,type=Path)
    parser.add_argument('--task',required=True,choices=TASKS)
    parser.add_argument('--trust-pickle',action='store_true')
    parser.add_argument('--no-compile',action='store_true')
    parser.add_argument('--max-iters',type=int,help='Short development run; cannot be published')
    args=parser.parse_args()
    if not args.trust_pickle:parser.error('Trusted source execution requires --trust-pickle.')
    if args.max_iters is not None and args.max_iters<1:parser.error('--max-iters must be positive.')
    generate(args.source_root.resolve(),args.task,not args.no_compile,args.max_iters)


if __name__=='__main__':
    main()
