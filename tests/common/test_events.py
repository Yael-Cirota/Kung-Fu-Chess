from common.events import Event, EventBus, EventNames, InMemoryEventBus


class TestEventTraceIdRoundTrip:
    def test_trace_id_round_trips_through_publish_subscribe(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe(EventNames.MOVE_LOGGED, received.append)

        event = Event(name=EventNames.MOVE_LOGGED, payload={"foo": "bar"}, trace_id="trace-1")
        bus.publish(event)

        assert len(received) == 1
        assert received[0].trace_id == "trace-1"
        assert received[0].payload == {"foo": "bar"}

    def test_trace_id_defaults_to_none(self):
        event = Event(name=EventNames.GAME_OVER, payload={})
        assert event.trace_id is None


class TestInMemoryEventBusFanOut:
    def test_multiple_subscribers_all_receive_the_event(self):
        bus = InMemoryEventBus()
        calls = []
        bus.subscribe(EventNames.GAME_OVER, lambda e: calls.append("a"))
        bus.subscribe(EventNames.GAME_OVER, lambda e: calls.append("b"))

        bus.publish(Event(name=EventNames.GAME_OVER, payload={}))

        assert calls == ["a", "b"]

    def test_publish_with_no_subscribers_is_a_no_op(self):
        bus = InMemoryEventBus()
        bus.publish(Event(name=EventNames.GAME_OVER, payload={}))  # must not raise

    def test_unsubscribe_stops_delivery(self):
        bus = InMemoryEventBus()
        calls = []
        handler = calls.append
        bus.subscribe(EventNames.GAME_OVER, handler)
        bus.unsubscribe(EventNames.GAME_OVER, handler)

        bus.publish(Event(name=EventNames.GAME_OVER, payload={}))

        assert calls == []

    def test_unsubscribe_unknown_handler_is_a_no_op(self):
        bus = InMemoryEventBus()
        bus.unsubscribe(EventNames.GAME_OVER, lambda e: None)  # must not raise

    def test_one_bad_subscriber_does_not_stop_the_others(self):
        bus = InMemoryEventBus()
        calls = []

        def bad_handler(event):
            raise RuntimeError("boom")

        bus.subscribe(EventNames.GAME_OVER, bad_handler)
        bus.subscribe(EventNames.GAME_OVER, lambda e: calls.append("survived"))

        bus.publish(Event(name=EventNames.GAME_OVER, payload={}))

        assert calls == ["survived"]

    def test_satisfies_event_bus_protocol(self):
        assert isinstance(InMemoryEventBus(), EventBus)
