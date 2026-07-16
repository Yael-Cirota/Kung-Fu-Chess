from pathlib import Path

import ui.graphics.sprite_loader as sprite_loader_module
from ui.graphics.sprite_loader import SpriteLoader


class FakeResolver:
    def __init__(self):
        self.calls = []

    def resolve(self, piece_symbol, state=None, frame_index=None):
        self.calls.append((piece_symbol, state, frame_index))
        return Path(f"/{piece_symbol}/{state}/{frame_index}.png")


class FakeImg:
    instances_created = 0

    def __init__(self):
        self.path = None
        self.size = None
        self.keep_aspect = None
        FakeImg.instances_created += 1

    def read(self, path, size=None, keep_aspect=False):
        self.path = path
        self.size = size
        self.keep_aspect = keep_aspect
        return self


def use_fake_img(monkeypatch):
    FakeImg.instances_created = 0
    monkeypatch.setattr(sprite_loader_module, "Img", FakeImg)


class TestLoading:
    def test_resolves_and_reads_the_sprite(self, monkeypatch):
        use_fake_img(monkeypatch)
        resolver = FakeResolver()
        loader = SpriteLoader(resolver, sprite_size_px=(64, 64))

        img = loader.get("wK")

        assert img.path == Path("/wK/None/None.png")
        assert img.size == (64, 64)
        assert img.keep_aspect is True

    def test_forwards_state_and_frame_index_to_resolver(self, monkeypatch):
        use_fake_img(monkeypatch)
        resolver = FakeResolver()
        loader = SpriteLoader(resolver, sprite_size_px=(64, 64))

        loader.get("wK", state="move", frame_index=2)

        assert resolver.calls == [("wK", "move", 2)]


class TestCaching:
    def test_same_request_is_served_from_cache(self, monkeypatch):
        use_fake_img(monkeypatch)
        resolver = FakeResolver()
        loader = SpriteLoader(resolver, sprite_size_px=(64, 64))

        first = loader.get("wK", state="move", frame_index=1)
        second = loader.get("wK", state="move", frame_index=1)

        assert first is second
        assert FakeImg.instances_created == 1
        assert len(resolver.calls) == 1

    def test_distinguishes_by_symbol_state_and_frame(self, monkeypatch):
        use_fake_img(monkeypatch)
        resolver = FakeResolver()
        loader = SpriteLoader(resolver, sprite_size_px=(64, 64))

        loader.get("wK", state="move", frame_index=1)
        loader.get("wK", state="move", frame_index=2)
        loader.get("bK", state="move", frame_index=1)

        assert FakeImg.instances_created == 3
