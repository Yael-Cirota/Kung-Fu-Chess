from dataclasses import dataclass, field
from typing import Dict, Optional

from kfchess.model.piece import Color


def _empty_scores() -> Dict[str, int]:
    return {Color.WHITE.value: 0, Color.BLACK.value: 0}


@dataclass
class GameState:
    """Holds the small set of mutable state GameEngine owns directly."""
    game_over: bool = False
    winner: Optional[str] = None
    scores: Dict[str, int] = field(default_factory=_empty_scores)

    def add_score(self, color: str, points: int) -> None:
        """Credit `color` with `points` for a capture (pure data mutation, no rules)."""
        self.scores[color] = self.scores.get(color, 0) + points
