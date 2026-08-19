"""The room directory: `room_id -> owning server` from Server_Design.md §2, with
the lease-epoch fencing from §8. A room-server does not decide whether it still
owns a room by trusting its own memory - it asks the directory, whose answer is
authoritative. `claim` mints a new epoch (or increments the stored one, modeling
a reclaim after the previous owner's lease lapsed); `renew` is how the owner
proves it is still alive, and fails the instant the epoch it holds is no longer
current - the definitive "you lost ownership" signal §8 depends on. Mirrors
`client_session.py`'s Protocol + in-memory-registry shape."""

from dataclasses import dataclass
from typing import Dict, Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class RoomLease:
    room_id: str
    server_id: str
    lease_epoch: int


@runtime_checkable
class RoomDirectory(Protocol):
    async def claim(self, room_id: str, server_id: str) -> RoomLease: ...

    async def renew(self, room_id: str, server_id: str, lease_epoch: int) -> bool: ...

    async def resolve(self, room_id: str) -> Optional[RoomLease]: ...

    async def release(self, room_id: str, server_id: str, lease_epoch: int) -> None: ...


class InMemoryRoomDirectory:
    """The single-process directory: used directly by the monolith (one
    server_id, claims never contend) and as the fake in tests for anything
    built against `RoomDirectory`. Has no real TTL - there is no wall clock to
    expire against in-process - so a "reclaim after the previous owner's lease
    lapsed" is modeled by calling `claim` again for the same room_id, which
    always mints the next epoch and immediately fences out the prior owner's
    epoch on their next `renew`."""

    def __init__(self):
        self._leases: Dict[str, RoomLease] = {}

    async def claim(self, room_id: str, server_id: str) -> RoomLease:
        existing = self._leases.get(room_id)
        next_epoch = existing.lease_epoch + 1 if existing is not None else 1
        lease = RoomLease(room_id=room_id, server_id=server_id, lease_epoch=next_epoch)
        self._leases[room_id] = lease
        return lease

    async def renew(self, room_id: str, server_id: str, lease_epoch: int) -> bool:
        current = self._leases.get(room_id)
        return current is not None and current.server_id == server_id and current.lease_epoch == lease_epoch

    async def resolve(self, room_id: str) -> Optional[RoomLease]:
        return self._leases.get(room_id)

    async def release(self, room_id: str, server_id: str, lease_epoch: int) -> None:
        current = self._leases.get(room_id)
        if current is not None and current.server_id == server_id and current.lease_epoch == lease_epoch:
            del self._leases[room_id]
