"""Write one golden command line per committed model file.

Run it, commit what it writes, and `backend/tests/test_server_argv.py` then
holds every committed entry to the exact process it stands up. The list is
built from the committed entry rather than from a literal, so a flag that
reaches the server reaches the golden file too.

    python backend/utilities/capture_server_argv.py

The golden is a mapping from flag to value rather than the flat list, because
what llama-server runs is the set of flags and their values - the order they
arrive in changes nothing. A mapping also reads in a diff as the thing it
mirrors, the `server` block of the model file.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.llm.server import server_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "config" / "models"
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "server-argv"

#: Fixed inputs, so the only thing that moves between two captures is the entry
#: and the builder. POSIX separators, because a captured Windows path would put
#: a backslash in a committed file (`CLAUDE.md` section 2).
BINARY = Path("bin/llama-server")
WEIGHTS = Path("var/models/weights.gguf")
PORT = 8080


def _is_a_flag(token: str) -> bool:
    """A leading dash is a flag unless the token is a negative number."""
    if not token.startswith("-"):
        return False
    try:
        float(token)
    except ValueError:
        return True
    return False


def flags_of(argv: Sequence[str]) -> dict[str, str | None]:
    """Every flag the command line carries, with its argument or None.

    The binary is dropped - it is the path this capture chose, not a flag. A
    repeated flag raises rather than overwriting, because two values for one
    flag is a builder fault and the last one silently winning hides it.
    """
    flags: dict[str, str | None] = {}
    rest = list(argv[1:])
    while rest:
        token = rest.pop(0)
        if not _is_a_flag(token):
            raise ValueError(f"{token} is an argument with no flag in front of it")
        if token in flags:
            raise ValueError(f"{token} is on the command line twice")
        flags[token] = None if not rest or _is_a_flag(rest[0]) else rest.pop(0)
    return flags


def command_line(config: ModelsConfig) -> dict[str, str | None]:
    """The flags the summarize entry stands its server up with.

    The weights path is written back with POSIX separators. It is the only
    argument this capture builds from a `Path`, and a committed file carries no
    backslash (`CLAUDE.md` section 2).
    """
    entry = config.summarize
    flags = flags_of(
        server_argv(
            binary=BINARY,
            weights=WEIGHTS,
            model=entry,
            server=entry.server,
            port=PORT,
        )
    )
    flags["--model"] = WEIGHTS.as_posix()
    return flags


def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(MODELS_DIR.glob("*.json")):
        config = ModelsConfig.model_validate_json(path.read_text(encoding="utf-8"))
        written = GOLDEN_DIR / path.name
        written.write_text(
            json.dumps(command_line(config), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"wrote {written.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
