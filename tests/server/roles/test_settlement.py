import asyncio
from dataclasses import replace

from common.config.schema import AppConfig
from common.events import Event, EventNames, InMemoryEventBus
from server.infrastructure.repositories import UserRecord
from server.roles.settlement import build_settlement

WHITE_ID = 11
BLACK_ID = 22


class FakeUserRepository:
    def __init__(self, elos):
        self._records = {
            user_id: UserRecord(user_id=user_id, username=f"u{user_id}", password_hash="h", salt="s", elo=elo)
            for user_id, elo in elos.items()
        }
        self.updates = []

    def find_by_username(self, username):  # pragma: no cover - unused by RatingUpdater
        return None

    def find_by_id(self, user_id):
        return self._records.get(user_id)

    def create(self, username, password_hash, salt, elo):  # pragma: no cover - unused
        raise NotImplementedError

    def update_elo(self, user_id, elo):
        self.updates.append((user_id, elo))


class FakeGameRecordRepository:
    def __init__(self):
        self.records = []

    def record_result(self, white_id, black_id, winner_id, ended_at_ms, reason):
        self.records.append((white_id, black_id, winner_id, ended_at_ms, reason))


def game_over_event(resigned_color="white"):
    return Event(
        name=EventNames.GAME_OVER,
        payload={
            "room_id": "room-1",
            "reason": "disconnect",
            "resigned_color": resigned_color,
            "white_id": WHITE_ID,
            "black_id": BLACK_ID,
            "ended_at_ms": 5000,
        },
    )


class TestBuildSettlement:
    def test_settles_a_game_over_from_the_bus(self):
        bus = InMemoryEventBus()
        users = FakeUserRepository({WHITE_ID: 1200, BLACK_ID: 1200})
        game_records = FakeGameRecordRepository()

        build_settlement(AppConfig(), bus, users, game_records)
        asyncio.run(bus.publish(game_over_event(resigned_color="white")))

        assert users.updates == [(BLACK_ID, 1216), (WHITE_ID, 1184)]
        assert len(game_records.records) == 1

    def test_uses_the_configured_k_factor(self):
        config = AppConfig()
        config = replace(config, matchmaking=replace(config.matchmaking, k_factor=1))
        bus = InMemoryEventBus()
        users = FakeUserRepository({WHITE_ID: 1200, BLACK_ID: 1200})
        game_records = FakeGameRecordRepository()

        build_settlement(config, bus, users, game_records)
        asyncio.run(bus.publish(game_over_event(resigned_color="white")))

        # K=1 -> +/-0.5 rounds to a 1-point swing instead of K=32's 16
        winner_update = dict(users.updates)[BLACK_ID]
        assert abs(winner_update - 1200) <= 1
