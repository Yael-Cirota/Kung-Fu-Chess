import cv2

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
    """

    def __init__(self, window_title: str = "Kung-Fu-Chess"):
        self._window_title = window_title
        self._window_open = False

    def load_image(self, path, size=None, keep_aspect=False) -> Img:
        return Img().read(path, size=size, keep_aspect=keep_aspect)

    def blit(self, frame: Img, image: Img, x: int, y: int) -> None:
        image.draw_on(frame, x, y)

    def show(self, frame: Img, delay_ms: int) -> bool:
        """Displays one frame in the live window. Returns False if the user asked to quit (Esc/q)."""
        self._window_open = True
        cv2.imshow(self._window_title, frame.img)
        key = cv2.waitKey(max(1, delay_ms)) & 0xFF
        return key not in (27, ord("q"))

    def save(self, frame: Img, path) -> None:
        cv2.imwrite(str(path), frame.img)

    def close(self) -> None:
        if self._window_open:
            cv2.destroyWindow(self._window_title)
            self._window_open = False
