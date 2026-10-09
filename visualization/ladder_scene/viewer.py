"""Unmodified climbing_short_fs:v0 reference with archived 18 cm rung geometry."""
from pathlib import Path
import json,time,ast,argparse
import numpy as np
import yaml,viser,yourdfpy
from viser.extras import ViserUrdf
parser=argparse.ArgumentParser(description='Self-contained ladder reference motion viewer')
parser.add_argument('--host',default='127.0.0.1')
parser.add_argument('--port',type=int,default=8094)
args=parser.parse_args()
D=Path(__file__).resolve().parent
a=np.load(D/'motion.npz'); mapping=json.loads((D/'mapping.json').read_text())
fps=float(a['fps'][0]); n=len(a['joint_pos'])
robot=yourdfpy.URDF.load(D/'main.urdf',filename_handler=lambda fname:str(D/fname.replace('package://unitree_description/','')))
server=viser.ViserServer(host=args.host,port=args.port)
server.scene.set_up_direction('+z')
server.initial_camera.position=(-1.8,-3.0,2.0)
server.initial_camera.look_at=(.4,0,1.1)
floor=server.scene.add_grid('/floor',width=6,height=6,cell_size=.1,section_size=1,position=(0,0,.0005),visible=False)
server.scene.add_mesh_simple('/ground_plane',vertices=np.array([[-3,-3,0],[3,-3,0],[3,3,0],[-3,3,0]],dtype=np.float32),faces=np.array([[0,1,2],[0,2,3]],dtype=np.uint32),color=(210,213,216),side='double')
root=server.scene.add_frame('/robot',show_axes=False)
body=ViserUrdf(server,robot,root_node_name='/robot')
cfg=yaml.safe_load((D/'scene.yaml').read_text())['env']['scene']
STEP_RAISE_M=0.03
ladder=server.scene.add_frame('/ladder',show_axes=False,position=(.03,0,STEP_RAISE_M),visible=False)
reconstructed=server.scene.add_frame('/reconstructed_ladder',show_axes=False,position=(.03,0,0))
server.scene.add_glb('/reconstructed_ladder/asset',(D/'reconstruction/ladder_reconstructed.glb').read_bytes())
for key,v in cfg.items():
 if key.startswith(('stair_lane_0','stair_connector')):
  pos=list(v['init_state']['pos']);pos[1]=0. if key.startswith('stair_lane_0') else pos[1]
  server.scene.add_box('/ladder/'+key,dimensions=tuple(v['spawn']['size']),position=tuple(pos),wxyz=tuple(v['init_state']['rot']),color=(180,160,140))
# Extract only literal generator constants; never execute its optimizer on import.
constants={}
for node in ast.parse((D/'generator_source_snapshot.py').read_text()).body:
 if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
  try:constants[node.targets[0].id]=ast.literal_eval(node.value)
  except (ValueError,TypeError):pass
preview=server.scene.add_frame('/generator_steps',show_axes=False,visible=False,position=(.03,0,STEP_RAISE_M))
for stair in range(1,constants['N_STAIRS']+1):
 server.scene.add_box(f'/generator_steps/step_{stair}',dimensions=(constants['STAIR_TREAD'],constants['STAIR_DEPTH'],.05),position=(.3+(stair-.5)*constants['STAIR_TREAD'],0,.3*stair),color=(180,160,140))
anchors=server.scene.add_frame('/anchors',show_axes=False,position=(0.04,0.0,-0.02))
for prefix,label,color in [('LEFT_FEET','left foot',(50,200,50)),('RIGHT_FEET','right foot',(200,50,50)),('LEFT_HAND','left hand',(50,100,255)),('RIGHT_HAND','right hand',(200,50,255))]:
 for ci,(_,_,stair) in enumerate(constants[prefix+'_CONTACTS']):
  # Match the generator's displayed anchor helper exactly (not its solver offsets).
  pos=np.array([.3+(stair-1)*constants['STAIR_TREAD'],constants[prefix+'_Y'],.3*stair+.07])
  if stair==0:pos[[0,2]]=[0,.03]
  server.scene.add_icosphere(f'/anchors/{prefix}_{ci}',radius=.025,color=color,position=pos)
paths=[]
for name,color in [('pelvis',(238,179,46)),('left_ankle_roll_link',(70,170,245)),('right_ankle_roll_link',(68,209,138))]:
 idx=mapping['body_names'].index(name);p=a['body_pos_w'][:,idx]
 paths.append(server.scene.add_line_segments('/paths/'+name,points=np.stack([p[:-1],p[1:]],axis=1),colors=color,line_width=2,visible=False))
server.gui.add_markdown('## Ladder reference\n`climbing_short_fs:v0` · 50 Hz\n\nVideo-reconstructed A-frame ladder; step tops shifted **+3 cm X, +3 cm Z** from the original RL scene. All reference markers: **+4 cm X, -2 cm Z** from generator positions.\n\n**Generator debug anchors:** left foot green, right foot red, left hand blue, right hand purple. Only contact reference points are shown. These are script guides, not measured contacts.')
layout=server.gui.add_dropdown('Step layout',options=('Reconstructed ladder','RL 18 cm rungs','Generator preview slabs'),initial_value='Reconstructed ladder')
show_anchors=server.gui.add_checkbox('Show generator anchors',initial_value=True)
show_floor=server.gui.add_checkbox('Show floor grid',initial_value=False)
play=server.gui.add_checkbox('playing',initial_value=False)
frame=server.gui.add_slider('timestep',min=0,max=n-1,step=1,initial_value=0)
speed=server.gui.add_slider('Speed',min=.1,max=2,step=.1,initial_value=1)
clock=server.gui.add_text('Time',initial_value='',disabled=True)
show_ladder=server.gui.add_checkbox('Show steps',initial_value=True)
show_paths=server.gui.add_checkbox('Show reference paths',initial_value=False)
restart=server.gui.add_button('Restart')
state={'frame':0.}
@frame.on_update
def scrub(event):
 if event.client_id is not None:state['frame']=float(frame.value)
@restart.on_click
def reset(_):state['frame']=0.
@show_ladder.on_update
def set_ladder(_):
 reconstructed.visible=show_ladder.value and layout.value=='Reconstructed ladder'
 ladder.visible=show_ladder.value and layout.value=='RL 18 cm rungs'
 preview.visible=show_ladder.value and layout.value=='Generator preview slabs'
@layout.on_update
def set_layout(event):set_ladder(event)
@show_anchors.on_update
def set_anchors(_):anchors.visible=show_anchors.value
@show_floor.on_update
def set_floor(_):floor.visible=show_floor.value
@show_paths.on_update
def set_paths(_):
 for p in paths:p.visible=show_paths.value
print(f'VISER_READY http://{args.host}:{args.port}',flush=True)
last=time.monotonic()
while True:
 now=time.monotonic()
 if play.value:state['frame']=(state['frame']+(now-last)*fps*speed.value)%n
 last=now;i=int(state['frame'])
 with server.atomic():
  root.position=a['body_pos_w'][i,0];root.wxyz=a['body_quat_w'][i,0]
  body.update_cfg(dict(zip(mapping['joint_names'],a['joint_pos'][i])))
  frame.value=i;clock.value=f'{i/fps:.2f} / {(n-1)/fps:.2f} s'
 time.sleep(1/fps)
