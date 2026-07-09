# Github repository:
# https://github.com/Yael-Cirota/Kung-Fu-Chess

import sys
from kfchess.texttests.script_runner import ScriptRunner

def run_application(vpl_input: str):
    """Core application logic orchestrator."""
    output = ScriptRunner().run(vpl_input)
    sys.stdout.write(output)

def main():
    """Entry point - Only handles OS-level I/O."""
    vpl_input = sys.stdin.read()
    run_application(vpl_input)

if __name__ == "__main__":  # pragma: no cover
    main()