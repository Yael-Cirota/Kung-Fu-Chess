from protocol.errors import ProtocolError


class TestProtocolError:
    def test_carries_the_reason(self):
        error = ProtocolError(ProtocolError.UNKNOWN_TYPE)
        assert error.reason == ProtocolError.UNKNOWN_TYPE
        assert str(error) == ProtocolError.UNKNOWN_TYPE

    def test_is_an_exception(self):
        assert isinstance(ProtocolError(ProtocolError.MALFORMED_JSON), Exception)
