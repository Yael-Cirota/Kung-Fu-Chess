import logging

from common.events import Event, EventNames, InMemoryEventBus
from server.application.activity_log import ActivityLog


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def make_logger():
    logger = logging.getLogger("test.activity_log")
    logger.handlers.clear()
    logger.setLevel("INFO")
    logger.propagate = False
    handler = ListHandler()
    logger.addHandler(handler)
    return logger, handler


class TestSubscription:
    def test_subscribes_to_every_documented_event_name(self):
        bus = InMemoryEventBus()
        logger, handler = make_logger()
        ActivityLog(bus, logger)

        for name in (
            EventNames.MOVE_LOGGED, EventNames.PIECE_CAPTURED, EventNames.GAME_STARTED,
            EventNames.GAME_OVER, EventNames.PLAYER_DISCONNECTED, EventNames.PLAYER_RECONNECTED,
        ):
            bus.publish(Event(name=name, payload={"room_id": "r1"}))

        assert len(handler.records) == 6

    def test_unrelated_events_are_not_logged(self):
        bus = InMemoryEventBus()
        logger, handler = make_logger()
        ActivityLog(bus, logger)

        bus.publish(Event(name=EventNames.SCORE_CHANGED, payload={}))

        assert handler.records == []


class TestLogLineContent:
    def test_carries_trace_id_room_id_layer_and_at_ms(self):
        bus = InMemoryEventBus()
        logger, handler = make_logger()
        ActivityLog(bus, logger)

        bus.publish(Event(
            name=EventNames.PIECE_CAPTURED,
            payload={"room_id": "room-1", "at_ms": 4200},
            trace_id="trace-9",
        ))

        record = handler.records[0]
        assert record.trace_id == "trace-9"
        assert record.room_id == "room-1"
        assert record.layer == "domain"
        assert record.at_ms == 4200
        assert record.getMessage() == EventNames.PIECE_CAPTURED

    def test_missing_optional_payload_keys_default_to_none(self):
        bus = InMemoryEventBus()
        logger, handler = make_logger()
        ActivityLog(bus, logger)

        bus.publish(Event(name=EventNames.GAME_OVER, payload={}))

        record = handler.records[0]
        assert record.room_id is None
        assert record.at_ms is None
        assert record.trace_id is None
