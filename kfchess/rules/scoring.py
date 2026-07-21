"""
Capture point-values - a scoring *policy*, kept in the rules layer alongside
the other move/legality policy rather than in model (which is pure data).
GameEngine consults this when a capture matures to credit the capturing
color. Values match standard chess material, with the king worth 10 so its
capture is still scored even though it simultaneously ends the game.
"""

from dataclasses import dataclass, field
from typing import Mapping

from kfchess.model.piece import PieceKind

POINT_VALUES = {
    PieceKind.PAWN: 1,
    PieceKind.KNIGHT: 3,
    PieceKind.BISHOP: 3,
    PieceKind.ROOK: 5,
    PieceKind.QUEEN: 9,
    PieceKind.KING: 10,
}


def points_for(kind: PieceKind) -> int:
    """Points a player earns for capturing a piece of `kind`."""
    return POINT_VALUES[kind]


@dataclass(frozen=True)
class ScoringPolicy:
    """Injectable capture point-values, defaulting to the values above so
    every existing caller keeps behaving identically."""

    point_values: Mapping[PieceKind, int] = field(default_factory=lambda: dict(POINT_VALUES))

    def points_for(self, kind: PieceKind) -> int:
        return self.point_values[kind]
