# SRP Review & Refactor Plan: ui / controller / kfchess.api

## Context

Goal: check whether the `ui` and `controller` layers honor the Single Responsibility
Principle, and plan the changes needed where they don't. During review the user also
asked to fold in the `kfchess/api` adapter.

**Verdict up front: these layers are largely SRP-clean.** The architecture is
deliberately layered (`ui → controller → kfchess.api → engine`), most modules are
small, single-purpose, and dependency-injected, and several docstrings explicitly
police their own boundaries. The problems are **localized to three files**, plus one
adapter cleanup and one non-SRP import bug worth fixing while we're in there.

**Explicitly NOT changing:** `controller/game_controller.py`. Its `GameController`
deliberately merged the old `kfchess.input.Controller` + `ui.state.PendingMotionTracker`
(see its docstring and the just-deleted `ui/state/` files in git status). "Orchestration
between ui and kfchess" is one legitimate responsibility; splitting it would revert that
recent, intentional refactor.

Already-clean modules (no action): `motion_predictor.py`, `piece_animator.py`,
`sprite_resolver.py`, `sprite_loader.py`, `piece_visual_state.py`, `window.py`,
`renderer.py`, `app.py` (legitimate coordinator), `board_mapper.py`, `dto.py`.

---

## Changes

### 1. `ui/img.py` — remove the display responsibility (SRP)
`Img` cohesively does "operations on an image" (read/resize, composite, text) — keep
that. The one violation is `Img.show()` (lines 89-94): it calls
`cv2.imshow`/`waitKey`/`destroyAllWindows`, breaking the invariant stated in
`ui/graphics/window.py` that cv2 live-display lives *only* in `Window`.

- Remove `Img.show()`. If a "display a still image and block" helper is genuinely
  needed, add it to `ui/graphics/window.py` (e.g. `Window.show_blocking(img)`), the
  one module allowed to touch a live display.
- Do **not** over-decompose `Img` into loader/compositor/annotator classes — that
  cohesion is fine.
- (Optional, low priority) `put_text` appears unused; note as dead code, don't let it
  drive the change.

### 2. `ui/ui_config.py` — config vs. loading logic + kill import-time I/O (SRP)
Today this module mixes static constants + a dataclass with filesystem/JSON *loading
logic*, and executes disk I/O as an **import side effect** (line 64:
`ANIMATION_STATE_CONFIGS = load_animation_configs(PIECES_DIR)`). Importing `ui_config`
touches the disk and raises if sprite folders are missing — coupling every importer to
disk state.

- Move `_load_animation_state_config` + `load_animation_configs` (and the
  `AnimationStateConfig` dataclass + `ANIMATION_STATE_NAMES` /
  `_ANIMATION_REFERENCE_PIECE_FOLDER` constants they use) into the animation package,
  e.g. a new `ui/animation/animation_config_loader.py`.
- `ui_config.py` keeps only declarative constants (sizes, paths, sprite-state names).
- Remove the module-level `ANIMATION_STATE_CONFIGS = ...` side effect. The composition
  root (`main.py` / new `app.py` wiring) calls `load_animation_configs(PIECES_DIR)`
  explicitly and injects the result into `PieceAnimator` (as it already does via the
  `ANIMATION_STATE_CONFIGS` symbol today).

### 3. `ui/main.py` — split the demo god-script (SRP, calibrated)
`main.py` is a demo harness (`# pragma: no cover - script entry point`), so calibrate:
a composition root that wires everything is *allowed* and should stay. The real target
is the god function `run_move_and_capture` (lines 49-88), which mixes: sim-stepping,
visual-state building, rendering, PNG disk-writing, settle-tick logic, live display,
and console printing.

- Extract a small **frame-capture / driver** helper out of `main.py` into its own
  module (e.g. `ui/demo_driver.py` or extend `ui/app.py`), separating:
  - "advance the sim until a piece settles" (loop/settle-tick control), from
  - "render + write a frame to disk" (a `save_frame(renderer, ...)` sink), from
  - console progress printing (the demo's reporting concern).
- Keep `main()` as the composition root + scripted scenario; move raw `cv2.imwrite`
  calls (lines 76, 143) behind the frame-writer helper so cv2 stops leaking into
  `main.py` (consistent with the Window/Img boundary).
- Keep the pieces small; this is demo code, not production — don't gold-plate.

### 4. `kfchess/api/session.py` — extract DTO translation from the adapter (SRP)
`EngineGameSession` is fundamentally an adapter (fine), but it blends three things:
pure delegation, **DTO translation** (`_to_piece_view`, `board_snapshot`, `motion_for`
field renames at lines 36-42, 76-96), and **piece-identity resolution** (`_find_piece`
linear grid scan, lines 98-103).

- Extract the engine→DTO mapping into a dedicated module, e.g.
  `kfchess/api/engine_mapping.py`: `piece_to_view(piece)`, `motion_to_info(motion)`,
  `snapshot_from_grid(grid)`, and `find_piece_by_id(grid, piece_id)`.
- `EngineGameSession` becomes thin: delegate to the engine, hand results to the mapper.
  This isolates "knowledge of engine internals / attribute renames" in one place.
- (Efficiency aside, not SRP) the repeated full-grid scans in `_find_piece` /
  `board_snapshot` can be consolidated in the mapper, but don't expand scope into a
  perf refactor.

### 5. `controller/factory.py` — fix import name collision (import hygiene, not SRP)
Lines 3 and 5 both import the name `GameController`; the concrete class (line 5)
shadows the Protocol (line 3), so the `-> GameController` return annotation resolves to
the concrete class and the Protocol import is dead. Alias one, e.g.
`from controller.api import GameController as GameControllerProtocol`, and annotate the
return as the Protocol. Small, worth doing while touching the layer; call it out as a
bug fix, not an SRP change.

---

## Critical files

- `ui/img.py` (remove `show`), `ui/graphics/window.py` (optional blocking-show home)
- `ui/ui_config.py` (strip to constants) + new `ui/animation/animation_config_loader.py`
- `ui/main.py` (decompose driver) + new `ui/demo_driver.py` (or extend `ui/app.py`)
- `kfchess/api/session.py` + new `kfchess/api/engine_mapping.py`
- `controller/factory.py` (alias fix)

Reuse existing utilities rather than reinventing: `build_visual_states` (`ui/app.py`),
`PieceAnimator` (`ui/animation/piece_animator.py`), `Window` (`ui/graphics/window.py`),
`BoardRenderer` (`ui/graphics/renderer.py`).

## Verification

- Run the existing test suites — they encode intended behavior and must stay green:
  `tests/ui/`, `tests/controller/`, and the kfchess api tests. In particular
  `tests/ui/graphics/test_window.py`, `tests/ui/test_img.py`, `tests/ui/test_ui_config.py`,
  `tests/controller/test_game_controller.py` will be directly affected — update them to
  match relocated symbols.
- Run the demo end-to-end headless: `python ui/main.py --no-window` and confirm it still
  prints the board, glides the pawn/knight, and writes frames + `rendered_board.png`.
- Confirm `import ui.ui_config` no longer touches the disk (no I/O at import time).
- `grep` for `cv2` outside `ui/graphics/window.py` and `ui/img.py` to confirm the
  display/imwrite leak is closed.
