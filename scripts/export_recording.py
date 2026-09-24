"""Small helper for exporting real VICAR trajectories to the static website.

Construct your scene and robot with Viser first. Then pass an update callback
that applies one frame of your actual trajectory to the existing scene handles.
See docs/VISER.md for an example and the hosting limitations.
"""
from pathlib import Path
from typing import Callable
import viser


def export_recording(server: viser.ViserServer, update_frame: Callable[[int], None],
                     frame_count: int, output: str | Path, fps: float = 30.0) -> Path:
    if frame_count < 1 or fps <= 0:
        raise ValueError('frame_count and fps must be positive')
    update_frame(0)
    serializer = server.get_scene_serializer()
    for frame in range(frame_count):
        update_frame(frame)
        serializer.insert_sleep(1.0 / fps)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(serializer.serialize())
    return path
