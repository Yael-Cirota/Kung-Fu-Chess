import contextlib
import io
from pathlib import Path
from typing import Optional, Union

from kfchess.model.board import Board
from kfchess.rules.rule_engine import RuleEngine
from kfchess.realtime.real_time_arbiter import RealTimeArbiter
from kfchess.engine.game_engine import GameEngine
from kfchess.input.board_mapper import BoardMapper
from kfchess.input.controller import Controller
from kfchess.io.board_printer import BoardPrinter
from kfchess.texttests.script_parser import (
    ScriptParser, ClickCommand, WaitCommand, PrintBoardCommand, JumpCommand,
)


class ScriptRunner:
    """
    Runs a parsed VPL script end to end through the full layered stack,
    returning captured output. Used both by pytest integration tests
    and standalone script files (see run_file).
    """

    def __init__(self, parser: Optional[ScriptParser] = None):
        self._parser = parser or ScriptParser()

    def run(self, vpl_text: str) -> str:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self._run(vpl_text)
        return buffer.getvalue()

    def run_file(self, path: Union[str, Path]) -> str:
        return self.run(Path(path).read_text())

    def _run(self, vpl_text: str) -> None:
        script = self._parser.parse(vpl_text)

        if script.error:
            print(script.error)
            return

        if script.board_grid is None:
            return

        board = Board(script.board_grid)
        rule_engine = RuleEngine()
        arbiter = RealTimeArbiter(board, rule_engine)
        game_engine = GameEngine(board, rule_engine, arbiter)
        controller = Controller(game_engine, BoardMapper())
        printer = BoardPrinter()

        for command in script.commands:
            self._execute(command, controller, game_engine, printer)

    @staticmethod
    def _execute(command, controller: Controller, game_engine: GameEngine, printer: BoardPrinter) -> None:
        if isinstance(command, ClickCommand):
            controller.on_click(command.x, command.y)
        elif isinstance(command, WaitCommand):
            game_engine.advance_clock(command.ms)
        elif isinstance(command, PrintBoardCommand):
            printer.print(game_engine.snapshot())
        elif isinstance(command, JumpCommand):
            controller.on_click(command.x, command.y)
            controller.on_click(command.x, command.y)
