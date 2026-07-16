from typing import Dict, Tuple

from ui.img import Img
from ui.graphics.sprite_resolver import SpriteResolver


class SpriteLoader:
    """
    Loads sprite images by piece symbol and caches them so each file is
    read from disk at most once. Delegates symbol -> file translation to
    an injected SpriteResolver; knows nothing about boards, positions,
    or kfchess beyond the bare symbol string it's asked to load.
    """

    def __init__(self, resolver: SpriteResolver, sprite_size_px: Tuple[int, int]):
        self._resolver = resolver
        self._sprite_size_px = sprite_size_px
        self._cache: Dict[tuple, Img] = {}

    def get(self, piece_symbol: str, state: str = None, frame_index: int = None) -> Img:
        cache_key = (piece_symbol, state, frame_index)
        if cache_key not in self._cache:
            path = self._resolver.resolve(piece_symbol, state, frame_index)
            self._cache[cache_key] = Img().read(path, size=self._sprite_size_px, keep_aspect=True)
        return self._cache[cache_key]
