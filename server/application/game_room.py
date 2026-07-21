"""Aggregate root for a single match: owns the kfchess GameSession, the
command_queue moves drain from before the clock advances, seat assignment,
and room lifecycle. Delegates all rule/motion logic to the GameSession it
owns; seats and RoomStatus transitions are its own invariants to protect."""

from typing import Dict, List, Optional

from common.events import Event, EventBus, EventNames
from common.tracing import TraceIdGenerator
from kfchess.api import EngineConfig, EngineEvent, EngineEventKind, GameSession, create_game_session
from protocol import codec, messages as m
from server.domain.connection_id import ConnectionId
from server.domain.pending_move import PendingMove
from server.domain.room_status import RoomStatus
from server.domain.websocket_port import WebSocketManager

_ENGINE_EVENT_TO_BUS_NAME = {
    EngineEventKind.MOVE_EXECUTED: EventNames.MOVE_LOGGED,
    EngineEventKind.PIECE_CAPTURED: EventNames.PIECE_CAPTURED,
    EngineEventKind.MOVE_STOPPED: EventNames.MOVE_STOPPED,
    EngineEventKind.GAME_OVER: EventNames.GAME_OVER,
}


class GameRoom:
    def __init__(
        self,
        room_id: str,
        session: Optional[GameSession],
        websocket_manager: WebSocketManager,
        bus: Optional[EventBus] = None,
        trace_id_generator: Optional[TraceIdGenerator] = None,
        broadcast_hz: int = 20,
        max_engine_step_ms: int = 100,
    ):
        self.room_id = room_id
        self.session = session
        self._websocket_manager = websocket_manager
        self._bus = bus
        self._trace_id_generator = trace_id_generator
        self._broadcast_interval_ms = 1000 / broadcast_hz
        self._max_engine_step_ms = max_engine_step_ms

        self.status = RoomStatus.WAITING
        self._command_queue: List[PendingMove] = []
        self._seats: Dict[str, ConnectionId] = {}
        # Survives disconnection on purpose: a seat's user_id is match data, not
        # connection state, so settlement can still identify a player whose
        # connection died and whose ClientSession is long gone.
        self._seat_user_ids: Dict[str, int] = {}
        self._viewer_conn_ids: List[ConnectionId] = []
        self._move_trace_ids: Dict[int, str] = {}
        self._tick_trace_id: Optional[str] = None

        self._last_tick_ms: Optional[int] = None
        self._last_broadcast_ms: Optional[int] = None
        self._seq = 0

    # --- seats & lifecycle ---

    def assign_seat(self, role: str, conn_id: ConnectionId, user_id: Optional[int] = None) -> None:
        """A player seat without a `user_id` leaves the game unrated: RatingUpdater
        cannot identify the players, so no Elo is written and no game_record is
        stored. Match-start wiring must pass it; only deliberately unrated rooms
        should omit it."""
        if role == "viewer":
            self.add_viewer(conn_id)
            return

        self._seats[role] = conn_id
        if user_id is not None:
            self._seat_user_ids[role] = user_id
        if self.status is RoomStatus.WAITING and len(self._seats) >= 2:
            self.status = RoomStatus.RUNNING
            self._websocket_manager.broadcast(list(self._seats.values()), codec.encode(self._game_started_message()))
        elif self.status is not RoomStatus.WAITING:
            self._send_join_in_progress(conn_id)

    def add_viewer(self, conn_id: ConnectionId) -> None:
        self._viewer_conn_ids.append(conn_id)
        if self.status is not RoomStatus.WAITING:
            self._send_join_in_progress(conn_id)

    def _send_join_in_progress(self, conn_id: ConnectionId) -> None:
        """A late joiner (spectator or reconnecting player) gets GameStarted
        immediately followed by the current StateUpdate - exactly the
        ClockEstimator mid-game rebasing path built for on the client side."""
        self._websocket_manager.send_to(conn_id, codec.encode(self._game_started_message()))
        self._websocket_manager.send_to(conn_id, codec.encode(self._state_update_message()))

    def _game_started_message(self) -> m.GameStarted:
        snapshot = self.session.board_snapshot()
        return m.GameStarted(server_ms=self.session.clock_ms, rows=snapshot.rows, cols=snapshot.cols)

    # --- command queue ---

    def enqueue_move(self, pending: PendingMove) -> None:
        self._command_queue.append(pending)

    # --- tick: drain -> advance -> broadcast, in that fixed order ---

    def tick(self, now_ms: int) -> None:
        if self._last_tick_ms is None:
            self._last_tick_ms = now_ms

        self._drain()

        dt = min(now_ms - self._last_tick_ms, self._max_engine_step_ms)
        if dt > 0:
            self._tick_trace_id = self._new_trace_id()
            self.session.wait(dt)
            self._tick_trace_id = None
            self._last_tick_ms += dt

        if self.session.game_over and self.status is not RoomStatus.ENDED:
            self.status = RoomStatus.ENDED

        if self._last_broadcast_ms is None or now_ms - self._last_broadcast_ms >= self._broadcast_interval_ms:
            self._broadcast_state()
            self._last_broadcast_ms = now_ms

    def _drain(self) -> None:
        # Only what's on the queue *now* is applied; anything enqueued while
        # this drains (e.g. via a re-entrant enqueue_move call) waits for the
        # next tick, since self._command_queue is already a fresh empty list.
        pending_moves, self._command_queue = self._command_queue, []
        for pending in pending_moves:
            piece_before = self.session.piece_at(pending.from_pos)
            result = self.session.request_move(pending.from_pos, pending.to_pos)
            if result.is_accepted and piece_before is not None and pending.trace_id is not None:
                self._move_trace_ids[piece_before.piece_id] = pending.trace_id
            ack = m.MoveAck(
                client_seq=pending.client_seq,
                accepted=result.is_accepted,
                reason=None if result.is_accepted else result.reason,
            )
            self._websocket_manager.send_to(pending.connection_id, codec.encode(ack))

    def _broadcast_state(self) -> None:
        self._seq += 1
        self._websocket_manager.broadcast(self.connection_ids(), codec.encode(self._state_update_message()))

    def _state_update_message(self) -> m.StateUpdate:
        snapshot = self.session.board_snapshot()
        return m.StateUpdate(
            server_ms=self.session.clock_ms,
            seq=self._seq,
            pieces=snapshot.pieces(),
            motions=self._motion_entries(snapshot),
            move_log=self.session.move_log(),
            scoreboard=self.session.scoreboard(),
            game_over=self.session.game_over,
        )

    def _motion_entries(self, snapshot) -> List[m.MotionEntry]:
        entries = []
        for piece in snapshot.pieces():
            motion = self.session.motion_for(piece.piece_id)
            if motion is not None:
                entries.append(m.MotionEntry(piece_id=piece.piece_id, motion=motion))
        return entries

    def connection_ids(self) -> List[ConnectionId]:
        return list(self._seats.values()) + list(self._viewer_conn_ids)

    def player_user_ids(self) -> Dict[str, int]:
        """color -> user_id for the two seated players, for result settlement."""
        return dict(self._seat_user_ids)

    # --- forced resign (disconnect) ---

    def force_resign(self, color: str) -> None:
        if self.status is RoomStatus.ENDED:
            return
        self.status = RoomStatus.ENDED
        if self._bus is not None:
            self._bus.publish(Event(
                name=EventNames.GAME_OVER,
                payload={"room_id": self.room_id, "reason": "disconnect", "resigned_color": color},
                trace_id=self._new_trace_id(),
            ))

    # --- EngineEventSink: kfchess calls this during session.wait() ---

    def emit(self, event: EngineEvent) -> None:
        if self._bus is None:
            return
        name = _ENGINE_EVENT_TO_BUS_NAME.get(event.kind)
        if name is None:
            return

        trace_id = self._tick_trace_id
        if event.piece is not None and event.piece.piece_id in self._move_trace_ids:
            trace_id = self._move_trace_ids.pop(event.piece.piece_id)

        self._bus.publish(Event(
            name=name,
            payload={"room_id": self.room_id, "engine_event": event},
            trace_id=trace_id,
        ))

    def _new_trace_id(self) -> Optional[str]:
        return self._trace_id_generator.new_id() if self._trace_id_generator is not None else None


def create_game_room(
    room_id: str,
    starting_board_text: str,
    websocket_manager: WebSocketManager,
    bus: Optional[EventBus] = None,
    trace_id_generator: Optional[TraceIdGenerator] = None,
    engine_config: Optional[EngineConfig] = None,
    broadcast_hz: int = 20,
    max_engine_step_ms: int = 100,
) -> GameRoom:
    """Builds a GameRoom with its GameSession's event_sink wired back to
    itself, so engine events reach the bus tagged with room_id/trace_id."""
    room = GameRoom(
        room_id=room_id,
        session=None,
        websocket_manager=websocket_manager,
        bus=bus,
        trace_id_generator=trace_id_generator,
        broadcast_hz=broadcast_hz,
        max_engine_step_ms=max_engine_step_ms,
    )
    room.session = create_game_session(starting_board_text, config=engine_config, event_sink=room)
    return room
