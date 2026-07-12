from typing import List, Set

from kfchess.model.board import Board
from kfchess.model.piece import PieceState
from kfchess.model.position import Position
from kfchess.rules.rule_engine import RuleEngine
from kfchess.realtime.motion import MoveOutcome, MoveOutcomeStatus, PendingMove

CELL_SIZE = 100        # pixels
PIECE_SPEED = 100      # pixels per second

# Deterministic per-cell duration, derived from CELL_SIZE / PIECE_SPEED.
# Cell-steps (Chebyshev distance), not Euclidean pixel distance, drive
# timing - a 3-cell diagonal move takes exactly 3x this, same as a
# 3-cell orthogonal move.
MOVE_DURATION_MS_PER_CELL = int(CELL_SIZE / PIECE_SPEED * 1000)

JUMP_DURATION_MS = MOVE_DURATION_MS_PER_CELL


class RealTimeArbiter:
    """
    Manages active movement objects, advances simulated time, and
    performs atomic execution of arrival and capture. The board is
    mutated only here, only atomically, only on arrival.
    """

    def __init__(self, board: Board, rule_engine: RuleEngine):
        self._board = board
        self._rule_engine = rule_engine
        self._clock_ms = 0
        self._pending: List[PendingMove] = []
        self._moving: Set = set()
        self._airborne: Set = set()

    @property
    def clock_ms(self) -> int:
        return self._clock_ms

    def is_moving(self, piece) -> bool:
        return piece in self._moving

    def is_airborne(self, piece) -> bool:
        return piece in self._airborne

    def begin_move(self, piece, from_pos: Position, to_pos: Position) -> None:
        if from_pos == to_pos:
            execute_at = self._clock_ms + JUMP_DURATION_MS
            self._airborne.add(piece)
        else:
            dr = abs(to_pos.row - from_pos.row)
            dc = abs(to_pos.col - from_pos.col)
            distance = max(dr, dc)
            execute_at = self._clock_ms + distance * MOVE_DURATION_MS_PER_CELL

        self._pending.append(PendingMove(piece, from_pos, to_pos, execute_at))
        self._moving.add(piece)
        piece.state = PieceState.MOVING

    def advance(self, ms: int) -> List[MoveOutcome]:
        self._clock_ms += ms

        ready = sorted(
            (m for m in self._pending if m.execute_at <= self._clock_ms),
            key=lambda m: m.execute_at,
        )
        self._pending = [m for m in self._pending if m.execute_at > self._clock_ms]

        still_airborne = frozenset(self._airborne)
        return [self._mature(move, still_airborne) for move in ready]

    def abort(self, piece) -> None:
        self._release(piece)

    def cancel_all_pending(self) -> None:
        """Drops every move not yet matured (used to end all further play, e.g. on game over)."""
        self._pending = []

    def _release(self, piece) -> None:
        self._moving.discard(piece)
        self._airborne.discard(piece)
        if piece.state is not PieceState.CAPTURED:
            piece.state = PieceState.IDLE

    def _mature(self, move: PendingMove, still_airborne: frozenset) -> MoveOutcome:
        piece, from_pos, to_pos = move.piece, move.from_pos, move.to_pos

        if self._board.get(from_pos) is not piece:
            self._release(piece)
            return MoveOutcome(MoveOutcomeStatus.ABORTED_PREMOVE, piece, from_pos, to_pos)

        if from_pos == to_pos:
            self._release(piece)
            return MoveOutcome(MoveOutcomeStatus.EXECUTED, piece, from_pos, to_pos)

        result = self._rule_engine.validate(self._board, from_pos, to_pos)
        if not result.is_valid:
            self._release(piece)
            return MoveOutcome(MoveOutcomeStatus.ABORTED_ILLEGAL, piece, from_pos, to_pos)

        defender = self._board.get(to_pos)
        if defender is not None and defender in still_airborne:
            self._board.move_piece(from_pos)
            piece.state = PieceState.CAPTURED
            self._release(piece)
            return MoveOutcome(MoveOutcomeStatus.CAPTURED_ON_ARRIVAL, piece, from_pos, to_pos)

        captured = defender
        self._board.set(to_pos, piece)
        self._board.move_piece(from_pos)
        piece.has_moved = True
        if captured is not None:
            captured.state = PieceState.CAPTURED

        promoted_kind = self._rule_engine.promotion_kind(self._board, piece, to_pos)
        if promoted_kind is not None:
            piece.kind = promoted_kind

        self._release(piece)

        return MoveOutcome(
            MoveOutcomeStatus.EXECUTED, piece, from_pos, to_pos, captured_piece=captured
        )
