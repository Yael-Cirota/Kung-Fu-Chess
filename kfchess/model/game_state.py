from dataclasses import dataclass


@dataclass
class GameState:
    """Holds the small set of mutable state GameEngine owns directly."""
    game_over: bool = False
