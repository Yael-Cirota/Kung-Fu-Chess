from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class UserRecord:
    user_id: int
    username: str
    password_hash: str
    salt: str
    elo: int


@runtime_checkable
class UserRepository(Protocol):
    def find_by_username(self, username: str) -> Optional[UserRecord]: ...

    def find_by_id(self, user_id: int) -> Optional[UserRecord]: ...

    def create(self, username: str, password_hash: str, salt: str, elo: int) -> UserRecord: ...

    def update_elo(self, user_id: int, elo: int) -> None: ...


@runtime_checkable
class GameRecordRepository(Protocol):
    def record_result(
        self,
        white_id: int,
        black_id: int,
        winner_id: Optional[int],
        ended_at_ms: int,
        reason: str,
    ) -> None: ...
