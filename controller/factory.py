from kfchess.api import GameSession

from controller.api import GameController as GameControllerProtocol
from controller.board_mapper import BoardMapper
from controller.game_controller import GameController


def build_game_controller(session: GameSession, cell_size_px: int = 100) -> GameControllerProtocol:
    """Builds a fully-wired GameController from a GameSession, hiding BoardMapper construction/wiring."""
    return GameController(session, BoardMapper(cell_size_px=cell_size_px))
