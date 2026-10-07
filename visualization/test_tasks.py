"""Independent checks for task ranges, hand mapping, objects and browser poses."""
import gzip
import json
import unittest
import msgspec
import zstandard
import numpy as np
from scipy.spatial.transform import Rotation
import yourdfpy
from .data import ROOT, JOINT_NAMES

# Audited from the five source scripts (including bimanual's +0.07 m Z shift).
EXPECTED = {
    'tabletop-left': (306,320,[9,17,2],[0,-.3,.058133676052093526],[.2,.08,.07813367605209352],10000),
    'tabletop-right': (306,220,[9,17,2],[0,-.08,.058133676052093526],[.2,.3,.07813367605209352],20000),
    'under-table-pickup': (250,385,[5,10,5],[0,0,-.1],[.05,.1,0],10000),
    'bimanual-pick-place': (50,480,[5,1,10],[0,0,.57],[.05,0,.67],10000),
    'ladder-climbing': (1,364,[1,1,1],[0,0,.07],[0,0,.07],10000),
}
DATA = ROOT/'motions/tasks'
PUBLIC = ROOT.parent/'assets/augmentation/tasks'


class TaskTests(unittest.TestCase):
    def test_revised_ladder_contacts_geometry_and_limits(self):
        with np.load(DATA/'ladder-climbing.npz',allow_pickle=False) as file:data=dict(file)
        meta=json.loads(str(data['metadata']))
        grid=json.loads((PUBLIC/'ladder-climbing.json').read_text())
        self.assertEqual(meta['script'],'augment_climbing_motions_g1_vis.py')
        self.assertEqual(len(meta['active_joints']),24)
        self.assertNotIn('left_hip_yaw_joint',meta['active_joints'])
        self.assertNotIn('right_hip_yaw_joint',meta['active_joints'])
        self.assertEqual(meta['HAND_ROT_INDICES'],[20,69,320,340])
        self.assertEqual(meta['LEFT_FEET_CONTACTS'],[[0,69,0],[95,165,1],[206,363,3]])
        self.assertEqual(meta['RIGHT_FEET_CONTACTS'],[[0,115,0],[150,225,2],[244,363,3]])
        self.assertEqual(meta['LEFT_HAND_CONTACTS'],[[69,156,4],[206,297,6]])
        self.assertEqual(meta['RIGHT_HAND_CONTACTS'],[[140,240,5],[280,297,6]])
        np.testing.assert_allclose(data['STAIR_ORIGIN'],[.4,0,0])
        for name in meta['active_joints']:
            angles=data['body_joints'][:,:,JOINT_NAMES.index(name)]
            lower,upper=meta['joint_limit_constraints'][name]
            self.assertGreaterEqual(float(angles.min()),lower-2e-6)
            self.assertLessEqual(float(angles.max()),upper+2e-6)
        recording=(PUBLIC/'ladder-climbing-base.viser').read_bytes()
        payload=zstandard.ZstdDecompressor().decompress(recording[8:])
        header=msgspec.msgpack.decode(payload[8:8+int.from_bytes(payload[:8],'little')])
        messages={(m['type'],m.get('name')):m for t,m in header['messages'] if t==0}
        self.assertEqual(len(grid['boxNodes']),10)
        for contact in meta['visual_contacts']:
            stair=contact['stair']
            y=contact['position'][1]
            visual=[.4+(stair-1)*.076,y,.3*stair+.07] if stair else [0,y,.03]
            offset=.17 if 'foot' in contact['node'] else .12
            target=[.4+(stair-1)*.076+offset,y,.3*stair+.09] if stair else [offset,y,.05]
            np.testing.assert_allclose(contact['position'],visual,atol=1e-7)
            np.testing.assert_allclose(contact['optimizer_position'],target,atol=1e-7)
            np.testing.assert_allclose(messages['SetPositionMessage',contact['node']]['position'],visual,atol=1e-7)
            self.assertLess(contact['end'],364)
        for stair in range(1,7):
            name=f'/stairs/step_{stair}'
            np.testing.assert_allclose(messages['SetPositionMessage',name]['position'],[.4+(stair-.5)*.076,0,.3*stair])
            np.testing.assert_allclose(messages['BoxMessage',name]['props']['dimensions'],[.076,1,.05])
        self.assertFalse(any(layer['id']=='obstacles' for layer in grid['layers']))
        self.assertFalse(any(m.get('name','').startswith(('/collision/','/obstacles/')) for _,m in header['messages']))
        self.assertEqual(grid['quaternionShape'],[1,364,24,4])

    def test_source_ranges_fingers_and_browser_kinematics(self):
        hands=yourdfpy.URDF.load(str(ROOT/'robot-hands/g1.urdf'))
        self.assertEqual(len(hands.actuated_joint_names),43)
        for key,(N,T,counts,minimum,maximum,iterations) in EXPECTED.items():
            with self.subTest(task=key):
                with np.load(DATA/f'{key}.npz',allow_pickle=False) as file:data=dict(file)
                meta=json.loads(str(data['metadata']))
                grid=json.loads((PUBLIC/f'{key}.json').read_text())
                self.assertEqual(data['joints'].shape,(N,T,43))
                self.assertEqual(data['poses'].shape,(T,7))
                self.assertEqual(meta['iterations'],iterations)
                self.assertEqual(meta['source_iterations'],iterations)
                self.assertEqual(len(np.unique(data['shifts'],axis=0)),N)
                self.assertEqual(grid['provenance']['source_script_sha256'],meta['source_script_sha256'])
                np.testing.assert_allclose(data['shifts'].min(axis=0),minimum,atol=1e-7)
                np.testing.assert_allclose(data['shifts'].max(axis=0),maximum,atol=1e-7)
                for i,axis in enumerate('xyz'):
                    settings=grid['axes'][axis]
                    self.assertEqual(len(settings['values']),counts[i])
                    self.assertIn(settings['default'],settings['values'])
                    np.testing.assert_allclose(settings['values'],np.unique(data['shifts'][:,i]))
                np.testing.assert_allclose(data['shifts'][grid['defaultIndex']],[grid['axes'][a]['default'] for a in 'xyz'])
                for field in ['joints','body_joints','poses','costs']:
                    self.assertTrue(np.isfinite(data[field]).all(),field)
                # Source files contain small magnitude errors (up to 0.00465
                # for bimanual). The rendered orientation must be normalized
                # to match the normalized rotation in the optimization FK.
                self.assertTrue((np.linalg.norm(data['poses'][:,:4],axis=1)>1e-8).all())
                recording=(PUBLIC/f'{key}-base.viser').read_bytes()
                payload=zstandard.ZstdDecompressor().decompress(recording[8:])
                header=msgspec.msgpack.decode(payload[8:8+int.from_bytes(payload[:8],'little')])
                root_messages=[(t,m) for t,m in header['messages'] if m['type']=='SetOrientationMessage' and m['name']=='/base_new']
                if not root_messages:
                    # A constant identity root uses the scene node default;
                    # Viser omits redundant orientation messages.
                    np.testing.assert_allclose(data['poses'][:,:4],np.tile([1,0,0,0],(T,1)),atol=1e-7)
                for t,message in root_messages:
                    frame=min(T-1,int(round(t*grid['fps'])))
                    q=data['poses'][frame,:4]
                    np.testing.assert_allclose(message['wxyz'],q/np.linalg.norm(q),atol=2e-7)
                    self.assertAlmostEqual(np.linalg.norm(message['wxyz']),1,places=6)
                np.testing.assert_array_equal(data['joints'][:,:,:22],data['body_joints'][:,:,:22])
                np.testing.assert_array_equal(data['joints'][:,:,29:36],data['body_joints'][:,:,22:29])
                # Finger close windows are copied from the task, not guessed
                # from the selected object's world trajectory.
                if key in ['tabletop-left','tabletop-right','under-table-pickup']:
                    pick=130 if key=='under-table-pickup' else 100
                    ramp=np.clip((np.arange(T)-pick)/15,0,1)
                    expected=np.zeros((T,43))
                    if key=='tabletop-right':
                        expected[:,39:]=1.2*ramp[:,None];expected[:,38]=-1.2*ramp;expected[:,37]=-.4*ramp
                    else:
                        expected[:,25:29]=-1.2*ramp[:,None];expected[:,24]=1.2*ramp;expected[:,23]=.4*ramp
                    fingers=[*range(22,29),*range(36,43)]
                    np.testing.assert_allclose(data['joints'][:,:,fingers],np.broadcast_to(expected[:,fingers],(N,T,14)),atol=1e-7)
                if key=='tabletop-left':
                    np.testing.assert_allclose(data['body_joints'][:,-1,[12,15]]-data['body_joints'][:,219,[12,15]],np.tile([-.8,-1.6],(N,1)),atol=3e-7)
                    np.testing.assert_array_equal(data['poses'][220:],np.tile(data['poses'][219],(100,1)))
                if key=='ladder-climbing':np.testing.assert_array_equal(data['poses'][:,5],np.zeros(T))
                quats=np.frombuffer(gzip.decompress((PUBLIC/grid['quaternions']).read_bytes()),dtype='<f4').reshape(grid['quaternionShape'])
                self.assertEqual(quats.shape,(N,T,len(meta['active_joints']),4))
                np.testing.assert_allclose(np.linalg.norm(quats,axis=-1),1,atol=1e-6)
                for index in sorted(set([0,N//2,N-1])):
                    for frame in sorted(set([0,grid['hitFrame'],T-1])):
                        hands.update_cfg(data['joints'][index,frame])
                        for j,name in enumerate(meta['active_joints']):
                            joint=hands.joint_map[name]
                            actual=hands.get_transform(joint.child,joint.parent)[:3,:3]
                            decoded=Rotation.from_quat(quats[index,frame,j,[1,2,3,0]]).as_matrix()
                            np.testing.assert_allclose(decoded,actual,atol=3e-7)

    def test_carried_objects_and_penetration_channels_against_independent_fk(self):
        for key,(N,T,*_) in EXPECTED.items():
            if key=='ladder-climbing':continue
            with self.subTest(task=key):
                with np.load(DATA/f'{key}.npz',allow_pickle=False) as file:data=dict(file)
                meta=json.loads(str(data['metadata']))
                config=json.loads((PUBLIC/f'{key}.json').read_text())
                spec=config['dynamic']
                pack=np.frombuffer(gzip.decompress((PUBLIC/spec['file']).read_bytes()),dtype='<f4').reshape(N,T,spec['frameStride'])
                self.assertTrue(np.isfinite(pack).all())
                channels={(c['node'],c['property']):c for c in spec['channels']}
                def value(node,prop,index,frame):
                    c=channels[(node,prop)]
                    return pack[index,frame,c['offset']:c['offset']+c['width']]
                body=yourdfpy.URDF.load(str(DATA/meta['kinematic_urdf']),load_meshes=False,build_collision_scene_graph=False)
                for index in sorted(set([0,N//2,N-1])):
                    for frame in [0,config['hitFrame'],min(config['hitFrame']+35,T-1),T-1]:
                        if key=='bimanual-pick-place':
                            expected=data['object_traj_batch'][index,np.clip(frame,150,300)].copy()
                            expected[2]=np.clip(expected[2]-.2,.15,2)
                        else:
                            picked=max(frame,meta['PICK_TIME'])
                            body.update_cfg(dict(zip(JOINT_NAMES,data['body_joints'][index,picked])))
                            root=data['poses'][picked]
                            R=Rotation.from_quat(root[[1,2,3,0]]).as_matrix()
                            side='right' if key=='tabletop-right' else 'left'
                            hand=body.get_transform(f'{side}_rubber_hand')
                            offset=[-.08,.01,.06] if side=='right' else [-.08,-.01,-.03 if key=='tabletop-left' else .06]
                            expected=root[4:]+R@(hand[:3,3]+hand[:3,:3]@offset)
                            orientation=Rotation.from_quat(value('/object_cuboid','wxyz',index,frame)[[1,2,3,0]]).as_matrix()
                            np.testing.assert_allclose(orientation,R@hand[:3,:3],atol=1e-6)
                        np.testing.assert_allclose(value('/object_cuboid','position',index,frame),expected,atol=1e-6)
                        body.update_cfg(dict(zip(JOINT_NAMES,data['body_joints'][index,frame])))
                        root=data['poses'][frame]
                        R=Rotation.from_quat(root[[1,2,3,0]]).as_matrix()
                        for node,prop in channels:
                            if not node.startswith('/penetration/') or prop!='position':continue
                            name=node.rsplit('/',1)[1]
                            actual=root[4:]+R@body.get_transform(name)[:3,3]
                            np.testing.assert_allclose(value(node,'position',index,frame),actual,atol=1e-6)
                            depth=max(0,min(np.asarray(meta['PLATFORM_DIMENSIONS'])/2-abs(actual-np.asarray(meta['PLATFORM_POSITION']))))
                            fraction=np.clip(depth/.05,0,1)
                            color=[np.floor(255*fraction),np.floor(255*(1-fraction)) if depth>0 else 200,0]
                            np.testing.assert_allclose(value(node,'color',index,frame),color,atol=1)
                            radius=.012+.02*fraction if depth>0 else .007
                            self.assertAlmostEqual(value(node,'scale',index,frame)[0],radius/.007,places=5)

    def test_selected_branch_kinematics_and_gradients(self):
        import torch
        import pytorch_kinematics as pk
        from .task_augmentation import SelectedChain
        torch.set_num_threads(1)
        urdf=(DATA/'g1_29dof.urdf').read_bytes()
        whole=pk.build_chain_from_urdf(urdf)
        names={'left_rubber_hand','right_rubber_hand','left_shoulder_pitch_link','right_elbow_link','left_ankle_roll_link','right_ankle_roll_link'}
        selected=SelectedChain(whole,urdf,names)
        torch.manual_seed(4)
        q=torch.randn(7,29,requires_grad=True)
        values={name:q[:,i] for i,name in enumerate(JOINT_NAMES)}
        actual=whole.forward_kinematics(values)
        other=selected.forward_kinematics(values)
        loss1=loss2=0
        for name in names:
            matrix=actual[name].get_matrix();candidate=other[name].get_matrix()
            torch.testing.assert_close(matrix,candidate)
            weights=torch.randn_like(matrix)
            loss1=loss1+(matrix*weights).sum();loss2=loss2+(candidate*weights).sum()
        torch.testing.assert_close(torch.autograd.grad(loss1,q)[0],torch.autograd.grad(loss2,q)[0],atol=4e-6,rtol=1e-5)


if __name__=='__main__':unittest.main()
