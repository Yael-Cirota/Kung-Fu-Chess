from common.tracing import SecretsTraceIdGenerator, SequentialTraceIdGenerator, TraceId, TraceIdGenerator


class TestSequentialTraceIdGenerator:
    def test_generates_deterministic_ids(self):
        generator = SequentialTraceIdGenerator()
        assert generator.new_id() == "trace-1"
        assert generator.new_id() == "trace-2"

    def test_satisfies_trace_id_generator_protocol(self):
        assert isinstance(SequentialTraceIdGenerator(), TraceIdGenerator)


class TestSecretsTraceIdGenerator:
    def test_generates_collision_free_ids_within_a_run(self):
        generator = SecretsTraceIdGenerator()
        ids = {generator.new_id() for _ in range(50)}
        assert len(ids) == 50

    def test_satisfies_trace_id_generator_protocol(self):
        assert isinstance(SecretsTraceIdGenerator(), TraceIdGenerator)


class TestTraceId:
    def test_wraps_a_string_value(self):
        assert TraceId("abc123").value == "abc123"
