from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Result(Generic[T]):
    """A method that returns Result.failure(...) must perform no state mutation.
    `error` is always a stable reason constant, never a free-text message."""

    ok: bool
    value: Optional[T] = None
    error: Optional[str] = None

    @staticmethod
    def success(value: T) -> "Result[T]":
        return Result(ok=True, value=value)

    @staticmethod
    def failure(reason: str) -> "Result[T]":
        return Result(ok=False, error=reason)
