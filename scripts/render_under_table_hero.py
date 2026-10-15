"""Render the under-table Viser scene for the homepage hero.

Run with the website's Viser environment, then connect a browser to port 8097.
Use --preview to inspect framing before rendering all 385 source frames. Encode
frames with ffmpeg at 1000/33 fps, H.264 CRF 22, yuv420p and +faststart.
"""
from pathlib import Path
import argparse,json,sys,time
import numpy as np
from PIL import Image
import viser
import yourdfpy,trimesh

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from visualization.export_tasks import load_task,task_scene

HERO_TABLE_OFFSET = np.array([0.0, 0.0, -0.03])

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--port',type=int,default=8097)
    ap.add_argument('--preview',action='store_true')
    ap.add_argument('--robot-urdf',type=Path,help='Optional full-resolution matching robot URDF for rendering')
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'complete').unlink(missing_ok=True)
    if args.robot_urdf:
        load=yourdfpy.URDF.load
        visual_path=ROOT/'visualization/robot-hands/g1_under_table.urdf'
        reduced=load(visual_path,load_meshes=False)
        full=load(args.robot_urdf,load_meshes=True,load_collision_meshes=False,build_collision_scene_graph=False,
            filename_handler=lambda fname:str(args.robot_urdf.resolve().parent/fname))
        assert reduced.actuated_joint_names==full.actuated_joint_names
        for name in reduced.link_map:
            np.testing.assert_allclose(reduced.get_transform(name),full.get_transform(name),atol=1e-9)
        def load_visual(path,*a,**kw):
            return full if Path(path).resolve()==visual_path.resolve() else load(path,*a,**kw)
        yourdfpy.URDF.load=staticmethod(load_visual)
    add_mesh=viser.SceneApi.add_mesh_trimesh
    def smooth_robot(api,name,mesh,**kw):
        if not name.startswith('/base_new/'):return add_mesh(api,name,mesh,**kw)
        smooth=trimesh.graph.smooth_shade(mesh,angle=np.deg2rad(40),facet_minarea=None)
        smooth.metadata.pop('original_components',None)
        return api.add_glb(name,glb_data=smooth.export(file_type='glb',include_normals=True),**kw)
    viser.SceneApi.add_mesh_trimesh=smooth_robot
    server=viser.ViserServer(host='127.0.0.1',port=args.port)
    data=load_task('under-table-pickup');scene=task_scene(server,'under-table-pickup',data)
    # Lower both table layers another 3 cm for the hero composition.
    for name in ['/table_pointcloud','/table_voxels']:
        handle=server.scene._handle_from_node_name[name]
        handle.position=np.asarray(handle.position)+HERO_TABLE_OFFSET
    # Hide debugging geometry and trajectory guides for the background clip.
    hidden=['/Ground','/collision','/camera_pose','/right_anchor','/pick_point','/hit_box','/hit_box_mesh','/penetration','/traj_left_hand','/traj_right_hand']
    for name,h in server.scene._handle_from_node_name.items():
        if any(name==p or name.startswith(p+'/') for p in hidden):h.visible=False
    server.scene.add_grid('/hero_floor',width=20,height=20,plane='xy',cell_size=.25,section_size=1,
        cell_thickness=.45,section_thickness=.8,cell_color=(225,230,237),section_color=(212,220,230),
        plane_color=(247,249,252),plane_opacity=1,shadow_opacity=.12,position=(0,0,-.005))
    server.scene.set_background_image(np.full((16,16,3),255,dtype=np.uint8))
    # Move the look-at point to place the action in the right third, leaving
    # room for the title and the source demonstration card on the left.
    look=np.array([-.85,0,.69]);position=look+[.6,-4.2,.97];fov=.52
    server.initial_camera.position=position;server.initial_camera.look_at=look
    server.initial_camera.up=(0,0,1);server.initial_camera.fov=fov
    print('Waiting for rendering browser',flush=True)
    try:
        while not server.get_clients():time.sleep(.1)
        client=next(iter(server.get_clients().values()))
        client.camera.up_direction=(0,0,1);client.camera.position=position;client.camera.look_at=look;client.camera.fov=fov
        time.sleep(2)
        frames=[0,130,250,384] if args.preview else range(scene.T)
        for frame in frames:
            scene.update(frame,scene.default)
            raw=client.get_render(width=1920,height=1080,position=position,wxyz=client.camera.wxyz,fov=fov,transport_format='png',timeout=60)
            Image.fromarray(raw).convert('RGB').save(args.output/f'frame-{frame:04d}.png')
            if frame%30==0 or args.preview:print(f'Rendered {frame}/{scene.T-1}',flush=True)
        (args.output/'render.json').write_text(json.dumps(dict(task='under-table-pickup',variant=scene.default,frames=scene.T,
            fps=scene.meta['fps'],camera=dict(position=position.tolist(),look_at=look.tolist(),fov=fov),size=[1920,1080],
            sourceTableDisplayShift=scene.object_presentation['tableDisplayShift'],heroTableOffset=HERO_TABLE_OFFSET.tolist(),
            tableDisplayShift=(np.asarray(scene.object_presentation['tableDisplayShift'])+HERO_TABLE_OFFSET).tolist(),
            robot='g1_under_table.urdf',fullResolution=bool(args.robot_urdf)),indent=2)+'\n')
        (args.output/'complete').touch()
    finally:server.stop()
if __name__=='__main__':main()
