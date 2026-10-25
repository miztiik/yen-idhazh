"""Does the command-line builder emit explicitly supplied server settings unchanged?"""

from __future__ import annotations

from pathlib import Path

import pytest
from contracts._fixtures import entry_with

from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.llm.server import server_argv

pytestmark = pytest.mark.contract

def test_a_sampling_value_in_the_server_block_reaches_the_command_line() -> None:
    """The blocks are the control, and this is what proves it is structural.

    llama-server would accept `temperature` on its command line, so nothing in
    the builder refuses one - it emits whatever the block holds. What keeps a
    sampling value off the command line is that it lives in the other block and
    the builder never reads that one. A check that could be kept out of step
    with the builder is replaced by where the values sit.
    """
    strayed = ModelsConfig.model_validate(
        entry_with(server={"--ctx-size": 4096, "temperature": 0.7})
    ).summarizer
    argv = server_argv(
        binary=Path("bin/llama-server"),
        weights=Path("var/models/weights.gguf"),
        model=strayed,
        server=strayed.server,
        port=8080,
    )
    assert "temperature" in argv, "the builder emits the block verbatim, whatever is in it"
    assert "0.7" in argv


def test_a_flag_no_reader_of_ours_names_is_emitted_unchanged() -> None:
    """An option this project has never heard of reaches the server as written.

    That is the whole point of the block: naming one more llama-server option is
    a key in the model file and no edit anywhere else. A flag this build does
    not accept is refused by llama-server at start-up, which names it.
    """
    unknown = ModelsConfig.model_validate(
        entry_with(server={"--ctx-size": 4096, "--top-k": 40, "--mirostat": None})
    ).summarizer
    argv = server_argv(
        binary=Path("bin/llama-server"),
        weights=Path("var/models/weights.gguf"),
        model=unknown,
        server=unknown.server,
        port=8080,
    )
    assert argv[argv.index("--top-k") + 1] == "40"
    assert "--mirostat" in argv, "a null value is a bare flag"
    assert "None" not in argv, "a null value writes no argument beside its flag"
