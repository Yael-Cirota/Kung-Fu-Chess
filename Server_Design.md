# Kung-Fu-Chess: Scaling Plan

Target: 100M registered users, 10M concurrent players, ~1 move/2s per active user, 30-90s game duration.

This plan is grounded in the current codebase: a single Python process (`server/main.py`) holding
`rooms`, `client_sessions`, and the matchmaking queue as in-process dicts, a single-writer SQLite
database, an in-process `EventBus` with `RatingUpdater` settling finished games, and a websockets
accept loop with a `tick_forever` driver at `tick_hz=100` / `broadcast_hz=20`. Everything below
describes what changes and why, staying in Python throughout.

---

## 1. Database

### 1.1 Why SQLite doesn't survive this

**SQLite is not suitable at this scale**, and the code already shows why: `SqliteUserRepository`
commits every write, and `main.py` pins DB writes to a single-worker `ThreadPoolExecutor`
(`DB_EXECUTOR_MAX_WORKERS = 1`) to match SQLite's single-writer model. That's one writer, one file,
one machine — no horizontal scaling story, and it's a file, not a service other machines can reach
safely over a network.

**Plan:**
- **PostgreSQL** replaces SQLite for `users` and `game_records`. Start with one primary + read
  replicas; shard `users` by `user_id` (e.g. 100-500 shards) once a single primary stops absorbing
  the write rate.
- **Redis** takes over everything currently living in Python-process memory that needs to be
  *shared* across servers and doesn't need SQL durability:
  - `client_sessions` (today: `InMemoryClientSessionRegistry`)
  - the room directory (`room_id -> room_server_id`, replacing the single `self._rooms` dict)
  - the matchmaking queue (today: `MatchmakingService._queue`)

### 1.2 The schema itself has to change, not just the infrastructure

"Shard `users` by `user_id`" is not sufficient on its own, because the current schema is:

```sql
CREATE TABLE game_records (
    game_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    white_id   INTEGER NOT NULL,
    black_id   INTEGER NOT NULL,
    winner_id  INTEGER,
    ended_at_ms INTEGER NOT NULL,
    reason     TEXT NOT NULL,
    FOREIGN KEY (white_id)  REFERENCES users (user_id),
    FOREIGN KEY (black_id)  REFERENCES users (user_id),
    FOREIGN KEY (winner_id) REFERENCES users (user_id)
);
```

Every game row references **two different users**, which under `user_id` sharding land on two
different shards. Two consequences:

1. **Cross-shard FKs cannot be enforced.** No sharded Postgres topology enforces a foreign key
   whose target lives on another shard. These constraints have to be dropped and enforced in the
   application layer instead (or simply accepted as eventually-consistent, given the writer is a
   single well-tested code path — `RatingUpdater`).
2. **"Show me my game history" becomes a scatter-gather query.** If a game row lives on one shard,
   the opponent's history query has to fan out across all shards to find it. At 100M users that is
   the single most common history query and it must not scatter.

**Fix — write each game twice, once per side:**

```sql
-- canonical, immutable record of the game. Sharded by game_id.
CREATE TABLE game_records (
    game_id      BIGINT PRIMARY KEY,
    white_id     BIGINT NOT NULL,
    black_id     BIGINT NOT NULL,
    winner_id    BIGINT,
    ended_at_ms  BIGINT NOT NULL,
    reason       TEXT NOT NULL
);

-- per-user view of the same game. Sharded by user_id, co-located with the user.
CREATE TABLE game_participants (
    user_id      BIGINT NOT NULL,
    game_id      BIGINT NOT NULL,
    color        TEXT   NOT NULL,      -- 'white' | 'black'
    opponent_id  BIGINT NOT NULL,
    result       TEXT   NOT NULL,      -- 'win' | 'loss' | 'draw'
    elo_before   INTEGER NOT NULL,
    elo_after    INTEGER NOT NULL,
    ended_at_ms  BIGINT NOT NULL,
    PRIMARY KEY (user_id, game_id)
);
CREATE INDEX ON game_participants (user_id, ended_at_ms DESC);
```

This is deliberate denormalization: one game produces one `game_records` row and two
`game_participants` rows. In exchange, **every per-user history query is single-shard and index-ordered**,
and `elo_before`/`elo_after` make rating history reconstructible without replaying every game.
Game records are append-only and never updated, so the usual denormalization risk (divergent
copies) does not apply here.

`game_records` itself can be partitioned by time (monthly) since it's append-only and read rarely.

---

## 2. Splitting the single process into roles

Today `Server` (in `main.py`) is one process doing everything: accepting connections, running the
per-room tick loop, matchmaking, and DB writes. That has to split into independently-scaled roles:

| Role | What it owns | Scales on |
|---|---|---|
| **Gateway** | The client's websocket connection (`ws_server.py`'s `handle_connection`) | concurrent connections |
| **Room-server** | The authoritative `GameSession` + `GameRoom.tick` loop for a set of rooms | concurrent rooms |
| **Matchmaker** | The Elo-window queue (`MatchmakingService`) | queue depth / CPU (light) |
| **Game Allocator** | Placement recommendation: consistent hashing + room-server load signal | live room-server count / room churn rate |
| **Settlement workers** | Consume `GAME_OVER`, write Elo + game rows (§5) | events/sec |
| **DB tier** | Postgres (accounts, ratings, game records) | reads/writes, sharded |

A room's state (piece positions, cooldowns, `_command_queue`) must live in exactly one place to
stay consistent, so **each room is pinned to exactly one room-server for its lifetime** — this is
the one piece of state that cannot be replicated or shared. Everything else (session lookup, room
directory) goes through Redis.

### ADR-001: Client reaches its room-server via gateway relay, not direct redirect

**Status: decided — relay. Revisit only against measured latency data (see "Revisit trigger").**

This decision is made here rather than deferred because it determines where bandwidth lands,
whether room-servers must be publicly routable, and how draining works (§7) — too much depends on
it to leave open.

**Options considered:**

| | **Relay (chosen)** | **Direct redirect** |
|---|---|---|
| Client connections | one, to any gateway | two (gateway → room-server handoff) |
| Room-servers public-facing? | no — internal only | yes: public IP, TLS cert, DDoS surface |
| Egress path | room-server → gateway → client | room-server → client |
| Internal traffic | full broadcast volume crosses the internal fabric | near zero |
| Reconnection | client reconnects anywhere, gateway re-resolves | client must remember/re-resolve a specific host |
| Draining | drain gateways and room-servers independently | client-visible reconnect on room-server drain |

**Decision: relay.** The deciding factor is the existing reconnection protocol
(`AuthService` / `ClientSessionRegistry.rebind`, epoch-based eviction in
`dispatcher._bind_authenticated`), which assumes a client can log back in through *any* entry point
and be reattached to its session and room. Relay preserves that property for free. Direct redirect
would require the client to track, persist and re-resolve a specific room-server address across
reconnects, NAT rebinding and mobile network changes — and would push every room-server onto the
public internet, each needing its own TLS termination and DDoS exposure, for a fleet whose whole
design premise (§7) is that instances are cheap, numerous and constantly recycled.

**Accepted cost:** the full ~800 Gbps-1.3 Tbps broadcast volume (§4) crosses the internal fabric
once before reaching clients, and every move takes one extra internal hop. Within a single
availability zone this hop is sub-millisecond — negligible against a 2-second-per-move cadence and
a 50ms broadcast interval. Gateways and room-servers must therefore be **co-located within a
region** (§6) so this hop never crosses a WAN link.

**Revisit trigger:** if measured p99 gateway → room-server → gateway round-trip exceeds ~5ms, or
internal fabric cost becomes a material line item, reconsider direct redirect for long-lived rooms
only (tournaments/spectated games), keeping relay for ordinary matchmade games. `MatchFound`
already carries `room_id` and `color`, so extending it with a host field is a small protocol change
— the cost of switching later is low, which is itself part of why relay is safe to commit to now.

**Internal relay transport:** a persistent internal connection (gRPC bidirectional stream, or an
internal WebSocket — the codebase already speaks websockets end-to-end via `codec.py`) opened between
gateway and room-server per client-room membership, established from the directory lookup at
join/reconnect time. A broker (NATS, Redis Pub/Sub) is deliberately not used for this hop: fan-out per
room is 2 players plus up to `max_viewers=8` (§10), the destination is already known from the
directory, and a broker adds a hop with no fan-out benefit at that scale — brokers earn their cost at
fan-out counts far above what a single room ever has. (Redis Streams *is* the right tool for
§5's settlement path, where the fan-out is real: many settlement workers consuming one ordered log.)
The connection is keyed on `(room_id, lease_epoch)`, not just `room_id`: when §8's lease epoch changes
mid-room (a new owner claims after a partition), the gateway's existing connection is to a
room-server that can no longer prove ownership, so the gateway must drop it and re-resolve through
the directory rather than keep relaying over a stale link.

### Room placement & directory

- **Game Allocator** performs room-server selection: consistent hashing over live room-servers (so
  scaling the fleet reshuffles a minimal number of future placements), combined with a load signal
  (current room count, from server heartbeats in Redis) to avoid hotspotting. It is a separate,
  stateless, horizontally-scaled service — called by the Matchmaker at room creation — because it
  scales on a different axis (live room-server count / room churn rate) than the Matchmaker (queue
  depth) or the room-servers themselves (concurrent rooms).
- **The Allocator recommends, it does not claim.** It returns a candidate `server_id`; the chosen
  room-server itself performs the atomic `SET ... NX` write of
  `room:<room_id> -> {server_id, lease_epoch, created_at}` and owns the epoch from that point on.
  This keeps §8's fencing model intact — the owner mints its own epoch on claim and renews it on
  heartbeat. If the Allocator did the claiming instead, fencing tokens would be minted by a process
  that isn't the one proving liveness, breaking the "owner renews its own lease" invariant §8 depends
  on.
- Failure handling and the partition race are covered in §8.

---

## 3. Matchmaking and "everyone can play with everyone"

The requirement is that any player can play any other player and enter any room. Regional
deployment (§6) creates tension with this, resolved explicitly:

- **Room directory is global.** A room ID resolves to its owning server regardless of which region
  the looking-up gateway sits in. Joining a friend's room by ID always works, cross-region.
- **Ranked matchmaking is region-preferred, not region-locked.** `MatchmakingService` already
  widens its Elo window over time while a player waits; the same mechanism widens *geographically*:
  start in the local regional pool, and after a few seconds without a match, extend the search into
  neighbouring regions. Players in thin pools (small regions, extreme Elo) still match — they just
  wait marginally longer and accept higher latency, which is the correct tradeoff.
- **Cross-region games are hosted in one region**, chosen as the one minimizing combined RTT. One
  player takes the latency hit; this is unavoidable and is what every global multiplayer game does.

---

## 4. Network traffic

### Client → server (moves)
- 10M concurrent users x 1 move / 2s = **5M `MoveRequest`s/sec**
- ~80-100 bytes each (JSON + envelope) → **~400-500 MB/s ≈ 3-4 Gbps** inbound, globally.
- Manageable once spread across thousands of gateway instances.

### Server → client (state broadcasts) — the dominant cost
`GameRoom.tick` broadcasts a full `StateUpdate` (all pieces, in-flight motions, move log,
scoreboard) to every connection in the room at `broadcast_hz=20`, **regardless of whether anything
changed**, plus immediate `DeltaEvent`s on top for moves/captures (`BroadcastObserver`).

With ~5M concurrent 1v1 rooms:
- 5M rooms x 2 players x 20Hz = **200M outbound messages/sec**
- At ~500-800 bytes per `StateUpdate` → **~100-160 GB/s, i.e. ~800 Gbps-1.3 Tbps** aggregate egress.

That's ~200x the input traffic. It's a lot in absolute terms but it's the normal shape of real-time
multiplayer at scale, and **it distributes fine once sharded**: ~1000 concurrent players per
room-server (~500 rooms) is only ~80-100 Mbps of broadcast egress per instance — trivial for a
modern NIC. The takeaway isn't "too much traffic," it's "never centralize the broadcast."

### Heartbeats
`heartbeat_interval_ms=3000` → 10M / 3s ≈ **3.3M heartbeats/sec** each direction at ~50-80 bytes →
**~1.5-2 Gbps** each way. Small next to broadcast traffic, but gateways must budget for it.

### Payload reduction, in order of effort-to-benefit

1. **Cap the move log (do first, ~free).** `_state_update_message` sends the full `move_log` every
   tick, which grows unbounded through a match — meaning per-message size *increases* the longer a
   game runs. Cap to last N entries, or drop it from periodic broadcasts entirely and send it only
   on join/resync (`_send_join_in_progress` already does full-state-on-join).
2. **Enable websocket compression (`permessage-deflate`) (do second, one config line).** `StateUpdate`
   JSON is extremely repetitive — same keys, same square names, same colors, every 50ms. Typical
   compression on this shape of payload is 60-80%, for essentially no code change and no loss of
   debuggability. Cost is CPU per message; measure it, since at 200M msg/s CPU may bind before
   bandwidth does.
3. **Lower `broadcast_hz` 20 → 10 (do third, one config line).** `DeltaEvent`s already fire
   immediately on moves/captures (event-driven, not tick-gated), and `StateUpdate`/`DeltaEvent`
   already carry `MotionInfo` for client-side interpolation. Halves broadcast volume outright.
   Validate perceived smoothness before committing.
4. **Binary protocol for the hot path (do last, largest effort).** A fixed-layout binary encoding of
   `StateUpdate` (board as a fixed array, ids as uint16, coordinates as uint8) is realistically a
   5-10x size reduction versus raw JSON — but only ~2-3x versus *compressed* JSON, which is why it
   ranks after compression rather than instead of it. It is **not** a free win: it costs a
   client-and-server encoder rewrite, loses human-readable traffic in devtools, and makes protocol
   versioning something you must design rather than get for free. Scope it narrowly — apply binary
   encoding only to `StateUpdate`/`DeltaEvent`, which are ~99% of message volume, and leave login,
   matchmaking and room-control messages as JSON, where volume is negligible and debuggability is
   worth far more. `codec.py` is already the single encode/decode seam, so this is containable.

---

## 5. Persistence write path: durable event bus

The current path is already decoupled from the tick loop: `RatingUpdater` subscribes to `GAME_OVER`
on the in-process `EventBus` and hands the write to `ThreadPoolDbWriter`, so the game loop does not
block on Postgres. The problem at scale is not latency — it's **durability and buffering**:

- The `EventBus` is in-process, so it cannot deliver to settlement workers on other machines.
- If the room-server dies between game-end and DB commit, the result is **silently lost** — the
  players' Elo never updates.
- A DB slowdown or shard failover has nowhere to queue; work backs up in a thread pool inside a
  process that is designed to be killed and recycled freely (§7).

**Plan — replace the in-process bus with a Redis Stream (`XADD` / `XREADGROUP` consumer group):**

```
room-server ──publish GAME_OVER──► durable log (partitioned by game_id)
                                        │
                                        ▼
                            settlement worker pool (consumer group)
                                        │
                                        ├─► users: Elo update      (shard by user_id)
                                        ├─► game_records: insert   (shard by game_id)
                                        └─► game_participants: 2 inserts (shard by user_id)
```

- **Publish is fire-and-forget from the room-server's perspective** — it returns as soon as the log
  acknowledges, and the room-server can then be killed safely.
- **Settlement workers scale independently** of room-servers. Load is proportional to *games
  completed per second*, not to concurrent players or tick rate. Sizing: 10M concurrent players = 5M
  concurrent 1v1 games; at ~45s average duration, steady-state completion rate is 5M / 45 ≈
  **110k game-ends/sec**, which produces ~110k `game_records` inserts/sec, ~220k `game_participants`
  inserts/sec, and ~220k `users.elo` updates/sec. That row rate — not the game rate — is the real
  sizing input for both this tier and the `users` shard count.
- **At-least-once delivery is already safe here.** `RatingUpdater` keeps a `_settled` set and
  ignores repeat `GAME_OVER`s for a room — it was written this way because a room keeps ticking
  after a forced resign and the engine may publish its own `GAME_OVER` afterwards. That same
  idempotency is exactly what a redelivering consumer needs; it just has to move from an in-memory
  set to a durable uniqueness constraint (`game_records.game_id` primary key, or a settled-games
  key in Redis).
- **The four writes per game should be one transaction where co-located, and idempotent where not.**
  The two `game_participants` rows sit on different shards, so a distributed transaction is not
  worth it — write each idempotently keyed on `(user_id, game_id)` and let retries converge.

**Why Redis Streams and not Kafka.** Redis is already load-bearing and non-optional in this design
for five separate jobs — the §2 room directory and its `SET ... NX` claim, §8's lease epochs and TTL
renewal, §3's matchmaking queues, §2's placement load signal, and §6's per-region session state.
None of those have a Kafka equivalent. Kafka would therefore be a *second* stateful system earning
its keep on exactly one job (§5), and Streams already covers that job's requirements: consumer
groups give the competing-consumer fan-out the diagram above needs, and `XACK` plus the
pending-entries list give the at-least-once redelivery that `RatingUpdater`'s idempotency was
already written to tolerate. One system, one container, one operational surface.

**When to escalate to Kafka**: when the analytics / anti-cheat / leaderboard consumers below become
real. They need independent offsets and long retention over the same log, which is where a
`MAXLEN`-capped Stream stops being adequate and Kafka's per-consumer-group offset retention starts
paying for itself. That is also the §12.1 split trigger for giving settlement its own image. Until
those consumers exist, the escalation is unpaid-for complexity — Kafka is deferred, not rejected.

This also opens the door to consuming the same event stream for analytics, anti-cheat and
leaderboards without adding load to the game path.

---

## 6. Geographic deployment

The traffic numbers (§4) make single-region deployment untenable on two independent grounds:
**latency** (a player in Tel Aviv relaying through us-east-1 pays ~150ms RTT on a game where
`broadcast_hz=20` implies a 50ms state cadence — the network becomes 3x the tick interval) and
**concentration of risk** (a single region failure takes 100% of players offline).

**Plan: independent regional clusters, GeoDNS-routed.**

- Deploy a full stack — gateways + room-servers + matchmaker + Redis + Postgres read replicas — in
  each of ~5-8 regions (e.g. NA-East, NA-West, EU-West, EU-Central, APAC-SE, APAC-NE, SA-East).
- **GeoDNS / anycast routes each client to its nearest regional gateway.** No client is ever
  configured with a region; the DNS answer does it.
- **Gateways and room-servers must be co-located in the same region.** This is a hard constraint
  imposed by ADR-001: the relay hop is only cheap if it stays intra-region. Placement (§2) must
  therefore be region-scoped — a gateway never relays to a room-server in another region.
- **Redis is per-region for hot state** (sessions, room directory, queues) — it's ephemeral and
  latency-critical, so it must not cross a WAN. Cross-region room lookups (joining a friend's room
  abroad) go through a small global directory tier, which is a low-volume path and can afford
  WAN latency.
- **Postgres: one write primary per shard with cross-region read replicas.** Elo/game writes are
  ~200-300k/s globally but are asynchronous (§5), so cross-region write latency is absorbed by the
  event log rather than felt by players. Reads (login, profile, history) serve from local replicas.
- **Regional failure is survivable**: GeoDNS withdraws the failed region and its players reconnect
  into the neighbouring one. Games in flight are lost — acceptable, because they average 45 seconds
  (§7) and the disconnect path already exists.

Regional pools' effect on matchmaking is covered in §3.

---

## 7. Games last 30-90s — operational implications

This is the detail that most shapes deployment: **rooms are extremely short-lived and high-churn.**

- At 10M concurrent players and ~45s average game length, expect **hundreds of thousands of room
  create/destroy events per minute**, system-wide. Room creation must stay cheap (today's in-memory
  `GameRoom()` construction is; the Redis directory write must be too, or matchmaking latency
  suffers).
- **Room-servers are fungible, not pets.** A room-server holds no state worth preserving across
  restarts — a crash there is a mass-disconnect event, already handled by
  `disconnect_policy`/`force_resign`. So: autoscale aggressively on **concurrent room count**, and
  keep rooms-per-instance modest (a few hundred to ~1000) to bound crash blast radius and keep
  per-instance broadcast bandwidth predictable (§4).
- **Gateways and matchmaker scale on different axes** (connections; queue depth) — which is exactly
  why they are separate deployable units rather than one `Server` process.

### 7.1 Draining procedure

The short game length is what makes zero-impact rollouts possible: **wait 90 seconds and the
problem drains itself.** Concretely, per room-server:

1. **`preStop` hook fires** (or SIGTERM handler, outside Kubernetes). It immediately marks the
   instance ineligible for new placements — deregister from the placement pool in Redis and fail
   readiness checks. New rooms stop arriving within one placement cycle.
2. **Existing rooms keep running untouched.** No migration, no state transfer, no client-visible
   event. This is the entire benefit of pinning rooms to a server for their lifetime.
3. **Poll until drained**: loop on `len(rooms) == 0`, checking every second.
4. **`terminationGracePeriodSeconds: 120`.** Games run 30-90s, so 120s covers essentially the full
   distribution with margin. Instances that drain early exit early; the grace period is a ceiling,
   not a wait.
5. **Force-terminate on grace expiry.** Anything still running at 120s is anomalous (a stuck room or
   an idle-but-unclosed room). Those players hit the existing disconnect path — bounded, rare, and
   already handled.

The same pattern applies to gateways, but with a difference worth noting: a gateway's connections
are *not* time-bounded — a player may hold one open across many consecutive games. Gateways
therefore drain by **refusing new connections and closing idle ones with a reconnect hint**, letting
clients re-establish through the load balancer onto a healthy instance. That path is already
exercised in normal operation by `ClientSessionRegistry.rebind`.

---

## 8. Room placement under failure

`SET ... NX` prevents two servers from *claiming* a room concurrently, but it does not resolve what
happens when a room-server is partitioned from Redis while still holding live rooms: its directory
entry expires, another server can legitimately claim the room ID, and the original server keeps
ticking a room it no longer owns. Two servers then believe they are authoritative — with clients
potentially relayed to either.

**Mitigation — leases with fencing tokens:**

- The directory entry carries a **monotonically increasing `lease_epoch`**, incremented on every
  (re)claim.
- The owning room-server **renews its lease on a heartbeat** (e.g. every 2s, TTL 6s). Renewal fails
  if the epoch no longer matches — the definitive signal that ownership was lost.
- **Every relayed message carries the epoch.** A gateway relaying to a room-server tags the message
  with the epoch it read from the directory; the room-server rejects anything not matching its own.
  Stale-owner traffic is therefore rejected rather than acted on, even mid-partition.
- **A room-server that fails to renew stops ticking immediately** and drops its rooms, rather than
  continuing to serve state it can no longer prove it owns.

This is deliberately the same shape as the epoch-based session eviction already implemented in
`dispatcher._bind_authenticated`, where a newer login epoch invalidates an older binding — the same
reasoning applied to room ownership instead of session ownership.

**Recovery policy: don't recover — abandon.** When a room's ownership is genuinely lost, the correct
action is to **end the game and requeue both players**, not to attempt state reconstruction on the
new owner. Rebuilding an in-flight `GameSession` (piece positions, cooldown timers, queued commands)
across a partition is substantial complexity to rescue an average of **45 seconds of play**, in a
game where players are already going to requeue within seconds. Emit `GAME_OVER` with a
`server_fault` reason, settle it as a draw with no Elo change (the `RatingUpdater` path already
handles non-engine game-ends), and put both players back in matchmaking. Short games turn a hard
distributed-systems problem into a product decision.

**Testing this properly** means fault injection, not unit tests: kill room-servers mid-game under
load, partition a room-server from Redis while keeping it reachable from gateways (the case that
actually produces split ownership), expire leases under artificial Redis latency, and assert that
no client ever receives conflicting authoritative state and that no game is settled twice.

---

## 9. Summary architecture

```
                        GeoDNS / anycast
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
   [ Region: EU ]        [ Region: NA ]         [ Region: APAC ]
        │                      │                      │
   ┌────┴─────────────────────────────────────────────────────┐
   │  Gateways          (scale on connection count)           │
   │      │ intra-region relay (ADR-001)                      │
   │      ▼                                                   │
   │  Room-servers      (scale on room count; fungible)       │
   │      │                                                   │
   │  Matchmaker        (region-preferred, widens outward)    │
   │      │                                                   │
   │  Game Allocator    (placement recommendation, region-scoped) │
   │      │                                                   │
   │  Redis             (sessions, room directory + leases)   │
   └──────┼───────────────────────────────────────────────────┘
          │ publish GAME_OVER
          ▼
   Durable event log (Redis Streams, consumer group)
          │
          ▼
   Settlement workers ──► Postgres
                            ├─ users              (sharded by user_id)
                            ├─ game_records       (sharded by game_id)
                            └─ game_participants  (sharded by user_id)
```

## 10. Remaining open questions

- **Viewer fan-out**: `max_viewers=8` per room multiplies broadcast traffic per room by up to 5x
  over the 2-player baseline used in §4. Needs its own sizing pass once player traffic is validated —
  one of the two scenarios the load-test suite in §11 exists to answer.
- **Matchmaking scan cost**: `MatchmakingService.enqueue` currently scans an Elo-window queue.
  Whether that needs sharding by Elo band within a region depends on real queue depths — tracked via
  the matchmaker queue-depth metric in §11.
- **Compression CPU vs bandwidth**: §4 assumes `permessage-deflate` is worth its CPU at 200M msg/s.
  This needs measuring — it's the one optimization that could plausibly make things worse, and the
  other scenario the §11 load-test suite exists to answer.

---

## 11. Observability

None of the sizing assumptions already made in this plan (§4's Mbps-per-instance figure, §5's
game-ends/sec, ADR-001's ~5ms revisit trigger) are verifiable without an explicit metrics and
load-testing layer — §10's open questions are exactly the gaps this section exists to close.

**Load-bearing metrics** (the minimum needed to validate or refute numbers already claimed elsewhere
in this plan, not a generic SRE checklist):

| Metric | Why it's load-bearing | Where it's defined |
|---|---|---|
| p99 gateway → room-server → gateway RTT | ADR-001's revisit trigger fires at ~5ms | §2 (ADR-001) |
| Settlement-worker consumer-group lag vs. ~110k game-ends/sec | detects the durable log backing up before players notice missing Elo updates | §5 |
| Lease-renewal failure rate / fencing rejections | early signal of partition-driven split ownership, before it produces a doubly-settled game | §8 |
| Matchmaker queue depth + geographic-widening rate, per region/Elo-band | validates §3's "widen outward" behavior is actually converging, not just growing | §3 |
| Per-instance broadcast egress vs. the ~80-100 Mbps/instance estimate | confirms §4's "never centralize the broadcast" claim holds at real rooms-per-instance counts | §4 |
| Game Allocator placement latency + hotspot skew across room-servers | confirms consistent hashing + load signal is actually load-balancing, not just placing | §2 |

**Load testing.** The plan repeatedly defers decisions to "measure it" (§4's compression CPU tradeoff,
§10's viewer fan-out sizing) without saying how. A synthetic load-test harness — simulated gateways
driving `MoveRequest`s at the target 5M/sec and simulated clients absorbing `StateUpdate` broadcasts —
is what actually answers those two open questions, and also validates the room-churn assumption in
§7 (hundreds of thousands of create/destroy events per minute) before it's discovered in production.

**Health checks.** Room-server readiness must reflect placement eligibility, not just process
liveness — §7.1's draining procedure depends on a room-server failing readiness the instant it
deregisters, not on it merely being unresponsive. Gateway readiness should reflect capacity headroom
(open connection count vs. configured ceiling), not just an open port, so GeoDNS/load-balancer health
checks don't route into an already-saturated instance.

---

## 12. Containerization & local development

Everything above is production topology (regions, Kubernetes, sharded Postgres). None of it needs to
be true for a developer to run the full stack locally or in CI. This section covers how the code is
packaged into images, and the Docker Compose file that stands the whole architecture up on one
machine.

### 12.1 One image, many roles

The §2 role table lists five server roles, which invites the assumption that five images are needed.
It isn't. The full artifact set is:

| Artifact | Count | Why |
|---|---|---|
| `Dockerfile` (application) | 1 | All five §2 roles are the same Python package with the same dependency closure. Role is chosen by `command:`, never by image. |
| `Dockerfile.loadtest` (§11 harness) | 1 | Genuinely different dependencies (load-generation libraries), different build cadence, built rarely and run on demand. |
| `.dockerignore` | 1 | See §12.3. |
| `docker-compose.yml` | 1 | References the same application image once per service, overriding only `command:`. |
| Redis / Postgres | 0 | Official upstream images (`redis:7-alpine`, `postgres:16-alpine`). |
| Client | 0 | **Not containerized.** `client/` drives an OpenCV window and needs a display; it runs on the developer's machine against the containerized server. |

**Two hand-written Dockerfiles.** The load-bearing reason for a single application image is ADR-001:
gateways and room-servers are coupled at the protocol level (relayed frames carry the `lease_epoch`
from §8), so a gateway running older code relaying to a newer room-server is a real failure mode. One
image makes "every role is on the same code version" true by construction, across a fleet that (see
below) is continuously rolling. Per-role images make it something you must enforce.

#### Why one image is not a scalability limit

"One image" reads like "one deployable," and it isn't. **Image count and runtime scalability are
orthogonal**: an image is a build artifact, while scale comes from replica count per role, and every
role scales on its own axis regardless of which image produced it. At this plan's targets:

| Role | Sizing driver | Per-instance | Instances (global) |
|---|---|---|---|
| Room-server | 5M concurrent rooms; §7 caps rooms/instance to bound blast radius | ~500 rooms / 1000 players, ~80-100 Mbps egress (§4) | **~10,000** |
| Gateway | 10M concurrent connections | ~10k connections, ~1 Gbps relay egress | **~1,000** |
| Settlement | 110k game-ends/s → ~550k row-writes/s (§5) | ~1k events/s | **~100-200** |
| Matchmaker | ~220k enqueues/s | light | **~50** |
| Game Allocator | ~110k placements/s, stateless | light | **~50** |

That is ~11,500 containers built from one image, each role a separate Deployment, scaled and rolled
independently. None of those numbers change if five images are built instead of one.

The three things per-role images are assumed to buy, checked against this codebase:

- **Image size.** The roles' dependency closures are near-identical (`websockets` + a Redis client +
  a Postgres driver). Splitting saves single-digit MB. The real bloat is `opencv-python`, which
  §12.2 removes from the base dependencies — a ~200 MB win that one image captures identically.
- **Cold start.** This genuinely matters, since §7 autoscales room-servers aggressively against high
  room churn. But startup is dominated by interpreter and import time, and the image is layer-cached
  on the node after first pull. Five images sharing a base layer do not pull faster than one.
- **Blast radius / credential surface.** The argument with real content: an internet-facing gateway
  ships the same binary as a settlement worker that reaches Postgres. But credentials arrive from
  secrets and per-role service accounts at runtime and are never baked into the image, so the correct
  control is network policy plus per-role identity — not a separate image.

**Split trigger:** break a role out into its own image when its dependency closure genuinely
diverges — settlement adopting `confluent-kafka` (native `librdkafka`), or a room-server moving §4's
binary hot path into a compiled extension. Split that one role at that point, not preemptively. This
is already the rule `Dockerfile.loadtest` follows.

**The real scalability lever** is not image count: one Python process is single-core (GIL), so each
container is sized at roughly one vCPU, runs one process, and scales horizontally. That constraint is
what sets the instance counts above.

#### Entrypoint

Today's entrypoint is `python -m server.main`, which runs the single all-in-one `Server` built by
`build_server`. The one-image/N-commands story is **blocked on §2's role split existing in Python
first**: per-role entry points (`server.roles.gateway`, `server.roles.room`, `server.roles.matchmaker`,
`server.roles.allocator`, `server.roles.settlement`), each calling a narrowed builder factored out of
`build_server`. Docker selects among entry points; it does not create them. The role split is a Python
refactor, not something containerization provides.

#### Build shape

- **Multi-stage.** A `python:3.12-slim` builder stage resolves and installs dependencies into a
  virtualenv; a slim runtime stage copies only that venv plus the server-side packages. Run as a
  non-root user. `requires-python = ">=3.11"` is the floor.
- **Compose shape.** One YAML anchor holds the shared build and environment; each service overrides
  only its command:

```yaml
x-kfchess: &kfchess
  build: .
  environment: &kfchess-env
    KFC_HOST: "0.0.0.0"
    KFC_REDIS_URL: "redis://redis:6379"
    KFC_PG_DSN: "postgresql://kfchess@postgres/kfchess"

services:
  gateway:     { <<: *kfchess, command: ["python", "-m", "server.roles.gateway"],    ports: ["8765:8765"] }
  room-server: { <<: *kfchess, command: ["python", "-m", "server.roles.room"] }
  matchmaker:  { <<: *kfchess, command: ["python", "-m", "server.roles.matchmaker"] }
  allocator:   { <<: *kfchess, command: ["python", "-m", "server.roles.allocator"] }
  settlement:  { <<: *kfchess, command: ["python", "-m", "server.roles.settlement"] }
  redis:       { image: "redis:7-alpine" }
  postgres:    { image: "postgres:16-alpine" }
```

### 12.2 Three prerequisites in the current code

All three are properties of the code as it stands today, and all three surface at `docker run` time:

1. **`host = "127.0.0.1"` in `config/default.toml`.** In a container that binds loopback only, so
   published ports refuse connections — the most common containerization failure there is. The
   override already exists: `KFC_HOST` is in `_ENV_OVERRIDES`, so `ENV KFC_HOST=0.0.0.0` in the image
   (or per-service in compose) fixes it. No code change required.
2. **`_ENV_OVERRIDES` covers only four keys** — `KFC_DB_PATH`, `KFC_HOST`, `KFC_PORT`,
   `KFC_LOG_LEVEL` (`common/config/loader.py`). A compose file currently has no way to tell a process
   its Redis URL, its Postgres DSN, its event-log brokers, its region, or its role. The target
   topology therefore requires that table to grow — better still, a generic `KFC_<SECTION>_<FIELD>`
   rule driven off the `_SECTION_TYPES` dataclass fields, so new config keys become env-overridable
   for free. This is a **prerequisite of the compose file, not a Docker detail**.
3. **`opencv-python` and `numpy` are unconditional `[project.dependencies]`**, so installing the
   project drags OpenCV and its `libGL`/`libglib` system libraries into a server image that never
   imports them. The only `import cv2` / `import numpy` in the tree are under `ui/` and `tests/ui/` —
   `server/`, `client/`, `common/`, `protocol/` and `kfchess/` are clean. Both should move to a
   `[project.optional-dependencies] ui` extra, leaving `websockets` as the only base runtime
   dependency and dropping a GUI toolchain out of every server container.
4. **The Redis client is a new runtime dependency, and it must stay inside `server.infrastructure`.**
   The server stack is async end-to-end, so the client is `redis.asyncio` from `redis-py` (>= 4.2,
   which absorbed the old separate `aioredis` package — `aioredis` is the stale answer and should not
   be added). Two contract edits in `pyproject.toml` go with it: the new
   `server/infrastructure/redis_*.py` modules must join the `forbidden_modules` list of the
   "Infrastructure is reached only through Protocols" contract, or that contract silently stops
   covering the new infrastructure; and since `include_external_packages = true` is already set, the
   `redis` package itself should be forbidden to every source module except `server.infrastructure`,
   so no domain or application code can reach the client directly.

### 12.3 Image hygiene

- **`.dockerignore`** excludes `ui/`, `client/`, `tests/`, `.venv/`, `.git/`, `ui/frames/`,
  `__pycache__/`, `*.db`, `*.log`. Beyond size, this makes the import-linter contracts "Server and ui
  never see each other" and "ui and client never see the server" *physically* true inside the image:
  the forbidden packages are not merely unimported, they are absent.
- **Logs to stdout.** `configure_logger` writes to `config.logging.server_file` (`server.log`). In a
  container that path should be unset or `/dev/stdout` so the platform collects logs rather than
  accumulating them on an ephemeral filesystem.
- **The dev SQLite file.** `database.path = "kfchess.db"` is CWD-relative, so it lands inside the
  container and dies with it. Mount a named volume if persistence across `docker compose down` is
  wanted; otherwise accept the ephemerality deliberately. Production has no SQLite at all (§1).

### 12.4 Health checks: what Docker can and cannot do

§7.1's draining procedure and §11's readiness requirement both depend on an HTTP endpoint that **does
not exist today** — `run_server` calls `websockets.serve` and nothing else, so there is no HTTP
surface to probe.

- Docker's `HEALTHCHECK` stays deliberately trivial: a TCP connect to the websocket port, proving
  process liveness and nothing more.
- §11's actual requirement — *readiness reflects placement eligibility, not liveness* — needs a small
  HTTP admin surface (`/healthz`, `/readyz`) alongside the websocket server, with `/readyz` failing
  the instant §7.1's step 1 deregisters the instance from the placement pool.
- **Kubernetes probes, not `HEALTHCHECK`, are what §7.1 depends on.** A passing `HEALTHCHECK` does not
  satisfy §11.

### 12.5 Scope of the compose file

The compose file is **target-shaped**: it names the six services above because that is the
architecture of §9. Until §2's role split lands in code, only a single all-in-one `server` service is
actually runnable; the rest document the target. This is a dev/CI convenience, not a topology claim —
production behavior is governed entirely by §6.
