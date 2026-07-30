from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ForcedResign:
    room_id: str
    color: str


class DisconnectPolicy:
    """A timed grace period per (room, color). Rides the synchronous
    tick(now_ms) sweep already used for every timeout in this design - no new
    timer mechanism, no asyncio.sleep."""

    def __init__(self, grace_ms: int = 20000):
        self._grace_ms = grace_ms
        self._deadlines: Dict[Tuple[str, str], int] = {}

    def on_disconnect(self, room_id: str, color: str, now_ms: int) -> None:
        self._deadlines[(room_id, color)] = now_ms + self._grace_ms

    def on_reconnect(self, room_id: str, color: str) -> None:
        self._deadlines.pop((room_id, color), None)

    def deadline_for(self, room_id: str, color: str) -> Optional[int]:
        return self._deadlines.get((room_id, color))

    def tick(self, now_ms: int) -> List[ForcedResign]:
        resigned = []
        for (room_id, color), deadline_ms in list(self._deadlines.items()):
            if now_ms >= deadline_ms:
                resigned.append(ForcedResign(room_id=room_id, color=color))
                del self._deadlines[(room_id, color)]
        return resigned
