import cv2


class MouseInput:
    """
    The ui's single source of real human input: captures OS mouse clicks via
    a cv2 window callback and buffers them (in image-pixel space) for the
    game loop to drain each frame.

    Split out from ImgCanvas because "draw pixels" and "capture raw OS
    input" are different responsibilities that only happen to share cv2 -
    this class needs nothing from Img/rendering, only the title of a window
    that already exists. ImgCanvas still owns window creation, so it calls
    attach() once the window it made is ready.
    """

    def __init__(self):
        self._pending_clicks = []
        self._attached = False

    def attach(self, window_title: str) -> None:
        """Wires the mouse callback onto an already-created cv2 window. Idempotent."""
        if self._attached:
            return
        cv2.setMouseCallback(window_title, self._on_mouse)
        self._attached = True

    def drain_clicks(self):
        """Returns and clears the left-clicks buffered since the last call, as (x, y) image pixels."""
        clicks = self._pending_clicks
        self._pending_clicks = []
        return clicks

    def _on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self._pending_clicks.append((x, y))
