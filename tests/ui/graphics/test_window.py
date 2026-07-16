import ui.graphics.window as window_module
from ui.graphics.window import Window


class FakeFrame:
    def __init__(self):
        self.img = "fake-pixels"


class FakeCv2:
    def __init__(self, wait_key_return=ord("a")):
        self.imshow_calls = []
        self.wait_key_calls = []
        self.destroy_window_calls = []
        self._wait_key_return = wait_key_return

    def imshow(self, title, array):
        self.imshow_calls.append((title, array))

    def waitKey(self, delay_ms):
        self.wait_key_calls.append(delay_ms)
        return self._wait_key_return

    def destroyWindow(self, title):
        self.destroy_window_calls.append(title)


def install_fake_cv2(monkeypatch, wait_key_return=ord("a")):
    fake_cv2 = FakeCv2(wait_key_return)
    monkeypatch.setattr(window_module, "cv2", fake_cv2)
    return fake_cv2


class TestShow:
    def test_shows_the_frame_under_the_configured_title(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        window = Window("My Window")
        frame = FakeFrame()

        window.show(frame, delay_ms=40)

        assert fake_cv2.imshow_calls == [("My Window", "fake-pixels")]

    def test_waits_for_the_given_delay(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        window = Window()

        window.show(FakeFrame(), delay_ms=40)

        assert fake_cv2.wait_key_calls == [40]

    def test_clamps_delay_to_at_least_one_ms(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        window = Window()

        window.show(FakeFrame(), delay_ms=0)

        assert fake_cv2.wait_key_calls == [1]

    def test_returns_true_when_a_non_quit_key_was_pressed(self, monkeypatch):
        install_fake_cv2(monkeypatch, wait_key_return=ord("a"))
        window = Window()

        assert window.show(FakeFrame(), delay_ms=40) is True

    def test_returns_false_on_escape(self, monkeypatch):
        install_fake_cv2(monkeypatch, wait_key_return=27)
        window = Window()

        assert window.show(FakeFrame(), delay_ms=40) is False

    def test_returns_false_on_q(self, monkeypatch):
        install_fake_cv2(monkeypatch, wait_key_return=ord("q"))
        window = Window()

        assert window.show(FakeFrame(), delay_ms=40) is False

    def test_masks_wait_key_result_to_a_byte(self, monkeypatch):
        # cv2.waitKey can return values outside a byte on some platforms;
        # Window masks with 0xFF before comparing against the quit keys.
        install_fake_cv2(monkeypatch, wait_key_return=0x1FF & ~0xFF | ord("q"))
        window = Window()

        assert window.show(FakeFrame(), delay_ms=40) is False


class TestClose:
    def test_destroys_the_window_by_title(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        window = Window("My Window")

        window.close()

        assert fake_cv2.destroy_window_calls == ["My Window"]
