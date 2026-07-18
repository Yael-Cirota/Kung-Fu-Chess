from dataclasses import dataclass, field
from typing import List, Optional, Union

from kfchess.io.board_parser import BoardValidator, BoardParser
from kfchess.model.piece import Piece, PieceKind

_PIECE_KINDS = {
    'K': PieceKind.KING, 'Q': PieceKind.QUEEN, 'R': PieceKind.ROOK,
    'B': PieceKind.BISHOP, 'N': PieceKind.KNIGHT, 'P': PieceKind.PAWN,
}


def create_piece(token: str):
    """Factory function to convert text tokens (e.g. 'wK', '.') into Piece objects."""
    if token == '.':
        return None

    color, piece_type = token[0], token[1]
    kind = _PIECE_KINDS.get(piece_type)
    return Piece(color, kind) if kind else None


def parse_board_grid(raw_board_string: str) -> List[list]:
    """Converts a raw canonical board string into a 2D grid of Piece objects."""
    raw_grid = [row.split() for row in raw_board_string.splitlines()]
    return [[create_piece(token) for token in row] for row in raw_grid]


@dataclass(frozen=True)
class ClickCommand:
    x: int
    y: int


@dataclass(frozen=True)
class WaitCommand:
    ms: int


@dataclass(frozen=True)
class PrintBoardCommand:
    pass


@dataclass(frozen=True)
class PrintScoresCommand:
    pass


@dataclass(frozen=True)
class JumpCommand:
    x: int
    y: int


ScriptCommand = Union[ClickCommand, WaitCommand, PrintBoardCommand, PrintScoresCommand, JumpCommand]


def parse_command_line(line: str) -> Optional[ScriptCommand]:
    """Translates a single raw text line into a ScriptCommand, or None if unrecognized."""
    parts = line.strip().split()
    if not parts:
        return None

    cmd_type = parts[0]

    if cmd_type == "click" and len(parts) == 3:
        try:
            return ClickCommand(int(parts[1]), int(parts[2]))
        except ValueError:
            return None
    elif cmd_type == "jump" and len(parts) == 3:
        try:
            return JumpCommand(int(parts[1]), int(parts[2]))
        except ValueError:
            return None
    elif cmd_type == "wait" and len(parts) == 2:
        try:
            return WaitCommand(int(parts[1]))
        except ValueError:
            return None
    elif " ".join(parts) == "print board":
        return PrintBoardCommand()
    elif " ".join(parts) == "print scores":
        return PrintScoresCommand()

    return None


@dataclass
class ParsedScript:
    board_grid: Optional[List[list]]
    error: Optional[str]
    commands: List[ScriptCommand] = field(default_factory=list)


class ScriptParser:
    """Parses text-based VPL scripts (Board:/Commands: sections) into a ParsedScript."""

    def __init__(self, validator: Optional[BoardValidator] = None):
        self._validator = validator or BoardValidator(
            valid_colors={'w', 'b'},
            valid_pieces={'K', 'Q', 'R', 'B', 'N', 'P'},
        )

    def parse(self, vpl_text: str) -> ParsedScript:
        board_parser = BoardParser(validator=self._validator)
        raw_board_string = board_parser.parse(vpl_text)

        if raw_board_string.startswith("ERROR"):
            return ParsedScript(board_grid=None, error=raw_board_string)

        if not raw_board_string:
            return ParsedScript(board_grid=None, error=None)

        grid = parse_board_grid(raw_board_string)
        commands = self._parse_commands(vpl_text)
        return ParsedScript(board_grid=grid, error=None, commands=commands)

    @staticmethod
    def _parse_commands(vpl_text: str) -> List[ScriptCommand]:
        commands: List[ScriptCommand] = []
        commands_started = False

        for line in vpl_text.splitlines():
            line_str = line.strip()

            if line_str.startswith("Commands:"):
                commands_started = True
                continue

            if commands_started and line_str:
                command = parse_command_line(line_str)
                if command:
                    commands.append(command)

        return commands
