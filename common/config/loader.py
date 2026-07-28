import os
import tomllib
from dataclasses import fields, replace
from pathlib import Path
from typing import Callable, Mapping, Optional, Union

from common.config.schema import (
    AppConfig,
    ClientConfigData,
    ConnectionConfigData,
    DatabaseConfigData,
    EngineConfigData,
    LoggingConfigData,
    MatchmakingConfigData,
    PgConfigData,
    RedisConfigData,
    RoomsConfigData,
    ServerConfigData,
)

_SECTION_TYPES = {
    "engine": EngineConfigData,
    "server": ServerConfigData,
    "matchmaking": MatchmakingConfigData,
    "connection": ConnectionConfigData,
    "rooms": RoomsConfigData,
    "database": DatabaseConfigData,
    "redis": RedisConfigData,
    "pg": PgConfigData,
    "logging": LoggingConfigData,
    "client": ClientConfigData,
}

# Field types the generic env rule below knows how to parse out of a string.
# Mapping-typed fields (e.g. engine.point_values) are TOML/dict-shaped and
# have no sane single-value env encoding, so they're deliberately absent -
# they stay TOML-only.
_CASTERS: Mapping[type, Callable[[str], object]] = {
    int: int,
    float: float,
    str: str,
    bool: lambda v: v.strip().lower() in ("1", "true", "yes", "on"),
}

# Predates the generic KFC_<SECTION>_<FIELD> rule below; kept so these exact,
# already-documented names keep working. Applied after the generic rule, so
# an alias wins if both it and the generic form of the same key are set.
_LEGACY_ALIASES = {
    "KFC_DB_PATH": ("database", "path", str),
    "KFC_HOST": ("server", "host", str),
    "KFC_PORT": ("server", "port", int),
    "KFC_LOG_LEVEL": ("logging", "level", str),
}


def load_config(path: Optional[Union[str, Path]] = None, env: Optional[Mapping[str, str]] = None) -> AppConfig:
    """Loads TOML at `path` (missing keys fall back to dataclass defaults),
    then applies environment-variable overrides on top. Overrides are read as
    KFC_<SECTION>_<FIELD> (e.g. KFC_REDIS_URL, KFC_SERVER_BROADCAST_HZ),
    derived straight from each section dataclass's own fields - a new config
    field becomes env-overridable for free, no registration needed."""
    env = os.environ if env is None else env
    raw: dict = {}
    if path is not None and Path(path).exists():
        with open(path, "rb") as f:
            raw = tomllib.load(f)

    sections = {name: cls(**dict(raw.get(name, {}))) for name, cls in _SECTION_TYPES.items()}

    for section_name, cls in _SECTION_TYPES.items():
        for f in fields(cls):
            caster = _CASTERS.get(f.type)
            if caster is None:
                continue
            env_key = f"KFC_{section_name.upper()}_{f.name.upper()}"
            if env_key in env:
                sections[section_name] = replace(sections[section_name], **{f.name: caster(env[env_key])})

    for env_key, (section, field_name, caster) in _LEGACY_ALIASES.items():
        if env_key in env:
            sections[section] = replace(sections[section], **{field_name: caster(env[env_key])})

    return AppConfig(**sections)
