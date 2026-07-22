import ui.audio.winsound_sound_board as winsound_sound_board_module
from ui.audio.winsound_sound_board import WinsoundSoundBoard


class FakeWinsound:
    SND_FILENAME = 1
    SND_ASYNC = 2

    def __init__(self):
        self.played = []

    def PlaySound(self, path, flags):
        self.played.append((path, flags))


class TestWinsoundSoundBoard:
    def test_playing_a_known_name_forwards_the_path_with_async_filename_flags(self, monkeypatch):
        fake_winsound = FakeWinsound()
        monkeypatch.setattr(winsound_sound_board_module, "winsound", fake_winsound)
        board = WinsoundSoundBoard({"move": "C:/sounds/move.wav"})

        board.play("move")

        assert fake_winsound.played == [
            ("C:/sounds/move.wav", FakeWinsound.SND_FILENAME | FakeWinsound.SND_ASYNC)
        ]

    def test_playing_an_unknown_name_is_a_silent_no_op(self, monkeypatch):
        fake_winsound = FakeWinsound()
        monkeypatch.setattr(winsound_sound_board_module, "winsound", fake_winsound)
        board = WinsoundSoundBoard({"move": "C:/sounds/move.wav"})

        board.play("nonexistent")

        assert fake_winsound.played == []

    def test_disabled_when_winsound_is_unavailable(self, monkeypatch):
        monkeypatch.setattr(winsound_sound_board_module, "winsound", None)
        board = WinsoundSoundBoard({"move": "C:/sounds/move.wav"})

        board.play("move")  # must not raise
