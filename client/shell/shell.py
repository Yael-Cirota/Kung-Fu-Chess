"""Synchronous, fully-testable REPL brain: takes a line of user input,
optionally sends a wire message, and separately turns queued server
notifications into printable lines. `repl.py` is the only thing that
actually calls input()/print() - this class never touches either, so it is
tested with a FakeClientLink instead of real stdin/stdout."""

from dataclasses import dataclass, field
from typing import List, Optional

from client.net.client_link import ClientLink
from client.shell.commands import Command, CommandError, parse
from protocol import messages as m

HELP_TEXT = (
    "Commands: login <user> <pass> | register <user> <pass> | play | cancel | "
    "create-room | join-room <room_id> | leave-room <room_id> | help | quit"
)

_NOTIFICATION_FORMATTERS = {
    m.AuthOk: lambda msg: f"Logged in as {msg.username} (elo {msg.elo})",
    m.AuthError: lambda msg: f"Auth failed: {msg.reason}",
    m.MatchFound: lambda msg: f"Match found! Room {msg.room_id}, you are {msg.color}",
    m.MatchTimedOut: lambda msg: "Matchmaking timed out, still searching.",
    m.RoomCreated: lambda msg: f"Room created: {msg.room_id}",
    m.RoomJoined: lambda msg: f"Joined room {msg.room_id} as {msg.role} (players: {', '.join(msg.players)})",
    m.RoomError: lambda msg: f"Room error: {msg.reason}",
}


@dataclass(frozen=True)
class ActiveRoom:
    room_id: str
    role: str


@dataclass(frozen=True)
class CommandOutcome:
    lines: List[str] = field(default_factory=list)
    should_quit: bool = False


class Shell:
    def __init__(self, link: ClientLink):
        self._link = link
        self.active_room: Optional[ActiveRoom] = None

    def handle_command(self, line: str) -> CommandOutcome:
        result = parse(line)
        if not result.ok:
            return CommandOutcome(lines=[self._error_line(result.error, result.command)])

        if result.command is Command.QUIT:
            return CommandOutcome(should_quit=True)
        if result.command is Command.HELP:
            return CommandOutcome(lines=[HELP_TEXT])

        self._link.send(result.message)
        return CommandOutcome()

    @staticmethod
    def _error_line(error: str, command: Optional[Command]) -> str:
        if error == CommandError.WRONG_ARG_COUNT:
            return f"Wrong number of arguments for '{command.value}'. {HELP_TEXT}"
        return f"Unknown command. {HELP_TEXT}"

    def drain_notifications(self) -> List[str]:
        lines = []
        for message in self._link.drain_shell():
            self._apply(message)
            formatter = _NOTIFICATION_FORMATTERS.get(type(message))
            if formatter is not None:
                lines.append(formatter(message))
        return lines

    def _apply(self, message: object) -> None:
        if isinstance(message, m.MatchFound):
            self.active_room = ActiveRoom(room_id=message.room_id, role=message.color)
        elif isinstance(message, m.RoomJoined):
            self.active_room = ActiveRoom(room_id=message.room_id, role=message.role)

