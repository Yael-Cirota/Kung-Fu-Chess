from typing import Set

class MovementTracker:
    """
    Responsible for tracking which pieces are currently in transit.
    Adheres to the Single Responsibility Principle.
    """
    def __init__(self):
        # Using a Set for O(1) lookups
        self._moving_pieces: Set = set()

    def set_moving(self, piece) -> None:
        if piece is not None:
            self._moving_pieces.add(piece)

    def set_arrived(self, piece) -> None:
        if piece is not None:
            self._moving_pieces.discard(piece)

    def is_moving(self, piece) -> bool:
        return piece in self._moving_pieces