# Add containerization guidance to the scaling plan

## Context

[.claude/plans/Server_Design.md](.claude/plans/Server_Design.md) describes the production topology
(regions, role split, sharded Postgres, durable event log) but says almost nothing about packaging.
Its §12 mentions "a Docker Compose file standing up one gateway, one room-server, one matchmaker,
one Redis, one Postgres, and one settlement worker" in a single sentence and stops there.

The user asked two concrete questions the document does not answer:

1. **How do I use the Dockerfile?** — what goes in it, what the entrypoint is, how a single build
   serves the six services §12 already names.
2. **How many Dockerfiles do I need?** — the doc's role table (§2) lists five server roles, which
   invites the wrong assumption that five images are required.

There are currently **no Docker artifacts in the repo at all** (`Dockerfile`, `docker-compose.yml`,
`.dockerignore` all absent). Outcome: §12 grows into a self-contained containerization section that
answers both questions and flags the three repo-specific blockers that would otherwise be discovered
at `docker run` time.

**Scope note:** this task is a documentation edit. It does *not* create the Dockerfile, the compose
file, or the code changes it recommends — those become follow-up work. The plan below is written so
the doc edit is mechanical.

---

## The answer to be documented

**Two hand-written Dockerfiles. One image for the whole server fleet.**

| Artifact | Count | Why |
|---|---|---|
| `Dockerfile` (application) | 1 | All five §2 roles are the same Python package with the same dependency closure. Role is chosen by `command:`, never by image. |
| `Dockerfile.loadtest` (§11 harness) | 1 | Genuinely different deps (load-gen libraries), different build cadence, run on demand. |
| `.dockerignore` | 1 | — |
| `docker-compose.yml` | 1 | Same image referenced six times with six different commands. |
| Redis / Postgres / Kafka | 0 | Official upstream images. |
| Client | 0 | **Not containerized** — `client/` drives an OpenCV window and needs a display. |

The load-bearing reason for one image, which the section must state: ADR-001 couples gateway and
room-server at the protocol level (relayed messages carry `lease_epoch`, §8). A gateway running
older code relaying to a newer room-server is a real failure mode. One image makes "every role is on
the same code version" true by construction; per-role images make it something you have to enforce.

### Why one image is not a scalability limit

The section must address this head-on, because "one image" reads like "one deployable" and it isn't.
**Image count and runtime scalability are orthogonal:** the image is a build artifact, while scale
comes from replica count per role, and every role scales on its own axis regardless of which image
produced it. At the plan's targets:

| Role | Sizing driver | Per-instance | Instances (global) |
|---|---|---|---|
| Room-server | 5M concurrent rooms; §7 caps rooms/instance to bound blast radius | ~500 rooms / 1000 players, ~80-100 Mbps egress (§4) | **~10,000** |
| Gateway | 10M concurrent connections | ~10k conns, ~1 Gbps relay egress | **~1,000** |
| Settlement | 110k game-ends/s → ~550k row-writes/s (§5) | ~1k events/s | **~100-200** |
| Matchmaker | ~220k enqueues/s | light | **~50** |
| Allocator | ~110k placements/s, stateless | light | **~50** |

~11,500 containers from one image, each role a separate Deployment scaled and rolled independently.
None of those numbers change if five images are built instead of one.

The three things per-role images are assumed to buy, checked against this repo:

- **Image size** — role dependency closures are near-identical (`websockets` + Redis client +
  Postgres driver). Splitting saves single-digit MB. The real bloat is `opencv-python`, which §12.2
  removes from the base dependencies anyway; one image captures that ~200 MB win identically.
- **Cold start** — genuinely matters, since §7 autoscales room-servers aggressively against high room
  churn. But startup is dominated by interpreter + import time, and the image is node-layer-cached
  after first pull. Five images sharing a base layer do not pull faster than one.
- **Blast radius / credential surface** — the argument with real content: an internet-facing gateway
  shipping the same binary as a settlement worker that reaches Postgres. Credentials arrive from
  secrets and per-role service accounts at runtime, never baked into the image, so the correct
  control is network policy plus per-role identity — not a separate image.

**The split trigger to document:** split a role out into its own image when its dependency closure
genuinely diverges — settlement adopting `confluent-kafka` (native `librdkafka`), or a room-server
moving §4's binary hot path into a compiled extension. Split that one role then, not preemptively.
That is already the rule `Dockerfile.loadtest` follows.

**The real scalability lever to name alongside this:** one Python process is single-core (GIL), so
size each container at roughly one vCPU, run one process per container, and scale horizontally. That
constraint — not image count — is what sets the instance numbers above.

---

## Edit to make

**File:** [.claude/plans/Server_Design.md](.claude/plans/Server_Design.md)

Rewrite §12 (currently lines ~499-508, "Local development environment") as
**"§12 Containerization & local development"**. Expand in place — do **not** add a §13, because §12
already describes the same compose file and would otherwise be duplicated.

### 12.1 One image, many roles

- State the counts table above, followed by the **"Why one image is not a scalability limit"**
  material — the fleet-sizing table, the three counter-arguments, the split trigger, and the
  one-process-per-vCPU note. This belongs in the document, not just in the plan: §12 sits inside a
  scaling plan, so "one image" will be read as a scalability claim unless the orthogonality of build
  artifacts and replica counts is stated outright.
- Today's entrypoint is `python -m server.main` ([server/main.py:214-219](server/main.py#L214-L219)),
  which runs the single all-in-one `Server`. The N-commands story is **blocked on §2's role split
  existing in Python first** — per-role entry points (`server.roles.gateway`, `server.roles.room`,
  `server.roles.matchmaker`, `server.roles.allocator`, `server.roles.settlement`) that each call a
  narrowed builder factored out of `build_server`. Docker selects among entry points; it does not
  create them. Say this explicitly so the section isn't read as "Docker gives you the role split."
- Multi-stage build: a `python:3.12-slim` builder stage that resolves and installs dependencies into
  a virtualenv, and a slim runtime stage that copies only the venv plus the server-side packages.
  Run as a non-root user. `requires-python = ">=3.11"` ([pyproject.toml:5](pyproject.toml#L5)) is the
  floor.
- Sketch the compose shape: one `x-kfchess: &kfchess` anchor holding `build: .` plus shared
  environment, then six services that each override only `command:`.

### 12.2 Three prerequisites in the current code

These are the parts a reader will hit immediately, and all three are repo facts, not generic advice:

1. **`host = "127.0.0.1"`** ([config/default.toml:16](config/default.toml#L16)). In a container this
   binds loopback only, so published ports refuse connections — the single most common
   containerization failure. The override already exists: `KFC_HOST` is in `_ENV_OVERRIDES`, so the
   fix is `ENV KFC_HOST=0.0.0.0` in the image (or per-service in compose). No code change needed.

2. **`_ENV_OVERRIDES` is only four entries** —
   [common/config/loader.py:31-36](common/config/loader.py#L31-L36) covers `KFC_DB_PATH`, `KFC_HOST`,
   `KFC_PORT`, `KFC_LOG_LEVEL`. A compose file has no way to tell a process its Redis URL, its
   Postgres DSN, its event-log brokers, its region, or its role. The target topology therefore
   requires that table to grow — or, better, a generic `KFC_<SECTION>_<FIELD>` rule driven off the
   `_SECTION_TYPES` dataclass fields, so new config keys become env-overridable for free. Note this
   as a **prerequisite of the compose file, not a Docker detail**.

3. **`opencv-python` and `numpy` are unconditional runtime deps**
   ([pyproject.toml:6-10](pyproject.toml#L6-L10)), so `pip install .` drags OpenCV and its
   `libGL`/`libglib` system libraries into a server image that never imports them. **Verified:** the
   only `import cv2` / `import numpy` in the tree are under [ui/](ui/) and `tests/ui/` — `server/`,
   `client/`, `common/`, `protocol/` and `kfchess/` are clean. So the recommendation is to move
   **both** to a `[project.optional-dependencies] ui = [...]` extra, leaving `websockets` as the only
   base runtime dependency. The server image shrinks by hundreds of MB and stops carrying a GUI
   toolchain.

### 12.3 Image hygiene

- `.dockerignore` excludes `ui/`, `client/`, `tests/`, `.venv/`, `.git/`, `*.db`, `*.log`,
  `ui/frames/`, `__pycache__/`. Beyond size, this makes the existing import-linter contracts
  ("Server and ui never see each other", "ui and client never see the server",
  [pyproject.toml:69-90](pyproject.toml#L69-L90)) *physically* true inside the image — the forbidden
  packages aren't merely unimported, they aren't present.
- **Logs to stdout.** `configure_logger` writes to `config.logging.server_file` (`server.log`); in a
  container the file path should be unset/`/dev/stdout` so the platform collects logs.
- **The dev SQLite file.** `database.path = "kfchess.db"` is CWD-relative. In compose either mount a
  named volume or accept that it dies with the container — call it out either way. Production has no
  SQLite at all (§1).

### 12.4 Health checks — what Docker can and cannot do

§7.1's draining and §11's readiness requirement both need an HTTP endpoint that **does not exist**:
`run_server` calls `websockets.serve` and nothing else
([server/presentation/ws_server.py:100-108](server/presentation/ws_server.py#L100-L108)). There is no
HTTP surface to probe. Say plainly that:

- Docker's `HEALTHCHECK` stays deliberately trivial (TCP connect to the websocket port) and proves
  only process liveness.
- §11's real requirement — *readiness reflects placement eligibility, not liveness* — needs a small
  HTTP admin surface (`/healthz`, `/readyz`) added alongside the websocket server, with `/readyz`
  returning failure the instant §7.1 step 1 deregisters the instance from the placement pool.
- Kubernetes probes, not `HEALTHCHECK`, are what §7.1 actually depends on. Without this line a reader
  concludes a `HEALTHCHECK` satisfies §11.

### 12.5 Framing

Close by keeping §12's existing disclaimer: one compose file, **target-shaped** (the six services
§12 already names, with single-node Redis Streams standing in for Kafka). Until §2's role split lands
in code, only the single `server` service is actually runnable — the other five are the documented
target. This is a dev/CI convenience; production topology is governed entirely by §6.

---

## Verification

Documentation-only, so verification is by inspection plus the checks that guard against the doc
drifting from the code:

1. Re-read §12 end to end — it must answer "how many Dockerfiles" (2) and "how do I use it"
   (one image, `command:` selects the role) without needing §2 open alongside it.
2. Confirm no §13 was introduced and §9's summary diagram still matches the service list in §12.
3. Confirm every file/line reference in the new §12 resolves: `config/default.toml:16`,
   `common/config/loader.py:31-36`, `pyproject.toml:6-10`, `server/main.py:214-219`,
   `server/presentation/ws_server.py:100-108`.
4. No code changed, so `.venv\Scripts\python.exe -m pytest` and `.venv\Scripts\lint-imports.exe`
   should both be unaffected — run them once to confirm the tree is clean before committing.

## Follow-up work this plan deliberately does not do

Listed here so the boundary is explicit; each is a separate task:

- Write `Dockerfile`, `Dockerfile.loadtest`, `.dockerignore`, `docker-compose.yml`.
- Move `opencv-python`/`numpy` to a `ui` extra in `pyproject.toml`.
- Generalize `_ENV_OVERRIDES` in `common/config/loader.py`.
- Add the `/healthz` + `/readyz` HTTP admin surface.
- Split `build_server` into per-role builders and entry points (§2).
