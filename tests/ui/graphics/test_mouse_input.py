import ui.graphics.mouse_input as mouse_input_module
from ui.graphics.mouse_input import MouseInput


class FakeCv2:
    EVENT_LBUTTONDOWN = 1
    EVENT_MOUSEMOVE = 0

    def __init__(self):
        self.mouse_callbacks = {}

    def setMouseCallback(self, title, callback):
        self.mouse_callbacks[title] = callback

    def click(self, title, x, y):
        self.mouse_callbacks[title](self.EVENT_LBUTTONDOWN, x, y, 0, None)


def install_fake_cv2(monkeypatch):
    fake_cv2 = FakeCv2()
    monkeypatch.setattr(mouse_input_module, "cv2", fake_cv2)
    return fake_cv2


class TestAttach:
    def test_wires_the_callback_onto_the_named_window(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        mouse_input = MouseInput()

        mouse_input.attach("My Window")

        assert "My Window" in fake_cv2.mouse_callbacks

    def test_is_idempotent_across_repeated_calls(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        mouse_input = MouseInput()

        mouse_input.attach("My Window")
        first_callback = fake_cv2.mouse_callbacks["My Window"]
        fake_cv2.mouse_callbacks.clear()
        mouse_input.attach("My Window")

        assert "My Window" not in fake_cv2.mouse_callbacks
        assert first_callback is not None


class TestDrainClicks:
    def test_returns_buffered_left_clicks_and_then_empties(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        mouse_input = MouseInput()
        mouse_input.attach("My Window")

        fake_cv2.click("My Window", 30, 40)
        fake_cv2.click("My Window", 150, 260)

        assert mouse_input.drain_clicks() == [(30, 40), (150, 260)]
        assert mouse_input.drain_clicks() == []

    def test_ignores_non_left_button_mouse_events(self, monkeypatch):
        fake_cv2 = install_fake_cv2(monkeypatch)
        mouse_input = MouseInput()
        mouse_input.attach("My Window")

        callback = fake_cv2.mouse_callbacks["My Window"]
        callback(fake_cv2.EVENT_MOUSEMOVE, 10, 10, 0, None)

        assert mouse_input.drain_clicks() == []

    def test_is_empty_before_any_clicks(self):
        mouse_input = MouseInput()

        assert mouse_input.drain_clicks() == []
