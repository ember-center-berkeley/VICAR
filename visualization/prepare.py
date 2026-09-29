"""Import the verified TT_PLayer assets and prepare a smaller visual-only G1."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
import trimesh
from .data import ROOT, check_file, import_motion, write_catalog


def prepare_robot(source, with_hands=False):
    original = source / ('robots/g1_29dof_with_hand.urdf' if with_hands else 'g1_29dof.urdf')
    tree = ET.parse(original)
    out = ROOT / ('robot-hands' if with_hands else 'robot')
    (out / 'meshes').mkdir(parents=True, exist_ok=True)
    # This model is for visualization only. Preserve every joint/origin/axis;
    # omit collision/inertial data, including non-standard capsule geometry.
    for link in tree.findall('link'):
        for element in list(link):
            if element.tag in ('collision', 'inertial'):
                link.remove(element)
    mujoco = tree.find('mujoco')
    if mujoco is not None:
        tree.getroot().remove(mujoco)
    records = []
    for element in tree.findall('.//mesh'):
        name = Path(element.attrib['filename']).name
        mesh_path = check_file(source / 'robots' / 'meshes' / name)
        destination = out / 'meshes' / (Path(name).stem + '.ply')
        mesh = trimesh.load_mesh(mesh_path, process=True)
        before = len(mesh.faces)
        if before > 1600:
            mesh = mesh.simplify_quadric_decimation(face_count=1600)
        mesh.export(destination)
        element.set('filename', f'meshes/{destination.name}')
        records.append({'source': f'robots/meshes/{name}',
                        'sha256': hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
                        'faces_before': before, 'faces_after': len(mesh.faces)})
    ET.indent(tree)
    tree.write(out / 'g1.urdf', encoding='unicode', xml_declaration=True)
    (out / 'provenance.json').write_text(json.dumps({
        'urdf_source': str(original.relative_to(source)), 'urdf_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
        'processing': 'Visual meshes simplified toward a 1600-triangle target; constrained meshes retain more faces (see per-mesh counts). Joint geometry unchanged. Collision and inertial elements removed.',
        'meshes': records}, indent=2) + '\n')
    shutil.copyfile(source / 'IsaacLab/docs/licenses/assets/unitree-license.txt', out / 'LICENSE')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--trust-pickle', action='store_true')
    parser.add_argument('--robot-hands-only', action='store_true', help='Prepare the source forehand hand model without replacing the motion catalog')
    parser.add_argument('--replace-catalog', action='store_true', help='Recreate the catalog from tasks.json, replacing later manual imports')
    args = parser.parse_args()
    if args.robot_hands_only:
        prepare_robot(args.source_root.resolve(), with_hands=True)
        return
    if (ROOT / 'catalog.json').exists() and not args.replace_catalog:
        parser.error('catalog.json already exists. Use --replace-catalog to explicitly rebuild the audited imports.')
    source = args.source_root.resolve()
    prepare_robot(source)
    catalog = json.loads((ROOT / 'tasks.json').read_text())
    for task in catalog['tasks']:
        task['variants'] = []
        for candidate in task['imports']:
            path = source / candidate['source']
            if not path.exists():
                continue
            # Each import is an explicit, audited mapping, never a filename glob.
            motion = import_motion(path, candidate['fps'], candidate['source'], args.trust_pickle)
            motion.metadata['source_revision'] = catalog['source_revision']
            motion.metadata['stage'] = candidate['stage']
            motion.metadata['fps_basis'] = candidate['fps_basis']
            file = f"motions/{task['id']}-{candidate['id']}.npz"
            motion.save(ROOT / file)
            task['variants'].append({**candidate, 'file': file})
            print(f"{task['id']}/{candidate['id']}: {len(motion.joints)} frames at {motion.fps:g} fps")
    write_catalog(catalog)


if __name__ == '__main__':
    main()
