# Kung Fu Chess

A real-time chess variant. Unlike standard chess, there are no turns: both
players can move simultaneously at any time, and each move takes real time
to travel across the board. Pieces mid-move can be intercepted or can
capture on arrival, so timing and reflexes matter as much as strategy.

The project has three ways to play it:

- **VPL scripts** — a headless, deterministic text-scripting DSL for driving
  and testing games without any rendering or networking (`main.py`).
- **A local graphics demo** — OpenCV rendering and mouse input against an
  in-process engine, single machine, no network (`ui/main.py`).
- **Online multiplayer** — a websocket server (`server/main.py`) and a
  client (`client/main.py`) that reuses the same rendering/input stack as
  the local demo, driven by a remote game session instead of a local one.

## How the game differs from standard chess

- **No turns.** Either color can issue a move command at any time.
- **Moves take time.** A move's duration is proportional to the distance
  travelled (Chebyshev/cell-step distance, not pixels), so a 3-square move
  takes three times as long as a 1-square move.
- **A piece already in motion can't be redirected** until it arrives
  (`MOTION_IN_PROGRESS`).
- **Captures can happen on arrival.** If a piece arrives at a square
  currently occupied by an enemy piece that is itself airborne (mid-jump),
  the arriving piece is captured instead of capturing.
- **Winning condition:** capturing the opposing king ends the game
  immediately; all other pending moves are cancelled.
- Standard piece movement rules apply (rook/bishop/queen slide,
  knight/king step, pawn forward/double-step/diagonal-capture with
  queening promotion). Check, checkmate, castling, and en passant are
  intentionally out of scope.

## Project structure

```
kfchess/     Headless engine (the domain core), fully synchronous/deterministic
  api/         Public boundary: Protocols + DTOs + factory (GameSession,
               BoardSnapshot, MoveResult, EngineConfig, ...) - the only
               seam other layers are allowed to import through
  engine/      GameEngine - application command boundary (request_move,
               wait, game_over)
  realtime/    Simulated-clock motion, cooldown, collision, atomic arbiter
  rules/       Per-piece move legality (never mutates the board)
  model/       Board, Piece, Position, GameState - pure data, no rules/timing
  input/       Legacy pixel-click -> position (Controller/BoardMapper)
  io/          VPL text board parse/print
  texttests/   VPL script parser + runner

ui/          OpenCV rendering, sprite animation, frame capture, ClickHandler
             (pixel-click -> board-command translation); depends only on
             kfchess.api and common - never on a live engine object

common/      Shared, network-agnostic utilities: config loader/schema
             (TOML + env overrides), the async event bus, logging setup,
             tracing IDs, Result type

protocol/    Wire format shared by client and server: typed message classes
             (protocol/messages.py) and their JSON codec (protocol/codec.py)

server/      Websocket multiplayer server (application/domain/infrastructure/
             presentation layers)
  domain/       Client sessions, connection ids, pending moves, room status -
                 plain data/interfaces, no I/O
  application/   Auth, matchmaking, room lifecycle, ELO, disconnect policy,
                 activity log, room ticker - orchestrates domain + kfchess
  infrastructure/ SQLite user/game-record repositories, connection factory,
                 threaded DB writer - reached only through Protocols
  presentation/  Message dispatcher, connection registry, heartbeat monitor,
                 the websockets transport adapter (ws_server.py)

client/      Websocket multiplayer client
  net/         ClientLink (queues), inbound_router, ws_client (background
               asyncio/websockets thread + heartbeat loop)
  session/     RemoteGameSession (satisfies kfchess.api's GameSession
               Protocol), ClockEstimator, SnapshotStore, SyncEventBus
  shell/       Text REPL for login/register/matchmaking/room commands
               (login, register, play, cancel, create-room, join-room,
               leave-room, help, quit)

config/      default.toml - engine, server, matchmaking, connection,
             rooms, database, logging, and client settings

tests/       Mirrors the source tree, one test module per source module

main.py      Repo-root entry point: VPL text-scripting (the graded entry point)
```

**The layering is enforced by `import-linter`** (see `[tool.importlinter]`
in `pyproject.toml`), not just convention:

- `kfchess` and `common` never import outward (no `ui`, `server`, `client`).
- `kfchess` never imports `websockets`/`asyncio`/`socket`/`sqlite3` - the VPL
  path stays free of networking.
- `ui` and `client` may only cross into `kfchess.api`, never into
  `kfchess.model`/`rules`/`realtime`/`engine`/`input`/`io`/`texttests`.
- `protocol` sits above `kfchess`/`common`; `server` and `client` each sit
  above `protocol` -> `kfchess` -> `common`.
- `server` and `ui` never see each other; `ui` and `client` never see `server`.
- Inside `server`, `presentation` -> `application` -> `domain`, and
  `server.infrastructure`'s SQLite/connection modules are reached only
  through Protocols, never imported directly by `domain`/`application`.

`RuleEngine` never mutates the board; `Board` is only ever mutated
atomically by `RealTimeArbiter`, applying arrivals in maturation order.

## Requirements

- Python >= 3.11

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e . --group dev      # or: pip install opencv-python numpy websockets pytest coverage import-linter
```

## Running the tests

```powershell
.venv\Scripts\python.exe -m pytest
```

With coverage:

```powershell
.venv\Scripts\python.exe -m coverage run -m pytest
.venv\Scripts\python.exe -m coverage report
```

Architecture/layering lint (must pass):

```powershell
.venv\Scripts\lint-imports.exe
```

## Running a VPL script

`main.py` reads a VPL script from stdin and writes the script's output to
stdout:

```powershell
.venv\Scripts\python.exe main.py < path\to\script.vpl
```

## Running the local graphics demo

Single machine, no network, an in-process engine:

```powershell
.venv\Scripts\python.exe ui\main.py             # opens an OpenCV window
.venv\Scripts\python.exe ui\main.py --no-window # headless; writes ui/frames + rendered_board.png
```

## Running online multiplayer

Start the server (reads `config/default.toml`; websockets on
`127.0.0.1:8765` by default):

```powershell
.venv\Scripts\python.exe -m server.main
```

Then run one client per player:

```powershell
.venv\Scripts\python.exe -m client.main
```

The client opens a text REPL first. Available commands:

- `register <username> <password>` / `login <username> <password>`
- `play` — join the ELO-based matchmaking queue; `cancel` to leave it
- `create-room` — host a room and share the printed room id
- `join-room <room_id>` — join a room another player created
- `leave-room <room_id>`
- `help`, `quit`

Once a match starts, the REPL hands off to the same OpenCV render/input
stack the local demo uses, now driven by a `RemoteGameSession` synced to the
server's simulated clock instead of a local `EngineGameSession`. Each client
process plays exactly one game; restart the process to play again.

## The VPL scripting format

A VPL script has a `Board:` section describing the starting position and a
`Commands:` section describing a sequence of actions to execute against it.

```
Board:
wR . .
Commands:
click 50 50
click 250 50
wait 1000
print board
```

**Board section** — one row per line, tokens separated by spaces:
- `.` — empty square
- `<color><kind>` — a piece, e.g. `wK` (white king), `bP` (black pawn)
  - Colors: `w`, `b`
  - Kinds: `K`, `Q`, `R`, `B`, `N`, `P`

**Commands section** — one command per line:
- `click <x> <y>` — simulate a mouse click at pixel `(x, y)` (100px cells);
  the first click on a piece selects it, a second click on a different
  square requests a move there
- `jump <x> <y>` — shorthand for clicking the same square twice, requesting
  a same-square "jump" move (used to make a piece briefly airborne)
- `wait <ms>` — advance the simulated clock by `ms` milliseconds, maturing
  any moves scheduled to arrive by then
- `print board` — print the board's current state, one row per line
- `print scores` — print the running capture-point score as a single line,
  `White: <w>  Black: <b>` (pawn 1, knight/bishop 3, rook 5, queen 9, king 10)

Malformed boards produce a single-line error instead of running any
commands: `ERROR ROW_WIDTH_MISMATCH` or `ERROR UNKNOWN_TOKEN`.

## Design notes

- `GameEngine` is the only place `game_over` lives and the only public
  boundary callers use — it enforces application-level guards (game already
  over, piece already moving) before ever consulting `RuleEngine`.
- `RealTimeArbiter` owns all in-flight `Motion`/`PendingMove` state and is
  the sole mutator of `Board`, applying arrivals atomically in the order
  they mature.
- Move rejection reasons are stable string constants
  (`kfchess.rules.move_validation.MoveRejectionReason`), used consistently
  across the engine, the DSL, and the tests.
- `ui` and `client` both depend only on `kfchess.api`'s `GameSession`
  Protocol and DTOs — never on a live engine object — so the exact same
  render/input/animation code drives a local `EngineGameSession` and a
  networked `RemoteGameSession` with no branching.
- The server's tick pipeline and event bus are async; the client's
  `SyncEventBus` exists because `RemoteGameSession.wait()` is called
  synchronously from the 60fps render loop and can't await it.
