import cv2
import numpy as np
import pytest

from ui.img import Img


def write_png(path, array):
    cv2.imwrite(str(path), array)
    return path


def solid_bgr(width, height, color):
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = color
    return img


def solid_bgra(width, height, color, alpha):
    img = np.zeros((height, width, 4), dtype=np.uint8)
    img[:, :, :3] = color
    img[:, :, 3] = alpha
    return img


class TestRead:
    def test_loads_image_at_original_size_when_no_size_given(self, tmp_path):
        path = write_png(tmp_path / "sprite.png", solid_bgr(10, 6, (0, 0, 255)))

        img = Img().read(path)

        assert img.img.shape[:2] == (6, 10)

    def test_resizes_exactly_when_keep_aspect_false(self, tmp_path):
        path = write_png(tmp_path / "sprite.png", solid_bgr(10, 20, (0, 0, 255)))

        img = Img().read(path, size=(4, 4))

        assert img.img.shape[:2] == (4, 4)

    def test_shrinks_preserving_aspect_when_keep_aspect_true(self, tmp_path):
        path = write_png(tmp_path / "sprite.png", solid_bgr(20, 10, (0, 0, 255)))  # 2:1 landscape

        img = Img().read(path, size=(8, 8), keep_aspect=True)

        h, w = img.img.shape[:2]
        assert w == 8
        assert h == 4  # fits within box while preserving 2:1 ratio

    def test_returns_self_for_chaining(self, tmp_path):
        path = write_png(tmp_path / "sprite.png", solid_bgr(4, 4, (0, 0, 255)))

        result = Img().read(path)

        assert isinstance(result, Img)

    def test_raises_file_not_found_for_missing_path(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            Img().read(tmp_path / "does_not_exist.png")

    def test_accepts_path_object(self, tmp_path):
        path = write_png(tmp_path / "sprite.png", solid_bgr(4, 4, (0, 0, 255)))

        img = Img().read(path)

        assert img.img is not None


class TestDrawOn:
    def test_draws_opaque_sprite_at_given_position(self):
        frame = Img()
        frame.img = solid_bgr(10, 10, (255, 255, 255))
        sprite = Img()
        sprite.img = solid_bgr(4, 4, (0, 0, 255))

        sprite.draw_on(frame, 2, 3)

        assert tuple(frame.img[3, 2]) == (0, 0, 255)
        assert tuple(frame.img[3 + 3, 2 + 3]) == (0, 0, 255)
        assert tuple(frame.img[0, 0]) == (255, 255, 255)  # untouched corner

    def test_blends_using_alpha_channel_when_frame_also_has_alpha(self):
        frame = Img()
        frame.img = solid_bgra(4, 4, (0, 0, 0), alpha=255)
        sprite = Img()
        sprite.img = solid_bgra(4, 4, (255, 255, 255), alpha=128)

        sprite.draw_on(frame, 0, 0)

        # mask = 128/255 ~= 0.502 -> pixel ~= 128
        pixel = frame.img[0, 0]
        assert all(120 <= channel <= 135 for channel in pixel[:3])

    def test_blends_using_alpha_even_when_frame_has_no_alpha_channel(self):
        # A 4-channel sprite blitted onto a 3-channel frame must still respect
        # its own alpha: the sprite's transparent background stays transparent
        # (this is what keeps piece backgrounds from stamping a solid box onto
        # the side-panel canvas). Here alpha=128 blends white halfway onto black.
        frame = Img()
        frame.img = solid_bgr(4, 4, (0, 0, 0))
        sprite = Img()
        sprite.img = solid_bgra(4, 4, (255, 255, 255), alpha=128)

        sprite.draw_on(frame, 0, 0)

        assert frame.img.shape[2] == 3  # frame stays 3-channel
        assert all(120 <= channel <= 135 for channel in frame.img[0, 0])

    def test_transparent_sprite_region_leaves_frame_untouched(self):
        # The piece-background bug: a sprite pixel with alpha=0 must not paint
        # over the frame, whether or not the frame carries an alpha channel.
        for frame_img in (solid_bgr(4, 4, (10, 20, 30)),
                          solid_bgra(4, 4, (10, 20, 30), alpha=255)):
            frame = Img()
            frame.img = frame_img
            sprite = Img()
            sprite.img = solid_bgra(4, 4, (200, 200, 200), alpha=0)  # fully transparent

            sprite.draw_on(frame, 0, 0)

            assert tuple(frame.img[0, 0][:3]) == (10, 20, 30)

    def test_converts_bgr_sprite_onto_bgra_frame(self):
        frame = Img()
        frame.img = solid_bgra(6, 6, (0, 0, 0), alpha=255)
        sprite = Img()
        sprite.img = solid_bgr(3, 3, (10, 20, 30))

        sprite.draw_on(frame, 1, 1)  # should not raise despite channel mismatch

        assert frame.img.shape[2] == 4

    def test_does_not_mutate_the_source_sprite_when_channels_mismatch(self):
        # Regression test for the cached-sprite corruption bug: blitting a
        # 4-channel sprite onto a 3-channel frame must reconcile channels on
        # a local copy, never on the sprite's own (cached, reused) image.
        frame = Img()
        frame.img = solid_bgr(4, 4, (0, 0, 0))
        sprite = Img()
        sprite.img = solid_bgra(4, 4, (255, 255, 255), alpha=128)

        sprite.draw_on(frame, 0, 0)

        assert sprite.img.shape[2] == 4  # still 4-channel; alpha not stripped
        # And a second blit onto a 4-channel frame still alpha-blends,
        # proving the sprite's transparency survived the first draw.
        frame2 = Img()
        frame2.img = solid_bgra(4, 4, (0, 0, 0), alpha=255)
        sprite.draw_on(frame2, 0, 0)
        assert all(120 <= channel <= 135 for channel in frame2.img[0, 0][:3])

    def test_raises_when_frame_not_loaded(self):
        sprite = Img()
        sprite.img = solid_bgr(2, 2, (0, 0, 0))

        with pytest.raises(ValueError):
            sprite.draw_on(Img(), 0, 0)

    def test_raises_when_sprite_not_loaded(self):
        frame = Img()
        frame.img = solid_bgr(4, 4, (0, 0, 0))

        with pytest.raises(ValueError):
            Img().draw_on(frame, 0, 0)

    def test_raises_when_sprite_does_not_fit_at_position(self):
        frame = Img()
        frame.img = solid_bgr(4, 4, (0, 0, 0))
        sprite = Img()
        sprite.img = solid_bgr(3, 3, (255, 0, 0))

        with pytest.raises(ValueError):
            sprite.draw_on(frame, 2, 2)  # 2+3 > 4 on both axes


class TestFillRect:
    def test_opaque_fill_paints_the_region(self):
        img = Img()
        img.img = solid_bgr(10, 10, (0, 0, 0))

        img.fill_rect(2, 3, 4, 5, (10, 20, 30))

        assert tuple(img.img[3, 2]) == (10, 20, 30)
        assert tuple(img.img[3 + 4, 2 + 3]) == (10, 20, 30)
        assert tuple(img.img[0, 0]) == (0, 0, 0)  # outside the rect, untouched

    def test_alpha_blends_over_the_existing_pixels(self):
        img = Img()
        img.img = solid_bgr(4, 4, (0, 0, 0))

        img.fill_rect(0, 0, 4, 4, (200, 200, 200), alpha=0.5)

        assert all(95 <= channel <= 105 for channel in img.img[0, 0])

    def test_clips_to_the_image_bounds_without_raising(self):
        img = Img()
        img.img = solid_bgr(4, 4, (0, 0, 0))

        img.fill_rect(-2, -2, 4, 4, (5, 5, 5))  # runs off the top-left corner

        assert tuple(img.img[0, 0]) == (5, 5, 5)
        assert tuple(img.img[2, 2]) == (0, 0, 0)  # beyond the clipped rect

    def test_a_fully_offscreen_rect_is_a_noop(self):
        img = Img()
        img.img = solid_bgr(4, 4, (7, 7, 7))
        before = img.img.copy()

        img.fill_rect(10, 10, 3, 3, (0, 0, 0))

        assert np.array_equal(before, img.img)

    def test_only_touches_color_channels_on_a_bgra_frame(self):
        img = Img()
        img.img = solid_bgra(4, 4, (0, 0, 0), alpha=255)

        img.fill_rect(0, 0, 4, 4, (10, 20, 30))

        assert tuple(img.img[0, 0][:3]) == (10, 20, 30)
        assert img.img[0, 0][3] == 255  # alpha channel left intact

    def test_raises_when_not_loaded(self):
        with pytest.raises(ValueError):
            Img().fill_rect(0, 0, 2, 2, (0, 0, 0))


class TestPutText:
    def test_raises_when_not_loaded(self):
        with pytest.raises(ValueError):
            Img().put_text("hi", 0, 0, 1.0)

    def test_modifies_pixels_when_loaded(self):
        img = Img()
        img.img = solid_bgr(50, 20, (0, 0, 0))
        before = img.img.copy()

        img.put_text("A", 2, 15, 1.0, color=(255, 255, 255))

        assert not np.array_equal(before, img.img)
