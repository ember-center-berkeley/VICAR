"""Build the under-table robot with left Dex3 and a fixed right Unitree hand."""
from pathlib import Path
import argparse
import copy
import os
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DONOR = ROOT / 'visualization/ladder_scene/main.urdf'
HAND_MESH = ROOT / 'visualization/ladder_scene/meshes/g1/right_rubber_hand.STL'


def replace_right_hand(source, donor, mesh_filename, *, collision=False):
    """Remove only the right palm/finger subtree; retain solver helper frames.

    The fixed Unitree hand is named right_unitree_hand to distinguish its CAD
    origin from the existing right_rubber_hand solver contact frame at +0.1915 m.
    Its mounting transform and inertial come from the supplied ladder model.
    """
    tree = copy.deepcopy(source)
    mount = tree.find("joint[@name='right_hand_palm_joint']")
    if mount is None or mount.find('parent').get('link') != 'right_wrist_yaw_link':
        raise ValueError('Expected a right palm fixed to the right wrist yaw link.')
    removed = {mount.find('child').get('link')}
    while True:
        descendants = {j.find('child').get('link') for j in tree.findall('joint')
                       if j.find('parent').get('link') in removed}
        if descendants <= removed:
            break
        removed |= descendants
    for element in list(tree):
        if element.tag == 'link' and element.get('name') in removed:
            tree.remove(element)
        elif element.tag == 'joint' and (element.find('child').get('link') in removed
                                         or element.find('parent').get('link') in removed):
            tree.remove(element)
    new_mount = copy.deepcopy(donor.find("joint[@name='right_hand_palm_joint']"))
    new_mount.find('child').set('link', 'right_unitree_hand')
    hand = copy.deepcopy(donor.find("link[@name='right_rubber_hand']"))
    hand.set('name', 'right_unitree_hand')
    for mesh in hand.findall('.//mesh'):
        mesh.set('filename', mesh_filename)
    if collision:
        contact = ET.SubElement(hand, 'collision')
        ET.SubElement(contact, 'origin', xyz='0 0 0', rpy='0 0 0')
        geometry = ET.SubElement(contact, 'geometry')
        ET.SubElement(geometry, 'mesh', filename=mesh_filename)
    tree.extend([new_mount, hand])
    tree.set('name', 'g1_under_table_left_dex3_right_unitree')
    return tree


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-urdf', type=Path, default=ROOT/'visualization/robot-hands/g1.urdf')
    parser.add_argument('--output', type=Path, default=ROOT/'visualization/robot-hands/g1_under_table.urdf')
    parser.add_argument('--mesh', type=Path, default=HAND_MESH)
    parser.add_argument('--collision', action='store_true', help='Add a mesh collision for the physical RL model.')
    args = parser.parse_args()
    source = ET.parse(args.source_urdf).getroot()
    # Preserve existing mesh references when writing beside another directory.
    for mesh in source.findall('.//mesh'):
        original = (args.source_urdf.parent / mesh.get('filename')).resolve()
        mesh.set('filename', os.path.relpath(original, args.output.parent))
    tree = replace_right_hand(source, ET.parse(DONOR).getroot(),
                              os.path.relpath(args.mesh.resolve(), args.output.parent), collision=args.collision)
    ET.indent(tree, space='  ')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(tree).write(args.output, encoding='utf-8', xml_declaration=True)
    print(f'Wrote {args.output}: left Dex3, fixed right Unitree hand, 36 movable joints.')


if __name__ == '__main__':
    main()
