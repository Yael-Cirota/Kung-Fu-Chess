from server.application.allocator import Allocator, ServerLoad
from server.roles.allocator import build_allocator


class TestBuildAllocator:
    def test_returns_a_working_allocator(self):
        allocator = build_allocator()

        assert isinstance(allocator, Allocator)
        assert allocator.choose_server("room-1", [ServerLoad("s1", room_count=0)]) == "s1"
