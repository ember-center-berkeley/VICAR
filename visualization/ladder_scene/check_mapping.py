from pathlib import Path
import numpy as np, yourdfpy, json
from scipy.spatial.transform import Rotation
from scipy.optimize import linear_sum_assignment
D=Path(__file__).resolve().parent
r=yourdfpy.URDF.load(D/'main.urdf',filename_handler=lambda fname:str(D/fname.replace('package://unitree_description/','')))
a=np.load(D/'motion.npz')
queue=['pelvis']; joints=[]
while queue:
 parent=queue.pop(0)
 for j in r.robot.joints:
  if j.parent==parent:
   if j.type=='fixed':
    # Fixed descendants do not add an articulation depth.
    queue.insert(0,j.child)
   else:
    joints.append(j);queue.append(j.child)
print([j.name for j in joints])
errs=[]; mapping=None
for i in [0,100,250,400,604]:
 r.update_cfg(dict(zip([j.name for j in joints],a['joint_pos'][i])))
 root=Rotation.from_quat(a['body_quat_w'][i,0,[1,2,3,0]])
 ps=np.array([r.get_transform(j.child)[:3,3] for j in joints])
 ps=root.apply(ps)+a['body_pos_w'][i,0]
 distances=np.linalg.norm(ps[:,None,:]-a['body_pos_w'][i,None,1:,:],axis=-1)
 row,col=linear_sum_assignment(distances)
 print(i,float(distances[row,col].max()),col.tolist())
 errs.append(float(distances[row,col].max()))
 if mapping is None:mapping=col
 assert np.array_equal(mapping,col)
assert max(errs)<1e-4,errs
(D/'mapping.json').write_text(json.dumps({'joint_names':[j.name for j in joints],'body_names':['pelvis']+[next(j.child for n,j in enumerate(joints) if mapping[n]==idx) for idx in range(29)],'checked_frames':[0,100,250,400,604],'max_fk_error_m':max(errs)},indent=2))
