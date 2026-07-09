from pieces import King
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.rules.move_result import MoveRejectionReason, MoveValidationResult
from kfchess.rules.rule_engine import RuleEngine
from kfchess.engine.real_time_arbiter import RealTimeArbiter, MoveOutcomeStatus


class GameEngine:
    """
    Application service layer. Coordinates move validation, movement
    initiation (via RealTimeArbiter), and termination conditions.
    """

    def __init__(self, board: Board, rule_engine: RuleEngine, arbiter: RealTimeArbiter):
        self._board = board
        self._rule_engine = rule_engine
        self._arbiter = arbiter
        self.game_over = False

    @property
    def clock_ms(self) -> int:
        return self._arbiter.clock_ms

    def is_moving(self, piece) -> bool:
        return self._arbiter.is_moving(piece)

    def piece_at(self, pos: Position):
        return self._board.get(pos)

    def is_within_bounds(self, pos: Position) -> bool:
        return self._board.is_within_bounds(pos)

    def request_move(self, from_pos: Position, to_pos: Position) -> MoveValidationResult:
        if self.game_over:
            return MoveValidationResult.reject(MoveRejectionReason.GAME_OVER)

        result = self._rule_engine.validate(self._board, from_pos, to_pos)
        if not result.legal:
            return result

        piece = self._board.get(from_pos)
        self._arbiter.begin_move(piece, from_pos, to_pos)
        return MoveValidationResult.ok()

    def advance_clock(self, ms: int) -> None:
        outcomes = self._arbiter.advance(ms)

        king_captured = any(
            outcome.status is MoveOutcomeStatus.EXECUTED and isinstance(outcome.captured_piece, King)
            for outcome in outcomes
        )
        if king_captured:
            self.game_over = True
            self._arbiter.cancel_all_pending()
