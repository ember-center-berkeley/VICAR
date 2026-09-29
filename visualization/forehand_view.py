"""Local Viser X/Y/Z controls for the same forehand grid served on the website."""
import time
import numpy as np
import viser
from .data import ROOT, Motion
from .export_forehand import make_scene
from .forehand import ACTIVE_NAMES, DISPLAY_LIFT, DISPLAY_FPS


def view_forehand(host='127.0.0.1', port=8080):
    base = Motion.load(ROOT / 'motions/forehand-reference.npz')
    with np.load(ROOT / 'motions/forehand-grid.npz', allow_pickle=False) as data:
        shifts, arms, targets = data['shifts'], data['arms'], data['targets']
    server = viser.ViserServer(host=host, port=port)
    _, robot, root, marker, q, _ = make_scene(server, base)
    joint_ids = [robot.get_actuated_joint_names().index(name) for name in ACTIVE_NAMES]
    server.gui.add_markdown('## Forehand contact augmentation\n729 optimized motions from `augment_serves_forehand_g1.py`.')
    x = server.gui.add_slider('X shift (m)', min=-.12, max=-.04, step=.01, initial_value=-.08)
    y = server.gui.add_slider('Y shift (m)', min=-.04, max=.04, step=.01, initial_value=0.)
    z = server.gui.add_slider('Z shift (m)', min=-.04, max=.04, step=.01, initial_value=0.)
    playing = server.gui.add_checkbox('Play', initial_value=False)
    frame = server.gui.add_slider('Frame', min=0, max=len(q)-1, step=1, initial_value=0)
    speed = server.gui.add_slider('Speed', min=.25, max=2., step=.25, initial_value=1.)
    deadline, previous = time.monotonic(), None
    try:
        while True:
            if playing.value and time.monotonic() >= deadline:
                frame.value = (frame.value + 1) % len(q)
                deadline = time.monotonic() + 1 / (DISPLAY_FPS * speed.value)
            index = int(np.argmin(np.linalg.norm(shifts - [x.value, y.value, z.value], axis=1)))
            current = (index, frame.value)
            if previous != current:
                pose = q[frame.value].copy()
                pose[joint_ids] = arms[index, frame.value]
                with server.atomic():
                    root.position = base.positions[frame.value] + [0, 0, DISPLAY_LIFT]
                    root.wxyz = base.wxyz[frame.value]
                    robot.update_cfg(pose)
                    marker.position = targets[index] + [0, 0, DISPLAY_LIFT]
                previous = current
            time.sleep(.005)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
