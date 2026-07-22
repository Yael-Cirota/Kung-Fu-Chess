from pathlib import Path

from ui.graphics.sprite_resolver import SpriteResolver


class TestDefaultStateAndFrame:
    def test_resolves_using_configured_state_and_frame(self):
        resolver = SpriteResolver(Path("/skins/pieces1"), "idle", "1.png")

        path = resolver.resolve("wK")

        assert path == Path("/skins/pieces1/KW/states/idle/sprites/1.png")

    def test_uppercases_color_letter_in_folder_name(self):
        resolver = SpriteResolver(Path("/skins/pieces1"), "idle", "1.png")

        path = resolver.resolve("bP")

        assert path == Path("/skins/pieces1/PB/states/idle/sprites/1.png")


class TestExplicitStateAndFrame:
    def test_overrides_configured_state(self):
        resolver = SpriteResolver(Path("/skins/pieces1"), "idle", "1.png")

        path = resolver.resolve("wN", state="jump")

        assert path == Path("/skins/pieces1/NW/states/jump/sprites/1.png")

    def test_frame_index_is_one_indexed_on_disk(self):
        resolver = SpriteResolver(Path("/skins/pieces1"), "idle", "1.png")

        path = resolver.resolve("wN", state="move", frame_index=0)

        assert path == Path("/skins/pieces1/NW/states/move/sprites/1.png")

    def test_frame_index_three_maps_to_frame_file_four(self):
        resolver = SpriteResolver(Path("/skins/pieces1"), "idle", "1.png")

        path = resolver.resolve("wN", state="move", frame_index=3)

        assert path == Path("/skins/pieces1/NW/states/move/sprites/4.png")

    def test_accepts_string_pieces_dir(self):
        resolver = SpriteResolver("/skins/pieces1", "idle", "1.png")

        path = resolver.resolve("wK")

        assert path == Path("/skins/pieces1/KW/states/idle/sprites/1.png")
