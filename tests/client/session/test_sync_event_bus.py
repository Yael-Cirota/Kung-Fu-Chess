from common.events import Event
from client.session.sync_event_bus import SyncEventBus


def recorder(sink):
    def handler(event):
        sink.append(event)
    return handler


class TestPublishSubscribe:
    def test_a_subscribed_handler_receives_the_event(self):
        bus = SyncEventBus()
        received = []
        bus.subscribe("FOO", recorder(received))

        event = Event(name="FOO", payload={"x": 1})
        bus.publish(event)

        assert received == [event]

    def test_publish_is_synchronous_not_a_coroutine(self):
        bus = SyncEventBus()
        result = bus.publish(Event(name="FOO", payload={}))
        assert result is None  # no await needed, no coroutine object returned

    def test_unrelated_event_names_are_not_delivered(self):
        bus = SyncEventBus()
        received = []
        bus.subscribe("FOO", recorder(received))

        bus.publish(Event(name="BAR", payload={}))

        assert received == []

    def test_unsubscribe_stops_delivery(self):
        bus = SyncEventBus()
        received = []
        handler = recorder(received)
        bus.subscribe("FOO", handler)
        bus.unsubscribe("FOO", handler)

        bus.publish(Event(name="FOO", payload={}))

        assert received == []

    def test_unsubscribing_an_unknown_handler_is_a_no_op(self):
        bus = SyncEventBus()
        bus.unsubscribe("FOO", recorder([]))  # must not raise

    def test_a_bad_handler_does_not_stop_the_next_ones(self):
        bus = SyncEventBus()
        received = []

        def bad_handler(event):
            raise ValueError("boom")

        bus.subscribe("FOO", bad_handler)
        bus.subscribe("FOO", recorder(received))

        bus.publish(Event(name="FOO", payload={}))

        assert received == [Event(name="FOO", payload={})]
