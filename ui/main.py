import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kfchess.api import Position, create_game_session

from controller.factory import build_game_controller

from ui.ui_config import (
    CELL_SIZE_PX, BOARD_IMAGE_PATH, PIECES_DIR, SPRITE_STATE, SPRITE_FRAME_FILENAME,
    RENDERED_BOARD_OUTPUT_PATH, ANIMATION_FRAMES_OUTPUT_DIR,
)
from ui.animation.animation_config_loader import load_animation_configs
from ui.animation.piece_animator import PieceAnimator
from ui.graphics.sprite_resolver import SpriteResolver
from ui.graphics.sprite_loader import SpriteLoader
from ui.graphics.renderer import BoardRenderer
from ui.graphics.window import Window
from ui.app import build_visual_states
from ui.demo_driver import FrameWriter, run_move_and_capture, write_image

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
    return col * CELL_SIZE_PX + CELL_SIZE_PX // 2, row * CELL_SIZE_PX + CELL_SIZE_PX // 2


def print_board(game_controller) -> None:
    """Text dump of the current board, built from controller.api.BoardSnapshot rather than any kfchess type."""
    snapshot = game_controller.board_snapshot()
    grid = [["." for _ in range(snapshot.cols)] for _ in range(snapshot.rows)]
    for piece_view in snapshot.pieces():
        grid[piece_view.cell.row][piece_view.cell.col] = piece_view.symbol
    for row in grid:
        print(" ".join(row))


def main(show_window: bool = True) -> None:
    session = create_game_session(STARTING_BOARD)
    game_controller = build_game_controller(session, cell_size_px=CELL_SIZE_PX)
    animator = PieceAnimator(load_animation_configs(PIECES_DIR))

    resolver = SpriteResolver(PIECES_DIR, SPRITE_STATE, SPRITE_FRAME_FILENAME)
    sprite_loader = SpriteLoader(resolver, sprite_size_px=(CELL_SIZE_PX, CELL_SIZE_PX))
    renderer = BoardRenderer(sprite_loader, BOARD_IMAGE_PATH, CELL_SIZE_PX)
    window = Window("Kung-Fu-Chess - Stage 4 motion demo") if show_window else None

    ANIMATION_FRAMES_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frame_writer = FrameWriter(ANIMATION_FRAMES_OUTPUT_DIR)

    print("Starting board:")
    print_board(game_controller)

    try:
        # White pawn opening move: e2-e4, a 2-cell slide (row 6,col4 -> row 4,col4).
        pawn = game_controller.piece_at(Position(6, 4))
        select_x, select_y = cell_center_px(6, 4)
        dest_x, dest_y = cell_center_px(4, 4)
        game_controller.on_click(select_x, select_y)
        game_controller.on_click(dest_x, dest_y)
        run_move_and_capture(
            game_controller, animator, renderer, frame_writer, pawn.piece_id,
            "pawn slide (2 cells)", CELL_SIZE_PX, window,
        )

        print("\nBoard after the pawn's opening move:")
        print_board(game_controller)

        # White knight opening move: Nb1-c3 (row 7,col1 -> row 5,col2) - exercises
        # the "jump" animation, since JumpingProfile is what covers a knight move.
        knight = game_controller.piece_at(Position(7, 1))
        select_x, select_y = cell_center_px(7, 1)
        dest_x, dest_y = cell_center_px(5, 2)
        game_controller.on_click(select_x, select_y)
        game_controller.on_click(dest_x, dest_y)
        run_move_and_capture(
            game_controller, animator, renderer, frame_writer, knight.piece_id,
            "knight jump", CELL_SIZE_PX, window,
        )

        print("\nBoard after the knight's opening move:")
        print_board(game_controller)
    finally:
        if window is not None:
            window.close()

    rendered = renderer.render(
        game_controller.board_snapshot(),
        build_visual_states(game_controller, animator, game_controller.clock_ms, CELL_SIZE_PX),
    )
    write_image(RENDERED_BOARD_OUTPUT_PATH, rendered)
    print(f"\nRendered board image saved to: {RENDERED_BOARD_OUTPUT_PATH}")
    print(f"Per-tick animation frames saved under: {ANIMATION_FRAMES_OUTPUT_DIR} ({frame_writer.frames_written} frames)")


if __name__ == "__main__":  # pragma: no cover - script entry point, not exercised by imports
    main(show_window="--no-window" not in sys.argv)
