from pathlib import Path

# Rendering cell size in pixels - owned entirely by ui, independent of any
# engine-side timing constant (kfchess's own per-cell duration is a
# separate, unrelated number that happens to live in kfchess.realtime).
CELL_SIZE_PX = 100
BOARD_ROWS = 8
BOARD_COLS = 8

# Asset locations, kept under ui/assets/ so data is separate from code.
# Centralized here so a reskin (or moving assets again) is a one-line change.
UI_DIR = Path(__file__).resolve().parent
ASSETS_DIR = UI_DIR / "assets"
BOARD_IMAGE_PATH = ASSETS_DIR / "board.png"
PIECES_DIR = ASSETS_DIR / "pieces1"      # default skin; swap to pieces2 (or any other) to reskin
SPRITE_STATE = "idle"                    # which animation state supplies the static sprite
SPRITE_FRAME_FILENAME = "1.png"          # which frame of that state
RENDERED_BOARD_OUTPUT_PATH = UI_DIR / "rendered_board.png"
ANIMATION_FRAMES_OUTPUT_DIR = UI_DIR / "frames"
