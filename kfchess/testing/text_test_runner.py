import contextlib
import io
from pathlib import Path
from typing import List, Optional, Union

from kfchess.parsing.board_parser import BoardValidator, BoardParser
from kfchess.parsing.commands import CommandParser
from pieces import King, Queen, Rook, Bishop, Knight, Pawn

from kfchess.model.board import Board
from kfchess.rules.rule_engine import RuleEngine
from kfchess.engine.real_time_arbiter import RealTimeArbiter
from kfchess.engine.game_engine import GameEngine
from kfchess.ui.board_mapper import BoardMapper
from kfchess.ui.controller import Controller
from kfchess.ui.renderer import Renderer

_PIECE_CLASSES = {
    'K': King, 'Q': Queen, 'R': Rook,
    'B': Bishop, 'N': Knight, 'P': Pawn,
}


def create_piece(token: str):
    """Factory function to convert text tokens (e.g. 'wK', '.') into Piece objects."""
    if token == '.':
        return None

    color, piece_type = token[0], token[1]
    piece_class = _PIECE_CLASSES.get(piece_type)
    return piece_class(color) if piece_class else None


def parse_board_grid(raw_board_string: str) -> List[list]:
    """Converts a raw canonical board string into a 2D grid of Piece objects."""
    raw_grid = [row.split() for row in raw_board_string.splitlines()]
    return [[create_piece(token) for token in row] for row in raw_grid]


class _EngineAdapter:
    """
    Bridges the legacy Command objects (which call handle_click/advance_clock/
    print_board on a single 'engine') onto the split Controller/GameEngine/Renderer.
    """

    def __init__(self, controller: Controller, game_engine: GameEngine, renderer: Renderer):
        self._controller = controller
        self._game_engine = game_engine
        self._renderer = renderer

    def handle_click(self, x: int, y: int) -> None:
        self._controller.on_click(x, y)

    def advance_clock(self, ms: int) -> None:
        self._game_engine.advance_clock(ms)

    def print_board(self) -> None:
        self._renderer.render(self._game_engine.snapshot())


class TextTestRunner:
    """
    Parses text-based VPL scripts (Board:/Commands: sections) and runs
    them end to end through the full layered stack, returning captured
    output. Used both by pytest integration tests and standalone script
    files (see run_file).
    """

    def __init__(self, validator: Optional[BoardValidator] = None):
        self._validator = validator or BoardValidator(
            valid_colors={'w', 'b'},
            valid_pieces={'K', 'Q', 'R', 'B', 'N', 'P'},
        )

    def run(self, vpl_text: str) -> str:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self._run(vpl_text)
        return buffer.getvalue()

    def run_file(self, path: Union[str, Path]) -> str:
        return self.run(Path(path).read_text())

    def _run(self, vpl_text: str) -> None:
        parser = BoardParser(validator=self._validator)
        raw_board_string = parser.parse(vpl_text)

        if not raw_board_string or raw_board_string.startswith("ERROR"):
            if raw_board_string:
                print(raw_board_string)
            return

        grid = parse_board_grid(raw_board_string)
        board = Board(grid)
        rule_engine = RuleEngine()
        arbiter = RealTimeArbiter(board, rule_engine)
        game_engine = GameEngine(board, rule_engine, arbiter)
        controller = Controller(game_engine, BoardMapper())
        renderer = Renderer()
        adapter = _EngineAdapter(controller, game_engine, renderer)

        self._execute_commands(vpl_text, adapter)

    @staticmethod
    def _execute_commands(vpl_text: str, engine: _EngineAdapter) -> None:
        commands_started = False

        for line in vpl_text.splitlines():
            line_str = line.strip()

            if line_str.startswith("Commands:"):
                commands_started = True
                continue

            if commands_started and line_str:
                command = CommandParser.parse_line(line_str)
                if command:
                    command.execute(engine)
