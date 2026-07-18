from __future__ import annotations

import pathlib

import cv2
import numpy as np

class Img:
    def __init__(self):
        self.img = None

    def read(self, path: str | pathlib.Path,
             size: tuple[int, int] | None = None,
             keep_aspect: bool = False,
             interpolation: int = cv2.INTER_AREA) -> "Img":
        """
        Load `path` into self.img and **optionally resize**.

        Parameters
        ----------
        path : str | Path
            Image file to load.
        size : (width, height) | None
            Target size in pixels.  If None, keep original.
        keep_aspect : bool
            • False  → resize exactly to `size`
            • True   → shrink so the *longer* side fits `size` while
                       preserving aspect ratio (no cropping).
        interpolation : OpenCV flag
            E.g.  `cv2.INTER_AREA` for shrink, `cv2.INTER_LINEAR` for enlarge.

        Returns
        -------
        Img
            `self`, so you can chain:  `sprite = Img().read("foo.png", (64,64))`
        """
        path = str(path)
        self.img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if self.img is None:
            raise FileNotFoundError(f"Cannot load image: {path}")

        if size is not None:
            target_w, target_h = size
            h, w = self.img.shape[:2]

            if keep_aspect:
                scale = min(target_w / w, target_h / h)
                new_w, new_h = int(w * scale), int(h * scale)
            else:
                new_w, new_h = target_w, target_h

            self.img = cv2.resize(self.img, (new_w, new_h), interpolation=interpolation)

        return self

    def draw_on(self, other_img, x, y):
        if self.img is None or other_img.img is None:
            raise ValueError("Both images must be loaded before drawing.")

        # Never mutate src: SpriteLoader caches Img instances and reuses them
        # across frames, so flattening/altering self.img here would corrupt a
        # cached sprite's alpha for every later blit.
        src = self.img
        dst = other_img.img

        h, w = src.shape[:2]
        H, W = dst.shape[:2]

        if y + h > H or x + w > W:
            raise ValueError("Logo does not fit at the specified position.")

        roi = dst[y:y + h, x:x + w]

        if src.shape[2] == 4:
            # Alpha-composite the sprite over whatever is underneath, using the
            # sprite's OWN alpha. This is keyed off the sprite having alpha, not
            # off the destination matching channel counts: a transparent sprite
            # background must stay transparent even when blitted onto a plain
            # 3-channel frame (the side-panel canvas), which the old
            # channel-reconciling path silently flattened to an opaque paste.
            alpha = src[..., 3] / 255.0
            for c in range(3):
                roi[..., c] = (1 - alpha) * roi[..., c] + alpha * src[..., c]
            if roi.shape[2] == 4:
                # Composite the destination alpha too ("over" operator), so the
                # region stays at least as opaque as the sprite made it.
                dst_alpha = roi[..., 3] / 255.0
                roi[..., 3] = ((alpha + dst_alpha * (1 - alpha)) * 255).astype("uint8")
        else:
            # Opaque sprite: straight colour copy; mark opaque if dst has alpha.
            roi[..., :3] = src[..., :3]
            if roi.shape[2] == 4:
                roi[..., 3] = 255

    def fill_rect(self, x, y, w, h, color, alpha=1.0):
        """
        Paint a `w`x`h` rectangle at (x, y) in `color` (BGR), optionally
        alpha-blended over what is already there (alpha=1.0 is an opaque fill).
        The rectangle is clipped to the image bounds, so callers can request a
        highlight that runs off an edge without raising. Only the colour
        channels are touched, so this is safe on both 3- and 4-channel frames.
        """
        if self.img is None:
            raise ValueError("Image not loaded.")

        H, W = self.img.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(W, x + w), min(H, y + h)
        if x1 <= x0 or y1 <= y0:
            return

        roi = self.img[y0:y1, x0:x1, :3]
        fill = np.array(color[:3], dtype=np.float32)
        if alpha >= 1.0:
            roi[:] = fill.astype(roi.dtype)
        else:
            roi[:] = ((1.0 - alpha) * roi + alpha * fill).astype(roi.dtype)

    def put_text(self, txt, x, y, font_size, color=(255, 255, 255, 255), thickness=1):
        if self.img is None:
            raise ValueError("Image not loaded.")
        cv2.putText(self.img, txt, (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, font_size,
                    color, thickness, cv2.LINE_AA)
