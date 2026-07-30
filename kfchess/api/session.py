from typing import List, Optional, Protocol, runtime_checkable

from kfchess.api import engine_mapping
from kfchess.api.dto import BoardSnapshot, MotionInfo, MoveLogEntry, MoveResult, PieceView, Position, Scoreboard
from kfchess.api.events import EngineEvent, EngineEventKind, EngineEventSink
from kfchess.engine.game_engine import GameEngine


@runtime_checkable
class GameSession(Protocol):
    """
    The only contract kfchess exposes outside itself. Everything here deals
    in Positions and DTOs (PieceView/BoardSnapshot/MotionInfo/MoveResult) -
    never a live kfchess.model.Piece, never a kfchess-internal enum.
    """

    @property
    def clock_ms(self) -> int: ...

    @property
    def game_over(self) -> bool: ...

    @property
    def winner(self) -> Optional[str]: ...

    def is_within_bounds(self, pos: Position) -> bool: ...

    def piece_at(self, pos: Position) -> Optional[PieceView]: ...

    def request_move(self, from_pos: Position, to_pos: Position) -> MoveResult: ...

    def wait(self, ms: int) -> None: ...

    def is_moving(self, piece_id: int) -> bool: ...

    def board_snapshot(self) -> BoardSnapshot: ...

    def motion_for(self, piece_id: int) -> Optional[MotionInfo]: ...

    def move_log(self) -> List[MoveLogEntry]: ...

    def scoreboard(self) -> Scoreboard: ...


class EngineGameSession:
    """
    Adapts a kfchess.engine.GameEngine to the GameSession contract. Its sole
    job is delegation: it forwards calls to the engine and routes the raw
    Piece/motion objects through kfchess.api.engine_mapping for DTO
    translation. All knowledge of engine internals (attribute renames,
    grid traversal, piece_id lookup) lives in that mapping module, not here.
    """

    def __init__(self, engine: GameEngine, event_sink: Optional[EngineEventSink] = None):
        self._engine = engine
        self._event_sink = event_sink

    @property
    def clock_ms(self) -> int:
        return self._engine.clock_ms

    @property
    def game_over(self) -> bool:
        return self._engine.game_over

    @property
    def winner(self) -> Optional[str]:
        return self._engine.winner

    def is_within_bounds(self, pos: Position) -> bool:
        return self._engine.is_within_bounds(pos)

    def piece_at(self, pos: Position) -> Optional[PieceView]:
        piece = self._engine.piece_at(pos)
        return engine_mapping.piece_to_view(piece) if piece is not None else None

    def request_move(self, from_pos: Position, to_pos: Position) -> MoveResult:
        return self._engine.request_move(from_pos, to_pos)

    def wait(self, ms: int) -> None:
        was_over = self._engine.game_over
        outcomes = self._engine.wait(ms)
        if self._event_sink is None:
            return
        for outcome in outcomes:
            self._event_sink.emit(engine_mapping.outcome_to_event(outcome, self._engine.clock_ms))
        if not was_over and self._engine.game_over:
            self._event_sink.emit(
                EngineEvent(
                    kind=EngineEventKind.GAME_OVER,
                    at_ms=self._engine.clock_ms,
                    piece=None,
                    from_pos=None,
                    to_pos=None,
                    captured=None,
                    beneficiary_color=self._engine.winner,
                )
            )

    def is_moving(self, piece_id: int) -> bool:
        piece = engine_mapping.find_piece_by_id(self._engine.board_grid(), piece_id)
        return piece is not None and self._engine.is_moving(piece)

    def board_snapshot(self) -> BoardSnapshot:
        return engine_mapping.snapshot_from_grid(self._engine.board_grid())

    def motion_for(self, piece_id: int) -> Optional[MotionInfo]:
        piece = engine_mapping.find_piece_by_id(self._engine.board_grid(), piece_id)
        if piece is None:
            return None
        motion = self._engine.motion_for(piece)
        return engine_mapping.motion_to_info(motion) if motion is not None else None

    def move_log(self) -> List[MoveLogEntry]:
        return [engine_mapping.move_record_to_entry(record) for record in self._engine.move_log()]

    def scoreboard(self) -> Scoreboard:
        return engine_mapping.scoreboard_from_scores(self._engine.scores())
