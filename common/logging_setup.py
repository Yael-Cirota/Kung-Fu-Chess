import json
import logging
from typing import Optional


class JsonFormatter(logging.Formatter):
    """One JSON object per line. Every key is always present (None when the
    emitting call site didn't supply it) so log consumers never have to guess
    at record shape."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "trace_id": getattr(record, "trace_id", None),
            "room_id": getattr(record, "room_id", None),
            "layer": getattr(record, "layer", None),
            "event": record.getMessage(),
            "at_ms": getattr(record, "at_ms", None),
            "execution_time_ms": getattr(record, "execution_time_ms", None),
        }
        return json.dumps(payload)


def configure_logger(
    name: str,
    level: str = "INFO",
    file_path: Optional[str] = None,
) -> logging.Logger:
    """Builds an isolated logger (its own handler list, no propagation to the
    root logger) so client-side and server-side logging never bleed together."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    for existing in logger.handlers:
        existing.close()  # reconfiguring must not leak the previous file handle
    logger.handlers.clear()
    handler = logging.FileHandler(file_path) if file_path else logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
