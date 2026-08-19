"""Server_Design.md §2: the Game Allocator role. `Allocator` (see
server/application/allocator.py) is already stateless and config-free - it
takes candidates and a room_id per call, nothing at construction time - so
there is no meaningful object graph to assemble here beyond the instance
itself.

No `if __name__ == "__main__":` yet: the Allocator is called synchronously,
per room creation, by whichever process is placing a room. Exposing it to
other processes needs an RPC surface (gRPC, or an internal HTTP endpoint)
that doesn't exist in this codebase - building one is its own piece of work,
not implied by having the allocation logic itself. Until that surface exists,
`build_allocator` is what a future RPC handler would construct and call into."""

from server.application.allocator import Allocator


def build_allocator() -> Allocator:
    return Allocator()
