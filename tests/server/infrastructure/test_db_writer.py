from server.infrastructure.db_writer import DbWriter, InlineDbWriter


class TestInlineDbWriter:
    def test_runs_the_function_immediately_with_its_args(self):
        calls = []
        writer = InlineDbWriter()

        writer.submit(lambda a, b: calls.append((a, b)), 1, 2)

        assert calls == [(1, 2)]

    def test_satisfies_the_protocol(self):
        assert isinstance(InlineDbWriter(), DbWriter)
