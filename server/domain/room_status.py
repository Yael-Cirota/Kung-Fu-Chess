from enum import Enum


class RoomStatus(Enum):
    WAITING = "waiting"  # fewer than two players; Application gate rejects MoveRequest
    RUNNING = "running"  # set once a second player joins/is matched
    ENDED = "ended"  # set on GAME_OVER; Application gate rejects MoveRequest
