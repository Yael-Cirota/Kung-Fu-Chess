from common.result import Result


class TestResultSuccess:
    def test_success_carries_the_value(self):
        result = Result.success(42)
        assert result.ok is True
        assert result.value == 42
        assert result.error is None


class TestResultFailure:
    def test_failure_carries_the_reason(self):
        result = Result.failure("bad_input")
        assert result.ok is False
        assert result.value is None
        assert result.error == "bad_input"
