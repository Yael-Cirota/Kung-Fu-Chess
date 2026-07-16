import numpy as np

import ui.graphics.img_canvas as img_canvas_module
from ui.graphics.img_canvas import ImgCanvas
from ui.img import Img


class FakeCv2:
    EVENT_LBUTTONDOWN = 1
    EVENT_MOUSEMOVE = 0

    def __init__(self, wait_key_return=ord("a")):
        self.imshow_calls = []
        self.wait_key_calls = []
        self.imwrite_calls = []
        self.destroy_window_calls = []
        self.named_window_calls = []
        self.mouse_callbacks = {}
        self._wait_key_return = wait_key_return

    def imshow(self, title, array):
        self.imshow_calls.append((title, array))

    def waitKey(self, delay_ms):
        self.wait_key_calls.append(delay_ms)
        return self._wait_key_return

    def imwrite(self, path, array):
        self.imwrite_calls.append((path, array))
        return True

    def namedWindow(self, title):
        self.named_window_calls.append(title)

    def setMouseCallback(self, title, callback):
        self.mouse_callbacks[title] = callback

    def click(self, title, x, y):
        """Simulates the user left-clicking at (x, y) - what OpenCV would fire during waitKey."""
        self.mouse_callbacks[title](self.EVENT_LBUTTONDOWN, x, y, 0, None)

    def destroyWindow(self, title):
        self.destroy_window_calls.append(title)


def install_fake_cv2(monkeypatch, wait_key_return=ord("a")):
    fake_cv2 = FakeCv2(wait_key_return)
    monkeypatch.setattr(img_canvas_module, "cv2", fake_cv2)
    return fake_cv2


def loaded_img():
    img = Img()
    img.img = np.zeros((4, 4, 3), dtype=np.uint8)
    return img


class TestLoadImage:
    def test_loads_a_real_file_via_img(self, tmp_path):
        import cv2

        path = tmp_path / "sprite.png"
        cv2.imwrite(str(path), np.zeros((6, 10, 3), dtype=np.uint8))
        canvas = ImgCanvas()

        handle = canvas.load_image(path, size=(4, 4))

        assert isinstance(handle, Img)
        assert handle.img.shape[:2] == (4, 4)


class TestBlit:
    def test_delegates_to_the_sprite_draw_on(self):
        canvas = ImgCanvas()
        recorded = []

        class FakeSprite:
            def draw_on(self, frame, x, y):
                recorded.append((frame, x, y))

        frame = object()
        sprite = FakeSprite()

        canvas.blit(frame, sprite, 3, 7)

        assert recorded == [(frame, 3, 7)]


class TestShow:
    def test_shows_frame_under_the_configured_title(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        canvas = ImgCanvas("My Window")
        frame = loaded_img()

        canvas.show(frame, delay_ms=40)

        assert fake_cv2.imshow_calls == [("My Window", frame.img)]

    def test_clamps_delay_to_at_least_one_ms(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        canvas = ImgCanvas()

        canvas.show(loaded_img(), delay_ms=0)

        assert fake_cv2.wait_key_calls == [1]

    def test_returns_true_for_a_non_quit_key(self, monkeypatch):
        install_fake_cv2(monkeypatch, wait_key_return=ord("a"))
        canvas = ImgCanvas()

        assert canvas.show(loaded_img(), delay_ms=40) is True

    def test_returns_false_on_escape(self, monkeypatch):
        install_fake_cv2(monkeypatch, wait_key_return=27)
        canvas = ImgCanvas()

        assert canvas.show(loaded_img(), delay_ms=40) is False

    def test_returns_false_on_q(self, monkeypatch):
        install_fake_cv2(monkeypatch, wait_key_return=ord("q"))
        canvas = ImgCanvas()

        assert canvas.show(loaded_img(), delay_ms=40) is False

    def test_masks_wait_key_result_to_a_byte(self, monkeypatch):
        install_fake_cv2(monkeypatch, wait_key_return=0x1FF & ~0xFF | ord("q"))
        canvas = ImgCanvas()

        assert canvas.show(loaded_img(), delay_ms=40) is False


class TestSave:
    def test_writes_frame_pixels_to_the_path(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        canvas = ImgCanvas()
        frame = loaded_img()

        canvas.save(frame, "out.png")

        assert fake_cv2.imwrite_calls == [("out.png", frame.img)]


class TestInput:
    def test_creates_the_window_and_wires_the_mouse_callback_on_first_show(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        canvas = ImgCanvas("My Window")

        canvas.show(loaded_img(), delay_ms=1)

        assert fake_cv2.named_window_calls == ["My Window"]
        assert "My Window" in fake_cv2.mouse_callbacks

    def test_only_creates_the_window_once_across_repeated_shows(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        canvas = ImgCanvas("My Window")

        canvas.show(loaded_img(), delay_ms=1)
        canvas.show(loaded_img(), delay_ms=1)

        assert fake_cv2.named_window_calls == ["My Window"]

    def test_drain_returns_buffered_left_clicks_and_then_empties(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        canvas = ImgCanvas("My Window")
        canvas.show(loaded_img(), delay_ms=1)

        fake_cv2.click("My Window", 30, 40)
        fake_cv2.click("My Window", 150, 260)

        assert canvas.drain_clicks() == [(30, 40), (150, 260)]
        assert canvas.drain_clicks() == []

    def test_ignores_non_left_button_mouse_events(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        canvas = ImgCanvas("My Window")
        canvas.show(loaded_img(), delay_ms=1)

        callback = fake_cv2.mouse_callbacks["My Window"]
        callback(fake_cv2.EVENT_MOUSEMOVE, 10, 10, 0, None)

        assert canvas.drain_clicks() == []

    def test_drain_is_empty_before_any_clicks(self, monkeypatch):
        install_fake_cv2(monkeypatch)
        canvas = ImgCanvas()

        assert canvas.drain_clicks() == []


class TestClose:
    def test_destroys_the_window_only_after_it_was_shown(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        canvas = ImgCanvas("My Window")

        canvas.show(loaded_img(), delay_ms=1)
        canvas.close()

        assert fake_cv2.destroy_window_calls == ["My Window"]

    def test_close_is_a_noop_when_no_window_was_ever_shown(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        canvas = ImgCanvas("My Window")

        canvas.close()

        assert fake_cv2.destroy_window_calls == []
