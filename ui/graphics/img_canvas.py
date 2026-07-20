import cv2
import numpy as np

from ui.graphics.mouse_input import MouseInput
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

    Raw human input capture is delegated to a MouseInput, since buffering OS
    mouse events is a different concern from drawing pixels - ImgCanvas just
    owns the window handle MouseInput needs, and attaches it once the window
    it created is ready.
    """

    def __init__(self, window_title: str = "Kung-Fu-Chess"):
        self._window_title = window_title
        self._window_open = False
        self._mouse_input = MouseInput()

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

    def text_size(self, text, font_scale, thickness=1):
        """(width, height) in pixels of `text` at `font_scale`, matching draw_text's font -
        lets a caller center text without ever touching cv2 itself."""
        (width, height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        return width, height

    def fill_rect(self, frame: Img, x, y, w, h, color, alpha=1.0) -> None:
        frame.fill_rect(x, y, w, h, color, alpha=alpha)

    def blit(self, frame: Img, image: Img, x: int, y: int) -> None:
        image.draw_on(frame, x, y)

    def show(self, frame: Img, delay_ms: int) -> bool:
        """Displays one frame in the live window. Returns False if the user asked to quit.

        Quitting is any of: Esc/q, or closing the window with its title-bar X.
        The X is detected via WND_PROP_VISIBLE dropping below 1 - OpenCV has no
        close event, so we poll the property each frame after pumping waitKey.
        """
        self._ensure_window()
        cv2.imshow(self._window_title, frame.img)
        key = cv2.waitKey(max(1, delay_ms)) & 0xFF
        if key in (27, ord("q")):
            return False
        return cv2.getWindowProperty(self._window_title, cv2.WND_PROP_VISIBLE) >= 1

    def save(self, frame: Img, path) -> None:
        cv2.imwrite(str(path), frame.img)

    def drain_clicks(self):
        """Returns and clears the left-clicks buffered since the last call, as (x, y) image pixels."""
        return self._mouse_input.drain_clicks()

    def close(self) -> None:
        if self._window_open:
            # If the user closed the window with its X, the OS already tore it
            # down, so destroyWindow raises a NULL-window cv2.error. That is
            # exactly the state close() wants, so swallow it and mark it shut.
            try:
                cv2.destroyWindow(self._window_title)
            except cv2.error:
                pass
            self._window_open = False

    def _ensure_window(self):
        """Creates the auto-sized window and attaches the mouse input on first show.

        WINDOW_AUTOSIZE (the default) is deliberate: clicks arrive in the same
        image-pixel space the board mapper assumes (1:1 with the rendered
        frame). A resizable/scaled window would silently distort on_click.
        """
        if self._window_open:
            return
        cv2.namedWindow(self._window_title)
        self._mouse_input.attach(self._window_title)
        self._window_open = True
