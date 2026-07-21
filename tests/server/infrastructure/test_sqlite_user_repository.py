import sqlite3

import pytest

from server.infrastructure.connection_factory import apply_schema
from server.infrastructure.repositories import UserRecord
from server.infrastructure.sqlite_user_repository import SqliteUserRepository


@pytest.fixture
def repo():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_schema(conn)
    return SqliteUserRepository(conn)


class TestFindByUsername:
    def test_returns_none_when_no_user_exists(self, repo):
        assert repo.find_by_username("nobody") is None

    def test_returns_the_record_for_an_existing_user(self, repo):
        repo.create("alice", "hashed", "salt123", 1200)
        record = repo.find_by_username("alice")

        assert isinstance(record, UserRecord)
        assert record.username == "alice"
        assert record.password_hash == "hashed"
        assert record.salt == "salt123"
        assert record.elo == 1200


class TestFindById:
    def test_returns_none_when_no_user_exists(self, repo):
        assert repo.find_by_id(999) is None

    def test_returns_the_record_for_an_existing_user(self, repo):
        created = repo.create("alice", "hashed", "salt123", 1200)
        record = repo.find_by_id(created.user_id)

        assert isinstance(record, UserRecord)
        assert record.user_id == created.user_id
        assert record.username == "alice"
        assert record.elo == 1200


class TestCreate:
    def test_returns_a_record_with_an_assigned_user_id(self, repo):
        record = repo.create("bob", "hashed", "salt", 1200)
        assert record.user_id is not None
        assert record.username == "bob"

    def test_persists_across_repository_instances_on_the_same_connection(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        apply_schema(conn)

        SqliteUserRepository(conn).create("carol", "h", "s", 1200)
        second = SqliteUserRepository(conn)

        assert second.find_by_username("carol") is not None

    def test_duplicate_username_raises_integrity_error(self, repo):
        repo.create("dave", "h", "s", 1200)
        with pytest.raises(sqlite3.IntegrityError):
            repo.create("dave", "h2", "s2", 1200)


class TestUpdateElo:
    def test_changes_the_stored_elo(self, repo):
        created = repo.create("erin", "h", "s", 1200)
        repo.update_elo(created.user_id, 1250)

        assert repo.find_by_username("erin").elo == 1250

    def test_updating_an_unknown_user_id_is_a_no_op(self, repo):
        repo.update_elo(999, 1500)  # must not raise
