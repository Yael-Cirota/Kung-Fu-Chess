"""Implements GameSession fully, so existing UI code (ClickHandler,
run_game_loop) runs unchanged against a remote game exactly as it does
against a local EngineGameSession (see 'The remote session: keep the
GameSession Protocol unified'). wait(ms) is semantically overloaded: locally
it advances simulated time, here it drains the network queue and
extrapolates - see the GameSession Protocol docstring."""

from typing import List, Optional

from common.clock import Clock, MonotonicClock
from common.events import Event, EventNames
from kfchess.api.dto import BoardSnapshot, MotionInfo, MoveLogEntry, MoveResult, PieceView, Position, Scoreboard
from protocol import messages as m
from client.net.client_link import ClientLink
from client.session.clock_estimator import ClockEstimator
from client.session.snapshot_store import SnapshotStore
from client.session.sync_event_bus import SyncEventBus

# DeltaEvent.kind carries kfchess.api.EngineEventKind's wire value (see
# BroadcastObserver); MOVE_ABORTED has no bus mapping server-side either, so
# it has none here.
_DELTA_KIND_TO_EVENT_NAME = {
    "move_executed": EventNames.MOVE_LOGGED,
    "piece_captured": EventNames.PIECE_CAPTURED,
    "move_stopped": EventNames.MOVE_STOPPED,
    "game_over": EventNames.GAME_OVER,
}


class RemoteGameSession:
    def __init__(
        self,
        link: ClientLink,
        bus: Optional[SyncEventBus] = None,
        clock: Optional[Clock] = None,
        resync_threshold_ms: int = 1000,
        max_catchup_rate: float = 1.20,
        min_catchup_rate: float = 0.85,
    ):
        self._link = link
        self._bus = bus
        self._clock = clock if clock is not None else MonotonicClock()
        self._resync_threshold_ms = resync_threshold_ms
        self._max_catchup_rate = max_catchup_rate
        self._min_catchup_rate = min_catchup_rate
        self._start_wall_ms = self._clock.now_ms()
        self._estimator = ClockEstimator(max_catchup_rate, min_catchup_rate, resync_threshold_ms)
        self._store = SnapshotStore()
        self._client_seq = 0

        # Dispatch table keyed by exact message type, mirroring the server's
        # MessageDispatcher (server/presentation/dispatcher.py). Protocol
        # message dataclasses never subclass one another, so a type() lookup
        # is equivalent to the isinstance chain it replaces.
        self._handlers = {
            m.GameStarted: self._on_game_started,
            m.StateUpdate: self._on_state_update,
            m.HeartbeatAck: self._on_heartbeat_ack,
            m.GameEnded: lambda message: self._store.apply_game_ended(message),
            m.DeltaEvent: self._publish_delta,
            m.MoveAck: self._on_move_ack,
        }

    def _elapsed_wall_ms(self) -> int:
        return self._clock.now_ms() - self._start_wall_ms

    def elapsed_ms(self) -> int:
        """Public alias of the wall-clock origin `_apply` stamps HeartbeatAck
        receipt against. The outbound Heartbeat sender (client/net/ws_client.py)
        must stamp `client_ms` from this same origin - see 'on_heartbeat_ack'
        on ClockEstimator: client_sent_ms and client_recv_ms only mean
        anything as an RTT if they share a clock."""
        return self._elapsed_wall_ms()

    def reset_clock_origin(self) -> None:
        """Re-anchors elapsed_ms()/clock_ms to now and discards prior
        clock-sync state. Required before entering ui.game_loop.run_game_loop
        whenever an arbitrary amount of real time (a REPL prompt, waiting for
        an opponent to join) has elapsed since this session was constructed:
        without it, the first GameStarted/StateUpdate applied afterward would
        snap clock_ms to that elapsed duration, while run_game_loop's own
        render_ms starts fresh from zero - reproducing exactly 'the one
        non-obvious bug this design exists to avoid' (frozen board, dt_ms
        permanently negative). A HeartbeatAck already in flight across the
        reset yields one bad RTT sample; the next regular StateUpdate snaps
        it away."""
        self._start_wall_ms = self._clock.now_ms()
        self._estimator = ClockEstimator(self._max_catchup_rate, self._min_catchup_rate, self._resync_threshold_ms)

    # --- GameSession Protocol ---

    @property
    def clock_ms(self) -> int:
        return self._estimator.local_ms

    @property
    def game_over(self) -> bool:
        return self._store.game_over

    @property
    def winner(self) -> Optional[str]:
        return self._store.winner

    def is_within_bounds(self, pos: Position) -> bool:
        return self._store.is_within_bounds(pos)

    def piece_at(self, pos: Position) -> Optional[PieceView]:
        return self._store.piece_at(pos)

    def request_move(self, from_pos: Position, to_pos: Position) -> MoveResult:
        self._client_seq += 1
        self._link.send(m.MoveRequest(
            from_row=from_pos.row, from_col=from_pos.col,
            to_row=to_pos.row, to_col=to_pos.col,
            client_seq=self._client_seq,
        ))
        # Optimistic: the authoritative MoveAck arrives later on inbound_game
        # and is published on the bus instead (drives a rejection flash).
        return MoveResult.accepted()

    def wait(self, ms: int) -> None:
        for message in self._link.drain_game():
            self._apply(message)
        self._estimator.advance(ms)

    def is_moving(self, piece_id: int) -> bool:
        return self._store.motion_for(piece_id) is not None

    def board_snapshot(self) -> BoardSnapshot:
        return self._store.board_snapshot()

    def motion_for(self, piece_id: int) -> Optional[MotionInfo]:
        raw = self._store.motion_for(piece_id)
        if raw is None:
            return None
        return MotionInfo(
            from_pos=raw.from_pos,
            to_pos=raw.to_pos,
            start_ms=self._estimator.to_local(raw.start_ms),
            duration_ms=raw.duration_ms,
            is_jump=raw.is_jump,
        )

    def move_log(self) -> List[MoveLogEntry]:
        return self._store.move_log()

    def scoreboard(self) -> Scoreboard:
        return self._store.scoreboard()

    # --- inbound message handling ---

    def _apply(self, message) -> None:
        handler = self._handlers.get(type(message))
        if handler is not None:
            handler(message)

    def _on_game_started(self, message: m.GameStarted) -> None:
        self._store.apply_game_started(message)
        self._estimator.on_snapshot(message.server_ms, self._elapsed_wall_ms())

    def _on_state_update(self, message: m.StateUpdate) -> None:
        self._store.apply_state_update(message)
        self._estimator.on_snapshot(message.server_ms, self._elapsed_wall_ms())

    def _on_heartbeat_ack(self, message: m.HeartbeatAck) -> None:
        self._estimator.on_heartbeat_ack(message.client_ms, message.server_ms, self._elapsed_wall_ms())

    def _on_move_ack(self, message: m.MoveAck) -> None:
        # Accepted acks are dropped: request_move already returned optimistic
        # acceptance; only rejections need to flash on the bus.
        if not message.accepted:
            self._publish_move_rejected(message)

    def _publish_delta(self, message: m.DeltaEvent) -> None:
        if self._bus is None:
            return
        name = _DELTA_KIND_TO_EVENT_NAME.get(message.kind)
        if name is None:
            return
        self._bus.publish(Event(name=name, payload={"delta": message}, trace_id=message.trace_id))

    def _publish_move_rejected(self, message: m.MoveAck) -> None:
        if self._bus is None:
            return
        self._bus.publish(Event(name=EventNames.MOVE_REJECTED, payload={"reason": message.reason}))
