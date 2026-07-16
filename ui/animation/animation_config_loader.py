"""
Loads per-state animation timing from a skin's sprite folders.

Kept separate from ui.ui_config (which holds only declarative constants) so
that importing configuration never touches the filesystem: this loader's disk
I/O runs only when the composition root explicitly calls load_animation_configs.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


@dataclass(frozen=True)
class AnimationStateConfig:
    """One state's animation timing: how many sprite frames it has, how
    fast to play them, whether it loops, and what state follows it when
    a non-looping clip finishes."""
    frame_count: int
    frames_per_sec: int
    is_loop: bool
    next_state: str


ANIMATION_STATE_NAMES = ("idle", "move", "jump", "short_rest", "long_rest")

# Every piece/state folder under a skin ships its own states/<state>/config.json
# with identical {physics.next_state_when_finished, graphics.frames_per_sec,
# graphics.is_loop} content (verified across all 12 piece folders in pieces1/
# and pieces2/) - so it's read once from a single reference piece rather than
# duplicated per piece. Frame count is *not* in that metadata, so it's counted
# from the actual sprite files instead of assumed.
_ANIMATION_REFERENCE_PIECE_FOLDER = "KW"


def _load_animation_state_config(pieces_dir: Path, state: str) -> AnimationStateConfig:
    state_dir = pieces_dir / _ANIMATION_REFERENCE_PIECE_FOLDER / "states" / state
    frame_count = len(list((state_dir / "sprites").glob("*.png")))
    with open(state_dir / "config.json") as f:
        raw = json.load(f)
    return AnimationStateConfig(
        frame_count=frame_count,
        frames_per_sec=raw["graphics"]["frames_per_sec"],
        is_loop=raw["graphics"]["is_loop"],
        next_state=raw["physics"]["next_state_when_finished"],
    )


def load_animation_configs(pieces_dir: Path) -> Dict[str, AnimationStateConfig]:
    return {state: _load_animation_state_config(pieces_dir, state) for state in ANIMATION_STATE_NAMES}
