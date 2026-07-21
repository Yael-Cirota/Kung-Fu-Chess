from server.application.room_service import (
    PlayerRef, RoomErrorReason, RoomIdGenerator, RoomService, SecretsRoomIdGenerator,
    SequentialRoomIdGenerator,
)


def player(user_id, username="p"):
    return PlayerRef(user_id=user_id, username=f"{username}{user_id}")


class TestCreate:
    def test_creates_a_room_with_the_host_as_the_first_player(self):
        service = RoomService(SequentialRoomIdGenerator())
        room = service.create(player(1))

        assert room.room_id == "room-1"
        assert room.players == [player(1)]

    def test_ids_are_generated_sequentially(self):
        service = RoomService(SequentialRoomIdGenerator())
        first = service.create(player(1))
        second = service.create(player(2))
        assert first.room_id != second.room_id


class TestJoin:
    def test_second_player_is_assigned_black(self):
        service = RoomService(SequentialRoomIdGenerator())
        room = service.create(player(1))

        result = service.join(room.room_id, player(2))

        assert result.ok is True
        assert result.value.role == "black"

    def test_first_player_role_via_role_for_index(self):
        service = RoomService(SequentialRoomIdGenerator())
        room = service.create(player(1))
        assert room.role_for_index(0) == "white"

    def test_third_and_later_players_are_viewers(self):
        service = RoomService(SequentialRoomIdGenerator())
        room = service.create(player(1))
        service.join(room.room_id, player(2))

        result = service.join(room.room_id, player(3))

        assert result.value.role == "viewer"

    def test_joining_an_unknown_room_fails(self):
        service = RoomService(SequentialRoomIdGenerator())
        result = service.join("no-such-room", player(1))

        assert result.ok is False
        assert result.error == RoomErrorReason.ROOM_NOT_FOUND

    def test_joining_a_full_room_fails(self):
        service = RoomService(SequentialRoomIdGenerator(), max_viewers=1)
        room = service.create(player(1))
        service.join(room.room_id, player(2))
        service.join(room.room_id, player(3))  # the one allowed viewer

        result = service.join(room.room_id, player(4))

        assert result.ok is False
        assert result.error == RoomErrorReason.ROOM_FULL


class TestCancel:
    def test_removes_the_player_from_the_room(self):
        service = RoomService(SequentialRoomIdGenerator())
        room = service.create(player(1))
        service.join(room.room_id, player(2))

        service.cancel(room.room_id, 2)

        assert [p.user_id for p in service.get(room.room_id).players] == [1]

    def test_removing_the_last_player_deletes_the_room(self):
        service = RoomService(SequentialRoomIdGenerator())
        room = service.create(player(1))
        service.cancel(room.room_id, 1)

        assert service.get(room.room_id) is None

    def test_cancelling_in_an_unknown_room_is_a_no_op(self):
        service = RoomService(SequentialRoomIdGenerator())
        service.cancel("ghost-room", 1)  # must not raise


class TestGet:
    def test_returns_none_for_unknown_room(self):
        service = RoomService(SequentialRoomIdGenerator())
        assert service.get("ghost") is None


class TestSequentialRoomIdGenerator:
    def test_satisfies_the_protocol(self):
        assert isinstance(SequentialRoomIdGenerator(), RoomIdGenerator)


class TestSecretsRoomIdGenerator:
    def test_satisfies_the_protocol(self):
        assert isinstance(SecretsRoomIdGenerator(), RoomIdGenerator)

    def test_honors_the_configured_length(self):
        for length in (4, 6, 7, 12):
            assert len(SecretsRoomIdGenerator(length).next_id()) == length

    def test_ids_are_hex_and_distinct(self):
        generator = SecretsRoomIdGenerator(6)
        ids = {generator.next_id() for _ in range(200)}

        assert len(ids) > 190  # unguessable, so collisions are vanishingly rare
        assert all(set(room_id) <= set("0123456789abcdef") for room_id in ids)

    def test_works_as_the_generator_behind_a_room_service(self):
        service = RoomService(SecretsRoomIdGenerator(6))
        room = service.create(player(1))

        assert service.get(room.room_id) is room
