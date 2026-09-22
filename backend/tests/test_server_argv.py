"""Does every committed entry stand up the server it stood up yesterday?

Four questions the command-line builder has to answer, and each one can fail.
The golden files hold every flag and its value for every committed model file,
captured before the file started spelling llama-server's own flags - so a wrong
flag in a rewritten file is a red test rather than a run that starts on
somebody else's settings.

The golden is a mapping rather than the flat list, because the order flags
arrive in changes nothing about the process llama-server runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, read_text

from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.llm.server import SETTING_KEYS, server_argv
from utilities import capture_server_argv

pytestmark = pytest.mark.contract

GOLDEN_DIR = FIXTURES_DIR / "server-argv"

#: The values that decide which token is drawn. None of them is a server flag,
#: so none of them may appear on a command line under any spelling.
SAMPLING_KEYS = ("temperature", "top_p", "seed")


def model_files() -> list[Path]:
    """Every committed model file, which is bounded by how many models this
    project supports rather than by what the archive has piled up
    (`CLAUDE.md` Guardrail #12)."""
    return sorted((CONFIG_DIR / "models").glob("*.json"))


def model_id(path: Path) -> str:
    return path.stem


def entry_with(server: dict[str, Any]) -> Any:
    """The committed entry with its server block replaced, so a fixture case is
    one edit away from a file a person really wrote."""
    raw = json.loads(read_text(CONFIG_DIR / "models" / "qwen3.5-9b-q4km.json"))
    raw["summarize"]["server"] = server
    return ModelsConfig.model_validate(raw).summarize


@pytest.mark.parametrize("path", model_files(), ids=model_id)
def test_every_committed_entry_builds_the_golden_command_line(path: Path) -> None:
    """The command line is pinned whole, so a moved flag is a reviewable diff.

    Regenerate with `python backend/utilities/capture_server_argv.py` and read
    the diff - that is the review, and it is the only thing that can say a
    rewritten model file moved a flag nobody meant to move.
    """
    golden = GOLDEN_DIR / path.name
    assert golden.exists(), (
        f"{path.name} has no golden command line - run backend/utilities/capture_server_argv.py"
    )

    config = ModelsConfig.model_validate_json(read_text(path))

    assert capture_server_argv.command_line(config) == json.loads(read_text(golden))


def test_a_sampling_value_in_the_server_block_reaches_the_command_line() -> None:
    """The blocks are the control, and this is what proves it is structural.

    llama-server would accept `temperature` on its command line, so nothing in
    the builder refuses one - it emits whatever the block holds. What keeps a
    sampling value off the command line is that it lives in the other block and
    the builder never reads that one. A check that could be kept out of step
    with the builder is replaced by where the values sit.
    """
    strayed = entry_with({"--ctx-size": 4096, "temperature": 0.7})
    argv = server_argv(
        binary=Path("bin/llama-server"),
        weights=Path("var/models/weights.gguf"),
        model=strayed,
        server=strayed.server,
    )
    assert "temperature" in argv, "the builder emits the block verbatim, whatever is in it"
    assert "0.7" in argv


@pytest.mark.parametrize("path", model_files(), ids=model_id)
def test_no_committed_entry_puts_a_sampling_value_on_the_command_line(path: Path) -> None:
    """Every committed file keeps its sampling in the block nothing emits."""
    golden: dict[str, Any] = json.loads(read_text(GOLDEN_DIR / path.name))
    config = ModelsConfig.model_validate_json(read_text(path))

    for name in SAMPLING_KEYS:
        assert name in config.summarize.request, f"{name} left the request block"
        assert SETTING_KEYS[name] not in golden
        assert name not in golden


def test_a_flag_no_reader_of_ours_names_is_emitted_unchanged() -> None:
    """An option this project has never heard of reaches the server as written.

    That is the whole point of the block: naming one more llama-server option is
    a key in the model file and no edit anywhere else. A flag this build does
    not accept is refused by llama-server at start-up, which names it.
    """
    unknown = entry_with({"--ctx-size": 4096, "--top-k": 40, "--mirostat": None})
    argv = server_argv(
        binary=Path("bin/llama-server"),
        weights=Path("var/models/weights.gguf"),
        model=unknown,
        server=unknown.server,
    )
    assert argv[argv.index("--top-k") + 1] == "40"
    assert "--mirostat" in argv, "a null value is a bare flag"
    assert "None" not in argv, "a null value writes no argument beside its flag"
