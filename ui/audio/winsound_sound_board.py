from pathlib import Path
from typing import Dict

try:
    import winsound
except ImportError:  # pragma: no cover - Windows-only stdlib module
    winsound = None


class WinsoundSoundBoard:
    """
    SoundBoard backed by the stdlib `winsound` module - no extra dependency,
    but Windows-only. Disables itself (silently no-ops) on any other
    platform, so the rest of ui never needs to know audio isn't available.
    """

    def __init__(self, sound_paths: Dict[str, Path]):
        self._sound_paths = sound_paths

    def play(self, name: str) -> None:
        if winsound is None:
            return
        path = self._sound_paths.get(name)
        if path is None:
            return
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
