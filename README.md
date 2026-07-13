# Kung Fu Chess

A real-time chess variant engine written in Python. Unlike standard chess,
there are no turns: both players can move simultaneously at any time, and
each move takes real time to travel across the board. Pieces mid-move can
be intercepted or can capture on arrival, so timing and reflexes matter as
much as strategy.

The project is a headless engine plus a small text-based scripting DSL
("VPL") used to drive and test games deterministically, without any actual
rendering or networking layer.

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
kfchess/
  model/      Board, Piece, Position, GameState - pure data, no rules or timing
  rules/      Per-piece movement legality (RuleEngine, piece_rules, move_validation)
  realtime/   Simulated-clock motion tracking and atomic move execution (RealTimeArbiter, Motion)
  engine/     GameEngine - the public command boundary (request_move, wait, game_over)
  input/      Pixel-click -> board-position translation (Controller, BoardMapper)
  io/         Text board parsing/printing for the VPL scripting format
  texttests/  VPL script parser + runner that wires the whole stack together
tests/        Mirrors the package layout above, one test module per source module
main.py       CLI entry point: reads a VPL script from stdin, writes output to stdout
```

Each layer only depends on the ones below it: `model` has no dependencies,
`rules` depends only on `model`, `realtime` depends on `model`/`rules`,
`engine` composes `realtime`/`rules`/`model`, and `input`/`io`/`texttests`
sit on top as adapters. `RuleEngine` never mutates the board; `Board` is
only ever mutated atomically by `RealTimeArbiter` when a move matures.

## Requirements

- Python >= 3.10

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install pytest coverage
```

## Running the tests

```bash
pytest
```

With coverage:

```bash
coverage run -m pytest
coverage report
```

## Running a script

`main.py` reads a VPL script from stdin and writes the script's output to
stdout:

```bash
python main.py < path/to/script.vpl
```

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

Malformed boards produce a single-line error instead of running any
commands: `ERROR ROW_WIDTH_MISMATCH` or `ERROR UNKNOWN_TOKEN`.

## Design notes

- `GameEngine` is the only place `game_over` lives and the only public
  boundary `Controller`/`ScriptRunner` call into — it enforces
  application-level guards (game already over, piece already moving)
  before ever consulting `RuleEngine`.
- `RealTimeArbiter` owns all in-flight `Motion`/`PendingMove` state and is
  the sole mutator of `Board`, applying arrivals atomically in the order
  they mature.
- Move rejection reasons are stable string constants
  (`kfchess.rules.move_validation.MoveRejectionReason`), used consistently
  across the engine, the DSL, and the tests.
