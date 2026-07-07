from typing import Optional
from abc import ABC, abstractmethod

class Command(ABC):
    """Abstract Base Command."""
    @abstractmethod
    def execute(self, engine) -> None:
        pass


class ClickCommand(Command):
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def execute(self, engine) -> None:
        engine.handle_click(self.x, self.y)


class WaitCommand(Command):
    def __init__(self, ms: int):
        self.ms = ms

    def execute(self, engine) -> None:
        engine.advance_clock(self.ms)


class PrintBoardCommand(Command):
    def execute(self, engine) -> None:
        engine.print_board()


class CommandParser:
    """Responsible for translating raw text lines into executable Command objects."""
    @staticmethod
    def parse_line(line: str) -> Optional[Command]:
        parts = line.strip().split()
        if not parts:
            return None
        
        cmd_type = parts[0]
        
        if cmd_type == "click" and len(parts) == 3:
            try:          
                return ClickCommand(int(parts[1]), int(parts[2]))
            except ValueError as e:
                return e
        elif cmd_type == "wait" and len(parts) == 2:
            try:
                return WaitCommand(int(parts[1]))
            except ValueError as e:
                return e
            
            
        elif " ".join(parts) == "print board":
            return PrintBoardCommand()
            
        return None