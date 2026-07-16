from ui import ui_config


class TestModuleLevelConstants:
    def test_cell_size_is_defined_independently_of_kfchess(self):
        assert ui_config.CELL_SIZE_PX == 100

    def test_board_dimensions_are_standard_chess(self):
        assert ui_config.BOARD_ROWS == 8
        assert ui_config.BOARD_COLS == 8

    def test_config_no_longer_precomputes_animation_configs_at_import(self):
        # Animation data is now loaded on demand by
        # ui.animation.animation_config_loader, not baked into this module as
        # an import-time side effect - so the precomputed map is gone.
        assert not hasattr(ui_config, "ANIMATION_STATE_CONFIGS")
