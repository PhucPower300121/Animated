from __future__ import annotations

from typing import Iterable, List, Sequence
from PIL import Image


def _normalize_durations(durations: Sequence[float] | None, frame_count: int) -> List[int]:
    if frame_count <= 0:
        raise ValueError("Không có frame để lưu")

    if not durations:
        return [100] * frame_count

    values = [max(1, int(d)) for d in durations]
    if len(values) < frame_count:
        values.extend([values[-1]] * (frame_count - len(values)))
    return values[:frame_count]


def _as_rgba(frame: Image.Image) -> Image.Image:
    if frame.mode == "RGBA":
        return frame.copy()
    return frame.convert("RGBA")


def _needs_transparency_preserved(frames: Sequence[Image.Image]) -> bool:
    for frame in frames:
        if frame.mode in ("RGBA", "LA"):
            alpha = frame.getchannel("A")
            if alpha.getextrema()[0] < 255:
                return True
    return False


def save_gif_frames(
    frames: Sequence[Image.Image],
    durations: Sequence[float] | None,
    file_path: str,
    loop: int = 0,
) -> None:
    """Save frames to GIF while preserving transparency when present.

    The caller can pass RGB frames for normal GIFs or RGBA frames for
    transparent GIFs. Pillow will keep the alpha channel when the frames
    are RGBA, which prevents the checkerboard preview background from
    being baked into the exported GIF.
    """
    if not frames:
        raise ValueError("Không có frame để lưu")

    frame_count = len(frames)
    durations = _normalize_durations(durations, frame_count)

    preserve_transparency = _needs_transparency_preserved(frames)
    prepared_frames = [
        _as_rgba(frame) if preserve_transparency else frame.copy()
        for frame in frames
    ]

    first, rest = prepared_frames[0], prepared_frames[1:]
    first.save(
        file_path,
        save_all=True,
        append_images=rest,
        duration=durations,
        loop=loop,
        disposal=2,
        optimize=False,
    )
