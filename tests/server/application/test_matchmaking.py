from common.events import Event, EventNames, InMemoryEventBus
from server.application.matchmaking import Match, MatchmakingService, MatchTicket, MatchTimeout


def ticket(user_id, elo, username="p"):
    return MatchTicket(user_id=user_id, username=f"{username}{user_id}", elo=elo)


class TestEnqueueWithNoMatch:
    def test_first_ticket_in_the_window_returns_none(self):
        service = MatchmakingService(InMemoryEventBus())
        assert service.enqueue(ticket(1, 1200), now_ms=0) is None


class TestEnqueueMatchesWithinEloWindow:
    def test_two_tickets_within_the_window_match(self):
        bus = InMemoryEventBus()
        service = MatchmakingService(bus, elo_window=100)

        assert service.enqueue(ticket(1, 1200), now_ms=0) is None
        match = service.enqueue(ticket(2, 1250), now_ms=100)

        assert isinstance(match, Match)
        assert {match.white.user_id, match.black.user_id} == {1, 2}

    def test_lower_elo_is_assigned_white(self):
        service = MatchmakingService(InMemoryEventBus(), elo_window=100)
        service.enqueue(ticket(1, 1250), now_ms=0)
        match = service.enqueue(ticket(2, 1200), now_ms=0)

        assert match.white.user_id == 2
        assert match.black.user_id == 1

    def test_match_found_is_published_on_the_bus(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe(EventNames.MATCH_FOUND, received.append)
        service = MatchmakingService(bus, elo_window=100)

        service.enqueue(ticket(1, 1200), now_ms=0)
        service.enqueue(ticket(2, 1200), now_ms=0)

        assert len(received) == 1
        assert received[0].payload["match"].white.user_id in (1, 2)

    def test_tickets_outside_the_window_do_not_match(self):
        service = MatchmakingService(InMemoryEventBus(), elo_window=50)
        service.enqueue(ticket(1, 1000), now_ms=0)
        match = service.enqueue(ticket(2, 1200), now_ms=0)

        assert match is None

    def test_matched_tickets_are_removed_from_the_queue(self):
        bus = InMemoryEventBus()
        service = MatchmakingService(bus, elo_window=100)
        service.enqueue(ticket(1, 1200), now_ms=0)
        service.enqueue(ticket(2, 1200), now_ms=0)

        # Neither original ticket should still be queued to time out.
        assert service.tick(now_ms=1_000_000) == []


class TestEnqueueNeverMatchesAUserWithThemselves:
    def test_re_enqueueing_a_queued_user_does_not_self_match(self):
        service = MatchmakingService(InMemoryEventBus(), elo_window=100)
        service.enqueue(ticket(1, 1200), now_ms=0)

        assert service.enqueue(ticket(1, 1200), now_ms=100) is None

    def test_a_self_match_is_not_published_on_the_bus(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe(EventNames.MATCH_FOUND, received.append)
        service = MatchmakingService(bus, elo_window=100)

        service.enqueue(ticket(1, 1200), now_ms=0)
        service.enqueue(ticket(1, 1200), now_ms=100)

        assert received == []

    def test_a_skipped_self_still_matches_a_real_opponent(self):
        service = MatchmakingService(InMemoryEventBus(), elo_window=100)
        service.enqueue(ticket(1, 1200), now_ms=0)
        service.enqueue(ticket(2, 1200), now_ms=0)

        # User 1 was matched away; only user 2's re-entry remains unmatched.
        assert service.enqueue(ticket(2, 1200), now_ms=100) is None


class TestEnqueuePrefersTheLongestWaitingOpponent:
    def test_the_oldest_ticket_in_the_window_wins_over_the_closer_elo(self):
        service = MatchmakingService(InMemoryEventBus(), elo_window=100)
        # 150 apart, so these two do not match each other and both stay queued.
        service.enqueue(ticket(1, 1500), now_ms=0)
        service.enqueue(ticket(2, 1650), now_ms=100)

        # Both are inside the window of 1590; FIFO must pick 1, not the nearer 2.
        match = service.enqueue(ticket(3, 1590), now_ms=200)

        assert {match.white.user_id, match.black.user_id} == {1, 3}


class TestCancel:
    def test_cancelled_ticket_never_matches(self):
        service = MatchmakingService(InMemoryEventBus(), elo_window=100)
        service.enqueue(ticket(1, 1200), now_ms=0)
        service.cancel(1)

        match = service.enqueue(ticket(2, 1200), now_ms=0)
        assert match is None

    def test_cancelling_an_unqueued_user_is_a_no_op(self):
        service = MatchmakingService(InMemoryEventBus())
        service.cancel(999)  # must not raise


class TestTickTimeouts:
    def test_ticket_younger_than_timeout_is_not_timed_out(self):
        service = MatchmakingService(InMemoryEventBus(), timeout_ms=60000)
        service.enqueue(ticket(1, 1200), now_ms=0)

        assert service.tick(now_ms=59999) == []

    def test_ticket_at_the_timeout_boundary_times_out(self):
        service = MatchmakingService(InMemoryEventBus(), timeout_ms=60000)
        service.enqueue(ticket(1, 1200), now_ms=0)

        assert service.tick(now_ms=60000) == [MatchTimeout(user_id=1)]

    def test_match_timed_out_is_published_on_the_bus(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe(EventNames.MATCH_TIMED_OUT, received.append)
        service = MatchmakingService(bus, timeout_ms=60000)
        service.enqueue(ticket(1, 1200), now_ms=0)

        service.tick(now_ms=60000)

        assert len(received) == 1
        assert received[0].payload["user_id"] == 1

    def test_timed_out_ticket_is_removed_from_the_queue(self):
        service = MatchmakingService(InMemoryEventBus(), timeout_ms=60000)
        service.enqueue(ticket(1, 1200), now_ms=0)
        service.tick(now_ms=60000)

        assert service.tick(now_ms=120000) == []
