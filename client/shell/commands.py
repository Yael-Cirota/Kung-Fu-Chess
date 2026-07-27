"""Parses one line of shell input into a `Command` plus the outbound wire
message it builds, keyed off a dispatch table rather than an if/elif chain
(the shape `MessageDispatcher` was hand-edited into server-side - see
tests/server/presentation/test_dispatcher.py). `QUIT` and `HELP` have no
wire message: they are handled entirely by `Shell` and map to `None` here."""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional

from protocol import messages as m


class Command(Enum):
    LOGIN = "login"
    REGISTER = "register"
    PLAY = "play"
    CANCEL = "cancel"
    CREATE_ROOM = "create-room"
    JOIN_ROOM = "join-room"
    LEAVE_ROOM = "leave-room"
    HELP = "help"
    QUIT = "quit"


class CommandError:
    UNKNOWN_COMMAND = "unknown_command"
    WRONG_ARG_COUNT = "wrong_arg_count"


@dataclass(frozen=True)
class ParseResult:
    ok: bool
    command: Optional[Command] = None
    message: Optional[object] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class _Spec:
    arg_count: int
    build: Callable[[List[str]], Optional[object]]


_SPECS = {
    Command.LOGIN: _Spec(2, lambda args: m.LoginRequest(username=args[0], password=args[1])),
    Command.REGISTER: _Spec(2, lambda args: m.RegisterRequest(username=args[0], password=args[1])),
    Command.PLAY: _Spec(0, lambda args: m.PlayRequest()),
    Command.CANCEL: _Spec(0, lambda args: m.CancelQueueRequest()),
    Command.CREATE_ROOM: _Spec(0, lambda args: m.CreateRoomRequest()),
    Command.JOIN_ROOM: _Spec(1, lambda args: m.JoinRoomRequest(room_id=args[0])),
    Command.LEAVE_ROOM: _Spec(1, lambda args: m.LeaveRoomRequest(room_id=args[0])),
    Command.HELP: _Spec(0, lambda args: None),
    Command.QUIT: _Spec(0, lambda args: None),
}

_NAME_TO_COMMAND = {command.value: command for command in Command}


def parse(line: str) -> ParseResult:
    """Pure: no I/O, no session state. `Shell` supplies room-id/session
    context by construction, not by this parser reaching back into it."""
    words = line.strip().split()
    if not words:
        return ParseResult(ok=False, error=CommandError.UNKNOWN_COMMAND)

    command = _NAME_TO_COMMAND.get(words[0].lower())
    if command is None:
        return ParseResult(ok=False, error=CommandError.UNKNOWN_COMMAND)

    spec = _SPECS[command]
    args = words[1:]
    if len(args) != spec.arg_count:
        return ParseResult(ok=False, command=command, error=CommandError.WRONG_ARG_COUNT)

    return ParseResult(ok=True, command=command, message=spec.build(args))
