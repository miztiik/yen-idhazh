"""Exec the native process only after armed protection still identifies its expected parent."""

import os
import shutil
import sys
from pathlib import Path


def parent_bound_command(command: list[str]) -> list[str]:
    wrapper = shutil.which("setpriv")
    if sys.platform != "linux" or wrapper is None:
        raise OSError("Native parent-death protection requires Linux setpriv.")
    return [
        wrapper,
        "--pdeathsig=KILL",
        "--",
        sys.executable,
        str(Path(__file__).resolve()),
        str(os.getpid()),
        *command,
    ]


def main() -> None:
    try:
        expected_parent = int(sys.argv[1])
        command = sys.argv[2:]
        # setpriv has armed SIGKILL before this same-PID bootstrap starts.
        if expected_parent <= 0 or os.getppid() != expected_parent or not command:
            raise SystemExit(1)
        os.execv(command[0], command)
    except (OSError, ValueError, IndexError):
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
