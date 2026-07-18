from typing import Optional

from kfchess.api import BoardSnapshot, GameSession, MotionInfo, Position, Scoreboard

from controller.board_mapper import BoardMapper


class GameController:
    """
    Orchestration layer between ui and kfchess. Merges what used to be
    kfchess.input.Controller (pixel-click -> selection/move-request state
    machine) and ui.state.PendingMotionTracker (motion queries for the
    view) into one collaborator that speaks only kfchess.api DTOs - never
    a live kfchess.model.Piece, never a kfchess-internal enum. Motion state
    is never cached here: kfchess.api.GameSession.motion_for already
    answers live from the engine, so there is nothing to keep in sync.
    """

    def __init__(self, session: GameSession, board_mapper: BoardMapper):
        self._session = session
        self._board_mapper = board_mapper
        self.selected: Optional[Position] = None

    def on_click(self, x: int, y: int) -> None:
        pos = self._board_mapper.pixel_to_position(x, y)

        if not self._session.is_within_bounds(pos):
            self.selected = None
            return

        target = self._session.piece_at(pos)

        if self.selected is None:
            if target is not None:
                self.selected = pos
            return

        selected_piece = self._session.piece_at(self.selected)
        if pos != self.selected and target is not None and selected_piece is not None \
                and target.color == selected_piece.color:
            self.selected = pos
            return

        self._session.request_move(self.selected, pos)
        self.selected = None

    def advance(self, ms: int) -> None:
        self._session.wait(ms)

    def piece_at(self, pos: Position):
        return self._session.piece_at(pos)

    @property
    def clock_ms(self) -> int:
        return self._session.clock_ms

    @property
    def is_game_over(self) -> bool:
        return self._session.game_over

    def board_snapshot(self) -> BoardSnapshot:
        return self._session.board_snapshot()

    def motion_for(self, piece_id: int) -> Optional[MotionInfo]:
        return self._session.motion_for(piece_id)

    def move_log(self):
        return self._session.move_log()

    def scoreboard(self) -> Scoreboard:
        return self._session.scoreboard()
