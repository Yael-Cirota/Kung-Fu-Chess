import sqlite3
from typing import Optional

from server.infrastructure.repositories import UserRecord


class SqliteUserRepository:
    """Synchronous UserRepository backed by sqlite3. Every write commits
    immediately - single-writer, no transaction batching, matching sqlite3's
    own single-writer model."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def find_by_username(self, username: str) -> Optional[UserRecord]:
        row = self._conn.execute(
            "SELECT user_id, username, password_hash, salt, elo FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return _row_to_record(row) if row is not None else None

    def find_by_id(self, user_id: int) -> Optional[UserRecord]:
        row = self._conn.execute(
            "SELECT user_id, username, password_hash, salt, elo FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return _row_to_record(row) if row is not None else None

    def create(self, username: str, password_hash: str, salt: str, elo: int) -> UserRecord:
        cursor = self._conn.execute(
            "INSERT INTO users (username, password_hash, salt, elo) VALUES (?, ?, ?, ?)",
            (username, password_hash, salt, elo),
        )
        self._conn.commit()
        return UserRecord(
            user_id=cursor.lastrowid,
            username=username,
            password_hash=password_hash,
            salt=salt,
            elo=elo,
        )

    def update_elo(self, user_id: int, elo: int) -> None:
        self._conn.execute("UPDATE users SET elo = ? WHERE user_id = ?", (elo, user_id))
        self._conn.commit()


def _row_to_record(row: sqlite3.Row) -> UserRecord:
    return UserRecord(
        user_id=row["user_id"],
        username=row["username"],
        password_hash=row["password_hash"],
        salt=row["salt"],
        elo=row["elo"],
    )
