from typing import Optional

from kfchess.api import GameSession, Position

from ui.board_geometry import BoardGeometry


class ClickHandler:
    """
    Translates raw pixel clicks into board commands on a GameSession.

    Owns exactly one concern: the select/reselect/move state machine, which
    is per-player view state rather than game state and so can never move
    server-side. Pixel geometry is *not* its job - it delegates that to an
    injected BoardGeometry. Everything else the ui needs it reads from the
    GameSession directly; there is no delegating wrapper in between.

    No motion state is cached here: GameSession.motion_for already answers
    live from the engine, so there is nothing to keep in sync.
    """

    def __init__(self, session: GameSession, geometry: BoardGeometry):
        self._session = session
        self._geometry = geometry
        self.selected: Optional[Position] = None

    def on_click(self, x: int, y: int) -> None:
        pos = self._geometry.pixel_to_cell(x, y)

        if not self._session.is_within_bounds(pos):
            self.selected = None
            return

        target = self._session.piece_at(pos)

        if self.selected is None:
            if target is not None:
                self.selected = pos
            return

        selected_piece = self._session.piece_at(self.selected)
        if pos != self.selected and target is not None and selected_piece is not None \
                and target.color == selected_piece.color:
            self.selected = pos
            return

        self._session.request_move(self.selected, pos)
        self.selected = None
