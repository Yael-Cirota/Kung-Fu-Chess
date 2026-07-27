"""Holds the most recent server-authoritative state this client has
received. StateUpdate is the sole writer of position (see 'StateUpdate ...
remains the sole authority for position'); GameStarted supplies board
dimensions once, and GameEnded supplies the winner. A DeltaEvent never
touches this store - it is advisory-only (see 'Event-driven broadcasting')."""

from typing import Dict, List, Optional

from kfchess.api.dto import BoardSnapshot, MotionInfo, MoveLogEntry, PieceView, Position, Scoreboard
from protocol import messages as m


class SnapshotStore:
    def __init__(self):
        self._rows = 0
        self._cols = 0
        self._server_ms = 0
        self._pieces: List[PieceView] = []
        self._motions: Dict[int, MotionInfo] = {}
        self._move_log: List[MoveLogEntry] = []
        self._scoreboard = Scoreboard(white=0, black=0)
        self._game_over = False
        self._winner: Optional[str] = None

    def apply_game_started(self, message: m.GameStarted) -> None:
        self._rows = message.rows
        self._cols = message.cols
        self._server_ms = message.server_ms

    def apply_state_update(self, message: m.StateUpdate) -> None:
        self._server_ms = message.server_ms
        self._pieces = list(message.pieces)
        self._motions = {entry.piece_id: entry.motion for entry in message.motions}
        self._move_log = list(message.move_log)
        self._scoreboard = message.scoreboard
        self._game_over = message.game_over

    def apply_game_ended(self, message: m.GameEnded) -> None:
        self._game_over = True
        self._winner = message.winner

    @property
    def server_ms(self) -> int:
        return self._server_ms

    @property
    def game_over(self) -> bool:
        return self._game_over

    @property
    def winner(self) -> Optional[str]:
        return self._winner

    def is_within_bounds(self, pos: Position) -> bool:
        return 0 <= pos.row < self._rows and 0 <= pos.col < self._cols

    def piece_at(self, pos: Position) -> Optional[PieceView]:
        for piece in self._pieces:
            if piece.cell == pos:
                return piece
        return None

    def board_snapshot(self) -> BoardSnapshot:
        return BoardSnapshot(rows=self._rows, cols=self._cols, piece_views=list(self._pieces))

    def motion_for(self, piece_id: int) -> Optional[MotionInfo]:
        return self._motions.get(piece_id)

    def move_log(self) -> List[MoveLogEntry]:
        return list(self._move_log)

    def scoreboard(self) -> Scoreboard:
        return self._scoreboard
