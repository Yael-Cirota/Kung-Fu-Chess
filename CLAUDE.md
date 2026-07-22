# CLAUDE.md

Guidance for AI-assisted development in this repository.

## 1. Project Overview & Architecture

**Kung-Fu-Chess** is a real-time chess variant. There are no turns: both
colors may issue moves at any time, and every move takes real (simulated)
time to travel across the board proportional to its distance. Pieces in
motion cannot be redirected, can be captured on arrival, and capturing the
enemy king ends the game immediately. Check, checkmate, castling, and en
passant are intentionally out of scope. See `README.md` for the full ruleset.

The codebase is a **strictly layered stack**, top to bottom:

```
ui/          Graphics/animation demo: OpenCV rendering, sprite animation, frame
             capture, plus ClickHandler (pixel-click -> board-command translation)
kfchess/     The headless engine (the domain core)
  api/         Public boundary of the engine: Protocols + DTOs + factory
  engine/      GameEngine - application command boundary (request_move, wait, game_over)
  realtime/    Simulated-clock motion, cooldown, collision, atomic arbiter
  rules/       Per-piece move legality (never mutates the board)
  model/       Board, Piece, Position, GameState - pure data, no rules or timing
  input/       Legacy pixel-click -> position (Controller/BoardMapper, VPL path)
  io/          VPL text board parse/print
  texttests/   VPL script parser + runner
main.py      Repo-root entry point: VPL text-scripting (the graded entry point)
tests/       Mirrors the source tree, one test module per source module
```

**The central architectural rule: no layer touches another layer's internal
types.** Every boundary is crossed through a `Protocol` and immutable DTOs:

- `kfchess.api` re-exports `Position`, `PieceView`, `BoardSnapshot`,
  `MotionInfo`, `MoveResult`, and the `GameSession` Protocol. Nothing outside
  `kfchess` ever imports a `kfchess.model.Piece` or a `kfchess`-internal enum.
- `ui` depends on `kfchess.api` and nothing deeper: it holds `GameSession` and
  the DTOs, never a live engine object. `ui/click_handler.py` owns the only two
  inherently client-side concerns - pixel->cell geometry and the per-player
  select/reselect/move state machine - and calls `session.request_move`
  directly. There is no delegating wrapper layer in between.
- `ui/graphics/canvas.py` defines a `Canvas` Protocol that is the **only**
  seam allowed to touch OpenCV/`Img`; everything else in `ui` depends on the
  Protocol, not on `cv2`.

Adapters (e.g. `EngineGameSession` in `kfchess/api/session.py`) do nothing but
delegate to the layer below and route raw objects through a `*_mapping` module
for DTO translation.

## 2. Tech Stack & Primary Libraries

- **Language:** Python >= 3.10
- **Runtime deps:** `opencv-python` (rendering/windowing), `numpy` (image buffers)
- **Dev/tooling:** `pytest`, `coverage`, `import-linter` (architecture enforcement)
- **Packaging:** `pyproject.toml` (PEP 621), local `.venv`
- No web/network layer; the engine is fully headless and deterministic.

## 3. Coding Standards & Best Practices

- **Respect the layering.** `import-linter` enforces `ui -> kfchess` and
  forbids `ui` from reaching past `kfchess.api` into any engine internals
  (see `[tool.importlinter]` in `pyproject.toml`). If you add a cross-layer
  import, it must go through the `kfchess.api` Protocol seam, or the contract
  check fails.
- **Never leak internal types across a boundary.** Add fields to the DTOs in
  `kfchess/api/dto.py` and translate in `engine_mapping`/`api/*_mapping.py`;
  do not pass live `model` objects outward.
- **Protocols over base classes.** Boundaries are `@runtime_checkable
  Protocol` classes; concrete implementations are plain classes that
  structurally satisfy them.
- **Purity boundaries:** `rules` never mutates `Board`; `RealTimeArbiter` is
  the *sole* mutator of `Board`, applying arrivals atomically in maturation
  order. Preserve this.
- **Two-clocks rule (animation):** in `ui/app.py`, engine time drives *motion
  position* (where a piece is interpolated along its path) and wall/render
  time drives *only* cosmetic sprite-frame pacing. Never interpolate position
  against the render clock — read `build_visual_states` before touching it.
- **Config over constants:** rendering/layout knobs live in `ui/ui_config.py`;
  move rejection reasons are stable string constants in
  `kfchess.rules.move_validation.MoveRejectionReason`.
- **Testing is mandatory and mirrors the source tree.** One test module per
  source module under `tests/`. Collaborators are replaced with hand-written
  fakes (see `tests/ui/test_app.py`), not mocking frameworks. The project
  targets 100% line coverage (`.coveragerc` omits `tests/*`); mark genuinely
  unreachable script entry points with `# pragma: no cover`.

## 4. Common Commands

Use the project venv Python (`.venv\Scripts\python.exe`), or activate first.

```powershell
# Setup
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e . --group dev      # or: pip install pytest coverage import-linter

# Run tests
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest --disable-warnings

# Coverage
.venv\Scripts\python.exe -m coverage run -m pytest
.venv\Scripts\python.exe -m coverage report

# Architecture / layering lint (must pass)
.venv\Scripts\lint-imports.exe

# Run the VPL text-scripting entry point (graded)
.venv\Scripts\python.exe main.py < path\to\script.vpl

# Run the graphics/animation demo
.venv\Scripts\python.exe ui\main.py            # opens an OpenCV window
.venv\Scripts\python.exe ui\main.py --no-window # headless; writes ui/frames + rendered_board.png
```

## 5. AI Context

- **Two entry points, different purposes.** Repo-root `main.py` is the graded
  VPL text-scripting harness. `ui/main.py` is a self-contained graphics demo
  and is the composition root that wires `kfchess.api` to the `ui` stack.
  Do not merge or cross-wire them.
- **VPL DSL:** the deterministic scripting format (`Board:` + `Commands:` with
  `click`, `jump`, `wait`, `print board`) documented in `README.md`. It exists
  so games can be driven and asserted without rendering or timing flakiness;
  new engine behavior should be exercisable through it.
- **Simulated clock, not real time.** `wait <ms>` advances a virtual clock and
  matures scheduled arrivals; nothing sleeps. Tests are fully deterministic —
  keep them that way (no `time.sleep`, no wall-clock assertions in the engine).
- **Real-time chess semantics to keep in mind:** move duration ∝ Chebyshev
  cell distance; a moving piece rejects new commands (`MOTION_IN_PROGRESS`); a
  piece arriving on an airborne enemy is itself captured; king capture ends the
  game and cancels all pending moves. Post-move cooldown and move/jump
  durations live in `kfchess/realtime/` (`cooldown.py`, `movement_profile.py`).
- **When adding a feature that crosses layers,** the usual shape is: extend the
  DTO in `kfchess/api/dto.py`, populate it in the relevant `*_mapping` module,
  widen the `GameSession` Protocol, then consume it in `ui`.
  Run `lint-imports` and `pytest` before considering it done.
- **Sprite assets** live under `ui/assets/pieces1|pieces2/<PIECE>/states/<state>/`
  with per-state `config.json`. Reskinning is a one-line change of `PIECES_DIR`
  in `ui/ui_config.py`.
