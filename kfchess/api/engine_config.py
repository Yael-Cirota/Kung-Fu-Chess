from dataclasses import dataclass, field
from typing import Mapping

from kfchess.model.piece import PieceKind
from kfchess.realtime.cooldown import DEFAULT_JUMP_COOLDOWN_MS, DEFAULT_MOVE_COOLDOWN_MS
from kfchess.realtime.movement_profile import MOVE_DURATION_MS_PER_CELL
from kfchess.rules.scoring import POINT_VALUES


@dataclass(frozen=True)
class EngineConfig:
    """Injectable engine timing/scoring knobs. Defaults reproduce today's
    hard-coded constants exactly, so a factory call that omits config is
    unaffected. The VPL path never receives one of these - it keeps building
    its arbiter with hard-coded defaults so graded output stays byte-identical
    regardless of what is in config/default.toml."""

    move_duration_ms_per_cell: int = MOVE_DURATION_MS_PER_CELL
    jump_duration_ms: int = MOVE_DURATION_MS_PER_CELL
    move_cooldown_ms: int = DEFAULT_MOVE_COOLDOWN_MS
    jump_cooldown_ms: int = DEFAULT_JUMP_COOLDOWN_MS
    point_values: Mapping[PieceKind, int] = field(default_factory=lambda: dict(POINT_VALUES))
