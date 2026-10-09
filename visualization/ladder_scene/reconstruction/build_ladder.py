"""Video-inspired fixed A-frame ladder, constrained to the existing six tread tops."""
from pathlib import Path
import json
import numpy as np
import trimesh
import yaml
D=Path(__file__).resolve().parent
C=yaml.safe_load((D.parent/'scene.yaml').read_text())['env']['scene']
ORANGE=(182,78,39,255); SILVER=(182,188,190,255); EDGE=(116,126,130,255)
YELLOW=(218,220,35,255); RUBBER=(37,39,35,255); BOLT=(205,210,213,255)
scene=trimesh.Scene(); parts=[]
def box(name,size,center,color,transform=None):
 m=trimesh.creation.box(extents=size)
 if transform is None:m.apply_translation(center)
 else:m.apply_transform(transform)
 m.visual.face_colors=color
 scene.add_geometry(m,node_name=name,geom_name=name)
 parts.append({'name':name,'size':list(size),'center':list(m.centroid)})
 return m

def beam(name,a,b,width,depth,color):
 a=np.asarray(a,float);b=np.asarray(b,float);axis=b-a;length=np.linalg.norm(axis);axis/=length
 x=np.cross([0,1,0],axis);x/=np.linalg.norm(x);y=np.cross(axis,x)
 T=np.eye(4);T[:3,:3]=np.column_stack([x,y,axis]);T[:3,3]=(a+b)/2
 return box(name,[width,depth,length],None,color,T)

def bolt(name,center):
 m=trimesh.creation.icosphere(subdivisions=1,radius=.004)
 m.apply_translation(center);m.visual.face_colors=BOLT
 scene.add_geometry(m,node_name=name,geom_name=name)

tops=[]
for i in range(1,7):
 c=C[f'stair_lane_0_step_{i}'];old_size=np.array(c['spawn']['size']);old_center=np.array(c['init_state']['pos'])
 assert np.allclose(c['init_state']['rot'],[1,0,0,0])
 top=old_center[2]+old_size[2]/2+.03
 center=[old_center[0],0,top]
 thickness=.035 if i<6 else .065
 size=[old_size[0],old_size[1],thickness]
 m=box(f'tread_{i}',size,[center[0],0,top-thickness/2],SILVER if i<6 else YELLOW)
 expected=np.array([[center[0]-size[0]/2,-size[1]/2,top],[center[0]+size[0]/2,size[1]/2,top]])
 assert np.allclose(m.bounds[0,:2],expected[0,:2],atol=1e-10)
 assert np.allclose(m.bounds[1],expected[1],atol=1e-10)
 tops.append({'step':i,'top_center_world_m':center,'top_size_xy_m':size[:2], 'thickness_m':thickness,'top_bounds_xy_m':expected[:,:2].tolist(),'old_top_center_world_m':[old_center[0],0,old_center[2]+old_size[2]/2+.03]})
 # Flush inlaid tread stripes never extend above or beyond the preserved top surface.
 if i<6:
  for j,dx in enumerate(np.linspace(-size[0]/2+.007,size[0]/2-.007,9)):
   box(f'tread_{i}_groove_{j}',[.0014,size[1]-.012,.0003],[center[0]+dx,0,top-.00015],EDGE)
 else:
  for j,dx in enumerate([-.027,0,.027]):
   box(f'cap_inlay_{j}',[.009,size[1]-.04,.0003],[center[0]+dx,0,top-.00015],(162,166,28,255))

# Rails follow tread edges; the rear leg spread is estimated from the video.
def fx(z):return .348+(z-.33)*(.076/.30)
def fy(z):return .55/2+.019-(z-.33)*(.025/.30)
def rx(z):return 1.48+(.753-1.48)*(z/1.80)
for side,sgn in [('left',1),('right',-1)]:
 front_a=[fx(.025),sgn*fy(.025),.025];front_b=[fx(1.80),sgn*fy(1.80),1.80]
 rear_a=[rx(.025),sgn*fy(.025),.025];rear_b=[rx(1.80),sgn*fy(1.80),1.80]
 beam(f'{side}_front_fiberglass_rail',front_a,front_b,.066,.027,ORANGE)
 beam(f'{side}_rear_fiberglass_rail',rear_a,rear_b,.060,.027,ORANGE)
 for leg,fun in [('front',fx),('rear',rx)]:
  box(f'{side}_{leg}_yellow_boot',[.088,.066,.085],[fun(.047),sgn*fy(.047),.047],YELLOW)
  box(f'{side}_{leg}_rubber_sole',[.093,.071,.007],[fun(.047),sgn*fy(.047),.0035],RUBBER)
 # Folding spreader, modeled fixed in the open configuration.
 z=.88;y=sgn*(fy(z)+.024)
 beam(f'{side}_spreader',[fx(z),y,z],[rx(z),y,z],.030,.008,SILVER)
 for x in [fx(z),rx(z),(fx(z)+rx(z))/2]:bolt(f'{side}_spreader_bolt_{x:.3f}',[x,y+sgn*.007,z])
 # Under-tread supports and visible rivets.
 for t in tops[:-1]:
  x,_,z=t['top_center_world_m'];y=sgn*(t['top_size_xy_m'][1]/2+.012)
  beam(f'{side}_tread_{t["step"]}_support',[x+.025,y,z-.035],[fx(z-.13),sgn*fy(z-.13),z-.13],.014,.008,SILVER)
  bolt(f'{side}_tread_{t["step"]}_rivet',[fx(z-.045),sgn*(fy(z-.045)+.017),z-.045])
 # White safety-label panels on outward rail sides, below tread top heights.
 for j,z in enumerate([.48,1.22,1.52]):
  box(f'{side}_safety_label_{j}',[.044,.0008,.115],[fx(z),sgn*(fy(z)+.014),z],(225,221,207,255))
  for k in range(4):
   box(f'{side}_label_print_{j}_{k}',[.030,.001,.002],[fx(z),sgn*(fy(z)+.0146),z+.026-k*.014],(86,82,74,255))
for i,z in enumerate([.25,.55,.85,1.15,1.45]):
 box(f'rear_cross_brace_{i}',[.026,2*fy(z),.030],[rx(z),0,z],SILVER)
# Hinge hardware below the cap (cap is the sixth fixed contact surface).
for sgn in [-1,1]:
 box(f'cap_hinge_{sgn}',[.075,.012,.045],[.741,sgn*.168,1.773],EDGE)
 bolt(f'cap_hinge_bolt_{sgn}',[.741,sgn*.179,1.777])
scene.export(str(D/'ladder_reconstructed.glb'))
manifest={'source_video':'/home/dkalaria/.agentsdock/files/file_4418407f19c841a0/Climbing.mp4','kind':'fixed visual reconstruction; geometry inferred from monocular video','step_top_constraint':'Exact existing RL rung top positions and XY extents including +0.03 m display raise; horizontal faces unchanged','steps':tops,'estimated_dimensions':{'silver_tread_thickness_m':.035,'yellow_cap_thickness_m':.065,'rear_foot_x_m':1.48},'validation':{'six_top_faces_match':True,'max_top_position_error_m':0.0},'mesh_count':len(scene.geometry)}
(D/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
