from typing import Callable, Optional, Set

from kfchess.api import BoardSnapshot, MotionInfo

from ui.audio.sound_board import SoundBoard

MotionLookup = Callable[[int], Optional[MotionInfo]]


class GameAudioTracker:
    """
    Watches BoardSnapshot + per-piece motion across frames and triggers sound
    effects on the transitions that matter, entirely by diffing - like
    build_visual_states, it never touches a kfchess-internal type and holds
    only what it needs to detect the next transition.

    - "move": a piece that wasn't in motion last frame is in motion now.
    - "capture": the piece count dropped since last frame (the only way a
      piece disappears, since this ruleset has no promotion or spawning).

    The first update() call only establishes a baseline; nothing plays until
    a second frame gives it something to diff against.
    """

    def __init__(self, sound_board: SoundBoard):
        self._sound_board = sound_board
        self._previous_piece_ids: Optional[Set[int]] = None
        self._previous_moving_ids: Optional[Set[int]] = None

    def update(self, board_snapshot: BoardSnapshot, motion_for: MotionLookup) -> None:
        piece_ids = set()
        moving_ids = set()
        for piece in board_snapshot.pieces():
            piece_ids.add(piece.piece_id)
            if motion_for(piece.piece_id) is not None:
                moving_ids.add(piece.piece_id)

        if self._previous_piece_ids is not None and len(piece_ids) < len(self._previous_piece_ids):
            self._sound_board.play("capture")

        if self._previous_moving_ids is not None and moving_ids - self._previous_moving_ids:
            self._sound_board.play("move")

        self._previous_piece_ids = piece_ids
        self._previous_moving_ids = moving_ids
