import sqlite3

import pytest

from server.infrastructure.connection_factory import apply_schema
from server.infrastructure.sqlite_game_record_repository import SqliteGameRecordRepository
from server.infrastructure.sqlite_user_repository import SqliteUserRepository


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    apply_schema(connection)
    return connection


@pytest.fixture
def players(conn):
    users = SqliteUserRepository(conn)
    return users.create("white", "h", "s", 1200), users.create("black", "h", "s", 1200)


def rows(conn):
    return conn.execute("SELECT * FROM game_records ORDER BY game_id").fetchall()


class TestRecordResult:
    def test_stores_the_result(self, conn, players):
        white, black = players
        SqliteGameRecordRepository(conn).record_result(
            white_id=white.user_id,
            black_id=black.user_id,
            winner_id=black.user_id,
            ended_at_ms=4321,
            reason="disconnect",
        )

        stored = rows(conn)
        assert len(stored) == 1
        assert stored[0]["white_id"] == white.user_id
        assert stored[0]["winner_id"] == black.user_id
        assert stored[0]["ended_at_ms"] == 4321
        assert stored[0]["reason"] == "disconnect"

    def test_a_game_without_a_winner_stores_null(self, conn, players):
        white, black = players
        SqliteGameRecordRepository(conn).record_result(
            white_id=white.user_id,
            black_id=black.user_id,
            winner_id=None,
            ended_at_ms=1,
            reason="king_captured",
        )

        assert rows(conn)[0]["winner_id"] is None

    def test_appends_rather_than_replacing(self, conn, players):
        white, black = players
        repo = SqliteGameRecordRepository(conn)
        repo.record_result(white.user_id, black.user_id, white.user_id, 1, "king_captured")
        repo.record_result(white.user_id, black.user_id, black.user_id, 2, "disconnect")

        assert len(rows(conn)) == 2

    def test_persists_across_repository_instances_on_the_same_connection(self, conn, players):
        white, black = players
        SqliteGameRecordRepository(conn).record_result(white.user_id, black.user_id, None, 1, "disconnect")

        assert len(rows(conn)) == 1
