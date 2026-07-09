from kfchess.engine.game_snapshot import GameSnapshot


class Renderer:
    """Draws a read-only GameSnapshot. No mutable objects are exposed."""

    def render(self, snapshot: GameSnapshot) -> None:
        for row in snapshot.cells:
            row_str = " ".join(view.symbol if view is not None else '.' for view in row)
            print(row_str)
