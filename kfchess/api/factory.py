from typing import Optional

from kfchess.api.engine_config import EngineConfig
from kfchess.api.events import EngineEventSink
from kfchess.api.session import EngineGameSession, GameSession
from kfchess.engine.game_engine import GameEngine
from kfchess.model.board import Board
from kfchess.realtime.cooldown import CooldownPolicy
from kfchess.realtime.movement_profile import build_movement_profiles
from kfchess.realtime.real_time_arbiter import RealTimeArbiter
from kfchess.rules.rule_engine import RuleEngine
from kfchess.rules.scoring import ScoringPolicy
from kfchess.texttests.script_parser import parse_board_grid


def create_game_session(
    starting_board_text: str,
    config: Optional[EngineConfig] = None,
    event_sink: Optional[EngineEventSink] = None,
) -> GameSession:
    """Builds a fully-wired GameSession from a text board, hiding kfchess's
    internal construction sequence. `config` and `event_sink` default to None,
    which reproduces today's hard-coded engine behavior exactly - the VPL path
    never passes either, so graded output stays byte-identical."""
    grid = parse_board_grid(starting_board_text)
    board = Board(grid)
    rule_engine = RuleEngine()

    if config is None:
        arbiter = RealTimeArbiter(board, rule_engine)
        engine = GameEngine(board, rule_engine, arbiter)
    else:
        cooldown_policy = CooldownPolicy(config.move_cooldown_ms, config.jump_cooldown_ms)
        movement_profiles = build_movement_profiles(config.move_duration_ms_per_cell)
        arbiter = RealTimeArbiter(
            board,
            rule_engine,
            cooldown_policy=cooldown_policy,
            movement_profiles=movement_profiles,
            jump_duration_ms=config.jump_duration_ms,
        )
        scoring = ScoringPolicy(point_values=config.point_values)
        engine = GameEngine(board, rule_engine, arbiter, scoring=scoring)

    return EngineGameSession(engine, event_sink=event_sink)
