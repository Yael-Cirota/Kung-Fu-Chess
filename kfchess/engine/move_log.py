from dataclasses import dataclass

from kfchess.model.position import Position


@dataclass(frozen=True)
class MoveRecord:
    """
    One entry in GameEngine's move history: an *issued* (accepted) move, not
    necessarily a completed one - in this real-time variant a piece may be
    captured mid-flight or cancelled when a king falls, but the command the
    player gave still belongs in their log. Carries only the engine-internal
    facts (color/symbol strings, from/to Positions); kfchess.api translates it
    into the outward-facing MoveLogEntry DTO.
    """
    color: str
    symbol: str
    from_pos: Position
    to_pos: Position
