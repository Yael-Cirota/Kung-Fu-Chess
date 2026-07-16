import cv2
import numpy as np

from ui.img import Img


class ImgCanvas:
    """
    The concrete Canvas: the only ui object that turns Canvas calls into
    OpenCV/Img operations - loading pixels, alpha-blitting sprites, driving
    the live window, and writing rendered frames to disk. Consolidates what
    used to be scattered across renderer.py (Img), sprite_loader.py (Img),
    window.py (cv2), and demo_driver.py (cv2.imwrite) into one place.

    The live window is created lazily on the first show() and torn down by
    close(), so a headless run (save only, never show) touches no display at
    all - which is why a single class covers both the interactive demo and
    the offscreen render path.

    It is also the ui's single source of real human input: when the window is
    opened it installs an OpenCV mouse callback that buffers left-button
    clicks (in image-pixel space) for the game loop to drain each frame. This
    keeps cv2's event model - like its pixels and windows - from leaking
    anywhere above the Canvas seam.
    """

    def __init__(self, window_title: str = "Kung-Fu-Chess"):
        self._window_title = window_title
        self._window_open = False
        self._pending_clicks = []

    def load_image(self, path, size=None, keep_aspect=False) -> Img:
        return Img().read(path, size=size, keep_aspect=keep_aspect)

    def blank(self, size, color) -> Img:
        """A solid-color BGR frame of `size` (width, height) - the move-log side panel's canvas."""
        width, height = size
        img = Img()
        img.img = np.zeros((height, width, 3), dtype=np.uint8)
        img.img[:, :] = color
        return img

    def draw_text(self, frame: Img, text, x, y, font_scale, color, thickness=1) -> None:
        frame.put_text(text, x, y, font_scale, color=color, thickness=thickness)

    def blit(self, frame: Img, image: Img, x: int, y: int) -> None:
        image.draw_on(frame, x, y)

    def show(self, frame: Img, delay_ms: int) -> bool:
        """Displays one frame in the live window. Returns False if the user asked to quit (Esc/q)."""
        self._ensure_window()
        cv2.imshow(self._window_title, frame.img)
        key = cv2.waitKey(max(1, delay_ms)) & 0xFF
        return key not in (27, ord("q"))

    def save(self, frame: Img, path) -> None:
        cv2.imwrite(str(path), frame.img)

    def drain_clicks(self):
        """Returns and clears the left-clicks buffered since the last call, as (x, y) image pixels."""
        clicks = self._pending_clicks
        self._pending_clicks = []
        return clicks

    def close(self) -> None:
        if self._window_open:
            cv2.destroyWindow(self._window_title)
            self._window_open = False

    def _ensure_window(self):
        """Creates the auto-sized window and wires the mouse callback on first show.

        WINDOW_AUTOSIZE (the default) is deliberate: clicks arrive in the same
        image-pixel space the board mapper assumes (1:1 with the rendered
        frame). A resizable/scaled window would silently distort on_click.
        """
        if self._window_open:
            return
        cv2.namedWindow(self._window_title)
        cv2.setMouseCallback(self._window_title, self._on_mouse)
        self._window_open = True

    def _on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self._pending_clicks.append((x, y))
