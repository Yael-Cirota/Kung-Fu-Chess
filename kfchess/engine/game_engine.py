from kfchess.model.piece import PieceKind
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.model.game_state import GameState
from kfchess.rules.move_validation import MoveRejectionReason
from kfchess.rules.rule_engine import RuleEngine
from kfchess.realtime.real_time_arbiter import RealTimeArbiter
from kfchess.realtime.motion import MoveOutcomeStatus
from kfchess.engine.move_result import MoveResult


class GameEngine:
    """
    Application-service adapter: the public command boundary used by
    Controller and TextTestRunner. Owns game_over and enforces
    application-level guards (game over, motion already active on the
    shared track) before ever asking RuleEngine whether a move is
    legal. Validated moves are handed to RealTimeArbiter to begin a
    Motion; simulated time advances there too. Carries no piece rules,
    pixel mapping, rendering, or text parsing of its own.
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

    def request_move(self, from_pos: Position, to_pos: Position) -> MoveResult:
        if self.game_over:
            return MoveResult.rejected(MoveRejectionReason.GAME_OVER)

        piece = self._board.get(from_pos)
        if piece is not None and self._arbiter.is_moving(piece):
            return MoveResult.rejected(MoveRejectionReason.MOTION_IN_PROGRESS)

        validation = self._rule_engine.validate(self._board, from_pos, to_pos)
        if not validation.is_valid:
            return MoveResult.rejected(validation.reason)

        self._arbiter.begin_move(piece, from_pos, to_pos)
        return MoveResult.accepted()

    def wait(self, ms: int) -> None:
        """
        Advances simulated time by delegating strictly to RealTimeArbiter,
        which owns all Motion state and board mutation on arrival.
        GameEngine never mutates the Board's motion state itself - it only
        reads the returned outcomes to decide the win condition.
        """
        outcomes = self._arbiter.advance(ms)

        king_captured = any(self._is_king_captured(outcome) for outcome in outcomes)
        if king_captured:
            self.game_over = True
            self._arbiter.cancel_all_pending()

    @staticmethod
    def _is_king_captured(outcome) -> bool:
        if outcome.status is MoveOutcomeStatus.EXECUTED:
            return outcome.captured_piece is not None and outcome.captured_piece.kind is PieceKind.KING
        if outcome.status is MoveOutcomeStatus.CAPTURED_ON_ARRIVAL:
            return outcome.piece.kind is PieceKind.KING
        return False
