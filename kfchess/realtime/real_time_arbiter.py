from typing import Dict, List, Optional, Set

from kfchess.model.board import Board
from kfchess.model.piece import PieceKind, PieceState
from kfchess.model.position import Position
from kfchess.rules.rule_engine import RuleEngine
from kfchess.realtime.cooldown import CooldownPolicy, CooldownTracker
from kfchess.realtime.motion import Motion, MoveOutcome, MoveOutcomeStatus
from kfchess.realtime.movement_profile import (
    MovementProfile, DEFAULT_MOVEMENT_PROFILES, MOVE_DURATION_MS_PER_CELL,
)
from kfchess.realtime.collision import (
    CollisionDetector, CollisionResolver, ResolutionAction,
)

JUMP_DURATION_MS = MOVE_DURATION_MS_PER_CELL


class RealTimeArbiter:
    """
    Movement manager and sole board mutator. Advances simulated time and
    steps each active Motion one square at a time, so a sliding piece
    actually occupies the squares along its path while in flight. At every
    square it delegates: a MovementProfile decides the trajectory, a
    CollisionDetector classifies what is in the way, and a CollisionResolver
    turns that into an action (proceed / stop / capture) which this class
    applies. Post-motion cooldown is delegated to CooldownPolicy and
    CooldownTracker.

    "Arriving later" is emergent, not hard-coded: each tick the earliest
    ready step is processed first (ties broken by Motion.seq), so whoever
    reaches a contested square first occupies it and the later mover then
    resolves the collision - stopping on its preceding square against a
    friendly piece, or capturing an enemy.
    """

    def __init__(
        self,
        board: Board,
        rule_engine: RuleEngine,
        cooldown_policy: Optional[CooldownPolicy] = None,
        movement_profiles: Optional[Dict[PieceKind, MovementProfile]] = None,
        collision_detector: Optional[CollisionDetector] = None,
        collision_resolver: Optional[CollisionResolver] = None,
    ):
        self._board = board
        self._rule_engine = rule_engine
        self._cooldown_policy = cooldown_policy if cooldown_policy is not None else CooldownPolicy()
        self._movement_profiles = movement_profiles if movement_profiles is not None else DEFAULT_MOVEMENT_PROFILES
        self._detector = collision_detector if collision_detector is not None else CollisionDetector()
        self._resolver = collision_resolver if collision_resolver is not None else CollisionResolver()
        self._cooldowns = CooldownTracker()
        self._clock_ms = 0
        self._pending: List[Motion] = []
        self._moving: Set = set()
        self._airborne: Set = set()
        self._next_seq = 0

    @property
    def clock_ms(self) -> int:
        return self._clock_ms

    def is_moving(self, piece) -> bool:
        return piece in self._moving

    def is_airborne(self, piece) -> bool:
        return piece in self._airborne

    def is_on_cooldown(self, piece) -> bool:
        return self._cooldowns.is_active(piece, self._clock_ms)

    def begin_move(self, piece, from_pos: Position, to_pos: Position) -> None:
        self._next_seq += 1
        started_at_ms = self._clock_ms

        if from_pos == to_pos:
            motion = Motion(
                piece=piece, origin=from_pos, current=from_pos, remaining=[],
                next_step_at=self._clock_ms + JUMP_DURATION_MS,
                step_duration_ms=JUMP_DURATION_MS, is_jump=True, seq=self._next_seq,
                started_at_ms=started_at_ms, total_duration_ms=JUMP_DURATION_MS,
            )
            self._airborne.add(piece)
        else:
            profile = self._movement_profiles[piece.kind]
            step_duration = profile.step_duration_ms(from_pos, to_pos)
            path = profile.occupied_path(from_pos, to_pos)
            motion = Motion(
                piece=piece, origin=from_pos, current=from_pos,
                remaining=path,
                next_step_at=self._clock_ms + step_duration,
                step_duration_ms=step_duration, is_jump=False, seq=self._next_seq,
                started_at_ms=started_at_ms, total_duration_ms=step_duration * len(path),
            )

        self._pending.append(motion)
        self._moving.add(piece)
        piece.state = PieceState.MOVING

    def motion_for(self, piece) -> Optional[Motion]:
        """Read-only lookup of the in-flight Motion for `piece`, or None if it isn't moving."""
        for motion in self._pending:
            if motion.piece is piece:
                return motion
        return None

    def advance(self, ms: int) -> List[MoveOutcome]:
        self._clock_ms += ms

        outcomes: List[MoveOutcome] = []
        while True:
            ready = [m for m in self._pending if m.next_step_at <= self._clock_ms]
            if not ready:
                break
            motion = min(ready, key=lambda m: (m.next_step_at, m.seq))
            outcome = self._step(motion)
            if outcome is not None:
                self._pending.remove(motion)
                outcomes.append(outcome)
        return outcomes

    def abort(self, piece) -> None:
        self._pending = [m for m in self._pending if m.piece is not piece]
        self._release(piece)

    def cancel_all_pending(self) -> None:
        """Drops every motion still in flight (used to end all further play, e.g. on game over)."""
        self._pending = []

    def _release(self, piece) -> None:
        self._moving.discard(piece)
        self._airborne.discard(piece)
        if piece.state is not PieceState.CAPTURED:
            piece.state = PieceState.IDLE

    def _step(self, motion: Motion) -> Optional[MoveOutcome]:
        """
        Processes one square-step of a motion. Returns a MoveOutcome when
        the motion terminates (and the caller drops it), or None when the
        piece merely advanced a square and should keep going.
        """
        piece = motion.piece

        # The piece must still be standing where we left it; if something
        # displaced (or captured) it mid-flight, the move is void.
        if self._board.get(motion.current) is not piece:
            self._release(piece)
            return MoveOutcome(MoveOutcomeStatus.ABORTED_PREMOVE, piece, motion.origin, motion.target)

        if motion.is_jump:
            self._release(piece)
            self._start_cooldown(piece, motion.next_step_at, is_jump=True)
            return MoveOutcome(MoveOutcomeStatus.EXECUTED, piece, motion.origin, motion.current)

        next_pos = motion.remaining[0]
        occupant = self._board.get(next_pos)

        # A piece jumping in place on the target square destroys whatever
        # arrives while it is still airborne - the arriver is the loser.
        if occupant is not None and occupant in self._airborne:
            self._board.move_piece(motion.current)
            piece.state = PieceState.CAPTURED
            self._release(piece)
            return MoveOutcome(MoveOutcomeStatus.CAPTURED_ON_ARRIVAL, piece, motion.origin, next_pos)

        collision_type = self._detector.classify(piece, occupant)
        resolution = self._resolver.resolve(collision_type, piece, occupant)

        if resolution.action is ResolutionAction.STOP:
            self._release(piece)
            self._start_cooldown(piece, motion.next_step_at, is_jump=False)
            return MoveOutcome(MoveOutcomeStatus.STOPPED_BY_FRIENDLY, piece, motion.origin, motion.current)

        captured = resolution.captured_piece
        self._board.set(next_pos, piece)
        self._board.move_piece(motion.current)
        piece.has_moved = True
        motion.current = next_pos
        motion.remaining = motion.remaining[1:]
        if captured is not None:
            captured.state = PieceState.CAPTURED

        # A capture halts a slider on the square it took, just as a normal
        # slide stops at its first capture; otherwise it runs on until the
        # path is exhausted.
        if captured is not None or not motion.remaining:
            promoted_kind = self._rule_engine.promotion_kind(self._board, piece, next_pos)
            if promoted_kind is not None:
                piece.kind = promoted_kind
            self._release(piece)
            self._start_cooldown(piece, motion.next_step_at, is_jump=False)
            return MoveOutcome(
                MoveOutcomeStatus.EXECUTED, piece, motion.origin, next_pos, captured_piece=captured
            )

        motion.next_step_at += motion.step_duration_ms
        return None

    def _start_cooldown(self, piece, matured_at_ms: int, is_jump: bool) -> None:
        duration_ms = self._cooldown_policy.duration_for(is_jump)
        self._cooldowns.start(piece, matured_at_ms + duration_ms)
