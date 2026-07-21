from common.events import Event, EventNames, InMemoryEventBus
from kfchess.api import EngineEvent, EngineEventKind
from server.application.elo import EloCalculator
from server.application.rating_updater import RatingUpdater
from server.infrastructure.repositories import UserRecord

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
        self.records.append(
            {
                "white_id": white_id,
                "black_id": black_id,
                "winner_id": winner_id,
                "ended_at_ms": ended_at_ms,
                "reason": reason,
            }
        )


class FakeSession:
    def __init__(self, clock_ms=5000):
        self.clock_ms = clock_ms


class FakeRoom:
    def __init__(self, user_ids=None, clock_ms=5000):
        self._user_ids = {"white": WHITE_ID, "black": BLACK_ID} if user_ids is None else user_ids
        self.session = FakeSession(clock_ms)

    def player_user_ids(self):
        return dict(self._user_ids)


def make_updater(room=None, elos=None, k_factor=32):
    rooms = {} if room is None else {"room-1": room}
    users = FakeUserRepository(elos if elos is not None else {WHITE_ID: 1200, BLACK_ID: 1200})
    game_records = FakeGameRecordRepository()
    bus = InMemoryEventBus()
    updater = RatingUpdater(bus, rooms, users, game_records, EloCalculator(k_factor=k_factor))
    return bus, users, game_records, updater


def resign_event(resigned_color="white", room_id="room-1"):
    return Event(
        name=EventNames.GAME_OVER,
        payload={"room_id": room_id, "reason": "disconnect", "resigned_color": resigned_color},
    )


def engine_over_event(winner="white", room_id="room-1", at_ms=7000):
    engine_event = EngineEvent(
        kind=EngineEventKind.GAME_OVER,
        at_ms=at_ms,
        piece=None,
        from_pos=None,
        to_pos=None,
        captured=None,
        beneficiary_color=winner,
    )
    return Event(name=EventNames.GAME_OVER, payload={"room_id": room_id, "engine_event": engine_event})


class TestSubscription:
    def test_constructing_it_is_enough_to_settle_a_game_over(self):
        bus, _users, records, _u = make_updater(FakeRoom())

        # nobody holds a reference to the updater; it subscribed on construction
        bus.publish(resign_event())

        assert len(records.records) == 1

    def test_only_game_over_settles_a_game(self):
        bus, _users, records, _u = make_updater(FakeRoom())

        bus.publish(Event(name=EventNames.PIECE_CAPTURED, payload={"room_id": "room-1"}))

        assert records.records == []


class TestForcedResignIsRated:
    def test_the_disconnected_player_loses_elo_and_the_opponent_gains(self):
        bus, users, _records, _u = make_updater(FakeRoom())

        bus.publish(resign_event(resigned_color="white"))

        # equal ratings, K=32 -> winner +16, loser -16
        assert users.updates == [(BLACK_ID, 1216), (WHITE_ID, 1184)]

    def test_black_disconnecting_makes_white_the_winner(self):
        bus, users, _records, _u = make_updater(FakeRoom())

        bus.publish(resign_event(resigned_color="black"))

        assert users.updates == [(WHITE_ID, 1216), (BLACK_ID, 1184)]

    def test_records_the_game_with_the_disconnect_reason(self):
        bus, _users, records, _u = make_updater(FakeRoom(clock_ms=4321))

        bus.publish(resign_event(resigned_color="white"))

        assert records.records == [
            {
                "white_id": WHITE_ID,
                "black_id": BLACK_ID,
                "winner_id": BLACK_ID,
                "ended_at_ms": 4321,
                "reason": "disconnect",
            }
        ]

    def test_rating_change_reflects_the_gap_between_players(self):
        bus, users, _records, _u = make_updater(FakeRoom(), elos={WHITE_ID: 1600, BLACK_ID: 1200})

        bus.publish(resign_event(resigned_color="black"))

        # the heavy favourite winning gains little
        winner_update = dict(users.updates)[WHITE_ID]
        assert winner_update - 1600 < 16


class TestEngineGameOverIsRated:
    def test_king_capture_rates_the_beneficiary_as_winner(self):
        bus, users, records, _u = make_updater(FakeRoom())

        bus.publish(engine_over_event(winner="black"))

        assert users.updates == [(BLACK_ID, 1216), (WHITE_ID, 1184)]
        assert records.records[0]["reason"] == "king_captured"

    def test_uses_the_engine_event_timestamp(self):
        bus, _users, records, _u = make_updater(FakeRoom(clock_ms=1))

        bus.publish(engine_over_event(at_ms=9999))

        assert records.records[0]["ended_at_ms"] == 9999

    def test_a_game_over_without_a_winner_is_recorded_but_unrated(self):
        bus, users, records, _u = make_updater(FakeRoom())

        bus.publish(engine_over_event(winner=None))

        assert users.updates == []
        assert records.records[0]["winner_id"] is None


class TestSettlementIsIdempotent:
    def test_a_room_is_settled_only_once(self):
        bus, users, records, _u = make_updater(FakeRoom())

        bus.publish(resign_event(resigned_color="white"))
        bus.publish(engine_over_event(winner="black"))

        assert len(users.updates) == 2  # one pair, not two
        assert len(records.records) == 1

    def test_different_rooms_settle_independently(self):
        room_a, room_b = FakeRoom(), FakeRoom()
        users = FakeUserRepository({WHITE_ID: 1200, BLACK_ID: 1200})
        records = FakeGameRecordRepository()
        bus = InMemoryEventBus()
        RatingUpdater(bus, {"a": room_a, "b": room_b}, users, records, EloCalculator())

        bus.publish(resign_event(room_id="a"))
        bus.publish(resign_event(room_id="b"))

        assert len(records.records) == 2


class TestUnratedSituations:
    def test_an_unknown_room_is_ignored(self):
        bus, users, records, _u = make_updater(FakeRoom())

        bus.publish(resign_event(room_id="no-such-room"))

        assert users.updates == []
        assert records.records == []

    def test_a_room_missing_a_seated_player_is_not_settled(self):
        bus, users, records, _u = make_updater(FakeRoom(user_ids={"white": WHITE_ID}))

        bus.publish(resign_event(resigned_color="white"))

        assert users.updates == []
        assert records.records == []

    def test_a_missing_user_record_skips_the_elo_write_but_still_records(self):
        bus, users, records, _u = make_updater(FakeRoom(), elos={WHITE_ID: 1200})

        bus.publish(resign_event(resigned_color="white"))

        assert users.updates == []
        assert records.records[0]["winner_id"] == BLACK_ID

    def test_an_unrecognised_resigned_color_leaves_the_game_unrated(self):
        bus, users, records, _u = make_updater(FakeRoom())

        bus.publish(
            Event(name=EventNames.GAME_OVER, payload={"room_id": "room-1", "resigned_color": "green"})
        )

        assert users.updates == []
        assert records.records[0]["winner_id"] is None
