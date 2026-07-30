CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    elo INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS game_records (
    game_id INTEGER PRIMARY KEY AUTOINCREMENT,
    white_id INTEGER NOT NULL,
    black_id INTEGER NOT NULL,
    winner_id INTEGER,
    ended_at_ms INTEGER NOT NULL,
    reason TEXT NOT NULL,
    FOREIGN KEY (white_id) REFERENCES users (user_id),
    FOREIGN KEY (black_id) REFERENCES users (user_id),
    FOREIGN KEY (winner_id) REFERENCES users (user_id)
);
