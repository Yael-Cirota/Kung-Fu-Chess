"""Server_Design.md §2: the Game Allocator recommends which room-server
should claim a new room - it does not claim on its own behalf (the chosen
room-server performs the actual `directory.claim`, see §2's "Room placement &
directory"). Stateless and pure: no I/O, no Redis dependency of its own - the
caller supplies the load signal, since collecting fleet-wide heartbeats is its
own piece of infrastructure this pass does not build.

Consistent hashing over live room-servers means scaling the fleet reshuffles
only a minimal slice of future placements. On top of that, a candidate whose
`room_count` is more than 25% above the fleet average is excluded before the
hash ranking runs, so one hash-unlucky server doesn't become a hotspot just
because it is the nearest ring point for a run of room_ids - a tempered form
of "consistent hashing with bounded loads". The unweighted candidate closest
to the minimum load is always within the cap, so this never has to fall back
to "no acceptable candidate"."""

import hashlib
from dataclasses import dataclass
from typing import Optional, Sequence

_CAPACITY_FACTOR = 1.25
_RING_MODULUS = 1 << 128  # md5 digests are 128 bits


@dataclass(frozen=True)
class ServerLoad:
    server_id: str
    room_count: int


class Allocator:
    def choose_server(self, room_id: str, candidates: Sequence[ServerLoad]) -> Optional[str]:
        if not candidates:
            return None

        cap = (sum(c.room_count for c in candidates) / len(candidates)) * _CAPACITY_FACTOR
        acceptable = [c for c in candidates if c.room_count <= cap]
        nearest = min(acceptable, key=lambda c: _ring_distance(room_id, c.server_id))
        return nearest.server_id


def _ring_distance(room_id: str, server_id: str) -> int:
    return (_ring_position(server_id) - _ring_position(room_id)) % _RING_MODULUS


def _ring_position(key: str) -> int:
    return int(hashlib.md5(key.encode(), usedforsecurity=False).hexdigest(), 16)
