from kfchess.model.piece import King
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.model.game_state import GameState
from kfchess.rules.move_result import MoveRejectionReason, MoveValidationResult
from kfchess.rules.rule_engine import RuleEngine
from kfchess.realtime.real_time_arbiter import RealTimeArbiter
from kfchess.realtime.motion import MoveOutcomeStatus
from kfchess.engine.game_snapshot import GameSnapshot


class GameEngine:
    """
    Application service layer. Coordinates move validation, movement
    initiation (via RealTimeArbiter), and termination conditions.
    """

    def __init__(self, board: Board, rule_engine: RuleEngine, arbiter: RealTimeArbiter):
        self._board = board
        self._rule_engine = rule_engine
        self._arbiter = arbiter
        self._state = GameState()

    @property
    def game_over(self) -> bool:
        return self._state.game_over

    @game_over.setter
    def game_over(self, value: bool) -> None:
        self._state.game_over = value

    @property
    def clock_ms(self) -> int:
        return self._arbiter.clock_ms

    def is_moving(self, piece) -> bool:
        return self._arbiter.is_moving(piece)

    def piece_at(self, pos: Position):
        return self._board.get(pos)

    def is_within_bounds(self, pos: Position) -> bool:
        return self._board.is_within_bounds(pos)

    def snapshot(self) -> GameSnapshot:
        return GameSnapshot.of(self._board, clock_ms=self.clock_ms, game_over=self.game_over)

    def request_move(self, from_pos: Position, to_pos: Position) -> MoveValidationResult:
        if self.game_over:
            return MoveValidationResult.reject(MoveRejectionReason.GAME_OVER)

        result = self._rule_engine.validate(self._board, from_pos, to_pos)
        if not result.legal:
            return result

        piece = self._board.get(from_pos)
        if from_pos == to_pos and self._arbiter.is_moving(piece):
            return MoveValidationResult.reject(MoveRejectionReason.PIECE_ALREADY_MOVING)

        self._arbiter.begin_move(piece, from_pos, to_pos)
        return MoveValidationResult.ok()

    def advance_clock(self, ms: int) -> None:
        outcomes = self._arbiter.advance(ms)

        king_captured = any(self._is_king_captured(outcome) for outcome in outcomes)
        if king_captured:
            self.game_over = True
            self._arbiter.cancel_all_pending()

    @staticmethod
    def _is_king_captured(outcome) -> bool:
        if outcome.status is MoveOutcomeStatus.EXECUTED:
            return isinstance(outcome.captured_piece, King)
        if outcome.status is MoveOutcomeStatus.CAPTURED_ON_ARRIVAL:
            return isinstance(outcome.piece, King)
        return False
