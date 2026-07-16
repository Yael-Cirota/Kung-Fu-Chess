import cv2

from ui.img import Img


class Window:
    """
    Thin wrapper around the one place cv2 is allowed to touch a live
    display. Shows a rendered Img in a named window and waits the given
    number of milliseconds (non-blocking within that wait - a keypress
    ends it early). No board/piece/animation knowledge lives here.
    """

    def __init__(self, title: str = "Kung-Fu-Chess"):
        self._title = title

    def show(self, frame: Img, delay_ms: int) -> bool:
        """Displays one frame. Returns False if the user asked to quit (Esc/q)."""
        cv2.imshow(self._title, frame.img)
        key = cv2.waitKey(max(1, delay_ms)) & 0xFF
        return key not in (27, ord("q"))

    def close(self) -> None:
        cv2.destroyWindow(self._title)
