"""Does the command-line builder emit explicitly supplied server settings unchanged?"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from contracts._fixtures import entry_with
from pydantic import ValidationError
from support.paths import CONFIG_DIR

from idhazh.contracts.knobs.models import COMPANION_PATH_PATTERN, CompanionFile, ModelsConfig
from idhazh.fingerprint import DIGESTED_FLAGS, runtime_flags_spelling
from idhazh.llm.server import SETTING_KEYS, server_argv, setting, window
from utilities import model_refs

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("filename", ["mtp-model.gguf", "MTP/mtp-model.gguf"])
def test_companion_paths_match_between_contract_download_and_launch(filename: str) -> None:
    companion = {
        "repo": "models/Model-GGUF",
        "revision": "0" * 40,
        "file": filename,
        "sha256": "b" * 64,
        "flag": "--spec-draft-model",
    }
    model = ModelsConfig.model_validate(entry_with(companion_files=[companion])).summarizer
    weights = Path(model_refs.MODELS_DIR) / model.file
    argv = server_argv(
        binary=Path("bin/llama-server"),
        weights=weights,
        model=model,
        server=model.server,
        port=8080,
    )
    assert model_refs.COMPANION_PATH_RE.pattern == COMPANION_PATH_PATTERN
    assert model_refs.COMPANION_PATH_RE.fullmatch(filename)
    assert argv[argv.index("--spec-draft-model") + 1] == f"{model_refs.MODELS_DIR}/{filename}"
    assert CompanionFile.model_validate(companion).model_dump()["file"] == filename


@pytest.mark.parametrize(
    "filename",
    [
        "../mtp.gguf",
        "MTP/../mtp.gguf",
        "/MTP/mtp.gguf",
        "C:/MTP/mtp.gguf",
        "MTP\\mtp.gguf",
        "MTP//mtp.gguf",
        "MTP/./mtp.gguf",
        "MTP/.hidden",
        "MTP/mtp.gguf\n",
        "MTP/$(id).gguf",
        "MTP/mtp model.gguf",
    ],
)
def test_companion_path_readers_refuse_unsafe_segments(filename: str) -> None:
    with pytest.raises(ValidationError, match="file"):
        CompanionFile.model_validate(
            {"repo": "models/Model-GGUF", "revision": "0" * 40, "file": filename, "sha256": "b" * 64}
        )
    assert model_refs.COMPANION_PATH_RE.fullmatch(filename) is None


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


def test_long_parallel_and_load_mode_record_without_rewriting_runtime_argv() -> None:
    server = {"--ctx-size": 4096, "--parallel": 2, "--load-mode": "mmap+mlock", "--jinja": None}
    model = ModelsConfig.model_validate(entry_with(server=server)).summarizer
    before = list(server.items())
    argv = server_argv(
        binary=Path("llama-server"), weights=Path("weights.gguf"),
        model=model, server=server, port=8080,
    )
    assert setting(server, "n_parallel") == 2
    assert setting(server, "load_mode") == "mmap+mlock"
    assert argv[8:] == [
        "--ctx-size", "4096", "--parallel", "2", "--load-mode", "mmap+mlock", "--jinja"
    ]
    assert list(server.items()) == before


def test_short_context_spelling_supplies_the_same_window() -> None:
    assert setting({"-c": 4096}, "n_ctx") == window({"-c": 4096}) == 4096


def test_every_consumed_spelling_in_recorded_help_reaches_its_existing_recorded_key() -> None:
    from idhazh.llm.server_flags import RECORDED_SERVER_HELP, read_recorded_server_help

    pin = json.loads((CONFIG_DIR / "llama-cpp-pin.json").read_text(encoding="ascii"))
    assert RECORDED_SERVER_HELP == f"{pin['build']}-llama-server-help.txt"
    consumed = set(SETTING_KEYS.values()) | set(DIGESTED_FLAGS)
    covered: set[str] = set()
    for line in read_recorded_server_help().splitlines():
        if not line.startswith("-"):
            continue
        flags: list[str] = []
        for token in line.split():
            if not token.startswith("-"):
                break
            flags.append(token.removesuffix(","))
        keys = consumed.intersection(flags)
        if not keys:
            continue
        covered.update(keys)
        # Several recorded bare switches on one line are opposing choices.
        for canonical in keys:
            for spelling in flags if len(keys) == 1 else [canonical]:
                value = 7 if len(keys) == 1 else None
                server = {spelling: value}
                for name, key in SETTING_KEYS.items():
                    if key == canonical:
                        assert setting(server, name) == value, spelling
                if canonical in DIGESTED_FLAGS:
                    actual = runtime_flags_spelling(server)
                    assert set(actual) == set(DIGESTED_FLAGS)
                    assert actual[canonical] == ("set" if value is None else str(value)), spelling
                    for opposite in keys - {canonical}:
                        assert actual[opposite] == "runtime-default"
    assert covered == consumed


@pytest.mark.parametrize(
    "server",
    [
        {"-np": 2, "--parallel": 2},
        {"--ctx-checkpoints": 1, "--swa-checkpoints": 1},
        {"--jinja": None, "--no-jinja": None},
    ],
)
def test_shared_readers_refuse_duplicate_aliases_and_opposing_switches(
    server: dict[str, int | None],
) -> None:
    for read in (lambda: setting(server, "n_parallel"), lambda: runtime_flags_spelling(server)):
        with pytest.raises(ValueError, match=r"multiple spellings|opposing server switches"):
            read()


@pytest.mark.parametrize(
    ("text", "consumed", "reason"),
    [
        ("--parallel N  slots\n", frozenset({"-np"}), "declares no consumed flags"),
        ("-np, --parallel N  slots\n-np N  repeated\n", frozenset({"-np"}), "ambiguous"),
        ("--parallel N  other\n-np, --parallel N  slots\n", frozenset({"-np"}), "ambiguous"),
        ("--jinja, -j  template\n", frozenset({"--jinja"}), "unsupported bare"),
        ("-np, --parallel N  slots\n", frozenset({"-np", "--parallel"}), "ambiguous"),
    ],
)
def test_an_unsupported_or_ambiguous_help_contract_is_refused(
    text: str, consumed: frozenset[str], reason: str,
) -> None:
    from idhazh.llm.server_flags import parse_server_help

    with pytest.raises(ValueError, match=reason):
        parse_server_help(text, consumed)
