from kfchess.api.session import EngineGameSession, GameSession
from kfchess.engine.game_engine import GameEngine
from kfchess.model.board import Board
from kfchess.realtime.real_time_arbiter import RealTimeArbiter
from kfchess.rules.rule_engine import RuleEngine
from kfchess.texttests.script_parser import parse_board_grid


def create_game_session(starting_board_text: str) -> GameSession:
    """Builds a fully-wired GameSession from a text board, hiding kfchess's internal construction sequence."""
    grid = parse_board_grid(starting_board_text)
    board = Board(grid)
    rule_engine = RuleEngine()
    arbiter = RealTimeArbiter(board, rule_engine)
    engine = GameEngine(board, rule_engine, arbiter)
    return EngineGameSession(engine)
