from ui.animation.animation_config_loader import ANIMATION_STATE_NAMES, load_animation_configs
from ui.ui_config import PIECES_DIR


class TestLoadAnimationConfigs:
    def test_loads_every_declared_state(self):
        configs = load_animation_configs(PIECES_DIR)

        assert set(configs.keys()) == set(ANIMATION_STATE_NAMES)

    def test_frame_count_is_counted_from_sprite_files_on_disk(self):
        configs = load_animation_configs(PIECES_DIR)
        idle_dir = PIECES_DIR / "KW" / "states" / "idle" / "sprites"

        assert configs["idle"].frame_count == len(list(idle_dir.glob("*.png")))
        assert configs["idle"].frame_count > 0

    def test_metadata_fields_come_from_config_json(self):
        configs = load_animation_configs(PIECES_DIR)

        for state, config in configs.items():
            assert isinstance(config.frames_per_sec, int)
            assert config.frames_per_sec > 0
            assert isinstance(config.is_loop, bool)
            assert isinstance(config.next_state, str)
