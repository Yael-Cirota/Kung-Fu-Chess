import sqlite3
from pathlib import Path
from typing import Union

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def read_schema_sql() -> str:
    return _SCHEMA_PATH.read_text()


def apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(read_schema_sql())
    conn.commit()


def create_connection(path: Union[str, Path]) -> sqlite3.Connection:
    """Opens a sqlite3 connection with row access by column name and the
    schema applied (CREATE TABLE IF NOT EXISTS, so this is safe on an
    existing database file too)."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    apply_schema(conn)
    return conn
