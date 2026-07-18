from controller.api import Scoreboard
from ui.graphics.score_panel import ScorePanel, format_score


class FakeCanvas:
    """Records draw_text calls so panel layout can be asserted without pixels."""

    def __init__(self):
        self.texts = []  # (text, x, y, scale, color, thickness)

    def draw_text(self, frame, text, x, y, font_scale, color, thickness=1):
        self.texts.append((text, x, y, font_scale, color, thickness))


def make_panel(height_px=64, line_height_px=26, header_height_px=24, padding_px=10):
    return ScorePanel(
        height_px=height_px, white_text_color=(2, 2, 2), black_text_color=(3, 3, 3),
        font_scale=0.7, line_height_px=line_height_px,
        header_height_px=header_height_px, padding_px=padding_px,
    )


class TestFormatScore:
    def test_reads_as_label_and_number(self):
        assert format_score("White", 7) == "White: 7"
        assert format_score("Black", 0) == "Black: 0"


class TestHeight:
    def test_exposes_configured_height(self):
        assert make_panel(height_px=80).height_px == 80


class TestDraw:
    def test_draws_both_totals_with_their_colors(self):
        canvas = FakeCanvas()
        make_panel().draw(canvas, frame=object(), scoreboard=Scoreboard(white=7, black=3), board_width_px=800)

        by_text = {t[0]: t for t in canvas.texts}
        assert set(by_text) == {"White: 7", "Black: 3"}
        assert by_text["White: 7"][4] == (2, 2, 2)  # white text color
        assert by_text["Black: 3"][4] == (3, 3, 3)  # black text color

    def test_totals_sit_in_the_strip_and_stack_by_line_height(self):
        canvas = FakeCanvas()
        panel = make_panel(line_height_px=26, header_height_px=24, padding_px=10)
        panel.draw(canvas, frame=object(), scoreboard=Scoreboard(white=1, black=2), board_width_px=800)

        by_text = {t[0]: t for t in canvas.texts}
        assert by_text["White: 1"][1] == 810     # board_width + padding
        assert by_text["Black: 2"][1] == 810      # same column
        assert by_text["White: 1"][2] == 24       # header_height
        assert by_text["Black: 2"][2] == 24 + 26  # a line below white
