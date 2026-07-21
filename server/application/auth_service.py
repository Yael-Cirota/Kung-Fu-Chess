import hashlib
import secrets
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from common.result import Result
from server.infrastructure.repositories import UserRepository


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: int
    username: str
    elo: int


class AuthErrorReason:
    USERNAME_TAKEN = "username_taken"
    INVALID_CREDENTIALS = "invalid_credentials"


@runtime_checkable
class PasswordHasher(Protocol):
    def hash(self, password: str, salt: str) -> str: ...

    def new_salt(self) -> str: ...


class Pbkdf2PasswordHasher:
    """stdlib-only, no new dependency: hashlib.pbkdf2_hmac. CPU-bound, so a
    real deployment must offload it to a thread (see 'Blocking work never
    runs on the event loop' - a Phase 4 concern); this class itself stays
    plain and synchronous."""

    def __init__(self, iterations: int = 200_000):
        self._iterations = iterations

    def hash(self, password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), self._iterations
        ).hex()

    def new_salt(self) -> str:
        return secrets.token_hex(16)


class AuthService:
    """Synchronous, clock-free: identity and credentials only. Every failure
    path performs no repository mutation - a rejected register never creates
    a half-written user."""

    def __init__(self, users: UserRepository, hasher: PasswordHasher, starting_elo: int = 1200):
        self._users = users
        self._hasher = hasher
        self._starting_elo = starting_elo

    def register(self, username: str, password: str) -> Result[AuthenticatedUser]:
        if self._users.find_by_username(username) is not None:
            return Result.failure(AuthErrorReason.USERNAME_TAKEN)
        salt = self._hasher.new_salt()
        password_hash = self._hasher.hash(password, salt)
        record = self._users.create(username, password_hash, salt, self._starting_elo)
        return Result.success(AuthenticatedUser(user_id=record.user_id, username=record.username, elo=record.elo))

    def login(self, username: str, password: str) -> Result[AuthenticatedUser]:
        record = self._users.find_by_username(username)
        if record is None:
            return Result.failure(AuthErrorReason.INVALID_CREDENTIALS)
        if self._hasher.hash(password, record.salt) != record.password_hash:
            return Result.failure(AuthErrorReason.INVALID_CREDENTIALS)
        return Result.success(AuthenticatedUser(user_id=record.user_id, username=record.username, elo=record.elo))
