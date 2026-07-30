import secrets
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class TraceId:
    value: str


@runtime_checkable
class TraceIdGenerator(Protocol):
    def new_id(self) -> str: ...


class SecretsTraceIdGenerator:
    """Production generator: unpredictable, collision-resistant ids."""

    def new_id(self) -> str:
        return secrets.token_hex(8)


class SequentialTraceIdGenerator:
    """Test double: deterministic, collision-free within a test run."""

    def __init__(self):
        self._counter = 0

    def new_id(self) -> str:
        self._counter += 1
        return f"trace-{self._counter}"
