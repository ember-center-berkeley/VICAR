"""Render the supplied ladder scene as a white homepage hero loop.

Run in the website's Viser environment, then connect a browser to port 8097.
Use --preview to check five poses before rendering the full 605-frame motion.
Encode at the source 50 fps with H.264 CRF 22 and MP4 faststart.
"""
from pathlib import Path
import argparse
import json
import sys
import time

import numpy as np
from PIL import Image
import trimesh
import viser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from visualization.ladder import LadderScene, load_ladder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8097)
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'complete').unlink(missing_ok=True)

    add_mesh = viser.SceneApi.add_mesh_trimesh

    def smooth_robot(api, name, mesh, **kwargs):
        if not name.startswith('/robot/'):
            return add_mesh(api, name, mesh, **kwargs)
        smooth = trimesh.graph.smooth_shade(mesh, angle=np.deg2rad(40), facet_minarea=None)
        smooth.metadata.pop('original_components', None)
        return api.add_glb(name, glb_data=smooth.export(file_type='glb', include_normals=True), **kwargs)

    viser.SceneApi.add_mesh_trimesh = smooth_robot
    server = viser.ViserServer(host='127.0.0.1', port=args.port)
    data = load_ladder()
    scene = LadderScene(server, data)
    for name in ['/ground_plane', '/floor', '/paths']:
        server.scene._handle_from_node_name[name].visible = False
    # Preserve the package's marker locations; match the other hero's red dots.
    for contact in scene.meta['visual_contacts']:
        server.scene._handle_from_node_name[contact['node']].color = (235, 47, 61)
    server.scene.add_grid('/hero_floor', width=20, height=20, plane='xy', cell_size=.25,
                          section_size=1, cell_thickness=.45, section_thickness=.8,
                          cell_color=(225, 230, 237), section_color=(212, 220, 230),
                          plane_color=(247, 249, 252), plane_opacity=1, shadow_opacity=.12,
                          position=(0, 0, -.005))
    server.scene.set_background_image(np.full((16, 16, 3), 255, dtype=np.uint8))

    # Rear-oblique view with the full climb in the right third, beside the title.
    look = np.array([-.986, .610, 1.10])
    position = look + [-2., -5.2, 1.]
    fov = .54
    server.initial_camera.position = position
    server.initial_camera.look_at = look
    server.initial_camera.up = (0, 0, 1)
    server.initial_camera.fov = fov
    print('Waiting for rendering browser', flush=True)
    try:
        while not server.get_clients():
            time.sleep(.1)
        client = next(iter(server.get_clients().values()))
        client.camera.up_direction = (0, 0, 1)
        client.camera.position = position
        client.camera.look_at = look
        client.camera.fov = fov
        time.sleep(2)
        frames = [0, 150, 300, 450, 604] if args.preview else range(scene.T)
        for frame in frames:
            scene.update(frame, 0)
            raw = client.get_render(width=1920, height=1080, position=position,
                                    wxyz=client.camera.wxyz, fov=fov, transport_format='png', timeout=60)
            Image.fromarray(raw).convert('RGB').save(args.output / f'frame-{frame:04d}.png')
            if frame % 50 == 0 or args.preview:
                print(f'Rendered {frame}/{scene.T - 1}', flush=True)
        metadata = dict(task='ladder-climbing', variant=0, frames=scene.T, fps=scene.meta['fps'],
                        source=scene.meta['source'], reference=scene.meta['reference'],
                        archive_sha256=scene.meta['archive_sha256'],
                        camera=dict(position=position.tolist(), look_at=look.tolist(), fov=fov),
                        size=[1920, 1080], robot='visualization/ladder_scene/main.urdf',
                        ladderOffset=scene.meta['ladder_offset'], anchorOffset=scene.meta['anchor_offset'],
                        contactDotColor=[235, 47, 61], contactDotRadius=.025,
                        contactDots=scene.meta['visual_contacts'],
                        contactNote='Package reference guides; locations unchanged, recolored red for the hero.',
                        motion='Full reference motion at original speed; no pose or trajectory changes')
        (args.output / 'render.json').write_text(json.dumps(metadata, indent=2) + '\n')
        (args.output / 'complete').touch()
    finally:
        server.stop()


if __name__ == '__main__':
    main()
