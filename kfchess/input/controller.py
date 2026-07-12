from typing import Optional

from kfchess.model.position import Position
from kfchess.input.board_mapper import BoardMapper


class Controller:
    """
    Pure translator from pixel clicks to GameEngine commands. Maps
    coordinates via BoardMapper, tracks which piece is selected, and
    defers every legality decision to GameEngine.request_move - never
    calls Board or RuleEngine directly.
    """

    def __init__(self, game_engine, board_mapper: BoardMapper):
        self._game_engine = game_engine
        self._board_mapper = board_mapper
        self.selected: Optional[Position] = None

    def on_click(self, x: int, y: int) -> None:
        pos = self._board_mapper.pixel_to_position(x, y)
        on_board = self._game_engine.is_within_bounds(pos)
        
        if not on_board:
            self.selected = None
            return
        
        if self.selected is None:
            if self._game_engine.piece_at(pos) is not None:
                self.selected = pos
            return

        self._game_engine.request_move(self.selected, pos)
        self.selected = None
