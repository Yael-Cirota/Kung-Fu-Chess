from dataclasses import dataclass
from typing import Dict

# Defaults only - both durations are constructor parameters on
# CooldownPolicy, so callers can retune or inject an entirely different
# policy without touching this module.
DEFAULT_MOVE_COOLDOWN_MS = 1000
DEFAULT_JUMP_COOLDOWN_MS = 500


@dataclass(frozen=True)
class CooldownPolicy:
    """
    Answers exactly one question: after a piece finishes a motion, how
    long before it may move again? Move and jump durations are
    independent, supplied at construction - this class holds no piece
    rules, timing-per-cell math, or board access.
    """
    move_cooldown_ms: int = DEFAULT_MOVE_COOLDOWN_MS
    jump_cooldown_ms: int = DEFAULT_JUMP_COOLDOWN_MS

    def duration_for(self, is_jump: bool) -> int:
        return self.jump_cooldown_ms if is_jump else self.move_cooldown_ms


class CooldownTracker:
    """
    Tracks, per piece, the simulated-time timestamp at which its
    post-motion cooldown expires. Pure piece -> expiry bookkeeping; it
    knows nothing about motion, rules, or the board, and never decides
    durations - those come from CooldownPolicy.
    """

    def __init__(self):
        self._expires_at: Dict[object, int] = {}

    def start(self, piece, expires_at_ms: int) -> None:
        self._expires_at[piece] = expires_at_ms

    def is_active(self, piece, now_ms: int) -> bool:
        expiry = self._expires_at.get(piece)
        return expiry is not None and now_ms < expiry

    def clear(self, piece) -> None:
        self._expires_at.pop(piece, None)
