from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Protocol, Tuple, runtime_checkable

# Opaque handle to a loaded image. Consumers never inspect it - only the
# concrete Canvas that produced it knows its real type (an Img for ImgCanvas,
# a recording stub for a test fake). This is what lets everything above the
# platform layer stay ignorant of cv2/Img.
ImageHandle = Any


@runtime_checkable
class Canvas(Protocol):
    """
    The single seam that keeps cv2/Img out of the rest of ui. Every module in
    ui/graphics, ui/animation, and ui/app depends on this Protocol instead of
    importing Img (or cv2) directly; the concrete ImgCanvas is the only
    ui-side object that actually touches OpenCV pixels and windows.

    Deliberately *stateless*: load_image/blit/show/save each take the frame
    they operate on explicitly, matching how BoardRenderer.render already
    threads a frame through main.py and demo_driver.py. There is no shared
    frame buffer to copy or corrupt, and one concrete Canvas serves both the
    live demo (call show) and headless rendering (skip show, just save).
    """

    def load_image(self, path: Path, size: Optional[Tuple[int, int]] = None,
                   keep_aspect: bool = False) -> ImageHandle: ...

    def blank(self, size: Tuple[int, int], color: Tuple[int, int, int]) -> ImageHandle: ...

    def draw_text(self, frame: ImageHandle, text: str, x: int, y: int,
                  font_scale: float, color: Tuple[int, int, int], thickness: int = 1) -> None: ...

    def blit(self, frame: ImageHandle, image: ImageHandle, x: int, y: int) -> None: ...

    def show(self, frame: ImageHandle, delay_ms: int) -> bool: ...

    def save(self, frame: ImageHandle, path: Path) -> None: ...

    def drain_clicks(self) -> List[Tuple[int, int]]: ...

    def close(self) -> None: ...
