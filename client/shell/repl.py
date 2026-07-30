"""The only place in client/shell that touches input()/print() - Shell stays
fully unit-testable against a FakeClientLink because none of its methods
block on stdin. `run_repl` returns whenever the user quits or a room becomes
active (client/main.py then either exits or hands off to the cv2 game
loop, and calls run_repl again once that game ends)."""

from client.shell.shell import Shell


def run_repl(shell: Shell) -> bool:  # pragma: no cover - blocks on real stdin
    """Returns True if the user asked to quit, False if a room became
    active and the caller should hand off to the game loop."""
    print("Kung-Fu-Chess client. Type 'help' for commands.")
    while True:
        for line in shell.drain_notifications():
            print(line)
        if shell.active_room is not None:
            return False

        try:
            line = input("> ")
        except EOFError:
            return True

        outcome = shell.handle_command(line)
        for output_line in outcome.lines:
            print(output_line)
        if outcome.should_quit:
            return True
