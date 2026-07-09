from typing import Optional

from kfchess.model.position import Position
from kfchess.input.board_mapper import BoardMapper


class Controller:
    """
    Translates pixel clicks into board positions, maintains selected-piece
    state, and passes destination commands to GameEngine.
    """

    def __init__(self, game_engine, board_mapper: BoardMapper):
        self._game_engine = game_engine
        self._board_mapper = board_mapper
        self.selected: Optional[Position] = None

    def on_click(self, x: int, y: int) -> None:
        if self._game_engine.game_over:
            return

        pos = self._board_mapper.pixel_to_position(x, y)
        if not self._game_engine.is_within_bounds(pos):
            return

        target_piece = self._game_engine.piece_at(pos)

        if self.selected is None:
            if target_piece is not None:
                self.selected = pos
            return

        selected_piece = self._game_engine.piece_at(self.selected)
        if selected_piece is None:
            self.selected = None
            return

        if target_piece is not None and target_piece.color == selected_piece.color:
            if self._game_engine.is_moving(target_piece):
                return
            self.selected = pos
        else:
            self._game_engine.request_move(self.selected, pos)
            self.selected = None
