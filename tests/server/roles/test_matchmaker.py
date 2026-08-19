import asyncio
from dataclasses import replace

from common.config.schema import AppConfig
from common.events import InMemoryEventBus
from server.application.matchmaking import MatchTicket
from server.roles.matchmaker import build_matchmaker


class TestBuildMatchmaker:
    def test_returns_a_working_matchmaking_service(self):
        matchmaker = build_matchmaker(AppConfig(), InMemoryEventBus())

        result = asyncio.run(matchmaker.enqueue(MatchTicket(user_id=1, username="a", elo=1200), now_ms=0))

        assert result is None  # nobody else queued yet

    def test_uses_the_configured_elo_window_and_timeout(self):
        config = AppConfig()
        config = replace(config, matchmaking=replace(config.matchmaking, elo_window=1, timeout_ms=500))
        matchmaker = build_matchmaker(config, InMemoryEventBus())

        asyncio.run(matchmaker.enqueue(MatchTicket(user_id=1, username="a", elo=1200), now_ms=0))
        # a 500-elo gap is well outside elo_window=1, so no match forms
        match = asyncio.run(matchmaker.enqueue(MatchTicket(user_id=2, username="b", elo=1700), now_ms=0))

        assert match is None
