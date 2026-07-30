import sqlite3
from typing import Optional


class SqliteGameRecordRepository:
    """Append-only history of finished games. Commits per write, matching
    SqliteUserRepository's single-writer model. `winner_id` is NULL for a
    game that ended without a winner."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def record_result(
        self,
        white_id: int,
        black_id: int,
        winner_id: Optional[int],
        ended_at_ms: int,
        reason: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO game_records (white_id, black_id, winner_id, ended_at_ms, reason) "
            "VALUES (?, ?, ?, ?, ?)",
            (white_id, black_id, winner_id, ended_at_ms, reason),
        )
        self._conn.commit()
