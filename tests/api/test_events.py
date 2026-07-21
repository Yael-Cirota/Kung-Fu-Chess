from kfchess.api.events import EngineEvent, EngineEventKind, EngineEventSink
from kfchess.api.dto import Position


class FakeSink:
    def __init__(self):
        self.emitted = []

    def emit(self, event: EngineEvent) -> None:
        self.emitted.append(event)


class TestEngineEventSinkProtocol:
    def test_a_class_with_emit_satisfies_the_protocol(self):
        assert isinstance(FakeSink(), EngineEventSink)

    def test_a_class_without_emit_does_not_satisfy_the_protocol(self):
        class NotASink:
            pass

        assert isinstance(NotASink(), EngineEventSink) is False


class TestEngineEvent:
    def test_holds_the_given_fields(self):
        event = EngineEvent(
            kind=EngineEventKind.MOVE_EXECUTED,
            at_ms=1000,
            piece=None,
            from_pos=Position(0, 0),
            to_pos=Position(0, 1),
            captured=None,
            beneficiary_color=None,
        )
        assert event.kind is EngineEventKind.MOVE_EXECUTED
        assert event.at_ms == 1000
        assert event.from_pos == Position(0, 0)
        assert event.to_pos == Position(0, 1)
