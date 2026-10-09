"""Portable Viser scenes for pickup, bimanual manipulation and climbing."""
import argparse
import gzip
import hashlib
import json
import time
import numpy as np
from scipy.spatial.transform import Rotation
import viser
from viser.extras import ViserUrdf
import yourdfpy
from .data import ROOT
from .task_augmentation import DATA_DIR, TASKS

OUTPUT = ROOT.parent / 'assets/augmentation/tasks'


def load_task(key):
    if key=='ladder-climbing':
        from .ladder import load_ladder
        return load_ladder()
    with np.load(DATA_DIR/f'{key}.npz',allow_pickle=False) as file:
        data = dict(file)
    data['metadata'] = json.loads(str(data['metadata']))
    return data


def task_scene(server,key,data):
    if key=='ladder-climbing':
        from .ladder import LadderScene
        return LadderScene(server,data)
    return TaskScene(server,key,data)


def wxyz(matrix):
    shape = matrix.shape[:-2]
    return Rotation.from_matrix(matrix.reshape(-1,3,3)).as_quat()[:,[3,0,1,2]].reshape(*shape,4).astype(np.float32)


def table_geometry(key,data):
    """Display cleanup only; retain the captured geometry and solved motions."""
    points,colors=data['table_pts_world'],data['table_pts_colors']
    vertices,faces=data['table_vox_verts'],data['table_vox_faces']
    if key=='under-table-pickup':
        # The reconstruction contains a detached vertical fragment next to
        # the pickup object: 15 complete voxels at X=.45–.55, Y=.15–.35,
        # Z=.15–.45 m. Bounds lie in empty space around that fragment, below
        # the tabletop and away from the real table support at X>1 m.
        def artifact(p):
            return np.all((p>=[.4,.1,0]) & (p<=[.6,.4,.65]),axis=-1)
        keep=~artifact(points)
        points,colors=points[keep],colors[keep]
        faces=faces[~artifact(vertices[faces].mean(axis=1))]
        used,indices=np.unique(faces,return_inverse=True)
        vertices=vertices[used]
        faces=indices.reshape(-1,3).astype(np.uint32)
    return points,colors,vertices,faces


def bimanual_object_motion(data):
    """Visual pickup and release; leave the source contact solve untouched."""
    meta=data['metadata']
    path=data['object_traj_batch']
    start,end=meta['CONTACT_START_FRAME'],meta['CONTACT_END_FRAME']
    frames=np.arange(path.shape[1])
    dimensions=np.asarray(meta['OBJECT_DIMS'],dtype=float).copy()
    # The source's minimum center height is 15 cm. A 30 cm height rests on
    # the ground while retaining the 30 cm width between the grasping hands.
    dimensions[2]=.3
    half_height=dimensions[2]/2
    positions=path[:,np.clip(frames,start,end)].copy()
    positions[:,:,2]=np.clip(positions[:,:,2]-.2,half_height,2.)

    # Land on the visible voxel tabletop under each box footprint, rather
    # than the differently aligned collision proxy used by the optimizer.
    triangles=data['table_vox_verts'][data['table_vox_faces']]
    lower,upper=triangles.min(axis=1),triangles.max(axis=1)
    tabletop=[]
    for position in positions[:,end]:
        overlaps=np.all((upper[:,:2]>=position[:2]-dimensions[:2]/2)
                        & (lower[:,:2]<=position[:2]+dimensions[:2]/2),axis=1)
        if not overlaps.any():
            raise ValueError('No reconstructed table beneath the box placement.')
        tabletop.append(float(upper[overlaps,2].max()))
    tabletop=np.asarray(tabletop)
    landing=tabletop+half_height
    release=positions[:,end,2].copy()
    if np.any(landing>release+1e-6):
        raise ValueError('Box must be above the tabletop at release.')

    settle_end=min(end+round(.6*meta['fps']),len(frames)-1)
    progress=np.clip((frames-end)/(settle_end-end),0,1)
    # Quintic easing has zero velocity and acceleration at both ends.
    easing=progress**3*(10-15*progress+6*progress**2)
    after=frames>end
    positions[:,after,2]=release[:,None]+(landing-release)[:,None]*easing[after]
    presentation=dict(dimensions=dimensions.tolist(),groundZ=0,
        tabletopZ=tabletop.tolist(),releaseFrame=end,settleEndFrame=settle_end,
        settleSeconds=(settle_end-end)/meta['fps'],easing='quintic smoothstep',
        note='Visual release animation; source contact targets and robot motions are unchanged')
    return dimensions,positions,presentation


class TaskScene:
    def __init__(self,server,key,data):
        self.server,self.key,self.data = server,key,data
        self.meta=data['metadata']
        self.N,self.T,_=data['joints'].shape
        self.default=self.meta['default_index']
        self.channels=[]
        self.values=[]
        self.handles={}
        self.curves=[]
        self.layers=[]
        self.box_nodes=[]
        self.object_presentation=None
        server.scene.reset()
        server.scene.set_up_direction('+z')
        server.scene.world_axes.visible=False
        server.scene.add_grid('/Ground',width=8,height=8,cell_size=.25,section_size=1,
            plane_color=(247,249,252),plane_opacity=1,cell_color=(223,229,238),section_color=(188,200,216))
        self.model=yourdfpy.URDF.load(str(ROOT/'robot-hands/g1.urdf'))
        self.root=server.scene.add_frame('/base_new',show_axes=False)
        self.robot=ViserUrdf(server,self.model,root_node_name='/base_new')
        self.nodes={j.name:h.name for j,h in zip(self.robot._joint_map_values,self.robot._joint_frames)}
        self._manipulation()
        if 'table_pts_world' in data:
            points,colors,vertices,faces=table_geometry(key,data)
            server.scene.add_point_cloud('/table_pointcloud',points=points,colors=colors,point_size=.003)
            server.scene.add_mesh_simple('/table_voxels',vertices=vertices,faces=faces,
                color=(180,140,80),opacity=.5,side='double')
            self.layers.extend([
                dict(id='points',label='Table point cloud',nodes=['/table_pointcloud'],default=True),
                dict(id='voxels',label='Table voxels',nodes=['/table_voxels'],default=True)])
            camera=server.scene.add_camera_frustum('/camera_pose',fov=np.deg2rad(64),aspect=16/9,scale=.3,
                wxyz=wxyz(data['_R0']),position=data['_t0'].reshape(3),color=(255,100,0),visible=False)
            self.layers.append(dict(id='camera',label='Capture camera',nodes=[camera.name],default=False))
        visible=key=='tabletop-right'
        server.scene.add_box('/collision/platform',position=self.meta['PLATFORM_POSITION'],dimensions=self.meta['PLATFORM_DIMENSIONS'],
            color=(255,80,0),opacity=.8 if visible else .2,visible=visible)
        self.layers.append(dict(id='obstacles',label='Collision geometry',nodes=['/collision/platform'],default=visible))
        self.dynamic=np.concatenate(self.values,axis=-1).astype('<f4') if self.values else None
        center=np.mean(data['poses'][:,4:],axis=0)
        look=np.array([center[0]+.35,center[1],.75])
        server.initial_camera.look_at=look
        server.initial_camera.position=look+[2.1,-2.8,1.4]
        if key=='under-table-pickup':
            look[2]=.55
            server.initial_camera.look_at=look
            server.initial_camera.position=look+[1.8,-2.8,.35]
        server.initial_camera.up=(0,0,1)
        server.initial_camera.fov=.67
        self.update(0,self.default)

    def channel(self,handle,property,values):
        width=values.shape[-1]
        self.channels.append(dict(node=handle.name,property=property,width=width,offset=sum(v.shape[-1] for v in self.values)))
        self.values.append(np.asarray(values,dtype=np.float32))
        self.handles[handle.name]=handle

    def curve(self,name,points,color,width=3):
        handle=self.server.scene.add_spline_catmull_rom(name,points=points[self.default],color=color,thickness=width,thickness_units='screen')
        self.curves.append(dict(node=name,points=points))
        self.handles[name]=handle

    def _region(self,targets):
        minimum,maximum=targets.min(axis=0),targets.max(axis=0)
        x0,y0,z0=minimum;x1,y1,z1=maximum
        points=np.array([[x0,y0,z0],[x1,y0,z0],[x0,y1,z0],[x1,y1,z0],[x0,y0,z1],[x1,y0,z1],[x0,y1,z1],[x1,y1,z1]],dtype=np.float32)
        edges=np.array([(0,1),(1,3),(3,2),(2,0),(4,5),(5,7),(7,6),(6,4),(0,4),(1,5),(2,6),(3,7)])
        self.server.scene.add_line_segments('/hit_box',points=points[edges],colors=(0,0,255),thickness=2,thickness_units='screen')
        self.box_nodes.append('/hit_box')
        # Flat grids (bimanual Y) are drawn as their actual plane, without
        # duplicate coincident triangles or invented depth.
        active=np.flatnonzero(maximum-minimum>1e-8)
        if len(active)==3:
            faces=np.array([[0,1,3],[0,3,2],[4,6,7],[4,7,5],[0,4,5],[0,5,1],[2,3,7],[2,7,6],[0,2,6],[0,6,4],[1,5,7],[1,7,3]])
        elif len(active)==2:
            ids=[0,1<<active[0],(1<<active[0])+(1<<active[1]),1<<active[1]]
            faces=np.array([[ids[0],ids[1],ids[2]],[ids[0],ids[2],ids[3]]])
        else:
            faces=None
        if faces is not None:
            self.server.scene.add_mesh_simple('/hit_box_mesh',vertices=points,faces=faces.astype(np.uint32),color=(0,0,255),opacity=.15,side='double')
            self.box_nodes.append('/hit_box_mesh')

    def _manipulation(self):
        d,m=self.data,self.meta
        if self.key=='bimanual-pick-place':
            start,end=m['CONTACT_START_FRAME'],m['CONTACT_END_FRAME']
            path=d['object_traj_batch']
            self.targets=path[:,end]
            self.curve('/traj_object',path[:,start:end],(0,255,0))
            self.curve('/traj_left_hand',path[:,start:end]+[0,.15,0],(0,180,255),2)
            self.curve('/traj_right_hand',path[:,start:end]+[0,-.15,0],(255,80,200),2)
            dimensions,objects,self.object_presentation=bimanual_object_motion(d)
            self.object=self.server.scene.add_box('/object_cuboid',dimensions=tuple(dimensions),color=(255,200,0),opacity=.9)
            self.channel(self.object,'position',objects)
        else:
            pick=m['PICK_TIME']
            side='right' if self.key=='tabletop-right' else 'left'
            hand=f'{side}_rubber_hand'
            path=d[f'pos_{side}_hand_batch']
            self.targets=path[:,pick]
            window=path[:,pick-15:pick+15] if self.key=='under-table-pickup' else path[:,pick:]
            self.curve(f'/traj_{side}_hand',window,(0,255,0))
            frames=np.maximum(np.arange(self.T),pick)
            rotations=d[f'rotation_{hand}'][:,frames]
            offset=np.array([-.08,.01,.06]) if side=='right' else np.array([-.08,-.01,-.03 if self.key=='tabletop-left' else .06])
            position=d[f'world_{hand}'][:,frames]+np.einsum('ntij,j->nti',rotations,offset)
            self.object=self.server.scene.add_box('/object_cuboid',dimensions=(.04,.04,.15),color=(255,200,0),opacity=.9)
            self.channel(self.object,'position',position)
            self.channel(self.object,'wxyz',wxyz(rotations))
            if self.key in ['tabletop-right','under-table-pickup']:
                self._penetration(side)
            if self.key=='under-table-pickup':
                for label,position,radius in [('contact',m['RIGHT_HAND_CONTACT_POINT'],.015),('start',d['pos_right_hand_batch'][0,0],.01),('end',d['pos_right_hand_batch'][0,-1],.01)]:
                    self.server.scene.add_icosphere(f'/right_anchor/{label}',position=position,radius=radius,color=(220,50,50))
                self.layers.append(dict(id='support',label='Supporting-hand anchors',nodes=['/right_anchor'],default=True))
        self._region(self.targets)
        self.marker=self.server.scene.add_icosphere('/pick_point',radius=.005,color=(255,165,0),position=self.targets[self.default])
        self.layers.append(dict(id='paths',label='Contact trajectories',nodes=[c['node'] for c in self.curves],default=True))

    def _penetration(self,side):
        m=self.meta
        center=np.asarray(m['PLATFORM_POSITION'])
        half=np.asarray(m['PLATFORM_DIMENSIONS'])/2
        names=[name.removeprefix('world_') for name in self.data if name.startswith(f'world_{side}_') and 'ankle' not in name]
        nodes=[]
        for name in names:
            position=self.data[f'world_{name}']
            depth=np.maximum((half-np.abs(position-center)).min(axis=-1),0)
            fraction=np.clip(depth/.05,0,1)
            color=np.zeros((*depth.shape,3),dtype=np.float32)
            color[:,:,0]=np.floor(255*fraction)
            color[:,:,1]=np.where(depth>0,np.floor(255*(1-fraction)),200)
            radius=np.where(depth>0,.012+.02*fraction,.007)
            sphere=self.server.scene.add_icosphere(f'/penetration/{name}',radius=.007,color=(0,200,0))
            self.channel(sphere,'position',position)
            self.channel(sphere,'color',color)
            self.channel(sphere,'scale',(radius/.007)[:,:,None])
            nodes.append(sphere.name)
        self.layers.append(dict(id='penetration',label='Contact diagnostics',nodes=nodes,default=True))

    def update(self,frame,index):
        with self.server.atomic():
            pose=self.data['poses'][frame]
            # Source FK normalizes quaternion magnitude. Viser/Three.js assumes
            # unit quaternions, so normalize only the displayed orientation.
            self.root.wxyz=pose[:4]/np.linalg.norm(pose[:4])
            self.root.position=pose[4:]+[0,0,self.meta['lift']]
            self.robot.update_cfg(self.data['joints'][index,frame])
            if self.targets is not None:self.marker.position=self.targets[index]
            for curve in self.curves:self.handles[curve['node']].points=curve['points'][index]
            if self.dynamic is not None:
                values=self.dynamic[index,frame]
                for channel in self.channels:
                    v=values[channel['offset']:channel['offset']+channel['width']]
                    value=float(v[0]) if channel['width']==1 else tuple(v)
                    if channel['property']=='color':value=tuple(int(c) for c in v)
                    setattr(self.handles[channel['node']],channel['property'],value)


def export_task(server,key):
    d=load_task(key)
    m=d['metadata']
    if 'iterations' in m and m['iterations']!=m['source_iterations']:raise ValueError('Refusing to publish a shortened development solve.')
    scene=task_scene(server,key,d)
    N,T,_=d['joints'].shape
    active=m['active_joints']
    names=scene.robot.get_actuated_joint_names()
    quats=np.empty((N,T,len(active),4),dtype='<f4')
    for i,name in enumerate(active):
        joint=scene.model.joint_map[name]
        rotation=Rotation.from_matrix(joint.origin[:3,:3])*Rotation.from_rotvec(d['joints'][:,:,names.index(name)].reshape(-1,1)*joint.axis)
        quats[:,:,i]=rotation.as_quat()[:,[3,0,1,2]].reshape(N,T,4)
    recording=server.get_scene_serializer()
    for frame in range(T):
        scene.update(frame,scene.default)
        recording.insert_sleep(1/m['fps'])
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/f'{key}-base.viser').write_bytes(recording.serialize())
    compressed=gzip.compress(quats.tobytes(),mtime=0)
    # Version the ladder pack so cached rotations from an earlier source
    # cannot be paired with the new scene or joint mapping.
    suffix=f'-{hashlib.sha256(compressed).hexdigest()[:12]}' if key=='ladder-climbing' else ''
    quaternion_file=f'{key}-quaternions{suffix}.bin.gz'
    (OUTPUT/quaternion_file).write_bytes(compressed)
    config=dict(version=3,title=m['label'],frames=T,fps=m['fps'],defaultIndex=scene.default,
        hitFrame=m.get('PICK_TIME',m.get('CONTACT_START_FRAME',0)),
        nodes=[scene.nodes[name] for name in active],owner='',axes=m['axes'],
        quaternions=quaternion_file,quaternionShape=list(quats.shape),
        shifts=d['shifts'].tolist(),displayLift=0,normalizeRootQuaternion=True,boxNodes=scene.box_nodes,
        boxLabel='Contact markers' if key=='ladder-climbing' else 'Show contact region',
        layers=scene.layers,curves=[dict(node=c['node'],points=c['points'].tolist()) for c in scene.curves],
        provenance=dict(m))
    if 'costs' in d:
        config['provenance'].update(cost_min=float(d['costs'].min()),cost_max=float(d['costs'].max()))
    if key=='under-table-pickup':
        config['visualizationEdits']=['Remove detached reconstruction leg beside pickup object from table point cloud and voxel mesh; source geometry and optimization unchanged']
    if scene.object_presentation is not None:
        config['objectPresentation']=scene.object_presentation
    if scene.targets is not None:config.update(targetNode='/pick_point',targets=scene.targets.tolist())
    if scene.dynamic is not None:
        objects=gzip.compress(scene.dynamic.tobytes(),mtime=0)
        suffix=f'-{hashlib.sha256(objects).hexdigest()[:12]}' if key=='bimanual-pick-place' else ''
        object_file=f'{key}-objects{suffix}.bin.gz'
        (OUTPUT/object_file).write_bytes(objects)
        config['dynamic']=dict(file=object_file,frameStride=scene.dynamic.shape[-1],channels=scene.channels)
    (OUTPUT/f'{key}.json').write_text(json.dumps(config,separators=(',',':'))+'\n')
    print(f'Exported {key}: {N} motions, {T} frames, {len(active)} animated joints.',flush=True)


def view_task(key,host='127.0.0.1',port=8080):
    data=load_task(key)
    server=viser.ViserServer(host=host,port=port)
    scene=task_scene(server,key,data)
    server.gui.add_markdown(f"## {key.replace('-',' ').title()}")
    controls=[]
    for axis in 'xyz':
        settings=data['metadata']['axes'][axis]
        values=settings['values']
        if len(values)>1:
            slider=server.gui.add_slider(f'{axis.upper()} shift (m)',min=values[0],max=values[-1],step=settings['step'],initial_value=settings['default'])
            controls.append((slider,values))
        else:
            controls.append((None,values))
    contacts=server.gui.add_checkbox('Show contacts',initial_value=True)
    layer_controls=[(server.gui.add_checkbox(l['label'],initial_value=l['default']),l) for l in scene.layers]
    playing=server.gui.add_checkbox('Play',initial_value=False)
    speed=server.gui.add_slider('Speed',min=.25,max=2,step=.25,initial_value=1)
    frame=server.gui.add_slider('Frame',min=0,max=scene.T-1,step=1,initial_value=0)
    reset=server.gui.add_button('Restart')
    @reset.on_click
    def _(_event):
        frame.value=0
    deadline,previous=time.monotonic(),None
    visibility={}
    try:
        while True:
            if playing.value and time.monotonic()>=deadline:
                frame.value=(frame.value+1)%scene.T
                deadline=time.monotonic()+1/(scene.meta['fps']*speed.value)
            shift=[float(slider.value) if slider else values[0] for slider,values in controls]
            index=int(np.linalg.norm(data['shifts']-shift,axis=1).argmin())
            if previous!=(frame.value,index):
                scene.update(frame.value,index);previous=frame.value,index
            # Global handles are deliberately retained in the scene API; use
            # messages for group visibility just as offline playback does.
            from viser import _messages
            desired={name:contacts.value for name in scene.box_nodes}
            for control,layer in layer_controls:
                for name in layer['nodes']:
                    desired[name]=control.value
            for name,value in desired.items():
                if visibility.get(name)!=value:
                    server._websock_server.queue_message(_messages.SetSceneNodeVisibilityMessage(name=name,visible=value))
            visibility=desired
            time.sleep(.01)
    except KeyboardInterrupt:pass
    finally:server.stop()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task',choices=TASKS)
    args=parser.parse_args()
    server=viser.ViserServer(host='127.0.0.1',port=8098,verbose=False)
    try:
        for key in TASKS:
            if not args.task or key==args.task:export_task(server,key)
    finally:server.stop()


if __name__=='__main__':main()
