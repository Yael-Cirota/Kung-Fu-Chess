import sqlite3

from server.infrastructure.connection_factory import apply_schema, create_connection, read_schema_sql


class TestReadSchemaSql:
    def test_contains_the_expected_tables(self):
        sql = read_schema_sql()
        assert "CREATE TABLE IF NOT EXISTS users" in sql
        assert "CREATE TABLE IF NOT EXISTS game_records" in sql


class TestApplySchema:
    def test_creates_the_users_table_on_an_in_memory_connection(self):
        conn = sqlite3.connect(":memory:")
        apply_schema(conn)

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = {row[0] for row in cursor.fetchall()}
        assert {"users", "game_records"} <= table_names

    def test_is_idempotent_on_an_already_initialized_connection(self):
        conn = sqlite3.connect(":memory:")
        apply_schema(conn)
        apply_schema(conn)  # must not raise


class TestCreateConnection:
    def test_returns_a_connection_with_the_schema_applied(self):
        conn = create_connection(":memory:")
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = {row[0] for row in cursor.fetchall()}
        assert "users" in table_names

    def test_row_factory_allows_column_name_access(self):
        conn = create_connection(":memory:")
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, elo) VALUES ('a', 'h', 's', 1200)"
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE username = 'a'").fetchone()
        assert row["username"] == "a"
        assert row["elo"] == 1200
