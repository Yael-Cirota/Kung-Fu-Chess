from pathlib import Path

from ui.graphics.sprite_loader import SpriteLoader


class FakeResolver:
    def __init__(self):
        self.calls = []

    def resolve(self, piece_symbol, state=None, frame_index=None):
        self.calls.append((piece_symbol, state, frame_index))
        return Path(f"/{piece_symbol}/{state}/{frame_index}.png")


class FakeHandle:
    def __init__(self, path, size, keep_aspect):
        self.path = path
        self.size = size
        self.keep_aspect = keep_aspect


class FakeCanvas:
    def __init__(self):
        self.load_calls = []

    def load_image(self, path, size=None, keep_aspect=False):
        self.load_calls.append((path, size, keep_aspect))
        return FakeHandle(path, size, keep_aspect)


class TestLoading:
    def test_resolves_and_loads_the_sprite_through_the_canvas(self):
        canvas = FakeCanvas()
        resolver = FakeResolver()
        loader = SpriteLoader(canvas, resolver, sprite_size_px=(64, 64))

        handle = loader.get("wK")

        assert handle.path == Path("/wK/None/None.png")
        assert handle.size == (64, 64)
        assert handle.keep_aspect is True

    def test_forwards_state_and_frame_index_to_resolver(self):
        canvas = FakeCanvas()
        resolver = FakeResolver()
        loader = SpriteLoader(canvas, resolver, sprite_size_px=(64, 64))

        loader.get("wK", state="move", frame_index=2)

        assert resolver.calls == [("wK", "move", 2)]


class TestCaching:
    def test_same_request_is_served_from_cache(self):
        canvas = FakeCanvas()
        resolver = FakeResolver()
        loader = SpriteLoader(canvas, resolver, sprite_size_px=(64, 64))

        first = loader.get("wK", state="move", frame_index=1)
        second = loader.get("wK", state="move", frame_index=1)

        assert first is second
        assert len(canvas.load_calls) == 1
        assert len(resolver.calls) == 1

    def test_distinguishes_by_symbol_state_and_frame(self):
        canvas = FakeCanvas()
        resolver = FakeResolver()
        loader = SpriteLoader(canvas, resolver, sprite_size_px=(64, 64))

        loader.get("wK", state="move", frame_index=1)
        loader.get("wK", state="move", frame_index=2)
        loader.get("bK", state="move", frame_index=1)

        assert len(canvas.load_calls) == 3
