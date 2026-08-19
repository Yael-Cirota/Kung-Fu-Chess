# Refactor to Real-Time Client-Server Architecture

## Context

Kung-Fu-Chess today is a single-process desktop program. `ui/` renders with OpenCV and
polls a `GameSession` for state 60 times a second; `kfchess/` is a fully deterministic
headless engine whose clock only advances when someone calls `wait(ms)`. There is no
networking, no threading, no database, no logging, and no event system anywhere in the
repo — the only `import time` is an injectable wall clock in `ui/game_loop.py:23`.

The goal is multiplayer: two players on different machines playing the same real-time
game, with accounts, ELO-based matchmaking, spectator rooms, and graceful handling of
disconnects. That requires a server that owns the authoritative clock, a wire protocol,
persistence, and a client that renders someone else's game state instead of its own.

Two things must survive intact:

1. **The graded VPL harness** (`main.py` → `kfchess/texttests/script_runner.py`) must keep
   producing byte-identical stdout, fully offline. It builds its own engine directly at
   `script_runner.py:48-52`, so it is naturally insulated — the plan adds a lint contract
   to keep it that way mechanically.
2. **The two-clocks rule** (`ui/app.py:26-39`): engine time drives *where* a piece is
   interpolated; wall time drives *only* cosmetic sprite pacing. Getting this wrong across
   a network means pieces drawn past collisions the server hasn't resolved.

Decisions already made: server-authoritative engine; keep both the OpenCV UI and the VPL
path; `asyncio` + the `websockets` library; one client process (terminal shell first, cv2
window on game start); TOML config with env overrides; all behavior in synchronous
clock-injected classes with hand-written fakes, anemic transport adapters.

---

## The one non-obvious bug this design exists to avoid

`ui/game_loop.py:50-52`:

```python
render_ms = round((clock() - start) * MS_IN_SECOND)   # origin: loop start ≈ 0
dt_ms = min(render_ms - session.clock_ms, MAX_ENGINE_STEP_MS)
if dt_ms > 0:
    session.wait(dt_ms)
```

This subtraction is only valid because local `clock_ms` and `render_ms` **share an origin**.
A spectator (Player 3+) or a rejoining player receives their first snapshot with
`server_ms ≈ 45000` while their `render_ms ≈ 0`. Then `dt_ms = -45000`, the `dt_ms > 0` guard
never passes, `wait()` is never called, the inbound network queue never drains, and the
board renders frozen forever. Every viewer and every rejoin breaks.

**Fix: rebase server time to a client-local origin at the ingestion boundary** (see Phase 5).
`ui/game_loop.py` and `ui/app.py` then need *zero* changes.

---

## Proposed directory structure

```
config/default.toml                  # all extracted constants; env overrides on top

common/                              # bottom layer; imports nothing else in-repo
  clock.py                           # Clock Protocol, MonotonicClock, ManualClock
  events.py                          # EventBus Protocol, InMemoryEventBus, Event (carries trace_id)
  tracing.py            (NEW)        # TraceId, TraceIdGenerator Protocol - request correlation
  logging_setup.py                   # req 7: isolated logging, both sides; structured JSON audit format
  config/schema.py                   # frozen config dataclass tree
  config/loader.py                   # tomllib -> schema, env overrides

kfchess/                             # existing engine; layering preserved
  api/events.py         (NEW)        # EngineEvent DTOs + EngineEventSink Protocol
  api/engine_config.py  (NEW)        # frozen EngineConfig
  api/factory.py        (MOD)        # gains optional config + event_sink params
  api/session.py        (MOD)        # EngineGameSession gains optional event_sink
  engine/game_engine.py (MOD)        # wait() returns List[MoveOutcome]
  rules/scoring.py      (MOD)        # adds ScoringPolicy; keeps points_for

protocol/                            # wire format; may import kfchess.api + common
  messages.py                        # frozen request/response/event dataclasses
  codec.py                           # JSON <-> messages <-> kfchess DTOs
  errors.py

server/
  app.py                             # composition root (pragma: no cover)
  net/ws_server.py                   # websockets adapter, anemic (pragma)
  net/connection.py                  # Connection + WebSocketManager Protocols, registry
  net/dispatcher.py                  # Presentation gatekeeper: schema/size check, mints TraceId, MessageDispatcher: message -> handler (sync, tested)
  net/heartbeat.py                   # ConnectionMonitor.tick(now_ms)
  services/auth_service.py           # Application gatekeeper: identity, ties to PlayerSession (ClientSession)
  services/elo.py
  services/matchmaking.py            # MatchmakingService.tick(now_ms); publishes MATCH_FOUND/MATCH_TIMED_OUT
  services/activity_log.py           # EventBus subscriber; writes structured JSON audit log lines (NEW)
  services/broadcast_observer.py     # EventBus subscriber; maps domain events -> DeltaEvent wire frames (NEW)
  services/room_service.py           # create/join/cancel; role by entry order
  services/game_room.py              # aggregate root: owns GameSession + command_queue + seats; tick(now_ms) drains, advances, broadcasts
  services/room_ticker.py            # single tick fan-out over all rooms + monitors
  services/disconnect_policy.py      # 20s countdown -> auto-resign
  data/repositories.py               # UserRepository / GameRecordRepository Protocols
  data/sqlite_user_repository.py
  data/schema.sql
  data/connection_factory.py         # sqlite3 wiring (pragma)

client/
  app.py                             # composition root (pragma: no cover)
  net/ws_client.py                   # background-thread adapter (pragma)
  net/client_link.py                 # thread-safe queue hub; sync-testable
  session/clock_estimator.py         # server_ms -> local_ms rebasing + drift correction
  session/snapshot_store.py          # latest snapshot, rebased motions
  session/remote_session.py          # RemoteGameSession: implements GameSession
  shell/shell.py                     # sync Shell class (fully tested)
  shell/repl.py                      # input()/print() wrapper (pragma: no cover)
  shell/commands.py

ui/                                  # unchanged, except _build_scene() takes a session
```

`main.py` and `kfchess/texttests/` are **not touched**.

---

## Core interfaces & data models

### `common/clock.py`
```python
class Clock(Protocol):
    def now_ms(self) -> int: ...

class MonotonicClock:      # round(time.monotonic() * 1000)
class ManualClock:         # now_ms() / advance(ms) — test double AND server tick source
```

### `common/events.py`
```python
@dataclass(frozen=True)
class Event:
    name: str
    payload: Mapping[str, object]
    trace_id: Optional[str] = None   # request correlation; see common/tracing.py

Handler = Callable[[Event], None]

class EventBus(Protocol):
    def subscribe(self, name: str, handler: Handler) -> None: ...
    def unsubscribe(self, name: str, handler: Handler) -> None: ...
    def publish(self, event: Event) -> None: ...

class InMemoryEventBus:
    """Synchronous fan-out. Handler exceptions are logged and swallowed so one
    bad subscriber cannot kill a game tick."""
```

### `common/tracing.py`
```python
@dataclass(frozen=True)
class TraceId:
    value: str

class TraceIdGenerator(Protocol):
    def new_id(self) -> str: ...   # secrets-based in prod, sequential fake in tests

class SecretsTraceIdGenerator:     # secrets.token_hex(8)
class SequentialTraceIdGenerator:  # test double: "trace-1", "trace-2", ...
```

No context-vars, no thread-locals: everything in this codebase is synchronous and
clock-injected, so a `trace_id` is just an explicit string threaded through ordinary
function arguments and returned dataclasses — the same style already used for `Clock`
and `EventBus`. See "End-to-end observability" below for where it is minted and how far
it is allowed to travel.

Event name constants: `SCORE_CHANGED`, `MOVE_LOGGED`, `PIECE_CAPTURED`, `MOVE_STOPPED`,
`GAME_STARTED`, `GAME_OVER`, `PLAYER_DISCONNECTED`, `PLAYER_RECONNECTED`, `MATCH_FOUND`,
`MATCH_TIMED_OUT`. Audio triggers and start/end animations are **client-side subscribers**
to an in-process bus using these same names.

### `kfchess/api/events.py` — the engine's outbound port
```python
class EngineEventKind(Enum):
    MOVE_EXECUTED = "move_executed"
    MOVE_ABORTED = "move_aborted"
    MOVE_STOPPED = "move_stopped"
    PIECE_CAPTURED = "piece_captured"
    GAME_OVER = "game_over"

@dataclass(frozen=True)
class EngineEvent:
    kind: EngineEventKind
    at_ms: int
    piece: Optional[PieceView]
    from_pos: Optional[Position]
    to_pos: Optional[Position]
    captured: Optional[PieceView]
    beneficiary_color: Optional[str]

class EngineEventSink(Protocol):
    def emit(self, event: EngineEvent) -> None: ...
```

This deliberately does **not** reuse `common.events.EventBus`. `kfchess` keeps its
dependency surface at exactly zero new imports; a three-line adapter in
`server/services/game_room.py` bridges the two.

### `server/net/connection.py`
```python
@dataclass(frozen=True)
class ConnectionId:
    value: str

class Connection(Protocol):
    @property
    def connection_id(self) -> ConnectionId: ...
    def send(self, raw: str) -> None: ...    # non-blocking; adapter queues to the loop
    def close(self) -> None: ...

class WebSocketManager(Protocol):            # "IWebSocketManager"
    def register(self, conn: Connection) -> None: ...
    def unregister(self, conn_id: ConnectionId) -> None: ...
    def send_to(self, conn_id: ConnectionId, raw: str) -> None: ...
    def broadcast(self, conn_ids: Sequence[ConnectionId], raw: str) -> None: ...
    def connection_ids(self) -> List[ConnectionId]: ...
```

### `server/data/repositories.py`
```python
@dataclass(frozen=True)
class UserRecord:
    user_id: int
    username: str
    password_hash: str
    salt: str
    elo: int

class UserRepository(Protocol):              # "IUserRepository"
    def find_by_username(self, username: str) -> Optional[UserRecord]: ...
    def create(self, username: str, password_hash: str, salt: str, elo: int) -> UserRecord: ...
    def update_elo(self, user_id: int, elo: int) -> None: ...

class GameRecordRepository(Protocol):
    def record_result(self, white_id: int, black_id: int, winner_id: Optional[int],
                      ended_at_ms: int, reason: str) -> None: ...
```

Password hashing via stdlib `hashlib.pbkdf2_hmac` behind a `PasswordHasher` Protocol
(`hash(password, salt)`, `new_salt()`) — no new dependency, and a fake hasher keeps
auth tests fast.

### Server services — all synchronous, all clock-injected
```python
class AuthService:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, starting_elo: int): ...
    def register(self, username: str, password: str) -> AuthResult: ...
    def login(self, username: str, password: str) -> AuthResult: ...

class EloCalculator:
    def __init__(self, k_factor: int): ...
    def updated(self, winner_elo: int, loser_elo: int) -> Tuple[int, int]: ...

class MatchmakingService:
    def __init__(self, bus: EventBus, elo_window: int, timeout_ms: int): ...
    def enqueue(self, ticket: MatchTicket, now_ms: int) -> Optional[Match]: ...
    def cancel(self, user_id: int) -> None: ...
    def tick(self, now_ms: int) -> List[MatchTimeout]: ...

class RoomService:
    def create(self, host: PlayerRef, now_ms: int) -> Room: ...
    def join(self, room_id: str, player: PlayerRef) -> JoinResult: ...   # P1=WHITE, P2=BLACK, P3+=VIEWER
    def cancel(self, room_id: str, user_id: int) -> None: ...

class RoomIdGenerator(Protocol):
    def next_id(self) -> str: ...   # secrets-based in prod, sequential fake in tests

class ConnectionMonitor:
    def on_heartbeat(self, conn_id: ConnectionId, now_ms: int) -> None: ...
    def forget(self, conn_id: ConnectionId) -> None: ...       # called on eviction
    def tick(self, now_ms: int) -> List[DeadConnection]: ...   # newly-dead connections

@dataclass(frozen=True)
class DeadConnection:
    connection_id: ConnectionId
    epoch: int      # epoch at registration; teardown no-ops if < session's current epoch

class DisconnectPolicy:
    def on_disconnect(self, room_id: str, color: str, now_ms: int) -> None: ...
    def on_reconnect(self, room_id: str, color: str) -> None: ...
    def tick(self, now_ms: int) -> List[ForcedResign]: ...

@dataclass(frozen=True)
class PendingMove:
    color: str
    from_pos: Position
    to_pos: Position
    client_seq: int
    connection_id: ConnectionId    # for routing the eventual MoveAck
    trace_id: str                  # minted at the Presentation gate; see "End-to-end observability"

class RoomStatus(Enum):
    WAITING = "waiting"    # fewer than two players; Application gate rejects MoveRequest
    RUNNING = "running"    # set at the same GameStarted-trigger point below
    ENDED = "ended"         # set on GAME_OVER; Application gate rejects MoveRequest

class GameRoom:
    status: RoomStatus                                             # Application gatekeeper reads this
    def enqueue_move(self, pending: PendingMove) -> None: ...     # called from the dispatcher; never applies inline
    def tick(self, now_ms: int) -> Optional[StateUpdate]: ...     # drains queue, then advances, then (maybe) broadcasts
```

### `server/net/client_session.py` — connection identity and authorization

The engine has **no concept of color ownership**: `GameEngine.request_move`
(`game_engine.py:76-95`) checks game-over, motion, cooldown, and piece rules — never "is this
your color." That is correct locally, where one person drives both sides. On a server it means
color must be derived from the connection's assigned role and **never trusted from the client's
message**, or any client can move its opponent's pieces.

```python
@dataclass(frozen=True)
class ClientSession:
    connection_id: ConnectionId
    user_id: int
    username: str
    elo: int
    room_id: Optional[str]
    role: Optional[str]        # "white" | "black" | "viewer"
    epoch: int                 # bumped on every bind/rebind; see "Reconnection protocol"

class ClientSessionRegistry(Protocol):
    def bind(self, session: ClientSession) -> None: ...
    def get(self, conn_id: ConnectionId) -> Optional[ClientSession]: ...
    def by_user(self, user_id: int) -> Optional[ClientSession]: ...   # reconnect re-bind
    def update_room(self, conn_id: ConnectionId, room_id: str, role: str) -> None: ...
    def release(self, conn_id: ConnectionId) -> None: ...

    def rebind(self, user_id: int, conn_id: ConnectionId) -> Result[ClientSession]: ...
    """Evict-then-rebind: closes and unregisters any connection currently bound to
    user_id, bumps epoch, binds the session to conn_id. Idempotent, and independent
    of whether ConnectionMonitor has yet declared the old link dead. The single
    reconnect path — see 'Reconnection protocol' under Architectural improvements."""
```

This is load-bearing for three requirements at once: the dispatcher needs the user's ELO to
handle `PlayRequest` (req 4), the room/role to handle `MoveRequest` (req 5), and the user
identity to re-bind a returning connection and cancel a pending auto-resign (req 6).
`AuthOk` populates it; `release` happens on disconnect.

**Authorization rule, enforced in the dispatcher:** on `MoveRequest`, look up the session,
reject if `role` is `None` or `"viewer"`, and pass `session.role` — not anything from the
message — as the `color` field of the `PendingMove` given to `GameRoom.enqueue_move`.

### `protocol/messages.py`
Frozen dataclasses, discriminated by a `type` string in `codec.py`.

- **C→S:** `LoginRequest`, `RegisterRequest`, `PlayRequest`, `CancelQueueRequest`,
  `CreateRoomRequest`, `JoinRoomRequest`, `LeaveRoomRequest`,
  `MoveRequest(from_row, from_col, to_row, to_col, client_seq)`, `Heartbeat(client_ms)`.
- **S→C:** `AuthOk(user_id, username, elo)`, `AuthError(reason)`, `MatchFound(room_id, color)`,
  `MatchTimedOut`, `RoomCreated(room_id)`, `RoomJoined(room_id, role, players)`,
  `GameStarted(server_ms, rows, cols)`,
  `StateUpdate(server_ms, seq, pieces, motions, move_log, scoreboard, game_over)`,
  `MoveAck(client_seq, accepted, reason)`, `OpponentDisconnected(deadline_server_ms)`,
  `OpponentReconnected`, `GameEnded(winner, reason, elo_delta)`, `HeartbeatAck(client_ms, server_ms)`,
  `DeltaEvent(kind, trace_id, at_ms, piece, from_pos, to_pos, captured, beneficiary_color, scoreboard)`.

`StateUpdate` carries the **full** board and motion set — 32 pieces max, so delta
*compression* is unwarranted complexity, and it remains the **sole authority for position**;
`server_ms` is `session.clock_ms` at emit time. `DeltaEvent` is a separate, narrower message:
an immediate, advisory-only notification of one domain event (capture, move logged, game over),
sent outside the `StateUpdate` cadence so client-side effects (sound, animation) do not wait on
`broadcast_hz` — see "Event-driven broadcasting" below. It never carries enough information to
reconstruct board state and `RemoteGameSession` never treats it as if it did.

**Game-start trigger (decided, since req 5's flow has no explicit "start" step):**
`GameStarted` fires **automatically the moment a room reaches two players** — on the second
`join`, and on `MatchFound` for matchmade games (which is the same code path, with the server
creating the room and joining both players in ELO order). Viewers joining afterward receive
`GameStarted` followed immediately by the current `StateUpdate`; that mid-game join is exactly
the `ClockEstimator` rebasing path.

**Known limitation, stated as a decision:** `LoginRequest` and `RegisterRequest` carry the
password in cleartext over `ws://`. Acceptable for a local/LAN project; passwords are still
salted and PBKDF2-hashed **at rest**. Production use would need `wss://` — a transport change
only, requiring no application-layer redesign.

---

## Key design decisions

### Domain-driven design: aggregate boundaries and gatekeeping entities

This plan already draws these boundaries; this section names them so the intent survives
independent of who is reading the code.

- **`PlayerSession`** — the identity/authentication aggregate. In this plan it is
  `ClientSession` + `ClientSessionRegistry` (`server/net/client_session.py`, below). It knows a
  user's identity, ELO, and current room/role. It does **not** know about WebSocket framing
  (that is `Connection`/`WebSocketManager`, `server/net/connection.py`) or serialization (that
  is `protocol/codec.py`). A `ClientSession` object never touches a raw socket or a JSON blob.
- **`MatchmakingQueue`** — `MatchmakingService` (`server/services/matchmaking.py`). Owns ELO
  windows and enqueue/timeout bookkeeping only. It has no reference to `RoomService` and no
  knowledge that rooms or connections exist — enforced by "Internal EventBus as the
  service-to-service seam" below, where it publishes `MATCH_FOUND` instead of calling into room
  creation directly.
- **`GameRoom`** — the aggregate root for a single match. It controls seat assignment (White /
  Black / Spectators) and room lifecycle, and *delegates* simulation entirely to the
  `GameSession` it owns (`enqueue_move` / `tick`, below) rather than reimplementing any rule.
  Seats and lifecycle are `GameRoom`'s invariants to protect; move legality is not — that
  invariant belongs to the `kfchess` domain core one layer down.
- **Complete decoupling of the core engine from transport and framework concerns** is not
  aspirational here — it is the thing the import-linter contracts (below) check on every run.
  `kfchess/` imports no networking, no database, no `asyncio`; the "VPL path stays free of
  networking" contract makes that mechanical rather than a code-review habit. `kfchess.api` is
  the only seam an aggregate outside `kfchess` is allowed to touch (see `EngineEventSink`,
  "Getting events out of the engine," below) — the aggregates above depend on that Protocol,
  never on a `kfchess.model` or `kfchess.engine` type.

### Multi-layered fail-fast gatekeeping

Three tiers, each one only reachable if the previous one passed. A request that fails a gate is
rejected *at that gate* and never mutates state one layer further in:

| Tier | Where | Checks | Rejects |
|---|---|---|---|
| **Presentation** | `server/net/dispatcher.py`, `protocol/codec.py` | Message schema/JSON shape (`codec.py` round-trip validation, already in Phase 2); a frame-size ceiling (`max_frame_bytes`, new `[connection]` config key, below) so a malformed or hostile oversized payload is dropped before it is even parsed into a message type | Malformed JSON, unknown `type` discriminator, oversized frame |
| **Application** | `server/net/dispatcher.py` (post-parse), `ClientSessionRegistry`, `GameRoom` | Session bound and authenticated (`ClientSessionRegistry.get(conn_id)` is not `None`); role authorization (the existing "Authorization rule" below — a viewer or unbound connection cannot move); **room lifecycle state is `RUNNING`** (a `MoveRequest` for a room still in `WAITING` or already `ENDED` is rejected here, not handed to the engine) | Unauthenticated, wrong role, room not in progress |
| **Domain** | `kfchess.engine.GameEngine.request_move` / `kfchess.rules` | Move legality per piece kind, motion-in-progress, cooldown, board bounds — all pre-existing engine behavior, untouched by this plan | Illegal move, `MOTION_IN_PROGRESS`, cooldown active |

The `MoveRejectionReason` constants (`kfchess.rules.move_validation`) already model the Domain
tier's rejection vocabulary — this table just names the two tiers above it that the plan
previously described only piecemeal (Presentation validation was implicit in "codec round-trip
+ malformed-input rejection," Application validation was implicit in "Authorization rule,
enforced in the dispatcher"). `GameRoom` gains a `status: RoomStatus` field
(`WAITING | RUNNING | ENDED`) so the Application gate has something concrete to check; it is set
`RUNNING` at the same `GameStarted`-trigger point already decided below, and `ENDED` on
`GAME_OVER`.

### Application use cases, kept separate from domain logic

`server/services/*` **is** the application/use-case layer; `kfchess/` **is** the domain layer.
This plan already draws that line via `import-linter`'s "Engine and shared layers never import
outward" contract — this section just says so in DDD terms, rather than renaming existing
classes (`AuthService`, `MatchmakingService`, `RoomService`, `GameRoom`) to a `*UseCase` suffix,
which would be pure churn with no behavior or dependency-direction change.

- **Orchestration lives in Application:** `GameRoom.tick` sequencing (drain → advance →
  broadcast, below), `RoomTicker`'s fan-out over rooms, `DisconnectPolicy`'s countdown, and
  `MatchmakingService.tick`'s timeout sweep are all workflow — "what happens, and in what
  order" — not game rules.
- **Simulation stays pure in Domain:** `kfchess.rules` never mutates `Board`; `RealTimeArbiter`
  is the sole mutator, and it has no idea a `GameRoom`, a `tick_hz`, or a network exists. It
  answers "is this move legal, and when does it land" and nothing about who is allowed to ask.
- The dependency arrow only ever points one way — Application calls into Domain through
  `GameSession`/`kfchess.api`; Domain never calls back into Application. `EngineEventSink`
  (below) looks like an exception but isn't: it's a Protocol *owned and consumed* by the
  boundary, with `kfchess` holding only the abstract port, never a concrete Application type.

### Internal EventBus as the service-to-service seam (server-side)

`GameRoom`, `RoomService`, and the dispatcher never call `MatchmakingService`,
an activity logger, or ELO/persistence directly for anything that is not the
immediate synchronous response to the request being handled. Instead they
publish onto the shared `common.events.EventBus` (same bus and event names as
`common/events.py`), and secondary components subscribe:

- `server/services/activity_log.py` (**NEW**) — subscribes to `MOVE_LOGGED`,
  `PIECE_CAPTURED`, `GAME_STARTED`, `GAME_OVER`, `PLAYER_DISCONNECTED`,
  `PLAYER_RECONNECTED`; writes one line per event through the req-7 logging
  setup. It holds no reference to `GameRoom`, `Connection`, or the engine —
  only to the bus and a logger.
- ELO write-back and `GameRecordRepository.record_result` subscribe to
  `GAME_OVER` instead of being called inline from wherever the game actually
  ends (king capture, resignation, and forced-disconnect-resign are three
  different call sites in `GameRoom`/`DisconnectPolicy`; with a subscriber
  there is exactly one place that updates ratings, not three that each have
  to remember to).
- `MatchmakingService` still owns `enqueue`/`cancel`, called directly by the
  dispatcher because those are the synchronous response to `PlayRequest` /
  `CancelQueueRequest` — a queue insert has no meaningful "later" to defer
  to. What's decoupled is the *output* side: `MatchmakingService.tick`
  publishes `MATCH_FOUND` / `MATCH_TIMED_OUT` rather than holding a
  reference to `RoomService` and calling `room_service.create(...)` itself.
  `server/app.py` (or `RoomTicker`) subscribes to `MATCH_FOUND` and performs
  the room creation + `GameStarted` broadcast. This keeps `MatchmakingService`
  ignorant of rooms, connections, and the wire protocol — it only knows ELO
  numbers and a clock.

Net effect: `GameRoom` and the dispatcher depend on `EventBus`, not on each
secondary service's concrete type. A future subscriber (e.g. a webhook
notifier on `GAME_OVER`) touches zero existing files.

### Event-driven broadcasting: `BroadcastObserver` and delta effects

**Scope of this section, stated up front:** this adds a *latency* path for effect
notification, not a *bandwidth* optimization. It does not reopen the "`StateUpdate` carries the
full board" decision above — that reasoning (32 pieces, delta compression is unwarranted
complexity for something this small) stays true. What changes is that `PIECE_CAPTURED`,
`MOVE_LOGGED`, and `GAME_OVER` no longer have to wait for the next `broadcast_hz`-gated
`StateUpdate` to reach the client, and the client no longer has to *infer* them by diffing two
snapshots.

`server/services/broadcast_observer.py` (**NEW**) subscribes to the same `EventBus` as
`activity_log.py` — `MOVE_LOGGED`, `PIECE_CAPTURED`, `GAME_OVER` — and, for each event, sends a
small `DeltaEvent` message (new in `protocol/messages.py`, below) to every connection in the
room immediately, outside the `broadcast_hz` cadence. This is the second tier of a two-tier
pub/sub: `kfchess` emits `EngineEvent` → the `game_room.py` adapter republishes it as a
`common.events.Event` on the internal bus (already true, see "Getting events out of the engine"
below) → `BroadcastObserver`, an Application-layer subscriber, is what turns *that* into a wire
frame. `GameRoom` itself never imports `WebSocketManager` to do this — `BroadcastObserver` holds
that dependency so `GameRoom` stays about seats and simulation, not transport fan-out.

**Authoritative-for-position stays the full snapshot; deltas are advisory-for-effects only.**
A `DeltaEvent` is never used by `RemoteGameSession` to move a piece or update the board — only
`StateUpdate` does that, on the schedule already described in "Preserving the two-clocks rule."

**Delivery ordering is guaranteed, and the design leans on that rather than defending against
it.** Both messages travel the same WebSocket connection (`WebSocketManager.send_to(conn_id, …)`),
and WebSocket runs over TCP, which delivers bytes on one connection in send order. Combined with
`GameRoom.tick`'s fixed drain → advance → broadcast sequence — `BroadcastObserver` emits the
`DeltaEvent` during *advance*, the gated `StateUpdate` is built in *broadcast* — a delta always
reaches the client **before** the snapshot that reflects it. That is precisely the intended
effect: the sound and flash fire immediately, and the authoritative position for the same event
lands on the next `broadcast_hz` tick. Nothing here needs protecting against misordered delivery.

*This supersedes an earlier draft of this section, which justified the split by claiming the two
messages could arrive in either order. That claim was wrong at the transport layer and is
retracted; the two reasons below are the real ones.*

Advisory-only rests on two things instead:

1. **A `DeltaEvent` cannot reconstruct board state.** It describes one domain event, not a
   position set — there is no coherent way to treat it as authoritative even if one wanted to.
2. **Position must have exactly one writer.** `StateUpdate` → `SnapshotStore` → `ClockEstimator`
   is the single path that mutates position and `server_ms`. Admitting a second writer is what
   would put `ClockEstimator`'s monotonic-`server_ms` invariant at risk — not the network.

*Adapter requirement this depends on:* `Connection.send` is documented as "non-blocking; adapter
queues to the loop." That queue must be **per-connection and FIFO** — one ordered outbound queue
drained by one task per connection. Fanning a connection's frames across concurrent send tasks
would forfeit the ordering guarantee above at the application layer even though TCP preserves it
at the transport layer. `tests/server/net/test_ws_server.py` asserts enqueue order equals send order.

`RemoteGameSession.wait` publishes each `DeltaEvent` straight onto the client-side
`common.events.EventBus` under the same event names audio/animation subscribers already listen
to (`SCORE_CHANGED`, `PIECE_CAPTURED`, `MOVE_STOPPED`, `GAME_OVER` — see `common/events.py`
above), which **replaces** the "publish derived events" diffing this plan previously left
implicit in that step — there is no longer a need to diff consecutive `StateUpdate`s to
reconstruct what happened, because the server now says so explicitly and promptly. Position
itself is still only ever read from the latest `StateUpdate`.

`DeltaEvent` carries the same `trace_id` its originating `Event` carried (see "End-to-end
observability," below), so a capture's sound effect on the client can, in principle, be
correlated back to the exact `MoveRequest` that caused it — useful for debugging latency
complaints ("why did the capture sound play late") end to end.

### Getting events out of the engine: change the return type

`GameEngine.wait` currently computes `outcomes` at `game_engine.py:104` and throws them away.
Change the signature to `-> List[MoveOutcome]` and `return outcomes`; the body is otherwise
untouched.

This is the only layering-legal option. Injecting an event sink into `GameEngine` would force
`kfchess.engine` to either leak live `Piece` objects to whoever holds the sink, or import
`kfchess.api` DTOs — inverting the layer order, since `api` sits *above* `engine`. DTO mapping
must stay in `engine_mapping`.

Safety: `script_runner.py:69` calls `wait()` and ignores the result, so VPL is unaffected. No
existing test asserts `wait(...) is None`.

`EngineGameSession.wait` keeps its `-> None` signature (the `GameSession` Protocol is
unchanged) and maps outcomes to `EngineEvent`s through a new `engine_mapping.outcome_to_event`,
which mirrors the beneficiary inversion already in `_scoring_capture` (`game_engine.py:122-135`).

### The remote session: keep the `GameSession` Protocol unified

`RemoteGameSession` implements the existing Protocol (`kfchess/api/session.py:8-38`) in full:

| Member | Remote behavior |
|---|---|
| `clock_ms` | `estimator.local_ms` |
| `game_over` | last snapshot's flag |
| `is_within_bounds` / `piece_at` | from the latest snapshot |
| `request_move` | enqueue `MoveRequest`; return `MoveResult.accepted()` optimistically. The authoritative `MoveAck` arrives later and is published on the client bus (drives a rejection flash). |
| `wait(ms)` | **drain the inbound queue**, apply newest `StateUpdate`, feed `estimator.on_snapshot`, republish any queued `DeltaEvent`s onto the client bus (see "Event-driven broadcasting"), then `estimator.advance(ms)` |
| `is_moving` / `motion_for` | from snapshot motions, `start_ms` rebased |
| `board_snapshot` / `move_log` / `scoreboard` | straight off the latest snapshot |

**Do not split into read-model + command Protocols.** Both consumers need both halves:
`ClickHandler` calls `is_within_bounds`, `piece_at`, *and* `request_move`; `run_game_loop`
calls `game_over`, `clock_ms`, `wait`, `board_snapshot`, `move_log`, `scoreboard`. A split
hands every call site two objects and removes zero dependencies. The seam's entire value is
"existing UI code runs unchanged against either session," which the unified Protocol already
delivers.

The honest wart, named rather than designed around: **`wait(ms)` is semantically overloaded** —
"advance simulated time" locally, "pump the network and extrapolate" remotely. Document this
in the Protocol docstring as "advance this session's view of engine time by `ms`, performing
whatever work that entails."

### Preserving the two-clocks rule across the network

`client/session/clock_estimator.py` maps server engine time onto a client-local timeline that
shares `render_ms`'s origin:

```python
class ClockEstimator:
    """Monotonic by construction: engine_ms never rewinds, so a piece is never
    snapped backward past a square the server already resolved."""
    def __init__(self, max_catchup_rate: float = 1.20, min_catchup_rate: float = 0.85,
                 resync_threshold_ms: int = 1000): ...
    def on_snapshot(self, server_ms: int, local_ms: int) -> None: ...
    def on_heartbeat_ack(self, client_sent_ms: int, server_ms: int, client_recv_ms: int) -> None:
        """Half-RTT latency compensation: offsets server_ms by (client_recv_ms -
        client_sent_ms) / 2 before feeding it to the same rebasing logic as
        on_snapshot, since a HeartbeatAck's server_ms was stamped mid-flight,
        not at receipt. Rounds out to a call to on_snapshot internally."""
    def advance(self, ms: int) -> None: ...
    @property
    def local_ms(self) -> int: ...
    def to_local(self, server_ms: int) -> int: ...   # applied to MotionInfo.start_ms
```

`RemoteGameSession.clock_ms` returns `estimator.local_ms`; `motion_for()` returns a
`MotionInfo` rebuilt with `start_ms = estimator.to_local(raw.start_ms)` and the same
`duration_ms`. Because `clock_ms` and every `MotionInfo.start_ms` pass through the same
mapping within a frame, drift correction shifts both together and produces no visible jump —
`build_visual_states`' `progress(start_ms, duration_ms, engine_ms)` arithmetic is identical.

The offset is **snapped** only on the first snapshot or when drift exceeds
`resync_threshold_ms`; otherwise catch-up is bled off by scaling `advance(ms)` within
`[min_catchup_rate, max_catchup_rate]`, turning a 30ms wobble into a 200ms glide rather than
a teleport.

**Heartbeat replies are a second, higher-precision sync source, not just a liveness check.**
`client_link` sends `Heartbeat(client_ms)` on `heartbeat_interval_ms` (config, default 3000ms —
see `[connection]`); the server replies `HeartbeatAck(client_ms, server_ms=session.clock_ms)`
stamped at send time. `RemoteGameSession.wait` routes *both* sources into the estimator —
`StateUpdate.server_ms` at 20Hz via `on_snapshot`, and `HeartbeatAck` at the heartbeat cadence
via `on_heartbeat_ack`, which additionally corrects for one-way latency using the round-trip
`client_sent_ms`/`client_recv_ms` pair that `StateUpdate` doesn't carry. This matters most
exactly where "the one non-obvious bug this design exists to avoid" (top of this document)
matters most: a spectator's or rejoining player's *first* correct timestamp can come from
whichever arrives first — `GameStarted.server_ms`, the first `StateUpdate`, or a `HeartbeatAck`
completed while the initial snapshot is still in flight. Both entry points are safe to race
because `on_snapshot`/`on_heartbeat_ack` only ever snap on the first call or when drift exceeds
`resync_threshold_ms`, and otherwise glide — so whichever lands first establishes the origin, and
the other just confirms or nudges it.

Net result: the `dt_ms` subtraction, the `dt > 0` guard, the wait()-drains-the-queue trick,
and `MAX_ENGINE_STEP_MS` catch-up all survive. **`ui/game_loop.py` and `ui/app.py` need no
changes**, and `render_ms` still drives only sprite pacing.

### Timeouts without real waiting

No `asyncio.sleep` or `asyncio.wait_for` in business logic. Every timeout is a synchronous
`tick(now_ms)` against stored absolute deadlines:

- `MatchmakingService` — `now_ms - enqueued_at_ms >= 60000` → publish `MATCH_TIMED_OUT`.
- `ConnectionMonitor` — `last_heartbeat_ms` past `heartbeat_timeout_ms` → dead connection.
- `DisconnectPolicy` — `resign_deadline_ms = disconnect_ms + 20000` → forced resign. The
  deadline is sent to the client in `OpponentDisconnected(deadline_server_ms)` so the UI
  countdown renders from the authoritative number, not a locally-started timer.

The async layer is one dumb driver in `server/app.py`:
```python
async def _tick_forever(ticker, clock, interval_ms):   # pragma: no cover
    while True:
        ticker.tick(clock.now_ms())
        await asyncio.sleep(interval_ms / 1000)
```
Tests call `ticker.tick(0)`, `ticker.tick(59_999)`, `ticker.tick(60_000)` and assert on
published events. Zero real waiting.

`GameRoom.tick(now_ms)` first drains `command_queue` (see below), then computes
`dt = min(now_ms - last_tick_ms, MAX_ENGINE_STEP_MS)` and calls `session.wait(dt)`, then emits a
`StateUpdate` once `now_ms - last_broadcast_ms >= 1000 / broadcast_hz`. `tick_hz` and
`broadcast_hz` are independent config keys (see `[server]` below), not one derived from the
other — by default the engine ticks faster than it broadcasts (100Hz vs 20Hz), keeping
collision granularity fine while capping bandwidth, but either can be retuned without touching
the other (e.g. raising `tick_hz` for finer collision resolution on a LAN game without changing
how often clients receive updates).

### Blocking work never runs on the event loop: the DB executor

`SqliteUserRepository` is synchronous, and so is `hashlib.pbkdf2_hmac`. Both are reached from
code that would otherwise run directly on the `asyncio` loop, which would stall **every**
connected client — not just the one being served — for the duration of a disk read or a key
derivation. There are two distinct offenders, and the second is worse than the first:

| Path | Reached from | Blocks |
|---|---|---|
| `AuthService.login/register` → `find_by_username`/`create` + `pbkdf2_hmac` | the websocket handler, per `LoginRequest` | the loop, so every other client's frames queue behind one login |
| `GameRecordRepository.record_result` + `update_elo` (ELO write-back) | the `GAME_OVER` subscriber, which fires **inside `GameRoom.tick`** via `RoomTicker` | the tick fan-out — i.e. the simulation of *every room on the server*, not just the one that ended |

The second is the one that actually threatens gameplay: a disk write on game over would jitter
the clock of every unrelated live match sharing the ticker.

**Decision: a single-threaded `ThreadPoolExecutor` (`max_workers=1`) owned by `server/app.py`,
not an async SQLite library.** Three reasons, in order:

- `pbkdf2_hmac` is **CPU-bound**. An async driver would unblock the query and leave the hash
  blocking the loop — it fixes half the problem. A thread offload fixes both with one mechanism.
- `max_workers=1` **serializes DB access**, which matches SQLite's single-writer model and
  removes any need for connection pooling, `check_same_thread` juggling, or write-lock retry.
- It adds **no dependency**, consistent with the PBKDF2/stdlib choice already made above.

**The offload lives strictly in the anemic adapter layer**, which is what keeps the plan's
testing story intact. `AuthService`, `EloCalculator`, and `SqliteUserRepository` stay **plain
synchronous, clock-injected classes tested with hand-written fakes** — none of them learns the
word `async`. Only `server/app.py` and `server/presentation/ws_server.py` touch the executor:

```python
# server/presentation/ws_server.py  (pragma: no cover — anemic adapter)
result = await loop.run_in_executor(db_executor, auth_service.login, username, password)
```

Two call shapes, deliberately different:

- **Reads on the request path are awaited** (`login`, `register`) — the client is waiting for
  `AuthOk`/`AuthError`, so the handler for *that one connection* suspends while other
  connections continue to be served. That is the entire point.
- **Writes off the tick path are fire-and-forget** (`record_result`, `update_elo`) — `GameRoom`
  must not wait on a disk write to finish its tick. The `GAME_OVER` subscriber that performs ELO
  write-back is therefore split: the in-memory part (publishing `GameEnded`, freeing the seat)
  stays synchronous inside the tick, and the persistence part is handed to the executor via
  `loop.call_soon_threadsafe`-safe submission behind a `DbWriter` Protocol
  (`submit(fn, *args) -> None`). Tests inject a `FakeDbWriter` that runs `fn` inline, so
  assertions stay synchronous and deterministic.

This narrows — and does not contradict — the "the async layer is one dumb driver" claim above:
the async surface is still only `server/app.py` plus the transport adapter. What changes is that
the driver now owns **two** execution contexts (the loop and a one-thread DB executor) instead of
one, and the boundary between them is the same Protocol seam everything else in this plan uses.

*Tests:* `AuthService` and the ELO write-back subscriber are tested directly, synchronously, with
fake repositories — unchanged by this section. One adapter-level test asserts the handler calls
`run_in_executor` rather than invoking the repository inline (spy executor), and one asserts a
`GAME_OVER` tick completes without the `DbWriter` having finished — i.e. that the tick does not
block on persistence.

### Command queue draining is synchronous and happens before the clock advances

Moves arrive on the asyncio/websockets event loop at arbitrary points between ticks; letting a
`MoveRequest` mutate engine state *mid*-tick would risk a piece being redirected after its
motion has already been partially resolved for that frame — exactly the kind of async
interleaving bug the "no `asyncio.sleep` in business logic" rule (above) is designed to avoid,
extended to the inbound side too.

Fix: the dispatcher never calls into the engine from the websocket handler. It resolves `color`
from `ClientSessionRegistry` (never trusting the message), builds a `PendingMove`, and calls
`GameRoom.enqueue_move`, which only pushes onto a per-room `command_queue: Queue[PendingMove]`.
`GameRoom.tick(now_ms)` begins with, in strict order, and with no `await` between them (so the
sequence is atomic with respect to the event loop — nothing can interleave a queue push between
"read the queue" and "apply the moves"):

1. **Drain** — pop every `PendingMove` currently on the queue (bounded by what's there *now*;
   anything enqueued mid-drain waits for the next tick) and apply each via
   `session.request_move`, building the corresponding `MoveAck`s.
2. **Advance** — only then call `session.wait(dt)`.
3. **Broadcast** — build and send `StateUpdate` per the `broadcast_hz` gate above.

This is the server-side mirror of `RemoteGameSession.wait` draining `inbound_game` before calling
`estimator.advance` (see "Preserving the two-clocks rule," below) — both sides follow "drain
fully, *then* advance the clock" as a fixed rule, never the reverse. It is what makes
`GameRoom.tick` safe to reason about with ordinary synchronous tests: `tick(now_ms)` is a pure
function of `(command_queue, session state, now_ms)` with no concurrent mutation possible inside
its body.

### End-to-end observability: TraceID propagation and structured audit logging

**Where a trace begins and where it stops.** A `TraceId` (`common/tracing.py`, above) is minted
exactly once, at the Presentation gate — `server/net/dispatcher.py`, the instant a raw message
is parsed off the socket — via an injected `TraceIdGenerator`. From there it is threaded through
ordinary function arguments and returned dataclasses, never a contextvar or thread-local, in
keeping with this plan's synchronous, clock-injected style:

- `MoveRequest` → dispatcher resolves `color` and builds `PendingMove(..., trace_id=trace_id)`
  (already added to the dataclass above).
- `GameRoom.tick`, while draining, applies each `PendingMove` and — via the same
  `game_room.py` adapter that turns an `EngineEvent` into a `common.events.Event` (see "Getting
  events out of the engine," below) — publishes that event with `trace_id=pending.trace_id`.
- For events with no single originating request (e.g. a `MOVE_STOPPED` that resolves during
  `session.wait(dt)` from a collision between two independently-submitted moves), `GameRoom`
  falls back to a per-tick `trace_id` from the same generator, so **every** published `Event`
  carries one — never `None` in practice, even though the field is `Optional` for the rare
  engine-internal test event that has no request behind it at all.
- `BroadcastObserver` (above) copies `event.trace_id` onto the outgoing `DeltaEvent` unchanged.
- `activity_log.py` writes it into the structured log line (format below).

**`kfchess` itself stays trace-free.** This mirrors the reasoning already given for
`EngineEvent` (below, "Getting events out of the engine"): threading a `trace_id` into
`GameEngine.request_move` would touch the VPL path's call signature and risk the
byte-identical-output guarantee for zero benefit, since VPL scripts have no request to
correlate. The trace boundary is the same `server/services/game_room.py` adapter that already
converts engine-internal types to `common.events.Event` — one more field on an existing
translation, not a new seam.

**Structured audit log format**, one JSON object per line, written by `activity_log.py`
(server-side) and an equivalent client-side subscriber for `DeltaEvent`-driven effects:
```json
{"trace_id": "a1b2c3d4", "room_id": "f3k9dz", "layer": "domain", "event": "PIECE_CAPTURED",
 "at_ms": 43210, "execution_time_ms": 0.8}
```
`layer` is one of `presentation | application | domain`, set by whichever tier logs the line
(the dispatcher logs `presentation`-tier rejections directly; `activity_log.py` logs
domain events at `domain`; a future Application-tier audit line, e.g. a rejected `MoveRequest`
for a non-`RUNNING` room, logs `application`). `execution_time_ms` is wall-clock time to handle
the request, measured with the injected `Clock`, not `time.perf_counter()` directly, so it stays
fake-clock-testable. This reuses `common/logging_setup.py` (already in the plan for req 7) for
the underlying handler/rotation config; it changes the *record shape* logging emits, not where
logging is configured.
*Tests:* a `FakeTraceIdGenerator` produces deterministic ids; a full-stack test asserts the same
`trace_id` appears on the `MoveAck`, the `DeltaEvent`, and the `activity_log` line produced by
one `MoveRequest`.

### Engine config injection — and its asymmetry

Two of three knobs are already injectable; the third is not.

- **Already injectable:** `RealTimeArbiter.__init__` (`realtime/real_time_arbiter.py:37-45`)
  accepts `cooldown_policy` and `movement_profiles` — the factory just never passes them.
  `MOVE_DURATION_MS_PER_CELL` is a module constant read by `SlidingProfile`/`JumpingProfile`,
  so those two need a `ms_per_cell` ctor param defaulting to the existing constant.
- **Not injectable:** `GameEngine` imports `points_for` directly (`game_engine.py:7`, used at
  `:120`). Add a frozen `ScoringPolicy` wrapping a kind→points mapping, give `GameEngine` an
  optional `scoring: Optional[ScoringPolicy] = None`, and keep the module-level `points_for`
  so nothing else breaks.

`create_game_session` gains two optional params, both defaulting to `None`, so
`ui/main.py:70`'s existing call keeps working verbatim:
```python
def create_game_session(
    starting_board_text: str,
    config: Optional[EngineConfig] = None,
    event_sink: Optional[EngineEventSink] = None,
) -> GameSession:
```

**The VPL path never receives config** — it builds its own arbiter at `script_runner.py:48-52`
and keeps hard-coded defaults. Deliberate: graded output must be byte-identical regardless of
what is in `config/default.toml`.

### Client threading model

Three contexts, but the **main thread is phased**, never concurrent with itself:

```
Main thread:  Shell REPL (blocking input())  →  cv2 game loop  →  Shell REPL  → ...
BG thread:    asyncio loop + websockets connection (started once, lives for the process)
```

`client/net/client_link.py` owns both queue endpoints. Exactly three things cross the
boundary, all **immutable frozen dataclasses** on `queue.Queue` — no locks, no shared mutable
state, no engine object:

1. `outbound: Queue[Message]` — main → ws (moves, shell commands, heartbeats)
2. `inbound_game: Queue[Message]` — ws → main (`StateUpdate`, `MoveAck`, `GameEnded`,
   `OpponentDisconnected`, `HeartbeatAck`, `DeltaEvent` — routed here, not `inbound_shell`,
   because `RemoteGameSession.wait` is what feeds `HeartbeatAck` to
   `ClockEstimator.on_heartbeat_ack` and republishes `DeltaEvent` onto the client `EventBus`,
   every frame)
3. `inbound_shell: Queue[Message]` — ws → main (`AuthOk`, `MatchFound`, `RoomCreated`, `MatchTimedOut`)

`RemoteGameSession.wait(ms)` is called every frame at 60fps, so network ingestion is naturally
paced at 60Hz against a 20Hz feed, and bus subscribers (audio, animations) fire on the main
thread. When `GameEnded` arrives, `game_over` flips and `run_game_loop`'s
`while running and not session.game_over` exits, returning control to the REPL.

**Known limitation, handled explicitly:** a `MatchFound` arriving while the REPL blocks in
`input()` cannot interrupt it. The REPL calls `shell.drain_notifications()` at the top of every
iteration, immediately before printing the prompt — so the user sees "Match found! Opening
board…" as soon as they press Enter on anything. A non-blocking prompt is out of scope.

Shutdown: `ws_client.stop()` sets an `asyncio.Event` via `loop.call_soon_threadsafe`; the bg
thread is a daemon so a hard exit can never hang the process.

### Import-linter contracts

```toml
[tool.importlinter]
root_packages = ["kfchess", "ui", "common", "protocol", "server", "client"]

[[tool.importlinter.contracts]]
name = "Client stack layers"
type = "layers"
layers = ["client", "ui", "protocol", "kfchess", "common"]

[[tool.importlinter.contracts]]
name = "Server stack layers"
type = "layers"
layers = ["server", "protocol", "kfchess", "common"]

[[tool.importlinter.contracts]]
name = "Server internals layers"
type = "layers"
layers = ["server.app", "server.net", "server.services", "server.data"]

[[tool.importlinter.contracts]]
name = "Server and client/ui never see each other"
type = "forbidden"
source_modules = ["server"]
forbidden_modules = ["ui", "client"]

[[tool.importlinter.contracts]]
name = "ui and client never see the server"
type = "forbidden"
source_modules = ["ui", "client"]
forbidden_modules = ["server"]

[[tool.importlinter.contracts]]
name = "client only crosses into kfchess.api"
type = "forbidden"
source_modules = ["client"]
forbidden_modules = [
    "kfchess.model", "kfchess.rules", "kfchess.realtime",
    "kfchess.engine", "kfchess.input", "kfchess.io", "kfchess.texttests",
]
allow_indirect_imports = true

[[tool.importlinter.contracts]]
name = "Engine and shared layers never import outward"
type = "forbidden"
source_modules = ["kfchess", "common", "protocol"]
forbidden_modules = ["server", "client", "ui"]

[[tool.importlinter.contracts]]
name = "VPL path stays free of networking"
type = "forbidden"
source_modules = ["kfchess"]
forbidden_modules = ["websockets", "asyncio", "socket", "sqlite3"]
```

The existing `"ui only crosses into kfchess.api"` contract is kept verbatim. The last contract
mechanically enforces that the graded offline path can never grow a network dependency.

*Note:* `kfchess/api/factory.py:6` already imports `kfchess.texttests.script_parser` — a
pre-existing quirk (`api` reaching sideways into `texttests`). It does not block any contract
above, but is worth a follow-up: move `parse_board_grid` into `kfchess/io/`.

---

## Architectural improvements

Five refinements layered on top of the design above. Each is written to reconcile with — not
re-decide — the choices already made; where one overlaps an existing element (the
`net/services/data` layout, `MoveResult`, `DisconnectPolicy`), that overlap is named explicitly
rather than duplicated.

### 1. Adopt an explicit DDD directory layout

Rename the server's flat, functional folders (`net/`, `services/`, `data/`) to layer-named
directories so the dependency direction is legible from the path alone and inward-only
imports are enforced structurally rather than by convention:

| New layer dir | Supersedes | Holds |
|---|---|---|
| `server/presentation/` | `server/net/` | `ws_server.py`, `connection.py`, `dispatcher.py`, `heartbeat.py` — transport adapters + the Presentation gate |
| `server/application/` | `server/services/` | `auth_service.py`, `elo.py`, `matchmaking.py`, `room_service.py`, `game_room.py`, `room_ticker.py`, `disconnect_policy.py`, `activity_log.py`, `broadcast_observer.py` — use-case orchestration |
| `server/domain/` | *(new, thin)* | `client_session.py` (`ClientSession` + registry Protocol), `RoomStatus`, `PendingMove`, and the server's own value objects — the entities/invariants the server owns that are **not** game rules |
| `server/infrastructure/` | `server/data/` | `repositories.py`, `sqlite_user_repository.py`, `schema.sql`, `connection_factory.py`, and the logging/hashing adapters |

**Honest note on the thin `domain/` layer:** the *rich* game domain lives in `kfchess/`, one
package down, and stays there — the server does not reimplement chess. `server/domain/` holds
only the server-specific invariants (a connection's identity/role, a room's lifecycle status)
that have no place in the engine but are still pure data + rules, not orchestration. `GameRoom`
stays in `application/` because its job is orchestration (drain → advance → broadcast); its
*invariants* (seat assignment, `RoomStatus` transitions) are expressed through the value objects
it imports from `domain/`. This keeps the "Application use cases, kept separate from domain
logic" decision above intact under the new names.

The single-direction rule (`presentation → application → domain`, and everything →
`infrastructure` only through Protocols) replaces the existing "Server internals layers"
import-linter contract:

```toml
[[tool.importlinter.contracts]]
name = "Server internals layers"
type = "layers"
layers = ["server.app", "server.presentation", "server.application", "server.domain"]

[[tool.importlinter.contracts]]
name = "Infrastructure is reached only through Protocols"
type = "forbidden"
source_modules = ["server.domain", "server.application"]
forbidden_modules = ["server.infrastructure.sqlite_user_repository",
                     "server.infrastructure.connection_factory"]
allow_indirect_imports = true
```

All file paths named elsewhere in this document (`server/net/dispatcher.py`,
`server/services/game_room.py`, `server/data/repositories.py`, …) refer to their post-rename
locations under this layout; the "Proposed directory structure" tree above is the pre-rename
sketch and this section is authoritative on final placement.

### 2. Compatibility re-exports (Facade) for migration safety

The rename in (1) — and any later move — would break every `from server.net.dispatcher import
MessageDispatcher` in the test tree at once. To make each migration a mechanical, reviewable
step rather than a big-bang rewrite, add **module-level re-export shims** at the old import
paths for the duration of the migration:

```python
# server/net/__init__.py  (compatibility facade — remove once all imports are updated)
from server.presentation.dispatcher import MessageDispatcher  # noqa: F401
from server.presentation.connection import Connection, WebSocketManager  # noqa: F401
```

Rules that keep the facade from becoming permanent debt:

- A shim contains **only** re-exports — never logic. If a shim needs a body, the move was done
  wrong.
- Each shim carries a `# compatibility facade — remove by end of Phase <n>` comment, and its
  removal is a checklist item in the phase that finishes the corresponding move.
- The import-linter layer contracts are written against the **new** paths, so a shim cannot be
  used to smuggle in a dependency that violates layering — it only forwards names.

This is the same idea as `kfchess.api` re-exporting `Position`/`PieceView`/… as a stable public
seam, applied temporarily to the internal server tree during restructuring.

### 3. Domain validation via a `Result[T]` pattern

Introduce a small, frozen `Result[T]` in `common/` and have domain-facing methods that can fail
return it instead of raising, returning sentinels, or (worst) mutating on the failure path:

```python
# common/result.py
@dataclass(frozen=True)
class Result(Generic[T]):
    ok: bool
    value: Optional[T] = None
    error: Optional[str] = None      # a stable reason constant, never a free-text message

    @staticmethod
    def success(value: T) -> "Result[T]": ...
    @staticmethod
    def failure(reason: str) -> "Result[T]": ...
```

**Relationship to the existing types, stated so this does not fork the vocabulary:**

- `kfchess`'s public `MoveResult` (`kfchess/api/dto.py`) and the `MoveRejectionReason` constants
  stay exactly as they are — they are already a result-return type in spirit and the VPL path
  depends on their shape. `Result[T]` is **not** retrofitted into `GameEngine.request_move`;
  doing so would touch the byte-identical graded path for no gain (same reasoning as
  "`kfchess` itself stays trace-free").
- `Result[T]` is for the **server/application and server/domain** methods that today would
  otherwise signal failure ad-hoc: `AuthService.register/login` (already sketched as returning
  `AuthResult` — fold that into `Result[AuthOk]`), `RoomService.join` (`JoinResult` →
  `Result[Room]`), `MatchmakingService.enqueue`, and `ClientSessionRegistry` binds. The
  invariant the pattern buys: **a method that returns `Result.failure(...)` has performed no
  state mutation** — no half-registered user, no seat consumed on a rejected join. This is the
  application-layer analogue of the "rules never mutate `Board`" purity rule.
- `error` carries a stable reason constant (like `MoveRejectionReason`), so the dispatcher can
  map it to a wire `reason` field and the audit log can key on it — never a localized string.

*Tests:* every `Result.failure` path asserts the relevant repository/registry was **not**
mutated (spy fake), mirroring the "rejected at that gate, never mutates state one layer further
in" guarantee in the gatekeeping table.

### 4. Reconnection protocol: a timed grace period that holds session state

The plan already has the *punitive* half of disconnect handling — `DisconnectPolicy`'s 20s
countdown to auto-resign (`disconnect_grace_ms`) and `ClientSessionRegistry.by_user` for
re-binding a returning connection. This improvement makes the *state-preservation* half
explicit: during the grace window the player's `ClientSession` (identity, room, role, ELO) and
their seat in the `GameRoom` are **held, not released**, so a reconnect is a re-bind rather than
a re-join from scratch.

- **On disconnect** (`ConnectionMonitor` reports a dead `ConnectionId`): `DisconnectPolicy`
  starts the countdown *and* the session is moved to a `pending_reconnect` state keyed by
  `user_id` with `reconnect_deadline_ms = now_ms + disconnect_grace_ms` — the same deadline
  already sent to the opponent in `OpponentDisconnected(deadline_server_ms)`. The seat is **not**
  freed; `ClientSessionRegistry.release(conn_id)` is *not* called yet.
- **On reconnect within the window** (a fresh `Connection` authenticates as the same `user_id`):
  `ClientSessionRegistry` rebinds the existing `ClientSession` to the new `ConnectionId`,
  `DisconnectPolicy.on_reconnect` cancels the pending resign, the opponent gets
  `OpponentReconnected`, and the returning client is sent `GameStarted` + the current
  `StateUpdate` — which is exactly the `ClockEstimator` mid-game rebasing path already built for
  spectators. **No new client code:** rejoin reuses the join-in-progress ingestion path.

**Reconnect must not depend on the disconnect having been noticed first.** `ConnectionMonitor`
only reports a connection dead after `heartbeat_timeout_ms` (10s) elapses with no heartbeat. A
client whose link drops and is restored inside that window reconnects while the server still
believes the old `ConnectionId` is live — so `by_user` would find a session bound to a dead
socket, the user would hold two registry entries, and the seat's identity would depend on which
of the two paths ran first. Two mechanisms close this, and both are required:

**(a) Proactive eviction, gated on successful authentication.** The moment a connection
authenticates as `user_id` U, the server *unconditionally* tears down any existing binding for U
before establishing the new one — it never inspects whether the old link is believed healthy.
Eviction is: close the old `Connection`, `unregister` it from `WebSocketManager` **and** drop its
entry from `ConnectionMonitor` (both, or the monitor keeps ticking a connection nobody owns), then
rebind the surviving `ClientSession` to the new `ConnectionId`. Authentication is the gate
because it is the point at which the reconnecting party has proven it is entitled to seize U's
seat; an unauthenticated frame can never evict anyone.

**This collapses reconnection into a single idempotent path.** "Reconnect after the monitor
noticed" and "reconnect before the monitor noticed" stop being two cases: both are *evict-then-
rebind*, and the only difference is whether `DisconnectPolicy.on_reconnect` finds a countdown to
cancel (it is a no-op if not). There is no ordering dependency left between `ConnectionMonitor`
and the reconnect handler.

**(b) A session epoch, so the late teardown is harmless.** Eviction fixes the arrival order but
not its aftermath: `ConnectionMonitor` will still declare the *old* `ConnectionId` dead seconds
later, and that callback must not release the session the new connection is now using. Give
`ClientSession` a monotonically increasing `epoch: int`, bumped on every bind and rebind, and
stamp each `ConnectionId` registration with the epoch current at registration time. Every
teardown path — `ConnectionMonitor.tick`'s dead list, `DisconnectPolicy`, the transport's own
close callback — is then required to **compare epochs and no-op when the stamped epoch is older
than the session's current epoch**:

```python
def on_connection_dead(self, conn_id: ConnectionId, epoch: int, now_ms: int) -> None:
    session = self._registry.get(conn_id)
    if session is None or epoch < session.epoch:
        return          # stale: this conn was already evicted by a newer login
    ...                 # genuine disconnect; start the grace countdown
```

The epoch is the mechanism that actually makes the race unobservable. Eviction alone would still
leave a live session vulnerable to a delayed callback fired against the identity it replaced.

*Tests for the race specifically:* a reconnect arriving **before** `ConnectionMonitor` has
declared the old connection dead rebinds successfully and leaves exactly one registry entry for
the user; the old connection's subsequent monitor-declared death is a **no-op** that neither
releases the session nor starts a countdown (assert via a spy `DisconnectPolicy` that it was never
called); the old `Connection.close()` was invoked exactly once and its `ConnectionMonitor` entry
was dropped; a genuine disconnect with no intervening reconnect still starts the countdown
normally (the epoch check must not suppress real teardowns).
- **On deadline expiry** (`DisconnectPolicy.tick` fires `ForcedResign`): *now* the session is
  released and the seat freed, `GAME_OVER` is published (driving ELO write-back via the existing
  subscriber), and the game ends.

This adds one state (`pending_reconnect`) and one deadline field; it introduces no new timer
mechanism — it rides the synchronous `tick(now_ms)` sweep already used for every timeout. It
does **not** add cross-session reconnection across server restarts (state is in-memory); that is
a deliberate out-of-scope boundary, same class of decision as `ws://`-not-`wss://`.

*Tests:* reconnect at `deadline - 1ms` rebinds and cancels the resign (seat never freed);
reconnect at `deadline + 1ms` finds the seat already gone and is treated as a fresh join/spectate;
the opponent receives `OpponentReconnected` exactly once.

### 5. Tick-stamped logging for replayability

Stamp every validated move with the authoritative simulation tick at which it was applied, so a
completed game's move log is a **deterministic replay script**, not just an audit trail. The
engine is already fully deterministic under `wait(ms)` (the property the VPL harness depends on);
capturing the exact `server_ms` per applied move closes the loop between a live network game and
the offline, reproducible engine.

- When `GameRoom.tick` drains and applies a `PendingMove`, the resulting `MOVE_LOGGED`
  `Event` — and the `move_log` entry carried in `StateUpdate` — gains an `at_tick_ms` field set
  to `session.clock_ms` **at apply time** (the same authoritative value already stamped as
  `EngineEvent.at_ms`). Since a whole drain batch applies before `session.wait(dt)`, every move
  in one drain shares that tick, which is correct: they were all applied at the same simulated
  instant.
- `activity_log.py` writes `at_tick_ms` into its structured JSON line (it already logs `at_ms`
  from the event; this makes the field a first-class, queryable key). Combined with the
  `trace_id` from the observability section, one line now answers both "which request caused
  this" and "at which simulation tick" — the two coordinates a replay needs.
- **Replay reconstruction** (a natural extension, not required for the core feature): feeding the
  ordered `(at_tick_ms, color, from, to)` tuples of a recorded game into a fresh
  `EngineGameSession` — advancing `wait()` to each `at_tick_ms` and issuing the move — must
  reproduce the identical final board and score. This is directly testable offline with no
  network, and doubles as the strongest possible determinism regression for the engine seams in
  Phase 1.

`at_tick_ms` is additive on `MOVE_LOGGED`, the `move_log` DTO, and the audit line only; it does
**not** enter the VPL path (whose logs must stay byte-identical) and does not change any
position authority — `StateUpdate` remains the sole source of truth for where pieces are.

*Tests:* two moves drained in the same tick share one `at_tick_ms`; a recorded game replayed
tick-by-tick against a fresh engine yields a bit-identical final `BoardSnapshot` and `Scoreboard`.

---

## Implementation phases

Each phase leaves the suite green, the VPL output byte-identical, and the local OpenCV game
playable.

**Phase 0 — Foundations (no behavior change).**
Bump `requires-python = ">=3.11"` (stdlib `tomllib`). Declare `pytest`, `coverage` (currently
undeclared) and `websockets` in `pyproject.toml`. Add `common/` and `config/default.toml`. Add
the `common` root package + contracts to import-linter.
*Tests:* `tests/common/` — clock, event bus fan-out and exception isolation (`Event.trace_id`
round-trips through `publish`/`subscribe` unchanged), `TraceIdGenerator` fakes are deterministic
and collision-free within a test run, config loader (env-override precedence, missing-key
defaults), logging setup (structured JSON record shape: `trace_id`/`room_id`/`layer`/
`execution_time_ms` keys always present).

**Phase 1 — Engine seams.**
`GameEngine.wait` returns outcomes; `ScoringPolicy`; `ms_per_cell` on movement profiles;
`EngineConfig`; `kfchess/api/events.py`; `engine_mapping.outcome_to_event`; factory and
`EngineGameSession` gain optional params.
*Tests:* extend `tests/engine/test_game_engine.py` (outcomes returned, custom scoring),
`tests/api/test_session.py` (events emitted via a `FakeEventSink`; **nothing** emitted when
sink is `None`), `tests/api/test_factory.py` (config threading).
**Regression gate:** run the VPL corpus and diff stdout against pre-change output.

**Phase 2 — Protocol + persistence.**
`protocol/messages.py`, `protocol/codec.py` (round-trip every message type incl.
`BoardSnapshot`/`MotionInfo`/`Scoreboard` fidelity, plus malformed-input rejection).
`server/data/` with `schema.sql` and `SqliteUserRepository` tested against
`sqlite3.connect(":memory:")` — deterministic, no files on disk.

**Phase 3 — Server services (largest phase).**
`AuthService`, `PasswordHasher`, `EloCalculator`, `MatchmakingService`, `RoomService`,
`RoomIdGenerator`, `ConnectionMonitor`, `DisconnectPolicy`, `GameRoom`, `RoomTicker`,
`MessageDispatcher`, `ConnectionRegistry`, `ClientSessionRegistry`. Every timeout tested by
calling `tick(now_ms)` at boundary values. `GameRoom` tested with a **real**
`EngineGameSession` (it is deterministic) plus a `FakeWebSocketManager` capturing broadcasts.
*Tests must include the authorization cases:* a viewer's `MoveRequest` is rejected; a
`MoveRequest` naming a color the connection does not own is resolved to the connection's own
role, not the requested one; an unbound connection is rejected.
*Tests must include the queue-draining cases:* `GameRoom.tick` applies everything enqueued
before the tick started and defers anything enqueued during drain to the next tick; a move
enqueued after `wait(dt)` would have made it illegal (piece already moving) is rejected via its
`MoveAck`, not silently dropped or applied against stale state.
*Tests must include the EventBus wiring:* `GameRoom` publishing `GAME_OVER` / `MOVE_LOGGED` /
`PIECE_CAPTURED` is asserted via a subscribed fake handler, never via a direct call into ELO
write-back or `activity_log`; `MatchmakingService.tick` publishing `MATCH_FOUND` is asserted the
same way, with no direct reference from `MatchmakingService` to `RoomService`.
*Tests must include the gatekeeper tiers:* a `MoveRequest` for a room whose `status` is
`WAITING` or `ENDED` is rejected at the Application gate (asserted via `MoveAck(accepted=False)`
and that `GameEngine.request_move` was never called — use a spy/counting fake session); an
oversized raw frame is rejected at the Presentation gate before `codec.decode` runs.
*Tests must include tracing:* a `PendingMove`'s `trace_id` reaches the `Event` published for its
resulting `MOVE_LOGGED`/`PIECE_CAPTURED`/`GAME_OVER`, unchanged; a per-tick fallback `trace_id`
is used (and is non-`None`) for events with no originating `PendingMove`.
*Tests must include the reconnect race:* the four cases listed under "Reconnection protocol" —
reconnect before the monitor declares death, the stale monitor callback no-op, eviction closing
and forgetting the old connection, and a genuine disconnect still starting its countdown.
*Tests must include `BroadcastObserver`:* subscribing to `PIECE_CAPTURED` produces a
`DeltaEvent` sent to every connection in the room via `FakeWebSocketManager`, independent of and
without waiting for the next `broadcast_hz`-gated `StateUpdate`.
*Ships:* the entire server, headless and fully driven by tests.

**Phase 4 — websockets adapter + server entry point.**
`server/net/ws_server.py`, `server/app.py`, plus the single-threaded DB executor and the
`DbWriter` seam (see "Blocking work never runs on the event loop"). One test: drive the handler
coroutine with a scripted fake websocket, assert it calls `register`/`dispatch`/`unregister`.
*Tests:* auth is dispatched through the executor rather than called inline (spy executor); a
`GAME_OVER` tick returns without waiting on `DbWriter`; per-connection outbound enqueue order
equals send order (the ordering guarantee "Event-driven broadcasting" relies on). `app.py` entirely
`# pragma: no cover`. Manually smoke-tested, never in the automated suite.

**Phase 5 — Client session.**
`ClockEstimator`, `SnapshotStore`, `ClientLink`, `RemoteGameSession`.
*Tests:* `isinstance(s, GameSession)` (the Protocol is `runtime_checkable`); the
**join-in-progress case** — first snapshot at `server_ms=45000` with `render_ms=0` still
yields `clock_ms` near 0 and advancing motions; monotonicity under a backward-jumping server
timestamp; drift bounded by the catch-up rates; **the heartbeat-ack rebasing path** —
`on_heartbeat_ack` establishing (or correcting) the origin ahead of the first `StateUpdate` for
a spectator whose join races the broadcast loop, and RTT compensation shifting the offset by
half the simulated round-trip. Critically, drive the **real** `run_game_loop`
against a `RemoteGameSession` + `FakeCanvas` + `FakeClientLink`, proving the
"`game_loop` unchanged" claim rather than asserting it. **`DeltaEvent` handling:** a
`DeltaEvent` arriving on `inbound_game` is republished on the client `EventBus` under its
domain event name and never mutates `SnapshotStore`/board position — assert board state is
unchanged by a `DeltaEvent` alone and only changes on the next `StateUpdate`.

**Phase 6 — Client shell + entry point.**
`Shell` (tested exhaustively against `FakeClientLink`), `commands.py`, `repl.py`,
`ws_client.py`, `client/app.py` (last three pragma'd). Refactor `ui/main.py`'s `_build_scene()`
to take an injected `session` so local and remote entry points share it.

**Phase 7 — Cross-cutting polish.**
Client bus subscribers for audio and start/end animations, now driven by `DeltaEvent`-sourced
events rather than snapshot diffing; disconnect-countdown overlay in the renderer; server-side
`activity_log.py` structured-JSON logging subscribers; ELO write-back on `GAME_OVER`.

---

## Configurations to extract

`config/default.toml` → frozen dataclasses via `common/config/loader.py`. Env overrides
(`KFC_DB_PATH`, `KFC_HOST`, `KFC_PORT`, `KFC_LOG_LEVEL`) applied *after* TOML.

**`[engine]`** — from hard-coded constants (VPL keeps defaults regardless):

| Key | Current source |
|---|---|
| `move_duration_ms_per_cell = 1000` | `realtime/movement_profile.py:12` |
| `jump_duration_ms = 1000` | `realtime/real_time_arbiter.py:16` |
| `move_cooldown_ms = 1000` | `realtime/cooldown.py:7` |
| `jump_cooldown_ms = 500` | `realtime/cooldown.py:8` |
| `point_values` (P1 N3 B3 R5 Q9 K10) | `rules/scoring.py:11-18` |
| `starting_board` | `ui/main.py:36-45` |

**`[server]`** — `host = "127.0.0.1"`, `port = 8765`, `tick_hz = 100` (engine step cadence —
replaces a hard-coded 10ms interval), `broadcast_hz = 20` (state-broadcast cadence — replaces
the hard-coded 50ms interval), `max_engine_step_ms = 100` (from `ui/game_loop.py:33`). Kept as
two independent keys rather than one derived from the other, so physics/collision granularity
(`tick_hz`) and network bandwidth (`broadcast_hz`) can be tuned separately; `GameRoom.tick`
converts each to milliseconds internally (`1000 / hz`).

**`[matchmaking]`** — `elo_window = 100`, `timeout_ms = 60000`, `starting_elo = 1200`,
`k_factor = 32`.

**`[connection]`** — `heartbeat_interval_ms = 3000`, `heartbeat_timeout_ms = 10000`,
`disconnect_grace_ms = 20000`, `max_frame_bytes = 16384` (Presentation-gatekeeper ceiling; see
"Multi-layered fail-fast gatekeeping").

**`[rooms]`** — `max_viewers = 8`, `room_id_length = 6`.

**`[database]`** — `path = "kfchess.db"` (env `KFC_DB_PATH`).

**`[logging]`** — `level`, `client_file`, `server_file`, `format`, `max_bytes`, `backup_count`.

**`[client]`** — `fps = 60` (from `ui/game_loop.py:27`), `server_url`,
`resync_threshold_ms = 1000`, `max_catchup_rate = 1.20`, `min_catchup_rate = 0.85`.

**Deliberately not extracted:** the ~30 constants in `ui/ui_config.py` (pixel geometry, panel
colors, sprite paths). They are presentation values with no server counterpart; folding them
into deployment config couples the renderer to it for no benefit. An independent refactor if
ever wanted.

---

## Verification

**Per phase:**
```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\lint-imports.exe
.venv\Scripts\python.exe -m coverage run -m pytest; .venv\Scripts\python.exe -m coverage report
```

**VPL regression gate (after Phase 1, then every phase):** capture stdout for each VPL script
before the change and diff after. Output must be byte-identical.
```powershell
.venv\Scripts\python.exe main.py < path\to\script.vpl
```

**Local game still playable (after Phases 1 and 6):**
```powershell
.venv\Scripts\python.exe ui\main.py
.venv\Scripts\python.exe ui\main.py --no-window   # headless frame capture
```

**End-to-end multiplayer smoke test (after Phase 6)** — manual, not in the suite:
1. `python -m server.app` in one terminal.
2. Two client terminals: `python -m client.app`. Register two users, confirm both start at ELO 1200.
3. `play` in both within the ±100 window → both receive `MatchFound`, boards open, White and Black assigned.
4. Move a piece in one client; confirm it animates smoothly in **both**, and that the move log
   and score panel update on both.
5. Create a room in a third client, join with two more → confirm P1=White, P2=Black, P3=Viewer,
   and that the viewer's board animates correctly **despite joining mid-game** (this is the
   `ClockEstimator` rebasing path — the highest-risk code in the plan).
6. Kill one client process → confirm the opponent sees a 20-second countdown and an auto-resign
   at zero, with ELO updated in SQLite.
7. `play` with only one client queued → confirm `MatchTimedOut` after 60 seconds.
8. Inspect the client and server log files for the full activity trail.

**Determinism guard:** the suite must contain no `time.sleep`, no real sockets, no
`pytest-asyncio` integration tests, and no wall-clock assertions. If a new test needs to wait,
that is a signal the logic under test is missing an injected clock.
