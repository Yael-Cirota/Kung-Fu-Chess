from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from common.events import Event, EventBus, EventNames


@dataclass(frozen=True)
class MatchTicket:
    user_id: int
    username: str
    elo: int


@dataclass(frozen=True)
class Match:
    white: MatchTicket
    black: MatchTicket


@dataclass(frozen=True)
class MatchTimeout:
    user_id: int


class MatchmakingService:
    """Owns ELO windows and enqueue/timeout bookkeeping only - no reference
    to RoomService, no knowledge that rooms or connections exist. Publishes
    MATCH_FOUND / MATCH_TIMED_OUT rather than calling into room creation
    directly (see 'Internal EventBus as the service-to-service seam')."""

    def __init__(self, bus: EventBus, elo_window: int = 100, timeout_ms: int = 60000):
        self._bus = bus
        self._elo_window = elo_window
        self._timeout_ms = timeout_ms
        self._queue: Dict[int, Tuple[MatchTicket, int]] = {}

    def enqueue(self, ticket: MatchTicket, now_ms: int) -> Optional[Match]:
        # Dict iteration follows insertion order (guaranteed since 3.7), so this
        # scan is FIFO: the longest-waiting opponent inside the ELO window wins,
        # not the closest ELO. Do not swap _queue for an unordered container.
        for other_id, (other_ticket, _enqueued_at_ms) in self._queue.items():
            if other_id == ticket.user_id:
                continue
            if abs(other_ticket.elo - ticket.elo) <= self._elo_window:
                del self._queue[other_id]
                white, black = (ticket, other_ticket) if ticket.elo <= other_ticket.elo else (other_ticket, ticket)
                match = Match(white=white, black=black)
                self._bus.publish(Event(name=EventNames.MATCH_FOUND, payload={"match": match}))
                return match

        self._queue[ticket.user_id] = (ticket, now_ms)
        return None

    def cancel(self, user_id: int) -> None:
        self._queue.pop(user_id, None)

    def tick(self, now_ms: int) -> List[MatchTimeout]:
        timed_out = []
        for user_id, (_ticket, enqueued_at_ms) in list(self._queue.items()):
            if now_ms - enqueued_at_ms >= self._timeout_ms:
                del self._queue[user_id]
                timed_out.append(MatchTimeout(user_id=user_id))
                self._bus.publish(Event(name=EventNames.MATCH_TIMED_OUT, payload={"user_id": user_id}))
        return timed_out
