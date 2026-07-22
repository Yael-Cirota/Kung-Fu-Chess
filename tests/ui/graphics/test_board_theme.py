from dataclasses import FrozenInstanceError

import pytest

from ui.graphics.board_theme import BoardTheme


class TestBoardTheme:
    def test_defaults_enable_both_overlays(self):
        theme = BoardTheme()
        assert theme.highlight_last_move is True
        assert theme.highlight_selected is True
        assert theme.show_coordinates is True

    def test_is_immutable(self):
        theme = BoardTheme()
        with pytest.raises(FrozenInstanceError):
            theme.last_move_alpha = 0.9

    def test_fields_are_overridable(self):
        theme = BoardTheme(
            highlight_last_move=False, last_move_color=(1, 2, 3), last_move_alpha=0.5,
            highlight_selected=False, selected_color=(11, 12, 13), selected_alpha=0.6,
            show_coordinates=False, coordinate_color=(4, 5, 6),
            coordinate_font_scale=0.9, coordinate_thickness=2, coordinate_margin_px=7,
            coordinate_outline_color=(8, 9, 10), coordinate_outline_thickness=4,
        )
        assert theme.highlight_last_move is False
        assert theme.last_move_color == (1, 2, 3)
        assert theme.last_move_alpha == 0.5
        assert theme.highlight_selected is False
        assert theme.selected_color == (11, 12, 13)
        assert theme.selected_alpha == 0.6
        assert theme.show_coordinates is False
        assert theme.coordinate_color == (4, 5, 6)
        assert theme.coordinate_font_scale == 0.9
        assert theme.coordinate_thickness == 2
        assert theme.coordinate_margin_px == 7
        assert theme.coordinate_outline_color == (8, 9, 10)
        assert theme.coordinate_outline_thickness == 4
