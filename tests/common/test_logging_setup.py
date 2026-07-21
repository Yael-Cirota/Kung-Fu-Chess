import json
import logging

from common.logging_setup import configure_logger


class TestConfigureLogger:
    def test_writes_one_json_object_per_line_to_the_given_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        logger = configure_logger("kfchess.test.file", level="INFO", file_path=str(log_file))

        logger.info("PIECE_CAPTURED")
        for handler in logger.handlers:
            handler.flush()

        line = log_file.read_text().strip()
        record = json.loads(line)
        assert record["event"] == "PIECE_CAPTURED"

    def test_record_shape_always_has_the_four_keys(self, tmp_path):
        log_file = tmp_path / "test.log"
        logger = configure_logger("kfchess.test.shape", level="INFO", file_path=str(log_file))

        logger.info("MOVE_LOGGED")
        for handler in logger.handlers:
            handler.flush()

        record = json.loads(log_file.read_text().strip())
        assert set(record.keys()) == {"trace_id", "room_id", "layer", "event", "at_ms", "execution_time_ms"}
        assert record["trace_id"] is None
        assert record["room_id"] is None
        assert record["layer"] is None
        assert record["at_ms"] is None
        assert record["execution_time_ms"] is None

    def test_extra_fields_populate_the_record(self, tmp_path):
        log_file = tmp_path / "test.log"
        logger = configure_logger("kfchess.test.extra", level="INFO", file_path=str(log_file))

        logger.info(
            "GAME_OVER",
            extra={"trace_id": "trace-1", "room_id": "room-a", "layer": "domain",
                   "at_ms": 1000, "execution_time_ms": 0.5},
        )
        for handler in logger.handlers:
            handler.flush()

        record = json.loads(log_file.read_text().strip())
        assert record["trace_id"] == "trace-1"
        assert record["room_id"] == "room-a"
        assert record["layer"] == "domain"
        assert record["at_ms"] == 1000
        assert record["execution_time_ms"] == 0.5

    def test_logger_does_not_propagate_to_the_root_logger(self, tmp_path):
        logger = configure_logger("kfchess.test.isolated", level="INFO", file_path=str(tmp_path / "x.log"))
        assert logger.propagate is False

    def test_reconfiguring_replaces_handlers_rather_than_accumulating(self, tmp_path):
        log_file = tmp_path / "test.log"
        configure_logger("kfchess.test.reconfig", level="INFO", file_path=str(log_file))
        logger = configure_logger("kfchess.test.reconfig", level="INFO", file_path=str(log_file))
        assert len(logger.handlers) == 1

    def test_defaults_to_a_stream_handler_when_no_file_path_given(self):
        logger = configure_logger("kfchess.test.stream", level="DEBUG")
        assert isinstance(logger.handlers[0], logging.StreamHandler)
