# Server_Design.md §2 — Role split, pass one

## Context

`Server_Design.md` §2 calls for splitting the single `Server` process (`server/main.py`)
into five independently-scaled roles (gateway, room-server, matchmaker, allocator,
settlement), coordinated through a Redis-backed room directory with lease-epoch fencing
(§8) instead of the in-process `rooms: Dict[str, GameRoom]` the whole object graph
currently shares by reference. This was deliberately deferred out of the §4/§12 pass
already completed on this branch (`feat/server-scaling-plan`) as its own design pass —
this is that pass.

**Why "pass one" and not the whole of §2**: §2's ADR-001 already decided gateways reach
room-servers via a relayed connection, not direct redirect. That relay is a real
persistent transport between two live OS processes. Building it now, with no second
process to relay to, produces code that can't be exercised end-to-end — exactly the
`full_move_log` dead-parameter mistake caught earlier this session, at far larger scale.
So this pass builds everything that **is** independently testable today — the seams a
real relay would plug into — and stops at the relay boundary itself. `docker-compose.yml`
already documents this staging (only `server` is uncommented; the five role services are
commented out pending `server.roles.*`); this pass makes four of those five
(`room`, `matchmaker`, `allocator`, `settlement`) real and honestly documents why
`gateway`'s standalone entry point still can't do useful work alone.

## What's in scope

1. **`RoomDirectory`** — the Redis-backed room registry from §2/§8, with an in-memory
   fake for tests, following the exact `ClientSessionRegistry`/`InMemoryClientSessionRegistry`
   precedent (`server/domain/client_session.py`).
2. **Lease-epoch fencing (§8)** — a room-server renews its claim every tick; on renewal
   failure it stops ticking and **abandons** the room (ends it `server_fault`, settled as
   a no-Elo draw, per §8's "don't recover — abandon" policy), instead of continuing to
   serve state it can't prove it owns.
3. **Settlement decoupled from the live `rooms` dict** — `RatingUpdater` currently calls
   `self._rooms.get(room_id)` to read seat user-ids and `clock_ms` at settlement time.
   That's a hard dependency on being in the same process as the room. Move that data onto
   the `GAME_OVER` event payload at publish time instead, so settlement can be driven
   purely from the event stream (a prerequisite for it ever being a separate consumer, and
   valuable independent of process topology).
4. **Game Allocator (§2)** — stateless consistent-hashing placement recommender over a
   room-server load signal. Pure logic, no I/O, easy to unit test in isolation.
5. **Per-role builders** — factor `build_server` (`server/main.py`) into narrower
   `server/roles/{room,matchmaker,allocator,settlement}.py` builders, each independently
   runnable (`python -m server.roles.<role>`), plus `server/roles/gateway.py` documented
   as blocked on the ADR-001 relay. `server/main.py`'s monolith builder is rewritten to
   compose all of them in one process — behaviorally unchanged from today.

**Out of scope for this pass** (explicitly deferred, not forgotten):
- The ADR-001 internal relay transport itself (gateway ↔ room-server).
- §5's Redis Streams durable event bus — settlement's entry point in this pass still
  consumes whatever `EventBus` it's given (in-process `InMemoryEventBus` in the monolith);
  making it consume a durable Redis Stream is §5's own pass.
- Actually running any of this against a live Redis — verified via hand-written fakes,
  same as every other infra seam in this codebase (`redis` is confirmed importable in
  `.venv`, version 8.0.1, so the real client code is written, but exercised only via its
  fake in tests, consistent with "Docker itself was never run" for §12).

## 1. `RoomDirectory` (domain Protocol + in-memory fake)

New file `server/domain/room_directory.py`, mirroring `client_session.py`'s shape:

```python
@dataclass(frozen=True)
class RoomLease:
    room_id: str
    server_id: str
    lease_epoch: int

@runtime_checkable
class RoomDirectory(Protocol):
    async def claim(self, room_id: str, server_id: str) -> RoomLease: ...
    async def renew(self, room_id: str, server_id: str, lease_epoch: int) -> bool: ...
    async def resolve(self, room_id: str) -> Optional[RoomLease]: ...
    async def release(self, room_id: str, server_id: str, lease_epoch: int) -> None: ...

class InMemoryRoomDirectory:
    ...
```

- `claim` mints `lease_epoch=1` on a fresh room_id, or increments the stored epoch if the
  slot is unclaimed/expired (mirrors `SET ... NX` + the "Allocator recommends, room-server
  claims" split from §2 — the caller already decided which `server_id` should own this
  room; the directory's job is only the atomic claim + epoch).
- `renew` succeeds only if `(room_id, server_id, lease_epoch)` still matches the stored
  lease; a stale epoch (lost ownership) returns `False` rather than raising — the caller
  (room-server ticker) decides what to do with that, per §8.
- Async because the Redis-backed implementation is async (`redis.asyncio`); the in-memory
  fake is async too so both satisfy the same Protocol without a sync/async split.

## 2. `server/infrastructure/redis_client.py` + `redis_directory.py`

Two module names are already pinned by the import-linter contract added in the §4/§12
pass (`pyproject.toml`, "Infrastructure is reached only through Protocols" and the
redis-isolation contract) — use these exact names, not `redis_room_directory.py`.

- `redis_client.py`: thin factory `create_redis_client(url: str) -> redis.asyncio.Redis`,
  the same shape as `infrastructure/connection_factory.py` for sqlite.
- `redis_directory.py`: `RedisRoomDirectory` implementing `RoomDirectory`. Primitive
  choice, picked for fake-ability (per advisor guidance — no Lua):
  - Store `f"{server_id}:{lease_epoch}"` as the value at key `room:{room_id}`.
  - `claim`: `GET` then `SET ... NX EX <ttl>` if absent/expired, else increment epoch and
    `SET` unconditionally (still safe: only reached after confirming no live claim).
  - `renew`: `SET key value XX EX <ttl> GET` — compare the returned old value to what's
    expected; only refresh the TTL if it matched. No Lua required.
  - Tested against a hand-written fake redis client (a small dict-based stand-in
    implementing just `get`/`set`/`delete` with the `nx`/`xx`/`ex`/`get` kwargs actually
    used) — consistent with "collaborators are replaced with hand-written fakes, not
    mocking frameworks" (CLAUDE.md §3).

## 3. Lease fencing in the room-server tick loop

New `server/application/room_server_ticker.py` (room-only ticker, split out of today's
`RoomTicker`, which currently also drives `connection_monitor`/`disconnect_policy`/
`matchmaking_service` — all gateway/matchmaker concerns that don't belong on a room-server
in a real split):

```python
class RoomServerTicker:
    def __init__(self, rooms: Dict[str, GameRoom], directory: RoomDirectory, server_id: str, lease_ttl_ms: int): ...
    async def tick(self, now_ms: int) -> None:
        for room_id, room in list(self._rooms.items()):
            lease = self._leases[room_id]
            if not await self._directory.renew(room_id, self._server_id, lease.lease_epoch):
                await room.abandon()          # §8: don't recover, abandon
                del self._rooms[room_id]
                continue
            await room.tick(now_ms)
```

Renewal is throttled to `lease_ttl_ms / 2` (heartbeat, not every tick) — same pattern as
`_broadcast_interval_ms` throttling in `GameRoom.tick`.

`GameRoom.abandon()` (new method, alongside the existing `force_resign`): ends the room
and publishes `GAME_OVER` with `reason="server_fault"` and no `resigned_color`/
`engine_event`. Existing `RatingUpdater._winner_color` already returns `None` for that
shape → settles as a draw, no Elo change — §8's exact requirement falls out of the
existing settlement logic with no special-casing needed there.

`RoomTicker` (today's fused version) stays as-is for the monolith path — it's correct for
a single process. `RoomServerTicker` is the standalone room-server's tick loop.

## 4. Settlement decoupled from `rooms`

`GameRoom` already has `player_user_ids()` and `session.clock_ms` available at the moment
it publishes `GAME_OVER` (in `emit()` for the engine-driven path, in `force_resign()` and
the new `abandon()` for the others). Enrich the payload at publish time instead of making
the subscriber dereference `self._rooms.get(room_id)` later:

- `emit()`: when `event.kind is EngineEventKind.GAME_OVER`, add `white_id`/`black_id`/
  `ended_at_ms` to the payload alongside `engine_event`.
- `force_resign()` / `abandon()`: same three keys added directly.

`RatingUpdater._on_game_over` drops its `rooms` constructor parameter entirely and reads
`white_id`/`black_id`/`ended_at_ms` straight off `event.payload` — no `self._rooms.get(...)`
left. This is the change that makes `server/roles/settlement.py` meaningfully standalone:
it never needs a `GameRoom` object, only the event.

`server/main.py`'s `RatingUpdater(...)` call site drops the `rooms=` argument to match.

## 5. Game Allocator

New `server/application/allocator.py`:

```python
@dataclass(frozen=True)
class ServerLoad:
    server_id: str
    room_count: int

class Allocator:
    def choose_server(self, room_id: str, candidates: Sequence[ServerLoad]) -> Optional[str]:
        ...  # consistent hashing over candidates, tie-broken toward lower room_count
```

Pure, no I/O, no Redis dependency itself (§2: "a separate, stateless, horizontally-scaled
service" — the load signal it consumes comes from wherever heartbeats are collected, out
of scope to build a full heartbeat pipeline this pass; `ServerLoad` is passed in, not
fetched). Hooks into both room-creation call sites — `MessageDispatcher._handle_create_room_request`
and `MatchRoomCoordinator._on_match_found` — as an optional collaborator: when present,
its recommendation is what `directory.claim(room_id, server_id=...)` uses; when absent
(monolith mode, one process, no fleet to choose from), room creation keeps today's
behavior unchanged (claims under a single fixed `server_id`).

## 6. Per-role builders

`server/main.py` currently has one `build_server(config) -> Server` doing everything.
Split into `server/roles/`:

- `server/roles/room.py` — `build_room_server(config) -> RoomServerProcess` wiring:
  `rooms` dict, `RoomServerTicker`, `RoomDirectory` (Redis-backed via `config.redis.url`),
  bus, event publishing. `if __name__ == "__main__": # pragma: no cover` runs its own
  tick-forever loop (same shape as `ws_server.run_server`'s driver, minus the websocket
  accept loop — a room-server has no public listener in ADR-001).
- `server/roles/matchmaker.py` — wires `MatchmakingService` + its tick loop, standalone.
- `server/roles/allocator.py` — wires `Allocator`; **no RPC surface exists yet** to expose
  it over the network (that's part of the relay/internal-transport work this pass
  explicitly excludes), so this entry point constructs the object and documents the gap
  rather than faking a network boundary that doesn't exist. Still worth having as the
  narrowed builder — it's what a future RPC wrapper would call into.
- `server/roles/settlement.py` — wires `RatingUpdater` (now `rooms`-free per §4 above) to
  whatever `EventBus` it's given. Standalone-runnable against the in-process bus is a
  no-op in a separate process (nothing publishes to it) — the docstring says explicitly
  that this role only becomes independently useful once §5's Redis Streams bus lands, and
  points at `Server_Design.md` §5.
- `server/roles/gateway.py` — **not built as a standalone entry point this pass.** Its
  docstring explains why: `MessageDispatcher` calls room methods directly in-process
  (`self._rooms[...].enqueue_move(...)`, `.assign_seat(...)`) — reaching a room in another
  process needs the ADR-001 relay, which doesn't exist yet. Documented as the next pass,
  not stubbed with fake behavior.
- `server/main.py`'s `build_server` is rewritten to call the room/matchmaker/allocator
  builders and compose them into one process alongside the dispatcher/websocket layer —
  identical externally-observed behavior to today, now expressed as composition of the
  same narrowed pieces the standalone roles use, rather than one flat function.

`docker-compose.yml` stays as-is (five roles still commented) except its comment is
updated: `room`/`matchmaker`/`allocator`/`settlement` now have real entry points but
still can't run as *separate containers* usefully without the relay (room-server would
have no client-visible way to be reached) — so uncommenting them would still be
misleading. This pass makes the code true; it doesn't change what compose claims is
runnable, matching §12.5's own scoping.

## Verification

- `.venv\Scripts\python.exe -m pytest` — new test modules mirror the source tree:
  `tests/server/domain/test_room_directory.py`, `tests/server/infrastructure/test_redis_directory.py`
  (against the hand-written fake redis client), `tests/server/application/test_room_server_ticker.py`,
  `tests/server/application/test_allocator.py`, `tests/server/roles/test_room.py` etc.,
  plus updates to `tests/server/application/test_rating_updater.py` (payload-driven, no
  `rooms` fixture) and `tests/server/application/test_game_room.py` (`abandon()` coverage).
- `.venv\Scripts\coverage run -m pytest && coverage report` — 100% on every touched file,
  matching the standard this codebase already holds itself to.
- `.venv\Scripts\lint-imports.exe` — the two redis contracts (already added in the §4/§12
  pass) now have real modules to cover; must still report all contracts kept, and the new
  `server.roles` package must respect "Server internals layers".
- Manual read-through confirming `server/main.py`'s monolith behavior is unchanged (no
  functional test regressions expected in `tests/server/test_main.py`).
