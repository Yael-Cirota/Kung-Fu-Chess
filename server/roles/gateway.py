"""Server_Design.md §2, ADR-001: the gateway role. Not built this pass.

`MessageDispatcher` (server/presentation/dispatcher.py) reaches a room by
calling methods directly on a live `GameRoom` object pulled out of an
in-process `rooms` dict - `self._rooms[...].enqueue_move(...)`,
`.assign_seat(...)`, `room.status`. Every one of those calls assumes the
room-server is the same process as the gateway. ADR-001 already decided a
real gateway reaches a room-server through a relayed connection instead
(gateway <-> room-server, keyed on `(room_id, lease_epoch)` so a stale
relayed connection is rejected the instant a lease changes hands, §8) - but
that relay is a real persistent transport between two live OS processes, and
building it with no second process to relay to would be exactly the kind of
unexercised code this pass has deliberately avoided elsewhere (see
`server/roles/room.py`, `server/roles/matchmaker.py`).

Building the relay is the next design pass, once `server/roles/room.py`'s
`RoomServer` has somewhere to be reached from. `build_gateway` raises rather
than silently returning an incomplete object graph, so a caller finds out
immediately rather than discovering it at the first relayed move."""


def build_gateway(*args, **kwargs):
    raise NotImplementedError(
        "server.roles.gateway is not implemented yet - it depends on the ADR-001 "
        "gateway<->room-server relay (Server_Design.md §2), which this pass did not build. "
        "See this module's docstring."
    )
