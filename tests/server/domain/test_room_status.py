from server.domain.room_status import RoomStatus


def test_has_the_three_lifecycle_values():
    assert {s.value for s in RoomStatus} == {"waiting", "running", "ended"}
