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
PIECES_DIR = ASSETS_DIR / "pieces"       # default skin; swap to any other skin folder to reskin
SPRITE_STATE = "idle"                    # which animation state supplies the static sprite
SPRITE_FRAME_FILENAME = "1.png"          # which frame of that state
RENDERED_BOARD_OUTPUT_PATH = UI_DIR / "rendered_board.png"
ANIMATION_FRAMES_OUTPUT_DIR = UI_DIR / "frames"

# Sound effects, keyed by the names GameAudioTracker/main.py play() calls use.
SOUNDS_DIR = ASSETS_DIR / "sounds"
MOVE_SOUND_PATH = SOUNDS_DIR / "move.wav"
CAPTURE_SOUND_PATH = SOUNDS_DIR / "capture.wav"
WIN_SOUND_PATH = SOUNDS_DIR / "win.wav"

# Move-log side panel (drawn to the right of the board so board pixels - and
# therefore click-to-cell mapping - stay at the origin, unchanged). Colors are
# BGR to match OpenCV. The panel splits into a White column and a Black column
# so each player reads back only the moves they issued.
MOVE_LOG_PANEL_WIDTH_PX = 280
MOVE_LOG_BG_COLOR = (32, 32, 32)
MOVE_LOG_HEADER_COLOR = (180, 180, 180)
MOVE_LOG_WHITE_TEXT_COLOR = (240, 240, 240)
MOVE_LOG_BLACK_TEXT_COLOR = (120, 200, 120)
MOVE_LOG_FONT_SCALE = 0.5
MOVE_LOG_LINE_HEIGHT_PX = 22
MOVE_LOG_HEADER_HEIGHT_PX = 30
MOVE_LOG_PADDING_PX = 12

# Score band, drawn at the top of the same right-hand strip (above the move
# log, which is pushed down by SCORE_PANEL_HEIGHT_PX). Shows each player's
# running capture-point total. Colors are BGR to match OpenCV.
SCORE_PANEL_HEIGHT_PX = 64
SCORE_WHITE_TEXT_COLOR = (240, 240, 240)
SCORE_BLACK_TEXT_COLOR = (120, 200, 120)
SCORE_FONT_SCALE = 0.7
SCORE_LINE_HEIGHT_PX = 26
SCORE_HEADER_HEIGHT_PX = 24
SCORE_PADDING_PX = 12

# Cosmetic board overlays (last-move highlight, selected-piece highlight,
# edge coordinate labels). These draw only *over* the board pixels, never
# shifting geometry or click mapping.
# Off by default: a piece's cell should only stay marked while it is the
# active selection (see BOARD_HIGHLIGHT_SELECTED below), not linger green
# after the move has already landed.
BOARD_HIGHLIGHT_LAST_MOVE = False
BOARD_LAST_MOVE_COLOR = (90, 200, 130)   # BGR: soft green
BOARD_LAST_MOVE_ALPHA = 0.30
BOARD_HIGHLIGHT_SELECTED = True
BOARD_SELECTED_COLOR = (60, 170, 250)    # BGR: warm amber
BOARD_SELECTED_ALPHA = 0.35
BOARD_SHOW_COORDINATES = True
BOARD_COORDINATE_COLOR = (230, 230, 230)  # BGR: near-white glyph
BOARD_COORDINATE_FONT_SCALE = 0.38
BOARD_COORDINATE_THICKNESS = 1
BOARD_COORDINATE_MARGIN_PX = 5
BOARD_COORDINATE_OUTLINE_COLOR = (30, 30, 30)  # BGR: near-black halo for contrast
BOARD_COORDINATE_OUTLINE_THICKNESS = 3

# Winner overlay, shown over the board once the game ends. Timed off the wall
# clock, so it keeps animating even though the engine clock is frozen at that
# point. Colors are BGR to match OpenCV.
WINNER_DISPLAY_DURATION_MS = 4500
WINNER_BACKDROP_COLOR = (20, 20, 20)       # BGR: near-black wash
WINNER_BACKDROP_MAX_ALPHA = 0.65
WINNER_FADE_IN_MS = 400
WINNER_TITLE_WHITE_COLOR = (245, 245, 245)  # BGR: near-white
WINNER_TITLE_BLACK_COLOR = (120, 200, 120)  # BGR: soft green, matches the black move-log column
WINNER_TITLE_BASE_FONT_SCALE = 1.6
WINNER_TITLE_PULSE_AMPLITUDE = 0.08
WINNER_TITLE_PULSE_PERIOD_MS = 1400
WINNER_TITLE_THICKNESS = 3
WINNER_SUBTITLE_COLOR = (210, 210, 210)
WINNER_SUBTITLE_FONT_SCALE = 0.8
WINNER_SUBTITLE_THICKNESS = 2
WINNER_TITLE_TO_SUBTITLE_GAP_PX = 46
