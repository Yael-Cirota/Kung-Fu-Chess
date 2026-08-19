from server.application.allocator import Allocator, ServerLoad


class TestNoCandidates:
    def test_returns_none(self):
        assert Allocator().choose_server("room-1", []) is None


class TestSingleCandidate:
    def test_is_always_chosen(self):
        assert Allocator().choose_server("room-1", [ServerLoad("s1", room_count=0)]) == "s1"


class TestDeterminism:
    def test_the_same_room_id_always_maps_to_the_same_candidate(self):
        allocator = Allocator()
        candidates = [ServerLoad(f"s{i}", room_count=0) for i in range(5)]

        first = allocator.choose_server("room-42", candidates)
        second = allocator.choose_server("room-42", candidates)

        assert first == second

    def test_different_room_ids_can_map_to_different_candidates(self):
        # Not a strict requirement of any single call, but a hash ring that
        # always picked the same candidate regardless of key would defeat the
        # entire point of consistent hashing.
        allocator = Allocator()
        candidates = [ServerLoad(f"s{i}", room_count=0) for i in range(5)]

        chosen = {allocator.choose_server(f"room-{i}", candidates) for i in range(50)}

        assert len(chosen) > 1


class TestBoundedLoad:
    def test_a_candidate_far_above_the_average_load_is_never_chosen(self):
        allocator = Allocator()
        overloaded = ServerLoad("hot", room_count=1000)
        cool = [ServerLoad(f"s{i}", room_count=0) for i in range(20)]
        candidates = [overloaded, *cool]

        chosen = {allocator.choose_server(f"room-{i}", candidates) for i in range(200)}

        assert "hot" not in chosen

    def test_evenly_loaded_candidates_are_all_eligible(self):
        # Every candidate sits exactly at the average, so none is excluded by
        # the cap - pure hash-ring selection should spread choices across
        # more than one of them.
        allocator = Allocator()
        candidates = [ServerLoad(f"s{i}", room_count=10) for i in range(5)]

        chosen = {allocator.choose_server(f"room-{i}", candidates) for i in range(50)}

        assert chosen <= {c.server_id for c in candidates}
        assert len(chosen) > 1


class TestFleetScaling:
    def test_adding_one_more_candidate_reshuffles_only_a_minority_of_placements(self):
        allocator = Allocator()
        before = [ServerLoad(f"s{i}", room_count=0) for i in range(4)]
        after = before + [ServerLoad("s4", room_count=0)]
        room_ids = [f"room-{i}" for i in range(300)]

        placements_before = {r: allocator.choose_server(r, before) for r in room_ids}
        placements_after = {r: allocator.choose_server(r, after) for r in room_ids}

        changed = sum(1 for r in room_ids if placements_before[r] != placements_after[r])
        assert changed / len(room_ids) < 0.5
