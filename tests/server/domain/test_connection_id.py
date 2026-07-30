from server.domain.connection_id import ConnectionId


def test_wraps_a_string_value():
    assert ConnectionId("conn-1").value == "conn-1"


def test_equal_values_compare_equal():
    assert ConnectionId("conn-1") == ConnectionId("conn-1")
