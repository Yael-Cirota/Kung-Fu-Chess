import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kfchess.api import Position, create_game_session

from ui.ui_config import (
    CELL_SIZE_PX, BOARD_IMAGE_PATH, PIECES_DIR, SPRITE_STATE, SPRITE_FRAME_FILENAME,
    RENDERED_BOARD_OUTPUT_PATH, ANIMATION_FRAMES_OUTPUT_DIR,
    MOVE_LOG_PANEL_WIDTH_PX, MOVE_LOG_BG_COLOR, MOVE_LOG_HEADER_COLOR,
    MOVE_LOG_WHITE_TEXT_COLOR, MOVE_LOG_BLACK_TEXT_COLOR, MOVE_LOG_FONT_SCALE,
    MOVE_LOG_LINE_HEIGHT_PX, MOVE_LOG_HEADER_HEIGHT_PX, MOVE_LOG_PADDING_PX,
    SCORE_PANEL_HEIGHT_PX, SCORE_WHITE_TEXT_COLOR, SCORE_BLACK_TEXT_COLOR,
    SCORE_FONT_SCALE, SCORE_LINE_HEIGHT_PX, SCORE_HEADER_HEIGHT_PX, SCORE_PADDING_PX,
    BOARD_HIGHLIGHT_LAST_MOVE, BOARD_LAST_MOVE_COLOR, BOARD_LAST_MOVE_ALPHA,
    BOARD_SHOW_COORDINATES, BOARD_COORDINATE_COLOR, BOARD_COORDINATE_FONT_SCALE,
    BOARD_COORDINATE_THICKNESS, BOARD_COORDINATE_MARGIN_PX,
    BOARD_COORDINATE_OUTLINE_COLOR, BOARD_COORDINATE_OUTLINE_THICKNESS,
)
from ui.animation.animation_config_loader import load_animation_configs
from ui.animation.piece_animator import PieceAnimator
from ui.graphics.sprite_resolver import SpriteResolver
from ui.graphics.sprite_loader import SpriteLoader
from ui.graphics.renderer import BoardRenderer
from ui.graphics.move_log_panel import MoveLogPanel
from ui.graphics.score_panel import ScorePanel
from ui.graphics.board_theme import BoardTheme
from ui.graphics.img_canvas import ImgCanvas
from ui.app import build_visual_states
from ui.board_geometry import BoardGeometry
from ui.click_handler import ClickHandler
from ui.demo_driver import FrameWriter, run_move_and_capture, write_image
from ui.game_loop import run_game_loop

STARTING_BOARD = (
    "bR bN bB bQ bK bB bN bR\n"
    "bP bP bP bP bP bP bP bP\n"
    ".  .  .  .  .  .  .  .\n"
    ".  .  .  .  .  .  .  .\n"
    ".  .  .  .  .  .  .  .\n"
    ".  .  .  .  .  .  .  .\n"
    "wP wP wP wP wP wP wP wP\n"
    "wR wN wB wQ wK wB wN wR"
)


def cell_center_px(row: int, col: int) -> tuple:
    return BoardGeometry(CELL_SIZE_PX).cell_center(Position(row, col))


def print_scores(session) -> None:
    """Text dump of the running score, built from a kfchess.api Scoreboard DTO."""
    scoreboard = session.scoreboard()
    print(f"White: {scoreboard.white}  Black: {scoreboard.black}")


def print_board(session) -> None:
    """Text dump of the current board, built from a kfchess.api BoardSnapshot DTO."""
    snapshot = session.board_snapshot()
    grid = [["." for _ in range(snapshot.cols)] for _ in range(snapshot.rows)]
    for piece_view in snapshot.pieces():
        grid[piece_view.cell.row][piece_view.cell.col] = piece_view.symbol
    for row in grid:
        print(" ".join(row))


def _build_scene(window_title: str):
    """Wires the full render/input/animation stack, returning the pieces both entry points share."""
    session = create_game_session(STARTING_BOARD)
    click_handler = ClickHandler(session, BoardGeometry(CELL_SIZE_PX))
    animator = PieceAnimator(load_animation_configs(PIECES_DIR))

    canvas = ImgCanvas(window_title)
    resolver = SpriteResolver(PIECES_DIR, SPRITE_STATE, SPRITE_FRAME_FILENAME)
    sprite_loader = SpriteLoader(canvas, resolver, sprite_size_px=(CELL_SIZE_PX, CELL_SIZE_PX))
    move_log_panel = MoveLogPanel(
        width_px=MOVE_LOG_PANEL_WIDTH_PX, bg_color=MOVE_LOG_BG_COLOR,
        header_color=MOVE_LOG_HEADER_COLOR, white_text_color=MOVE_LOG_WHITE_TEXT_COLOR,
        black_text_color=MOVE_LOG_BLACK_TEXT_COLOR, font_scale=MOVE_LOG_FONT_SCALE,
        line_height_px=MOVE_LOG_LINE_HEIGHT_PX, header_height_px=MOVE_LOG_HEADER_HEIGHT_PX,
        padding_px=MOVE_LOG_PADDING_PX, top_offset_px=SCORE_PANEL_HEIGHT_PX,
    )
    score_panel = ScorePanel(
        height_px=SCORE_PANEL_HEIGHT_PX, white_text_color=SCORE_WHITE_TEXT_COLOR,
        black_text_color=SCORE_BLACK_TEXT_COLOR, font_scale=SCORE_FONT_SCALE,
        line_height_px=SCORE_LINE_HEIGHT_PX, header_height_px=SCORE_HEADER_HEIGHT_PX,
        padding_px=SCORE_PADDING_PX,
    )
    board_theme = BoardTheme(
        highlight_last_move=BOARD_HIGHLIGHT_LAST_MOVE, last_move_color=BOARD_LAST_MOVE_COLOR,
        last_move_alpha=BOARD_LAST_MOVE_ALPHA, show_coordinates=BOARD_SHOW_COORDINATES,
        coordinate_color=BOARD_COORDINATE_COLOR, coordinate_font_scale=BOARD_COORDINATE_FONT_SCALE,
        coordinate_thickness=BOARD_COORDINATE_THICKNESS, coordinate_margin_px=BOARD_COORDINATE_MARGIN_PX,
        coordinate_outline_color=BOARD_COORDINATE_OUTLINE_COLOR,
        coordinate_outline_thickness=BOARD_COORDINATE_OUTLINE_THICKNESS,
    )
    renderer = BoardRenderer(
        canvas, sprite_loader, BOARD_IMAGE_PATH, CELL_SIZE_PX, move_log_panel, score_panel, board_theme
    )
    return session, click_handler, animator, canvas, renderer


def main() -> None:
    """Real interactive game: a human clicks pieces in the live window to play in real time."""
    session, click_handler, animator, canvas, renderer = _build_scene("Kung-Fu-Chess")

    print("Starting board:")
    print_board(session)
    print("\nClick a piece, then its destination. Press Esc or q to quit.")

    try:
        run_game_loop(canvas, session, click_handler, animator, renderer, CELL_SIZE_PX)
    finally:
        canvas.close()

    print("\nFinal board:")
    print_board(session)
    print("\nFinal score:")
    print_scores(session)


def run_capture_demo(show_window: bool = True) -> None:
    """Deterministic scripted demo: plays two fixed opening moves and captures every tick to disk."""
    session, click_handler, animator, canvas, renderer = _build_scene("Kung-Fu-Chess - Stage 4 motion demo")
    live_canvas = canvas if show_window else None

    ANIMATION_FRAMES_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frame_writer = FrameWriter(canvas, ANIMATION_FRAMES_OUTPUT_DIR)

    print("Starting board:")
    print_board(session)

    try:
        # White pawn opening move: e2-e4, a 2-cell slide (row 6,col4 -> row 4,col4).
        pawn = session.piece_at(Position(6, 4))
        select_x, select_y = cell_center_px(6, 4)
        dest_x, dest_y = cell_center_px(4, 4)
        click_handler.on_click(select_x, select_y)
        click_handler.on_click(dest_x, dest_y)
        run_move_and_capture(
            session, animator, renderer, frame_writer, pawn.piece_id,
            "pawn slide (2 cells)", CELL_SIZE_PX, live_canvas,
        )

        print("\nBoard after the pawn's opening move:")
        print_board(session)

        # White knight opening move: Nb1-c3 (row 7,col1 -> row 5,col2) - exercises
        # the "jump" animation, since JumpingProfile is what covers a knight move.
        knight = session.piece_at(Position(7, 1))
        select_x, select_y = cell_center_px(7, 1)
        dest_x, dest_y = cell_center_px(5, 2)
        click_handler.on_click(select_x, select_y)
        click_handler.on_click(dest_x, dest_y)
        run_move_and_capture(
            session, animator, renderer, frame_writer, knight.piece_id,
            "knight jump", CELL_SIZE_PX, live_canvas,
        )

        print("\nBoard after the knight's opening move:")
        print_board(session)
    finally:
        canvas.close()

    rendered = renderer.render(
        session.board_snapshot(),
        build_visual_states(
            session, animator,
            engine_ms=session.clock_ms, render_ms=session.clock_ms,
            cell_size_px=CELL_SIZE_PX,
        ),
    )
    write_image(canvas, RENDERED_BOARD_OUTPUT_PATH, rendered)
    print(f"\nRendered board image saved to: {RENDERED_BOARD_OUTPUT_PATH}")
    print(f"Per-tick animation frames saved under: {ANIMATION_FRAMES_OUTPUT_DIR} ({frame_writer.frames_written} frames)")


if __name__ == "__main__":  # pragma: no cover - script entry point, not exercised by imports
    if "--demo" in sys.argv:
        run_capture_demo(show_window="--no-window" not in sys.argv)
    else:
        main()
