"""Does the committed config validate, and is every tunable value a knob?"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

import pytest
from pydantic import StrictBool, ValidationError
from support.paths import CONFIG_DIR, REPO_ROOT, read_text

from idhazh import config
from idhazh.classify import dag
from idhazh.contracts import app_config
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.appearance_config import AppearanceConfig, ChartConfig
from idhazh.contracts.knobs.console import ConsoleConfig
from idhazh.contracts.knobs.evaluation import DriftConfig, EvaluationConfig
from idhazh.contracts.knobs.extract import ElementsConfig
from idhazh.contracts.knobs.finetune import FinetuneConfig
from idhazh.contracts.knobs.ledger import LedgerConfig
from idhazh.contracts.knobs.model_server import ModelServerConfig, is_loopback, resolve_base_url
from idhazh.contracts.knobs.observability import LoggingConfig, ObservabilityConfig
from idhazh.contracts.knobs.retention import PAGES_HARD_CAP_MB, RetentionConfig
from idhazh.contracts.knobs.similarity import SimilarityConfig
from idhazh.contracts.knobs.text_analysis import TextAnalysisConfig
from idhazh.contracts.knobs.ui import UiConfig, VisualSide
from idhazh.extract import TOKENS_PER_WORD
from idhazh.llm.server import DEFAULT_MAX_TOKENS, response_limit, window
from idhazh.measured import PROMPT_OVERHEAD_TOKENS as _PROMPT_OVERHEAD
from idhazh.measured import WORST_TOKENS_A_WORD as _WORST_TOKENS

from ._fixtures import CONFIG_FILES, CONFIG_NOT_OWNED, committed_models, copy_config

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("name", sorted(CONFIG_FILES), ids=lambda n: n)
def test_config_file_validates(name: str) -> None:
    CONFIG_FILES[name].from_json(read_text(CONFIG_DIR / name))


@pytest.mark.parametrize("name", sorted(CONFIG_FILES), ids=lambda n: n)
def test_the_config_file_names_every_knob_it_owns(name: str) -> None:
    """`config/` is the one source, so a knob absent from it is a knob nobody sees.

    A default in a Pydantic model keeps a fresh clone running
    (`test_a_fresh_clone_runs_on_the_defaults`); it does not tell the person
    reading `config/` that the knob exists. Measured 2026-09-17 before this
    landed: `idhazh.json` named 16 fewer knobs than it owns and
    `appearance.json` 2 fewer, while the other four named all of theirs.

    **Owns, not declares.** Three blocks sit on two models and only one file is
    their source; `CONFIG_NOT_OWNED` names the other side. Padding a legacy
    block out to its model would give one knob two answers in two files.

    Leaf paths rather than top-level keys, because a default nested inside a
    list entry is the shape that hides best: a block-level check cannot see one
    that a list entry omits.
    """
    model = CONFIG_FILES[name]
    committed = read_text(CONFIG_DIR / name)
    named = set(_leaf_paths(json.loads(committed)))
    complete = set(_leaf_paths(json.loads(model.from_json(committed).to_json())))
    not_ours = CONFIG_NOT_OWNED.get(name, frozenset())
    owned = {path for path in complete if not _under(path, not_ours)}

    assert owned <= named, (
        f"config/{name} does not name {sorted(owned - named)}. "
        f"Regenerate it through {model.__name__} rather than editing by hand, "
        "and drop back anything CONFIG_NOT_OWNED says another file owns."
    )


def _under(path: str, prefixes: frozenset[str]) -> bool:
    """Whether a dotted path is, or sits inside, one of the named blocks.

    `[` as well as `.`, because a list element's address is `key[0]` and an
    exclusion written for `key` has to reach it. Without that, `model_cdn_origins`
    was excluded and `model_cdn_origins[0]` was not.
    """
    return any(path == p or path.startswith(f"{p}.") or path.startswith(f"{p}[") for p in prefixes)


def _leaf_paths(node: object, path: str = "") -> list[str]:
    """Every leaf in a payload, addressed. A list index is part of the address."""
    if isinstance(node, dict):
        return [
            leaf
            for key, value in node.items()
            for leaf in _leaf_paths(value, f"{path}.{key}" if path else str(key))
        ]
    if isinstance(node, list):
        return [leaf for i, item in enumerate(node) for leaf in _leaf_paths(item, f"{path}[{i}]")]
    return [path]


def test_a_fresh_clone_runs_on_the_defaults() -> None:
    """The committed config selects the model; unrelated knobs retain defaults."""
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    minimal = AppConfig.model_validate({"models_file": committed.models_file})
    assert (CONFIG_DIR / minimal.models_file).is_file()


def test_source_code_does_not_select_a_model_when_the_pointer_is_missing() -> None:
    with pytest.raises(ValidationError, match="models_file"):
        AppConfig.model_validate({})


def test_a_trial_case_requires_a_trial_state_root() -> None:
    with pytest.raises(ValidationError, match=r"run\.trial_case_dirname requires"):
        AppConfig.model_validate(
            {"models_file": "models/test.json", "run": {"trial_case_dirname": "one-case"}}
        )


def test_a_trial_case_may_not_reuse_a_ledger_root(tmp_path: Path) -> None:
    """The case slug is checked against the state roots the ledger registry owns."""
    copy_config(tmp_path)
    path = tmp_path / "config" / "idhazh.json"
    raw = json.loads(read_text(path))
    raw["run"]["trial_state_dirname"] = "pipeline-tests"
    raw["run"]["trial_case_dirname"] = "raw"
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8", newline="\n")

    with pytest.raises(ValueError, match=r"run\.trial_case_dirname .*'raw'"):
        config.load(path.parent)


def test_the_config_refuses_a_pages_cap_above_the_platforms_own() -> None:
    """The direction the bound exists for. A cap config can raise is not a cap.

    Guardrail #2 says the budget is the platform and not a preference. That held while
    the 1024 was a module constant only because nobody edited it, which is not a
    control. It is a control now: the schema refuses the edit.
    """
    with pytest.raises(ValidationError):
        RetentionConfig(pages_hard_cap_mb=PAGES_HARD_CAP_MB + 1)

    raw = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    raw["retention"]["pages_hard_cap_mb"] = 2048
    with pytest.raises(ValidationError, match="pages_hard_cap_mb"):
        AppConfig.model_validate(raw)


def test_the_alarm_point_sits_below_the_pages_cap() -> None:
    """One reports and one stops, so an alarm at or above the cap never gets to warn.

    The two are set independently and the contract does not tie them together, so
    the committed pair is the only place a swapped pair would show.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).retention
    assert committed.site_budget_mb < committed.pages_hard_cap_mb


@pytest.mark.parametrize(
    ("declared", "fault"),
    [
        ("127.0.0.1:8080", "no scheme"),
        ("http://:8080", "no host"),
        ("http://a-box", "no port"),
        ("http://a-box:99999", "a port above 65535"),
        ("http://a-box:eighty", "a port that is not a number"),
        ("http://a-box:8080/v1", "a path"),
    ],
    ids=lambda case: case if " " in str(case) else "-",
)
def test_an_address_that_is_not_a_scheme_a_host_and_a_port_is_refused(
    declared: str, fault: str
) -> None:
    """Six ways to write an address a run cannot use, refused where it is declared.

    Every string here is the test's own, never the committed value: a case read
    out of `config/idhazh.json` would stop testing the grammar on the day an
    operator points the run at their own server (`CLAUDE.md` section 13).

    The port is the one a reader would not expect to be required. It is, because
    the server command reads the port back out of this value to bind with, and
    `http://a-box` parses cleanly while naming no port at all. A path is refused
    rather than dropped: the other four routes are built by replacing the whole
    path, so a prefix would hold on one of them and vanish from the rest, and a
    wrong address is worse than a refused one.
    """
    with pytest.raises(ValidationError):
        ModelServerConfig(base_url=declared)

    with pytest.raises(ValueError, match=r"model_server\.base_url"):
        resolve_base_url(declared)


def test_an_address_a_run_can_use_is_taken_and_tidied() -> None:
    """A trailing slash is an operator's habit, not a second address.

    Dropped rather than refused, because nothing downstream can tell the two
    apart and refusing would cost an operator a round trip to learn it. The
    stored value is the tidied one, so every later reader sees one spelling.
    """
    assert ModelServerConfig(base_url="http://10.0.0.5:9001/").base_url == "http://10.0.0.5:9001"
    assert ModelServerConfig(base_url="https://a-box:8443").base_url == "https://a-box:8443"


@pytest.mark.parametrize(
    "declared",
    [
        "http://mirror.example",
        "https://mirror.example/",
        "https://mirror.example/x?y=1",
        "https://mirror.example/it's",
    ],
)
def test_an_add_on_address_the_engine_cannot_join_onto_is_refused(declared: str) -> None:
    """The engine appends `/<version>/<platform>/<name>`, and the value lands in a `SET` statement."""
    with pytest.raises(ValidationError, match=r"engine_extension_repository"):
        LedgerConfig(engine_extension_repository=declared)


def test_an_add_on_mirror_under_a_path_is_taken_as_written() -> None:
    """The engine appends its own segments, so a prefix with a path is still an address."""
    mirror = "https://mirror.example/duckdb"
    assert LedgerConfig(engine_extension_repository=mirror).engine_extension_repository == mirror


@pytest.mark.parametrize(
    ("declared", "this_machine"),
    [
        ("http://127.0.0.1:8080", True),
        ("http://127.0.0.5:8080", True),
        ("http://[::1]:8080", True),
        ("http://localhost:8080", True),
        ("http://LocalHost:8080", True),
        ("http://192.168.1.20:9090", False),
        ("http://a-box:8080", False),
        ("http://ip6-localhost:8080", False),
    ],
)
def test_only_a_loopback_literal_or_localhost_answers_for_this_machine(
    declared: str, this_machine: bool
) -> None:
    """Who may answer for this machine, settled without asking a resolver.

    A name lookup would make the answer depend on something nobody wrote down,
    and a hosts entry can point `127.0.0.1` at a tunnel to a second machine - so
    `a-box` is not this machine even on a host where it resolves to one, and
    `ip6-localhost` is a Debian hosts convention rather than a reserved name.
    `localhost` is in because RFC 6761 reserves it, and the mixed-case spelling
    is here because the host is read as a host rather than off the authority.

    The reader is `runtime_build`, which writes what this answers into the run
    record, so a wrong yes is a published falsehood rather than a failed call.
    """
    assert is_loopback(ModelServerConfig(base_url=declared).base_url) is this_machine


@pytest.mark.parametrize(
    "declared",
    [
        "http://192.168.1.20:3020",
        "http://a-box:3020",
        "https://analysis.example:3020",
        "http://127.0.0.1",
        "http://127.0.0.1:3020/api",
        "127.0.0.1:3020",
    ],
)
def test_article_text_goes_to_an_analysis_service_on_this_machine_only(declared: str) -> None:
    """The recipient of article text is an address a person reads in a diff (Guardrail #11).

    A host that is not loopback is refused where the address is declared, and so
    is anything that is not a scheme, a host and a port: the service the digest
    job starts listens on the runner's own loopback and nowhere else. Every
    string is the test's own, never the committed value.
    """
    with pytest.raises(ValidationError, match=r"text_analysis\.base_url"):
        TextAnalysisConfig(base_url=declared)


def test_the_text_analysis_address_is_the_one_the_service_listens_on() -> None:
    """Two committed files name one port and neither reads the other.

    A port edited in only one of them sends every article to a port nothing
    listens on, and the run degrades quietly to the regex-only table.
    """
    listener = json.loads(read_text(CONFIG_DIR / "text-analysis" / "settings.json"))["listener"]
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).text_analysis

    for address in (committed.base_url, TextAnalysisConfig().base_url):
        declared = urlsplit(address)
        assert (declared.hostname, declared.port) == (listener["host"], listener["port"])


@pytest.mark.parametrize("language", ["EN", "en-US", "e", "english", ""])
def test_the_text_analysis_language_is_a_bare_lowercase_code(language: str) -> None:
    """One value names the wheel the sidecar installs and the language every request asks for.

    A workflow step reads it as a key, so it is a code a step never has to quote.
    """
    with pytest.raises(ValidationError, match="language"):
        TextAnalysisConfig(language=language)


def test_a_service_label_becomes_an_entity_a_place_or_not_a_quantity_and_nothing_else() -> None:
    """A use nobody defined is refused, never ignored.

    Ignoring it would turn a misspelt use into a label that silently does nothing.
    """
    with pytest.raises(ValidationError, match="label_kinds"):
        ElementsConfig.model_validate({"label_kinds": {"PERSON": "person"}})


#: What the summarize prompt costs before a word of the article reaches it, and
#: the hardest any published item has tokenized. Both records, their method and
#: what to do when either moves are in `idhazh.measured`.
PROMPT_OVERHEAD_TOKENS: Final = int(_PROMPT_OVERHEAD.value)

WORST_TOKENS_A_WORD: Final = _WORST_TOKENS.value


def _worst_sequence_tokens(committed: AppConfig) -> tuple[int, int]:
    """The longest prompt the cap allows, and that prompt plus a full answer.

    One derivation because the serving window and the training window have to
    agree about it. The cap is spent as words at `TOKENS_PER_WORD`, so an
    article whose prose tokenizes harder than that overruns the budget its own
    cap gave it, and both windows have to cover the article that did rather than
    the one that behaved.

    The answer term is the summarizer's response limit: the reply has no length
    bound of its own, so the most it can write is what the model file lets a
    request run to.
    """
    cut_words = int(committed.extract.truncation_cap_tokens / TOKENS_PER_WORD)
    worst_prompt = PROMPT_OVERHEAD_TOKENS + int(cut_words * WORST_TOKENS_A_WORD)
    return worst_prompt, worst_prompt + response_limit(committed_models().summarizer.sampling)


def test_the_longest_article_the_cap_allows_still_fits_the_window() -> None:
    """Keep the configured article cap and reply budget within the model window.

    Use measured token expansion because the extraction cap estimates tokens
    from word count and can undercount the rendered prompt.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    models = committed_models()
    n_ctx = window(models.summarizer.server)
    worst_prompt, worst_sequence = _worst_sequence_tokens(committed)
    answer = response_limit(models.summarizer.sampling)

    assert worst_sequence <= n_ctx, (
        f"the longest article extract.truncation_cap_tokens "
        f"({committed.extract.truncation_cap_tokens}) lets through is "
        f"{worst_prompt} prompt tokens, and {answer} of answer "
        f"puts the sequence at {worst_sequence} against a window of {n_ctx}. "
        "Raise --ctx-size in models.summarizer.server beside the cap, or lower the cap."
    )


def _worst_one_call_sequence_tokens(committed: AppConfig) -> tuple[int, int]:
    """The digest call's prompt at the cap, and the whole sequence behind it.

    A second derivation and not a widening of the one above, because the two
    paths render different prompts. The standalone summarizer sends one system
    turn and the article. The digest call sends its own system turn and the
    article, and then writes up to the model file's response limit. The tables
    of figures ride behind the article only where the work stage finds they fit:
    it reads an item without them otherwise, so the worst case the window has to
    hold is the article alone.

    **The arithmetic itself is `classify.dag`'s and this is the gate over it.**
    It used to be written out here, which put the number the production path
    never checked and the number this file asserts in two places - and two
    derivations of one quantity disagree the first time a term moves. What stays
    here is the cap, the knob and the window, all three read from `config/`
    (Guardrail #6).
    """
    cap = committed.extract.truncation_cap_tokens
    sampling = committed_models().summarizer.sampling
    return (
        dag.prompt_tokens(cap, table_bytes=0),
        dag.call_tokens(cap, table_bytes=0, sampling=sampling),
    )


def test_the_call_fits_the_window_at_the_cap() -> None:
    """Preserve admission under the existing pre-call estimate.

    This does not certify a complete continuation with finalized evidence or
    an explicit response limit. Those are diagnosed from the actual request.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    models = committed_models()
    n_ctx = window(models.summarizer.server)
    prompt, sequence = _worst_one_call_sequence_tokens(committed)

    assert sequence <= n_ctx, (
        f"the longest article extract.truncation_cap_tokens "
        f"({committed.extract.truncation_cap_tokens}) lets through makes a {prompt}-token "
        f"prompt. The "
        f"{response_limit(models.summarizer.sampling)}-token response limit puts the call at "
        f"{sequence} against a window of {n_ctx}, over by {sequence - n_ctx}. Measure the "
        "complete request before proposing a configuration or article-admission change."
    )


def test_the_gate_holds_room_for_the_whole_response_limit_the_model_file_names() -> None:
    """The reply has no length bound, so its reserve is the limit itself."""

    def held(sampling: dict[str, int]) -> int:
        return dag.call_tokens(1000, table_bytes=10, sampling=sampling)

    assert held({"max_tokens": 9000}) - held({"max_tokens": 8000}) == 1000
    assert held({}) == held({"max_tokens": DEFAULT_MAX_TOKENS})


def test_the_tables_are_held_at_a_token_a_byte_on_top_of_the_article() -> None:
    """A token spans at least one byte, so the bytes shown are a ceiling."""
    assert dag.prompt_tokens(1000, table_bytes=300) - dag.prompt_tokens(
        1000, table_bytes=0
    ) == 300


@pytest.mark.parametrize("key, limit", [("n_predict", 4213), ("max_tokens", 8192)])
def test_complete_request_accounting_uses_the_effective_response_limit(
    key: str, limit: int,
) -> None:
    request = {key: limit}
    assert dag.response_tokens(request) == limit
    assert dag.request_tokens(request, prompt_tokens=100) == 100 + limit


def test_request_accounting_refuses_ambiguous_or_unbounded_response_limits() -> None:
    for request in ({}, {"n_predict": -1}, {"max_tokens": True}, {"max_tokens": 2, "n_predict": 1}):
        with pytest.raises(ValueError, match="response-token limit"):
            dag.response_tokens(request)


def test_finetune_row_limits_fit_the_corpus_window() -> None:
    with pytest.raises(ValidationError, match="train_rows cannot exceed"):
        FinetuneConfig(corpus_rows=600, min_rows=500, train_rows=1000)
    with pytest.raises(ValidationError, match="min_rows cannot exceed"):
        FinetuneConfig(corpus_rows=500, train_rows=100, min_rows=600)


def test_finetune_rejects_an_unknown_teacher_role() -> None:
    payload = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    payload["finetune"]["teacher"] = "unknown_role"

    with pytest.raises(ValidationError, match=r"finetune\.teacher must name one of models"):
        AppConfig.model_validate(payload)


def test_finetune_teacher_has_a_distinct_base_repository() -> None:
    settings = config.load(CONFIG_DIR)
    teacher = settings.app.finetune.teacher
    ref = getattr(settings.models, teacher)

    assert ref.hf_base_repo, "the configured teacher needs a base repository for fine-tuning"
    assert ref.hf_base_repo != ref.repo, "the base repository must not point to the GGUF weights"


def test_the_training_window_covers_the_longest_row_the_cap_allows() -> None:
    """The same sum again, against the window a training session opens.

    A training row is a prompt the pipeline could have sent and an answer it
    could have returned, so it is the same sequence the test above sizes - and
    `finetune.sequence_length` short of it does not fail loudly. The wrangler and
    the notebook DROP an over-length row and count it, never truncate it, which
    is the right refusal and a silent one: at 8,192 against a 10,000-token cap
    the training set lost every article past about 5,500 words while production
    went on summarizing them.

    So the failure this catches is not a crash. It is a model tuned on the short
    half of its own job, found a session too late.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    _, worst_sequence = _worst_sequence_tokens(committed)
    window = committed.finetune.sequence_length

    assert worst_sequence <= window, (
        f"the longest article extract.truncation_cap_tokens "
        f"({committed.extract.truncation_cap_tokens}) lets through makes a "
        f"{worst_sequence}-token training row against finetune.sequence_length of "
        f"{window}, so the wrangler and the notebook would drop it and say so in a "
        "line nobody reads until the adapter is short. Raise "
        "finetune.sequence_length beside the cap, or lower the cap."
    )


def test_the_console_chart_size_is_a_knob_the_frontend_agrees_with() -> None:
    """A prerendered chart has no element to measure, so the size is given to it.

    Three copies of one number, and the test has to hold the two that decide the
    picture. Until 2026-09-05 it held the wrong pair: it compared the contract
    default against `config/idhazh.json` and then against the frontend's own
    fallback, and all three were 600 - while every console page drew at 760,
    because `consoleConfig()` merges `config/appearance.json` last and that file
    said 760. A green gate over three copies of a number nothing draws with is
    worse than no gate, because it reads as coverage.

    So the resolved value leads. `config/appearance.json` is the last merge
    layer, so what it declares is what the server draws at, and a clone with no
    `config/` has to draw the same picture - which means the contract default
    and the frontend's fallback have to be that same number, or a first paint
    somewhere is at a width nothing measured.
    """
    drawn = AppearanceConfig.from_json(read_text(CONFIG_DIR / "appearance.json")).console
    fresh = ConsoleConfig()
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")

    for field in ("chart_width", "chart_height"):
        shipped = getattr(drawn, field)
        assert getattr(fresh, field) == shipped, (
            f"config/appearance.json draws a console chart at {field}={shipped} and a "
            f"clone with no config/ would draw it at {getattr(fresh, field)}"
        )
        mirrored = re.search(rf"{field}:\s*(\d+)", reader)
        assert mirrored is not None, f"the frontend console defaults dropped {field}"
        assert int(mirrored.group(1)) == shipped, (
            f"the frontend's own {field} fallback is {mirrored.group(1)} and the "
            f"console draws at {shipped}"
        )


def test_the_window_the_console_opens_on_is_one_the_control_can_name() -> None:
    """A default outside the preset list opens the page on a window nothing selects.

    The control is four radio buttons, so a span that is not one of them leaves
    every button unchecked and the operator with no way back to what he is
    looking at.
    """
    with pytest.raises(ValidationError, match="window_presets"):
        ConsoleConfig(default_window_days=21)

    tuned = ConsoleConfig(default_window_days=21, window_presets=[7, 21, 60])
    assert tuned.default_window_days in tuned.window_presets


def test_a_preset_list_that_is_out_of_order_or_out_of_bounds_is_refused() -> None:
    """The presets are the only way the page sets its span.

    So `min_window_days` and `max_window_days` have no other reader, and a
    preset outside them would make both knobs decorative.

    The out-of-bounds case names its own `min_window_days` rather than leaning on
    the default. The default was 7 until 2026-09-06 and is 1 now, so a case
    written as `[3, 30]` against the default stopped being out of bounds without
    anything about the rule changing - a test that reads as a bound check and
    silently becomes a no-op.
    """
    with pytest.raises(ValidationError, match="ascending and distinct"):
        ConsoleConfig(window_presets=[30, 7, 90], default_window_days=30)
    with pytest.raises(ValidationError, match="ascending and distinct"):
        ConsoleConfig(window_presets=[7, 7, 30], default_window_days=30)
    with pytest.raises(ValidationError, match="min_window_days and max_window_days"):
        ConsoleConfig(window_presets=[3, 30], default_window_days=30, min_window_days=7)
    with pytest.raises(ValidationError, match="min_window_days and max_window_days"):
        ConsoleConfig(window_presets=[30, 400], default_window_days=30)


def test_the_console_window_presets_are_a_knob_the_frontend_agrees_with() -> None:
    """The same two-copies problem the chart size has, one field along.

    The frontend keeps its own console defaults so a fresh clone renders with no
    `config/`. If the two lists drift, the page draws a button for a window the
    contract would refuse.

    The committed list leads for the same reason it does above: it is the last
    merge layer, so it is the list the control really offers. Measured
    2026-09-06, all three copies read `[1, 7, 14, 30, 90]` - unlike the chart
    size, this one has never drifted.
    """
    offered = AppearanceConfig.from_json(read_text(CONFIG_DIR / "appearance.json")).console
    assert offered.window_presets == ConsoleConfig().window_presets, (
        "config/appearance.json offers a window list a clone with no config/ would not"
    )

    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"window_presets:\s*\[([\d,\s]+)\]", reader)
    assert mirrored is not None, "the frontend console defaults dropped window_presets"
    assert [int(part) for part in mirrored.group(1).split(",")] == offered.window_presets


def test_the_completeness_grace_is_a_knob_the_frontend_agrees_with() -> None:
    """The sentence under the console's tab strip decides from this when a record is late.

    The frontend keeps its own console defaults so a fresh clone renders with no
    `config/`. A clone that allowed a different number of days would tell its
    reader the pipeline had stopped on a day the committed build says it had not.
    """
    drawn = AppearanceConfig.from_json(read_text(CONFIG_DIR / "appearance.json")).console
    assert ConsoleConfig().completeness_grace_days == drawn.completeness_grace_days, (
        "config/appearance.json sets a completeness grace a clone with no config/ would not"
    )
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"completeness_grace_days:\s*(\d+)", reader)
    assert mirrored is not None, "the frontend console defaults dropped completeness_grace_days"
    assert int(mirrored.group(1)) == drawn.completeness_grace_days


def test_a_completeness_grace_of_zero_days_is_refused() -> None:
    """Zero would count the day the record was written as a day that is missing."""
    with pytest.raises(ValidationError, match="completeness_grace_days"):
        ConsoleConfig(completeness_grace_days=0)


@pytest.mark.parametrize(
    "knob",
    [
        "machine_colour_stops",
        "machine_colour_floor_share",
        "absent_hatch_degrees",
        "fleet_dot_max_px",
    ],
)
def test_the_machine_colour_knobs_are_ones_the_frontend_agrees_with(knob: str) -> None:
    """Three panels on the Hardware route draw a machine in the colour these decide.

    The frontend keeps its own console defaults so a fresh clone renders with no
    `config/`. A clone with a different number of steps, a different floor or a
    different hatch would colour one machine two ways between a build and a clone.
    """
    console = AppearanceConfig.from_json(read_text(CONFIG_DIR / "appearance.json")).console
    drawn = getattr(console, knob)
    assert getattr(ConsoleConfig(), knob) == drawn, (
        f"config/appearance.json sets console.{knob} a clone with no config/ would not"
    )
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(rf"\b{knob}:\s*([\d.]+)", reader)
    assert mirrored is not None, f"the frontend console defaults dropped {knob}"
    assert float(mirrored.group(1)) == drawn


def test_a_machine_colour_floor_of_the_whole_hue_is_refused() -> None:
    """A floor of the full hue would draw every step the same colour."""
    with pytest.raises(ValidationError, match="machine_colour_floor_share"):
        ConsoleConfig(machine_colour_floor_share=1.0)


#: The four thresholds that decide when a quiet day is drawn as a loud one, and
#: what the pair means: crossing the first fills that day's tile, crossing the
#: second puts the day in the panel's headline sentence.
RARE_EVENT_THRESHOLDS: Final = (
    "processor_lost_pct_marked",
    "processor_lost_pct_named",
    "model_disk_reads_marked",
    "model_disk_reads_named",
)


def test_the_rare_event_thresholds_are_knobs_the_frontend_agrees_with() -> None:
    """The same three-copies problem the chart size has, four fields along.

    The `ConsoleConfig` interface in `config.ts` is what a clone with no
    `config/` renders from, so a field missing there is a console drawing a
    threshold nobody set.
    """
    drawn = AppearanceConfig.from_json(read_text(CONFIG_DIR / "appearance.json")).console
    fresh = ConsoleConfig()
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")

    for field in RARE_EVENT_THRESHOLDS:
        shipped = getattr(drawn, field)
        assert getattr(fresh, field) == shipped, (
            f"config/appearance.json sets {field}={shipped} and a clone with no "
            f"config/ would use {getattr(fresh, field)}"
        )
        mirrored = re.search(rf"{field}: ([\d.]+)", reader)
        assert mirrored is not None, f"the frontend console defaults dropped {field}"
        assert float(mirrored.group(1)) == float(shipped), (
            f"the frontend's own {field} fallback is {mirrored.group(1)} and the "
            f"console resolves {shipped}"
        )


def test_a_threshold_that_names_a_day_the_strip_never_marked_is_refused() -> None:
    """Two thresholds a signal only work in one order.

    Equal is allowed, and the committed disk-read pair ships equal: a signal
    whose expected value is zero has no distribution to separate the two, so
    every day worth marking is worth naming.
    """
    with pytest.raises(ValidationError, match="processor_lost_pct_marked"):
        ConsoleConfig(processor_lost_pct_marked=20.0, processor_lost_pct_named=10.0)
    with pytest.raises(ValidationError, match="model_disk_reads_marked"):
        ConsoleConfig(model_disk_reads_marked=100, model_disk_reads_named=1)

    equal = ConsoleConfig(model_disk_reads_marked=7, model_disk_reads_named=7)
    assert equal.model_disk_reads_marked == equal.model_disk_reads_named


def test_a_threshold_that_would_mark_a_day_where_nothing_happened_is_refused() -> None:
    """The floor is what keeps a rare-event strip rare.

    A threshold of zero fills every tile of every day, including the days the
    host took nothing and the kernel reclaimed nothing - which is the cry-wolf
    failure the strip replaced a line chart to avoid.
    """
    with pytest.raises(ValidationError, match="processor_lost_pct_marked"):
        ConsoleConfig(processor_lost_pct_marked=0.0)
    with pytest.raises(ValidationError, match="model_disk_reads_marked"):
        ConsoleConfig(model_disk_reads_marked=0)


def test_the_offline_cache_takes_a_byte_ceiling_that_can_still_hold_one_day() -> None:
    """A day count cannot bound bytes, and a byte bound must fit a day.

    Measured 2026-09-02 over the 12 served days, one day payload runs 8,231 to
    1,373,593 bytes - a factor of 167 - so fourteen days is anything between
    115 KB and 19 MB and `offline_days_kept` promises the reader nothing about
    size. The floor is what stops the cure being worse: a ceiling under the
    largest day evicts that day as fast as it arrives, so the reader pays the
    download and keeps nothing. The ceiling stops a config edit quietly taking a
    tenth of a gigabyte of somebody's phone.
    """
    for refused in (0, 1_999_999, 100_000_001):
        with pytest.raises(ValidationError, match="offline_bytes_kept"):
            UiConfig(offline_bytes_kept=refused)


def test_the_archive_window_names_a_span_the_console_presets_already_offer() -> None:
    """One list of spans in the contract, not two.

    When the archive gets a window control it reuses the console's presets. So
    `archive_window_days` names a member of that list rather than declaring a
    second list of day counts, and both documents refuse a file where it does
    not - which is the same rule `console.default_window_days` has had since
    2026-08-29.

    Both documents are exercised, because a check on only one of them would pass
    on the file the console does not read. The cost is stated rather than
    hidden: a config that narrows the presets now has to name the archive's span
    inside the narrowed list, exactly as it already had to for
    `default_window_days`.
    """
    appearance = json.loads(read_text(CONFIG_DIR / "appearance.json"))
    narrowed = {
        **appearance,
        "console": {**appearance["console"], "window_presets": [7, 60], "default_window_days": 7},
    }
    with pytest.raises(ValidationError, match="archive_window_days"):
        AppearanceConfig.model_validate(narrowed)
    named = {**narrowed, "digest": {**narrowed["digest"], "archive_window_days": 60}}
    assert AppearanceConfig.model_validate(named).digest.archive_window_days == 60

    pipeline = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    narrowed = {
        **pipeline,
        "console": {**pipeline["console"], "window_presets": [7, 60], "default_window_days": 7},
    }
    with pytest.raises(ValidationError, match="archive_window_days"):
        AppConfig.model_validate(narrowed)
    named = {**narrowed, "ui": {**narrowed["ui"], "archive_window_days": 60}}
    assert AppConfig.model_validate(named).ui.archive_window_days == 60


def test_the_readout_cap_is_a_knob_the_frontend_agrees_with() -> None:
    """The same two-copies problem again, in the chart block.

    The cap is applied in the browser, off the frontend's own copy. Let the two
    drift and the browser test asserts one number while the contract bounds a
    different one, which is a gate that passes for the wrong reason.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"readout_max_share:\s*([\d.]+)", reader)
    assert mirrored is not None, "the frontend chart defaults dropped readout_max_share"
    assert float(mirrored.group(1)) == ChartConfig().readout_max_share


def test_the_seed_the_shell_carries_is_a_knob_the_frontend_agrees_with() -> None:
    """The same two-copies problem, on the one digest knob a browser never sees.

    `shell_seed_items` decides how many of a day's stories a prerendered
    document carries, so the build reads it on its own rather than through
    `uiConfig()` - everything that reader returns is inlined into every
    document, and no page reads this number. Two copies of it drift like any
    other pair, and a drift here would put a different number of stories in a
    document than the contract bounds.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"const SHELL_SEED_ITEMS = (\d+);", reader)
    assert mirrored is not None, "the frontend dropped its shell_seed_items fallback"
    assert int(mirrored.group(1)) == UiConfig().shell_seed_items


def test_the_leading_block_is_a_knob_the_frontend_agrees_with() -> None:
    """The third digest knob a browser never sees, and the newest of the three.

    A dated document's seed is the head of the day UNION its leads, because a
    lead is chosen across the whole day and need not sit inside a prefix. So
    this number is the second term of what that document may carry, and
    `frontend/tests/payload-weight.spec.ts` reads it as the bound. A drift here
    would bound a dated document at a count the contract never agreed to.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"const LEADING_STORIES = (\d+);", reader)
    assert mirrored is not None, "the frontend dropped its leading_stories fallback"
    assert int(mirrored.group(1)) == UiConfig().leading_stories


def test_the_holdout_reach_is_a_knob_the_frontend_agrees_with() -> None:
    """The Judgement route's own copy of the reach is the contract's default.

    The route reads `similarity.holdout_reach_days` off the file, falling back to
    its own copy on a clone with no `config/`. A drift between the two copies
    would let a bare clone draw a different set of marks than a configured one.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"const HOLDOUT_REACH_DAYS = (\d+);", reader)
    assert mirrored is not None, "the frontend dropped its holdout_reach_days fallback"
    assert int(mirrored.group(1)) == SimilarityConfig().holdout_reach_days


def test_the_archive_bounds_are_knobs_the_frontend_agrees_with() -> None:
    """A fresh clone must use the native browsing and Top defaults in both languages."""
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    expected = {
        "ARCHIVE_WINDOW_DAYS": UiConfig().archive_window_days,
        "ARCHIVE_TOP_VIEWPORTS": UiConfig().archive_top_viewports,
    }
    for constant, value in expected.items():
        mirrored = re.search(rf"const {constant} = (\d+(?:\.\d+)?);", reader)
        assert mirrored is not None, f"the frontend dropped its {constant} fallback"
        assert float(mirrored.group(1)) == value


def test_the_side_a_figure_sits_on_is_a_knob_the_frontend_agrees_with() -> None:
    """The knob nothing reads yet, pinned to the position the page renders.

    `visual_side` sat in both config files with two different values for a
    week, and nothing caught it because no component branches on it - the
    fallback merge just took one and dropped the other. It is reserved rather
    than dead: a figure gets a column of its own when the render spec is handed
    the width it will occupy (docs/concepts/design-system.md), and until then a
    default that names a position the page does not draw is a wrong answer
    waiting for a reader.

    So the three copies are checked against each other in one place: the
    contract's default, the frontend's fallback for a clone with no `config/`,
    and what `DigestItem.svelte` puts after what.
    """
    assert UiConfig().visual_side is VisualSide.TRAILING

    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    block = re.search(r"const DEFAULTS: UiConfig = \{(.*?)\};", reader, re.DOTALL)
    assert block is not None, "config.ts no longer declares a DEFAULTS block"
    mirrored = re.search(r"visual_side:\s*'(\w+)',", block.group(1))
    assert mirrored is not None, "the frontend dropped its visual_side default"
    assert mirrored.group(1) == UiConfig().visual_side.value

    card = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "components" / "DigestItem.svelte")
    assert card.index("<ItemVisual") > card.index("data-item-summary"), (
        "the card draws its figure before the summary, so `trailing` is the wrong default"
    )


def test_the_wait_worth_a_sentence_is_a_knob_the_frontend_agrees_with() -> None:
    """The two-copies problem on the one digest knob only a browser reads.

    `payload_slow_ms` bounds a wait that happens in a reader's browser, so a
    fresh clone with no config file resolves it from the frontend's own copy.
    Let the two drift and the sentence about a slow day fires at a moment the
    contract does not bound - and on a clone with no `config/` there is nothing
    else to catch it.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"payload_slow_ms:\s*(\d+),", reader)
    assert mirrored is not None, "the frontend dropped its payload_slow_ms default"
    assert int(mirrored.group(1)) == UiConfig().payload_slow_ms


def test_a_leading_block_that_could_never_draw_is_refused() -> None:
    """A floor above the ceiling fails silently: the block never appears."""
    with pytest.raises(ValidationError, match="leading_min"):
        UiConfig(leading_stories=3, leading_min=4)
    with pytest.raises(ValidationError, match="leading_per_desk"):
        UiConfig(leading_stories=3, leading_per_desk=4)




def test_historical_copying_config_preserves_only_the_corpus_length_cutoff() -> None:
    old = EvaluationConfig.model_validate({"verbatim_reject_ceiling": 0.63})
    assert old.corpus_compression_ceiling == 0.63
    assert "verbatim_reject_ceiling" not in old.model_dump()
    current = EvaluationConfig.model_validate(
        {"verbatim_reject_ceiling": 0.63, "corpus_compression_ceiling": 0.72}
    )
    assert current.corpus_compression_ceiling == 0.72
    assert "extractiveness_rise" not in DriftConfig.model_validate(
        {"extractiveness_rise": 0.9}
    ).model_dump()
    with pytest.raises(ValidationError, match="corpus_compression_ceiling"):
        EvaluationConfig.model_validate({"verbatim_reject_ceiling": 1.1})
    with pytest.raises(ValidationError, match="extra_forbidden"):
        EvaluationConfig.model_validate({"unknown_copying_limit": 0.2})


def test_the_item_health_census_is_not_switchable() -> None:
    """The denominator under every rate this project publishes has no off switch.

    Optional instruments can be disabled without removing item-health rows.
    The explicit switch list keeps the census from gaining an off switch.
    """
    switches = {
        name
        for name, field in ObservabilityConfig.model_fields.items()
        if field.annotation in (bool, StrictBool)
    }
    assert switches == {
        "evaluation_enabled",
        "tracing_enabled",
        "host_fingerprint",
        "host_telemetry_enabled",
        "memory_profiling_enabled",
        "host_fingerprint_frequency_enabled",
        "host_fingerprint_placement_enabled",
    }


def test_the_host_fingerprint_placement_switch_refuses_anything_but_a_boolean() -> None:
    for invalid in ("true", "false", 0, 1, None):
        with pytest.raises(ValidationError):
            ObservabilityConfig.model_validate(
                {"host_fingerprint_placement_enabled": invalid}
            )


def test_a_sample_rate_of_zero_is_refused_because_the_toggle_already_says_off() -> None:
    """Two ways to say off is how two ways of saying it end up disagreeing."""
    for refused in (0.0, -0.1, 1.1):
        with pytest.raises(ValidationError):
            ObservabilityConfig(sample_rate=refused)


def test_a_negative_heartbeat_is_refused_and_the_error_names_the_field() -> None:
    """Zero means never and is spelled. A negative number would mean it silently.

    That is the worst shape a misconfiguration of this knob can take: an
    operator who meant often gets never, and nothing says so. Refused at load,
    at the block and through the whole config, and the message names the field
    so a person reading it knows which line to fix.
    """
    with pytest.raises(ValidationError, match="waiting_heartbeat_seconds"):
        LoggingConfig(waiting_heartbeat_seconds=-1)
    with pytest.raises(ValidationError, match="waiting_heartbeat_seconds"):
        AppConfig.model_validate({"logging": {"waiting_heartbeat_seconds": -1}})
    assert LoggingConfig(waiting_heartbeat_seconds=0).waiting_heartbeat_seconds == 0


def test_a_config_still_spelling_the_judging_bound_under_run_is_refused() -> None:
    """The bound left `run` for `council`, and a stale file is answered by name.

    "extra inputs are not permitted" would leave an operator hunting for a
    number that is still there under another address, and a shard with no bound
    runs to the platform's 6 h ceiling before anything says so.
    """
    with pytest.raises(ValidationError, match=re.escape("council.shard_timeout_minutes")):
        AppConfig.model_validate({"run": {"judge_shard_timeout_minutes": 200}})


def test_a_config_still_spelling_the_fold_cover_under_run_is_refused() -> None:
    """The closed-day fold this number tuned is gone, and so is every rule for when it ran.

    A number left under `run` would be read by nothing, and whoever set it would
    believe they had moved a line that did not move - so it is refused, saying
    that nothing replaces it rather than pointing at a knob that no longer exists.
    """
    with pytest.raises(
        ValidationError,
        match=re.escape("run.settled_fold_after_days is gone and nothing replaces it"),
    ):
        AppConfig.model_validate({"run": {"settled_fold_after_days": 7}})


def test_a_config_still_spelling_a_setting_of_the_first_model_call_is_refused() -> None:
    """The model reads an item once now, and the two settings the first call read are gone.

    Whether a picture is asked for is decided by `visuals.enabled_kinds`, so a
    leftover `summarize.asks_for_a_visual_plan` is refused and pointed there. No
    task reads the labelling instructions, so a leftover `prompt_files.generate_labels`
    is refused with nothing to point at. Either would otherwise be a number somebody
    believes.
    """
    with pytest.raises(ValidationError, match=re.escape("is now visuals.enabled_kinds")):
        AppConfig.model_validate({"summarize": {"asks_for_a_visual_plan": False}})
    with pytest.raises(
        ValidationError,
        match=re.escape("prompt_files.generate_labels is gone and nothing replaces it"),
    ):
        AppConfig.model_validate({"prompt_files": {"generate_labels": "prompts/a.txt"}})


def test_no_judges_own_measurement_reaches_the_shared_config_contract() -> None:
    """A measured figure one judge produced may not sit where every reader loads it.

    `AppConfig` is imported by everything that reads config, the council's own
    modules included. While it held the judge's per-pair cost, a repository with
    no judge in it could not read its own config - and the check that cost fed
    could not move without moving the contract every stage validates against.

    Asserted over the module's whole namespace rather than one name, so a second
    judge's reading imported here fails the same way. Both names are known
    judge-owned readings today: the derived per-call figure and the measured
    per-pair one.
    """
    reached = sorted(
        name
        for name in vars(app_config)
        if name.startswith("SECONDS_A_") or name.endswith("_A_JUDGED_PAIR")
    )

    assert reached == [], (
        f"{reached} reached the shared config contract, so every module that reads "
        "config now carries one judge's measurement - and moving that measurement "
        "would re-size budgets nobody measured"
    )
