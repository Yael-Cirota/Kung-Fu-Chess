import asyncio

from common.events import Event, EventBus, EventNames, InMemoryEventBus


def recorder(sink, label=None):
    """An async handler that appends the event (or `label`) to `sink`. The bus
    awaits handlers, so a plain `list.append` is no longer a valid subscriber."""

    async def handler(event):
        sink.append(event if label is None else label)

    return handler


class TestEventTraceIdRoundTrip:
    def test_trace_id_round_trips_through_publish_subscribe(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe(EventNames.MOVE_LOGGED, recorder(received))

        event = Event(name=EventNames.MOVE_LOGGED, payload={"foo": "bar"}, trace_id="trace-1")
        asyncio.run(bus.publish(event))

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
        bus.subscribe(EventNames.GAME_OVER, recorder(calls, "a"))
        bus.subscribe(EventNames.GAME_OVER, recorder(calls, "b"))

        asyncio.run(bus.publish(Event(name=EventNames.GAME_OVER, payload={})))

        assert calls == ["a", "b"]

    def test_publish_with_no_subscribers_is_a_no_op(self):
        bus = InMemoryEventBus()
        asyncio.run(bus.publish(Event(name=EventNames.GAME_OVER, payload={})))  # must not raise

    def test_unsubscribe_stops_delivery(self):
        bus = InMemoryEventBus()
        calls = []
        handler = recorder(calls)
        bus.subscribe(EventNames.GAME_OVER, handler)
        bus.unsubscribe(EventNames.GAME_OVER, handler)

        asyncio.run(bus.publish(Event(name=EventNames.GAME_OVER, payload={})))

        assert calls == []

    def test_unsubscribe_unknown_handler_is_a_no_op(self):
        bus = InMemoryEventBus()
        bus.unsubscribe(EventNames.GAME_OVER, recorder([]))  # must not raise

    def test_one_bad_subscriber_does_not_stop_the_others(self):
        bus = InMemoryEventBus()
        calls = []

        async def bad_handler(event):
            raise RuntimeError("boom")

        bus.subscribe(EventNames.GAME_OVER, bad_handler)
        bus.subscribe(EventNames.GAME_OVER, recorder(calls, "survived"))

        asyncio.run(bus.publish(Event(name=EventNames.GAME_OVER, payload={})))

        assert calls == ["survived"]

    def test_a_sync_handler_is_swallowed_like_any_other_failure(self):
        # Guards the conversion itself: awaiting a `def` handler's None return
        # raises TypeError, which the fan-out logs and swallows. Documented so
        # nobody reads a silently-missing side effect as "the bus dropped it".
        bus = InMemoryEventBus()
        calls = []
        bus.subscribe(EventNames.GAME_OVER, lambda event: calls.append("sync"))
        bus.subscribe(EventNames.GAME_OVER, recorder(calls, "survived"))

        asyncio.run(bus.publish(Event(name=EventNames.GAME_OVER, payload={})))

        assert calls == ["sync", "survived"]

    def test_handlers_run_sequentially_and_do_not_interleave(self):
        # The determinism guarantee: a handler that yields to the loop still
        # completes before the next handler starts (no gather, no create_task).
        bus = InMemoryEventBus()
        calls = []

        async def slow(event):
            calls.append("slow-start")
            await asyncio.sleep(0)
            calls.append("slow-end")

        bus.subscribe(EventNames.GAME_OVER, slow)
        bus.subscribe(EventNames.GAME_OVER, recorder(calls, "next"))

        asyncio.run(bus.publish(Event(name=EventNames.GAME_OVER, payload={})))

        assert calls == ["slow-start", "slow-end", "next"]

    def test_satisfies_event_bus_protocol(self):
        assert isinstance(InMemoryEventBus(), EventBus)
