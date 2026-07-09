from typing import List, Set

from kfchess.model.board import Board
from kfchess.model.piece import Pawn, Queen
from kfchess.model.position import Position
from kfchess.rules.rule_engine import RuleEngine
from kfchess.realtime.motion import MoveOutcome, MoveOutcomeStatus, PendingMove

JUMP_DURATION_MS = 1000


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
            execute_at = self._clock_ms + distance * piece.move_delay_ms

        self._pending.append(PendingMove(piece, from_pos, to_pos, execute_at))
        self._moving.add(piece)

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

    def _mature(self, move: PendingMove, still_airborne: frozenset) -> MoveOutcome:
        piece, from_pos, to_pos = move.piece, move.from_pos, move.to_pos

        if self._board.get(from_pos) is not piece:
            self._release(piece)
            return MoveOutcome(MoveOutcomeStatus.ABORTED_PREMOVE, piece, from_pos, to_pos)

        if from_pos == to_pos:
            self._release(piece)
            return MoveOutcome(MoveOutcomeStatus.EXECUTED, piece, from_pos, to_pos)

        result = self._rule_engine.validate(self._board, from_pos, to_pos)
        if not result.legal:
            self._release(piece)
            return MoveOutcome(MoveOutcomeStatus.ABORTED_ILLEGAL, piece, from_pos, to_pos)

        defender = self._board.get(to_pos)
        if defender is not None and defender in still_airborne:
            self._board.remove(from_pos)
            self._release(piece)
            return MoveOutcome(MoveOutcomeStatus.CAPTURED_ON_ARRIVAL, piece, from_pos, to_pos)

        captured = defender
        self._board.set(to_pos, piece)
        self._board.remove(from_pos)
        piece.has_moved = True

        last_row = 0 if piece.color == 'w' else self._board.rows - 1
        if isinstance(piece, Pawn) and to_pos.row == last_row:
            promoted = Queen(piece.color)
            promoted.has_moved = True
            self._board.set(to_pos, promoted)

        self._release(piece)

        return MoveOutcome(
            MoveOutcomeStatus.EXECUTED, piece, from_pos, to_pos, captured_piece=captured
        )
