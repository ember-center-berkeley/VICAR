"""Shared ground reference and rigid carrying for under-table pickup variants.

The source motion/URDF is read-only. See docs/UNDER_TABLE_OBJECT_PLACEMENT.ipynb
for the derivation, the exact variant-110 offset and executable handoff checks.
"""
import numpy as np
from scipy.spatial.transform import Rotation

OBJECT_DIMENSIONS = np.array([0.04, 0.04, 0.25])
SOURCE_LOCAL_OFFSET = np.array([-0.08, -0.01, 0.06])
WORLD_PLACEMENT_SHIFT = np.array([0.0, -0.04, 0.0])
TABLE_DISPLAY_SHIFT = np.array([0.0, 0.0, -0.05])


def under_table_object_motion(data, *, reference_original_z=None):
    """Return dimensions, [N,T,3] centers, [N,T,4] wxyz, and metadata.

    Apply the world shift once at placement, then solve a constant contact-frame
    offset separately for each variant. A single world-Z correction grounds only
    the lowest original pickup position and preserves all height differences.
    When processing a subset, pass reference_original_z from the full bank;
    never recalibrate the ground reference when switching the selected variant.
    The object is upright before PICK_TIME and uses the original wrist rotation
    from PICK_TIME onward. No blending,
    later floor clamping, robot changes or contact re-optimization is performed.
    """
    pick = int(data['metadata']['PICK_TIME'])
    hand = np.asarray(data['world_left_rubber_hand'], dtype=np.float64)
    rotation = np.asarray(data['rotation_left_rubber_hand'], dtype=np.float64)
    count, frames, _ = hand.shape
    if not 0 < pick < frames:
        raise ValueError('Pickup must be inside the motion.')

    # Reconstruct the ORIGINAL visual center, never an already shifted export.
    # Match the prior website/RL float32 placement before applying the new shift.
    original = (hand[:, pick] + rotation[:, pick] @ SOURCE_LOCAL_OFFSET).astype(np.float32).astype(np.float64)
    if reference_original_z is None:
        reference_original_z = float(original[:, 2].min())
    height_shift = OBJECT_DIMENSIONS[2] / 2 - reference_original_z
    placement = original + WORLD_PLACEMENT_SHIFT
    placement[:, 2] += height_shift
    # solve() also handles tiny non-orthogonality in stored float32 FK matrices.
    offsets = np.linalg.solve(rotation[:, pick], (placement - hand[:, pick])[..., None])[..., 0]
    positions = hand + np.einsum('ntij,nj->nti', rotation, offsets)
    positions[:, :pick] = placement[:, None]
    quaternions = Rotation.from_matrix(rotation.reshape(-1, 3, 3)).as_quat()[:, [3, 0, 1, 2]].reshape(count, frames, 4)
    quaternions[:, :pick] = [1, 0, 0, 0]
    presentation = dict(
        dimensions=OBJECT_DIMENSIONS.tolist(), groundZ=0, pickFrame=pick,
        pickTimeSeconds=pick / data['metadata']['fps'],
        attachedReferenceLink='left_rubber_hand',
        sourceLocalOffset=SOURCE_LOCAL_OFFSET.tolist(),
        worldPlacementShift=WORLD_PLACEMENT_SHIFT.tolist(),
        groundReferenceOriginalZ=reference_original_z, worldHeightShift=height_shift,
        groundingPolicy='One world-Z correction from the full-bank lowest pickup center; preserve inter-variant height differences',
        originalPlacement=original.tolist(), initialPosition=placement.tolist(),
        localOffsets=offsets.tolist(), tableDisplayShift=TABLE_DISPLAY_SHIFT.tolist(),
        beforePickup='Stationary; identity wxyz [1,0,0,0]; only the lowest pickup placement has its bottom face on z=0',
        fromPickup='Fixed per-variant contact-frame offset and unchanged wrist rotation',
        shiftScope='World -Y shift at placement only; offset rotates with the wrist after pickup',
        note='Display edit for all variants; robot/contact solve unchanged; later floor penetration is not clamped',
    )
    return OBJECT_DIMENSIONS.copy(), positions.astype(np.float32), quaternions.astype(np.float32), presentation
