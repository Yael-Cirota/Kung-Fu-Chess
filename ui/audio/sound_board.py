from typing import Protocol, runtime_checkable


@runtime_checkable
class SoundBoard(Protocol):
    """The only seam allowed to touch a real audio backend - everything else
    in ui (GameAudioTracker, game_loop) plays sounds only by name."""

    def play(self, name: str) -> None: ...
