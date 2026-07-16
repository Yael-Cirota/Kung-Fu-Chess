from dataclasses import dataclass
from typing import Dict, Hashable, Tuple

# The two states a motion can be playing while a piece is actually moving.
# Everything else about the machine (how long a clip is, whether it loops,
# what it hands off to) comes from the injected per-state config, not from
# anything hard-coded here.
_MOTION_STATES = ("move", "jump")


@dataclass
class _PieceAnimation:
    state: str
    state_start_ms: int


class PieceAnimator:
    """
    Per-piece animation state machine: idle <-> move/jump -> short_rest/
    long_rest -> idle. Driven purely by per-piece motion signals (is this
    piece moving right now, and is that motion a jump?) and a now_ms value
    handed in by the caller - no knowledge of pixels, board layout, or
    kfchess. Frame advancement, looping, and state hand-off are all
    resolved through the injected AnimationStateConfig map, keyed by state
    name, so no fps/frame-count/loop-flag magic numbers live here.
    """

    def __init__(self, state_configs: Dict[str, object], idle_state: str = "idle"):
        self._configs = state_configs
        self._idle_state = idle_state
        self._pieces: Dict[Hashable, _PieceAnimation] = {}

    def update(self, piece_key: Hashable, is_moving: bool, is_jump: bool, now_ms: int) -> Tuple[str, int]:
        anim = self._pieces.get(piece_key)
        if anim is None:
            anim = _PieceAnimation(state=self._idle_state, state_start_ms=now_ms)
            self._pieces[piece_key] = anim

        if is_moving:
            desired_state = "jump" if is_jump else "move"
            if anim.state != desired_state:
                anim.state = desired_state
                anim.state_start_ms = now_ms
        else:
            self._advance_resting_state(anim, now_ms)

        frame_index = self._frame_index(anim.state, now_ms - anim.state_start_ms)
        return anim.state, frame_index

    def forget(self, piece_key: Hashable) -> None:
        self._pieces.pop(piece_key, None)

    def _advance_resting_state(self, anim: _PieceAnimation, now_ms: int) -> None:
        while True:
            if anim.state in _MOTION_STATES:
                # The motion signal just dropped - hand off to whatever
                # state that motion's clip points at (short_rest/long_rest)
                # regardless of that motion state's own loop flag.
                anim.state = self._configs[anim.state].next_state
                anim.state_start_ms = now_ms
                continue

            config = self._configs[anim.state]
            if config.is_loop:
                return

            elapsed_ms = now_ms - anim.state_start_ms
            clip_duration_ms = config.frame_count / config.frames_per_sec * 1000
            if elapsed_ms < clip_duration_ms:
                return

            anim.state = config.next_state
            anim.state_start_ms = now_ms

    def _frame_index(self, state: str, elapsed_ms: int) -> int:
        config = self._configs[state]
        raw_index = int(elapsed_ms / 1000 * config.frames_per_sec)
        if config.is_loop:
            return raw_index % config.frame_count
        return min(raw_index, config.frame_count - 1)
