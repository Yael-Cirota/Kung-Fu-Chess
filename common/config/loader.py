import os
import tomllib
from dataclasses import replace
from pathlib import Path
from typing import Mapping, Optional, Union

from common.config.schema import (
    AppConfig,
    ClientConfigData,
    ConnectionConfigData,
    DatabaseConfigData,
    EngineConfigData,
    LoggingConfigData,
    MatchmakingConfigData,
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
    "logging": LoggingConfigData,
    "client": ClientConfigData,
}

# env var -> (section, field, caster). Applied after TOML, so env always wins.
_ENV_OVERRIDES = {
    "KFC_DB_PATH": ("database", "path", str),
    "KFC_HOST": ("server", "host", str),
    "KFC_PORT": ("server", "port", int),
    "KFC_LOG_LEVEL": ("logging", "level", str),
}


def load_config(path: Optional[Union[str, Path]] = None, env: Optional[Mapping[str, str]] = None) -> AppConfig:
    """Loads TOML at `path` (missing keys fall back to dataclass defaults),
    then applies environment-variable overrides on top."""
    env = os.environ if env is None else env
    raw: dict = {}
    if path is not None and Path(path).exists():
        with open(path, "rb") as f:
            raw = tomllib.load(f)

    sections = {name: cls(**dict(raw.get(name, {}))) for name, cls in _SECTION_TYPES.items()}

    for env_key, (section, field_name, caster) in _ENV_OVERRIDES.items():
        if env_key in env:
            sections[section] = replace(sections[section], **{field_name: caster(env[env_key])})

    return AppConfig(**sections)
