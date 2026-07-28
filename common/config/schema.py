"""Frozen config dataclass tree. Generic data only - no kfchess types, since
common sits below kfchess in the dependency direction (kfchess depends on
common, never the reverse)."""

from dataclasses import dataclass, field
from typing import Mapping


def _default_point_values() -> Mapping[str, int]:
    return {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 10}


def _default_starting_board() -> str:
    return (
        "bR bN bB bQ bK bB bN bR\n"
        "bP bP bP bP bP bP bP bP\n"
        ".  .  .  .  .  .  .  .\n"
        ".  .  .  .  .  .  .  .\n"
        ".  .  .  .  .  .  .  .\n"
        ".  .  .  .  .  .  .  .\n"
        "wP wP wP wP wP wP wP wP\n"
        "wR wN wB wQ wK wB wN wR"
    )


@dataclass(frozen=True)
class EngineConfigData:
    move_duration_ms_per_cell: int = 1000
    jump_duration_ms: int = 1000
    move_cooldown_ms: int = 1000
    jump_cooldown_ms: int = 500
    point_values: Mapping[str, int] = field(default_factory=_default_point_values)
    starting_board: str = field(default_factory=_default_starting_board)


@dataclass(frozen=True)
class ServerConfigData:
    host: str = "127.0.0.1"
    port: int = 8765
    tick_hz: int = 100
    broadcast_hz: int = 20
    max_engine_step_ms: int = 100
    # Passed straight to websockets.serve(compression=...); "" disables
    # permessage-deflate. A config knob (not a constant) because §10 of the
    # scaling plan flags compression CPU-vs-bandwidth as something that needs
    # measuring under load, not assuming.
    compression: str = "deflate"
    # Which Server_Design.md §2 role this process runs as, and which region
    # it's deployed in. "monolith" is today's single-process default; the
    # per-role entry points (server.roles.*) set this to their own name.
    role: str = "monolith"
    region: str = "local"


@dataclass(frozen=True)
class MatchmakingConfigData:
    elo_window: int = 100
    timeout_ms: int = 60000
    starting_elo: int = 1200
    k_factor: int = 32


@dataclass(frozen=True)
class ConnectionConfigData:
    heartbeat_interval_ms: int = 3000
    heartbeat_timeout_ms: int = 10000
    disconnect_grace_ms: int = 20000
    max_frame_bytes: int = 16384


@dataclass(frozen=True)
class RoomsConfigData:
    max_viewers: int = 8
    room_id_length: int = 6


@dataclass(frozen=True)
class DatabaseConfigData:
    path: str = "kfchess.db"


@dataclass(frozen=True)
class RedisConfigData:
    # Server_Design.md §1.1/§2: shared state (sessions, room directory,
    # matchmaking queue) that today lives in in-process dicts. Unused until
    # §2's role split lands; present now so KFC_REDIS_URL round-trips through
    # the generic env-override rule.
    url: str = "redis://127.0.0.1:6379"


@dataclass(frozen=True)
class PgConfigData:
    # Server_Design.md §1: replaces SqliteUserRepository/
    # SqliteGameRecordRepository at scale. Empty by default - unused (and
    # unvalidated) until that migration happens.
    dsn: str = ""


@dataclass(frozen=True)
class LoggingConfigData:
    level: str = "INFO"
    client_file: str = "client.log"
    server_file: str = "server.log"
    format: str = "json"
    max_bytes: int = 1_000_000
    backup_count: int = 3


@dataclass(frozen=True)
class ClientConfigData:
    fps: int = 60
    server_url: str = "ws://127.0.0.1:8765"
    resync_threshold_ms: int = 1000
    max_catchup_rate: float = 1.20
    min_catchup_rate: float = 0.85


@dataclass(frozen=True)
class AppConfig:
    engine: EngineConfigData = field(default_factory=EngineConfigData)
    server: ServerConfigData = field(default_factory=ServerConfigData)
    matchmaking: MatchmakingConfigData = field(default_factory=MatchmakingConfigData)
    connection: ConnectionConfigData = field(default_factory=ConnectionConfigData)
    rooms: RoomsConfigData = field(default_factory=RoomsConfigData)
    database: DatabaseConfigData = field(default_factory=DatabaseConfigData)
    redis: RedisConfigData = field(default_factory=RedisConfigData)
    pg: PgConfigData = field(default_factory=PgConfigData)
    logging: LoggingConfigData = field(default_factory=LoggingConfigData)
    client: ClientConfigData = field(default_factory=ClientConfigData)
