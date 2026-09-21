"""Does the committed config validate, and is every tunable value a knob?"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh import config
from idhazh.classify import dag
from idhazh.classify.calls import label_budget_tokens, summarize_and_plan_budget_tokens
from idhazh.contracts import app_config, story_similarity_distribution
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.appearance_config import AppearanceConfig, ChartConfig
from idhazh.contracts.call_cost import CallKind
from idhazh.contracts.knobs import placement
from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.knobs.console import ConsoleConfig
from idhazh.contracts.knobs.council import CouncilConfig
from idhazh.contracts.knobs.evaluation import EvaluationConfig
from idhazh.contracts.knobs.inference import InferenceConfig
from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.contracts.knobs.observability import LoggingConfig, LogLevel, ObservabilityConfig
from idhazh.contracts.knobs.placement import (
    HOLDOUT_TWO_STORY_MAX,
    SameStoryConfig,
    SimilarityThresholdConfig,
)
from idhazh.contracts.knobs.retention import PAGES_HARD_CAP_MB, RetentionConfig
from idhazh.contracts.knobs.ui import UiConfig, VisualSide
from idhazh.contracts.knobs.windows import months_a_window_can_touch
from idhazh.contracts.story_similarity_distribution import (
    ScoreSlot,
    StorySimilarityDistribution,
)
from idhazh.extract import TOKENS_PER_WORD
from idhazh.fingerprint import NOT_DIGESTED, digested_inference_fields
from idhazh.measured import LABEL_BODY_TOKENS_A_WORD as _LABEL_A_WORD
from idhazh.measured import LABEL_MENU_TOKENS_A_ROW as _MENU_A_ROW
from idhazh.measured import LABEL_SCAFFOLD_TOKENS as _LABEL_SCAFFOLD
from idhazh.measured import PROMPT_OVERHEAD_TOKENS as _PROMPT_OVERHEAD
from idhazh.measured import SUMMARIZE_AND_PLAN_SEAM_TOKENS as _SUMMARIZE_AND_PLAN_SEAM
from idhazh.measured import WORST_TOKENS_A_WORD as _WORST_TOKENS
from idhazh.similarity import budget

from ._fixtures import (
    APP_CONFIG_EVERY_KNOB_DIFFERS,
    CONFIG_FILES,
    CONFIG_NOT_OWNED,
    committed_models,
    copy_config,
)

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
    `summarize.key_point_words_max` and `summarize.asks_for_a_visual_plan` were
    among the missing, and both are load-bearing.

    **Owns, not declares.** Three blocks sit on two models and only one file is
    their source; `CONFIG_NOT_OWNED` names the other side. Padding a legacy
    block out to its model would give one knob two answers in two files, which
    is exactly what `test_a_moved_block_is_declared_in_one_file_and_the_other_
    does_not_argue` exists to refuse - it caught this test's first draft doing
    it.

    Leaf paths rather than top-level keys, because a default nested inside a
    list entry is the shape that hides best: three `summarize.bands` entries
    omitted `over_length_action` and no block-level check would have seen it.
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
    """Every knob has a default now, so an empty config is usable.

    `models` was the one block with no default and it left this file on
    2026-09-14. What replaced it is `models_file`, which defaults to the
    committed model's file - so the empty mapping below is the whole config a
    fresh clone needs.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    minimal = AppConfig.model_validate({})
    assert minimal.models_file == committed.models_file, (
        "the default names the committed file, or a fresh clone reads a model "
        "nobody put there"
    )
    assert (CONFIG_DIR / minimal.models_file).is_file()
    assert minimal.run.safety_ceiling_per_run == committed.run.safety_ceiling_per_run
    assert minimal.retention.image_months == -1, "retention ships disabled"
    assert minimal.retention.dry_run is True
    assert minimal.retention.pages_hard_cap_mb == PAGES_HARD_CAP_MB, (
        "an unconfigured clone enforces the platform's own ceiling"
    )


def test_the_config_refuses_a_pages_cap_above_the_platforms_own() -> None:
    """The direction the bound exists for. A cap config can raise is not a cap.

    Guardrail #2 says the budget is the platform and not a preference. That held while
    the 1024 was a module constant only because nobody edited it, which is not a
    control. It is a control now: the schema refuses the edit, and the message
    names the number it refused, so an operator reading it learns the bound
    rather than only that the file is wrong.
    """
    with pytest.raises(ValidationError) as raised:
        RetentionConfig(pages_hard_cap_mb=PAGES_HARD_CAP_MB + 1)
    assert "less than or equal to 1024" in str(raised.value)

    raw = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    raw["retention"]["pages_hard_cap_mb"] = 2048
    with pytest.raises(ValidationError) as from_file:
        AppConfig.model_validate(raw)
    assert "pages_hard_cap_mb" in str(from_file.value)
    assert "1024" in str(from_file.value)


def test_the_config_takes_a_pages_cap_below_the_platforms_own() -> None:
    """The other case, and the reason the field is here at all.

    A bound only tested in the direction it permits is not a bound - it is a
    default nobody has pushed on. Lowering is the whole use: it buys an earlier
    and louder failure while there is still headroom to act in. The tuned fixture
    carries 900 so a lowered cap is exercised by every round trip, not only here.
    """
    assert RetentionConfig(pages_hard_cap_mb=1).pages_hard_cap_mb == 1

    raw = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    raw["retention"]["pages_hard_cap_mb"] = 512
    assert AppConfig.model_validate(raw).retention.pages_hard_cap_mb == 512

    tuned = AppConfig.from_json(read_text(APP_CONFIG_EVERY_KNOB_DIFFERS))
    assert tuned.retention.pages_hard_cap_mb == 900


def test_the_alarm_point_and_the_pages_cap_stay_two_knobs() -> None:
    """One reports and one stops, so one number cannot do both jobs.

    Collapsing them gives a warning nobody may ignore or a failure that arrives
    with no notice. The committed file spells both, 224 MB apart, and the tuned
    fixture moves them independently - which is the shape that proves they are
    two instruments rather than one written twice.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).retention
    assert committed.site_budget_mb == 800
    assert committed.pages_hard_cap_mb == PAGES_HARD_CAP_MB
    assert committed.site_budget_mb < committed.pages_hard_cap_mb

    tuned = AppConfig.from_json(read_text(APP_CONFIG_EVERY_KNOB_DIFFERS)).retention
    assert (tuned.site_budget_mb, tuned.pages_hard_cap_mb) == (600, 900)


def test_the_model_server_publishes_its_counters_without_being_asked_for() -> None:
    """A run that did not count is a run that cannot say how close it came.

    llama-server publishes the context high watermark only under `--metrics`.
    Off by default would mean the number exists on the runs nobody thought to
    switch it on for, which is every ordinary day.

    The fresh-clone case drops the settings block and the weights digest
    together. Those two move as a pair now: an entry that names measured bytes
    under a block declared for nothing is refused - and the turn envelope obeys
    the same rule, so its digest goes with them. The markers themselves stay,
    because they have no default and a clone that forgot them would not load.
    """
    committed = committed_models()
    models = committed.model_dump()
    for role in ModelsConfig.roles():
        entry = models[role]
        del entry["inference"]
        entry["sha256"] = None
        entry["turns"]["declared_for"] = None
    fresh = ModelsConfig.model_validate(models)

    assert fresh.summarize.inference.metrics is True, "a fresh clone must count"
    assert committed.summarize.inference.metrics is True, "the committed config must count"


def test_the_wider_window_is_the_summarizers_alone() -> None:
    """Row 3 raised one role, because one role is what was measured.

    The visual planner is different weights with its own settings block, and
    nothing has measured a wider window in front of them - so it keeps the
    conservative default. That is the whole reason the block sits on the entry
    rather than on `models`: a number measured against one model may not be
    inherited by another.

    The assertion is the relationship and not either number, so raising the
    summarizer's window beside the truncation cap does not need an edit here
    (Guardrail #6).

    Attention is pinned in the same file. `auto` is a runtime autodetect that
    may resolve differently on other silicon, and a run that cannot name the
    kernel it used cannot be compared with one that can (Guardrail #10).
    """
    models = committed_models()

    assert models.summarize.inference.n_ctx > InferenceConfig().n_ctx, (
        "the summarizer is the one role a measurement widened"
    )
    assert models.summarize.inference.flash_attention == "on"
    assert InferenceConfig().n_ctx == 8192, (
        "the default is the conservative window for weights nobody has measured"
    )


#: What the summarize prompt costs before a word of the article reaches it, and
#: the hardest any published item has tokenized. Both records, their method and
#: what to do when either moves are in `idhazh.measured`.
PROMPT_OVERHEAD_TOKENS: Final = int(_PROMPT_OVERHEAD.value)

WORST_TOKENS_A_WORD: Final = _WORST_TOKENS.value


#: The same four things for the two-call path, whose prompt this repository
#: renders itself. Same module, same reason.
LABEL_SCAFFOLD_TOKENS: Final = int(_LABEL_SCAFFOLD.value)

LABEL_BODY_TOKENS_A_WORD: Final = _LABEL_A_WORD.value

LABEL_MENU_TOKENS_A_ROW: Final = _MENU_A_ROW.value

SUMMARIZE_AND_PLAN_SEAM_TOKENS: Final = int(_SUMMARIZE_AND_PLAN_SEAM.value)


def _worst_sequence_tokens(committed: AppConfig) -> tuple[int, int]:
    """The longest prompt the cap allows, and that prompt plus a full answer.

    One derivation because the serving window and the training window have to
    agree about it. The cap is spent as words at `TOKENS_PER_WORD`, so an
    article whose prose tokenizes harder than that overruns the budget its own
    cap gave it, and both windows have to cover the article that did rather than
    the one that behaved.
    """
    inference = committed_models().summarize.inference
    cut_words = int(committed.extract.truncation_cap_tokens / TOKENS_PER_WORD)
    worst_prompt = PROMPT_OVERHEAD_TOKENS + int(cut_words * WORST_TOKENS_A_WORD)
    return worst_prompt, worst_prompt + inference.max_answer_tokens


def test_the_longest_article_the_cap_allows_still_fits_the_window() -> None:
    """Keep the configured article cap and reply budget within the model window.

    Use measured token expansion because the extraction cap estimates tokens
    from word count and can undercount the rendered prompt.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    inference = committed_models().summarize.inference
    worst_prompt, worst_sequence = _worst_sequence_tokens(committed)

    assert worst_sequence <= inference.n_ctx, (
        f"the longest article extract.truncation_cap_tokens "
        f"({committed.extract.truncation_cap_tokens}) lets through is "
        f"{worst_prompt} prompt tokens, and {inference.max_answer_tokens} of answer "
        f"puts the sequence at {worst_sequence} against a window of {inference.n_ctx}. "
        "Raise models.summarize.inference.n_ctx beside the cap, or lower the cap."
    )


def _worst_two_call_sequence_tokens(committed: AppConfig) -> tuple[int, int]:
    """The label call's prompt at the cap, and the whole sequence behind it.

    A second derivation and not a widening of the one above, because the two
    paths render different prompts. The single call sends one system turn and
    the article. The label call sends a system turn that carries both jobs, the article
    with an address in front of every sentence, and a menu of every quantity and
    date the extractor already cut - then pays for its own reply twice, once as
    a decode and once again inside the summarize-and-plan call's prompt.

    **The arithmetic itself is `classify.dag`'s and this is the gate over it.**
    It used to be written out here, which put the number the production path
    never checked and the number this file asserts in two places - and two
    derivations of one quantity disagree the first time a term moves. The three
    terms of the prompt and the per-turn seam are documented where they are
    computed; what stays here is the cap, the knob and the window, all three
    read from `config/` (Guardrail #6).
    """
    rows = committed.elements.max_per_article
    cap = committed.extract.truncation_cap_tokens
    return (
        dag.first_prompt_tokens(cap, menu_rows=rows),
        dag.sequence_tokens(cap, menu_rows=rows, prompt_config=committed.summarize),
    )


def test_the_sequence_is_two_calls_and_growing_it_is_an_escalation() -> None:
    """A third call is a design change, and this is what makes it stop being quiet.

    Every node's reply is paid twice - once as its own decode, and once again
    inside the prompt of every node behind it - so a third call does not cost a
    third of the sequence, it costs its own budget plus a seam plus the prompt
    it drags forward. At the committed window that is the difference between 80
    percent full and over.

    The import-time guard in `classify.dag` fires first and says the same thing.
    This test exists because a guard inside the module a change is editing is a
    guard that change can edit; a change that adds a node has to come here and
    say so as well, which is the point at which it stops being a quiet edit and
    becomes a design decision a person signs off.

    **A labelling row does not add a node.** It adds a field to the label call's reply
    shape, and `label_budget_tokens` re-derives the budget from the shape's
    own bounds on import.
    """
    assert len(dag.NODES) == dag.NODE_COUNT == 2
    assert [node.name.value for node in dag.NODES] == ["label", "summarize_and_plan"]
    assert {node.name.value for node in dag.NODES} <= {kind.value for kind in CallKind}, (
        "a node the ledger has no CallKind for records its cost as nothing"
    )


def test_the_two_calls_fit_the_window_at_the_cap() -> None:
    """The second call retains the first prompt and reply, so size the full context.

    Include the candidate menu and both reply budgets to catch config changes
    that could exhaust the window and truncate the summary or visual plan.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    inference = committed_models().summarize.inference
    prompt, sequence = _worst_two_call_sequence_tokens(committed)

    assert sequence <= inference.n_ctx, (
        f"the longest article extract.truncation_cap_tokens "
        f"({committed.extract.truncation_cap_tokens}) lets through makes a {prompt}-token "
        f"the label call prompt at elements.max_per_article of "
        f"{committed.elements.max_per_article}. The label call's {label_budget_tokens()}-token "
        f"reply, the {SUMMARIZE_AND_PLAN_SEAM_TOKENS}-token seam and the summarize-and-plan call's "
        f"{summarize_and_plan_budget_tokens(committed.summarize)}-token reply put the pair at "
        f"{sequence} against a window of {inference.n_ctx}, over by "
        f"{sequence - inference.n_ctx}. Raise models.summarize.inference.n_ctx, or "
        "lower extract.truncation_cap_tokens or elements.max_per_article beside it. "
        "KV is 32 KiB a token on the configured weights, so a doubling is about a "
        "gigabyte and docs/reference/pipeline-cost.md says what the runner had free."
    )


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


def test_a_wider_window_moves_the_stamp_and_the_verbosity_does_not() -> None:
    """The two halves of the digest decision, in one place.

    `n_ctx` is digested, so raising it stamps the work apart from every summary
    written at 8,192 - which is correct, because the prompt those summaries were
    written under could not have carried as much. `log_verbosity` is not, because
    a log level cannot move a logit and digesting it would have invalidated every
    earlier identity the day somebody turned the logging up.
    """
    assert "n_ctx" in digested_inference_fields()
    assert "log_verbosity" in NOT_DIGESTED
    assert NOT_DIGESTED["log_verbosity"].moves_logits is False


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


def test_a_console_chart_may_not_be_narrower_than_its_own_labels() -> None:
    with pytest.raises(ValueError):
        AppConfig.model_validate({"console": {"chart_width": 0}})


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


#: The four thresholds that decide when a quiet day is drawn as a loud one, and
#: what the pair means: crossing the first fills that day's tile, crossing the
#: second puts the day in the panel's headline sentence.
RARE_EVENT_THRESHOLDS: Final = (
    "processor_lost_pct_marked",
    "processor_lost_pct_named",
    "model_disk_reads_marked",
    "model_disk_reads_named",
)

#: A setting for each, chosen to differ from every committed value, so a load
#: that ignored the file resolves something this cannot mistake for a pass.
THRESHOLDS_MOVED: Final = {
    "processor_lost_pct_marked": 2.5,
    "processor_lost_pct_named": 40.0,
    "model_disk_reads_marked": 500,
    "model_disk_reads_named": 9000,
}


def test_moving_a_rare_event_threshold_in_the_config_moves_what_resolves(
    tmp_path: Path,
) -> None:
    """Guardrail #6's substitution test: edit the file, and the value moves with it.

    Both sides go through the same loader, so the only difference between them
    is the file on disk. A threshold held as a literal in the module that draws
    the strip would resolve the same on both sides, which is the defect this
    row exists to prevent and the one thing this check can fail for.

    What it cannot settle: whether the resolved number reaches a drawn tile.
    The two panels that read these four are not written yet, and the parity
    check below is as far as the value can be followed today.
    """
    copy_config(tmp_path)
    appearance = json.loads(read_text(tmp_path / "config" / "appearance.json"))
    appearance["console"] |= THRESHOLDS_MOVED
    (tmp_path / "config" / "appearance.json").write_text(
        AppearanceConfig.model_validate(appearance).to_json(), encoding="utf-8", newline="\n"
    )

    committed = config.load(CONFIG_DIR).appearance.console
    moved = config.load(tmp_path / "config").appearance.console
    for field, value in THRESHOLDS_MOVED.items():
        assert getattr(committed, field) != value, (
            f"console.{field} already ships at {value}, so this case no longer asks "
            "whether the file decides it - pick another value"
        )
        assert getattr(moved, field) == value, (
            f"console.{field} did not follow config/appearance.json, so something "
            "other than the config file decides when a day is drawn as loud"
        )


def test_the_rare_event_thresholds_are_knobs_the_frontend_agrees_with() -> None:
    """The same three-copies problem the chart size has, four fields along.

    `frontend/src/contracts/appearance-config.ts` is generated and the drift
    gate holds it. The `ConsoleConfig` interface in `config.ts` is not: it is
    what a clone with no `config/` renders from, so a field missing there is a
    console drawing a threshold nobody set.
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


def test_the_windows_and_the_reading_marks_are_the_spans_the_committed_config_names() -> None:
    """The six spans that bound a constant-cost read, read off disk.

    Each is asserted against `config/` rather than against the model, because a
    default and a committed value are two different facts and only the second is
    what ships. The console reads its window out of `config/appearance.json`,
    which is the last merge layer, and `config/idhazh.json` still carries the
    keys it carried before the split - so where both files name a span, both are
    read here and the pair has to agree.

    Why each number is what it is belongs in the field descriptions. This test
    only holds them still.
    """
    drawn = AppearanceConfig.from_json(read_text(CONFIG_DIR / "appearance.json"))
    legacy = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))

    assert 1 in drawn.console.window_presets, (
        "the console offers no one-day window, so the cheapest read it can do - one "
        "month file and the run that just finished - is unreachable"
    )
    assert drawn.console.min_window_days == 1
    assert drawn.console.max_window_days == 366, (
        "max_window_days is a retention floor: lowering it makes no page cheaper and "
        "authorises deleting month shards the console can still ask for"
    )
    assert drawn.digest.read_mark_days == 14
    assert drawn.digest.archive_recent_days == 14, (
        "the archive lists a different span from the one read marks survive, so it "
        "offers days that come back looking unread"
    )
    assert drawn.digest.read_mark_days == drawn.digest.archive_recent_days

    assert legacy.ui.read_mark_days == drawn.digest.read_mark_days
    assert legacy.console.min_window_days == drawn.console.min_window_days
    assert legacy.console.max_window_days == drawn.console.max_window_days

    # Two knobs nothing reads yet - the offline cache evicts on a day count
    # alone, and the archive has no window control - so the committed value and
    # the bounds either side of it are the whole of what can be checked today.
    assert drawn.digest.offline_bytes_kept == 20_000_000
    assert drawn.digest.archive_window_days in drawn.console.window_presets


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
    assert UiConfig(offline_bytes_kept=2_000_000).offline_bytes_kept == 2_000_000
    assert UiConfig(offline_bytes_kept=100_000_000).offline_bytes_kept == 100_000_000
    assert UiConfig().offline_bytes_kept == 20_000_000
    assert UiConfig().offline_bytes_kept > 1_373_593, (
        "the ceiling is under the largest day payload measured, so the cache would "
        "evict every large day the moment it arrived"
    )


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


def test_the_days_the_archive_lists_are_a_knob_the_frontend_agrees_with() -> None:
    """The same two-copies problem, on another digest knob a browser never sees.

    `archive_recent_days` decides how many days the archive lists as rows of
    their own before the months take over, so the build reads it on its own
    rather than through `uiConfig()`. A drift here would put a different number
    of days on the page than the contract bounds, and on a clone with no
    `config/` there is nothing else to catch it.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"const ARCHIVE_RECENT_DAYS = (\d+);", reader)
    assert mirrored is not None, "the frontend dropped its archive_recent_days fallback"
    assert int(mirrored.group(1)) == UiConfig().archive_recent_days


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

    card = read_text(
        REPO_ROOT / "frontend" / "src" / "lib" / "components" / "DigestItem.svelte"
    )
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


def test_the_seed_covers_what_a_reading_surface_draws_before_a_reader_acts() -> None:
    """The seed is what a document holds once the rest of the day arrives by fetch.

    Every lead is an anchor into the stream, so a document that carries fewer
    stories than the leading block holds is a block whose links scroll to
    nothing. That is the floor, and it is not the whole answer: the leads are
    chosen across the WHOLE day, so a lead can sit at position 300 of the
    published order and outside any prefix. Whichever row moves the item list
    to a browser fetch owns that, and this is the number it starts from.
    """
    ui = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).ui
    assert ui.shell_seed_items >= ui.leading_stories, (
        f"a {ui.shell_seed_items}-story seed cannot hold {ui.leading_stories} leads"
    )


def test_a_shared_subject_is_worth_less_than_a_second_feed_carrying_the_story() -> None:
    """Decision 3's ceiling, derived rather than spelled.

    A second feed carrying one address adds `collect.carriage_step` to that
    story's score, flat and whatever tier carried it. A recurring subject must
    not outrank a story two independent feeds carried today, so the
    shared-subject term stays under it. The ceiling was
    `tier_weights.trade_press * repetition_weight` until 2026-09-13 because the
    term multiplied a tier; it multiplies nothing now, so the bound cannot
    either, and it tightened from 0.6 to 0.25. Measured 2026-09-01 over 11
    committed days: a second carrier fires on 4.49 percent of the stories that
    record one and a shared subject on 12.85 percent, so the commoner signal is
    the one that has to be worth less.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    second_carrier = committed.collect.carriage_step
    assert committed.ui.lead_shared_subject_weight < second_carrier, (
        f"a shared subject is worth {committed.ui.lead_shared_subject_weight} against "
        f"{second_carrier} for a second feed carrying the story"
    )
    assert UiConfig().lead_shared_subject_weight < CollectConfig().carriage_step


def test_a_leading_block_that_could_never_draw_is_refused() -> None:
    """A floor above the ceiling fails silently: the block never appears."""
    with pytest.raises(ValidationError, match="leading_min"):
        UiConfig(leading_stories=3, leading_min=4)
    with pytest.raises(ValidationError, match="leading_per_desk"):
        UiConfig(leading_stories=3, leading_per_desk=4)


def test_a_reject_ceiling_under_the_brief_gate_is_refused() -> None:
    """The one edit that would silence a gate instead of tightening it.

    A refused item writes no score, so it leaves the corpus `brief_copying_ceiling`
    reads. Drop the reject to the gate's own number and every item the gate could
    have failed is gone before it looks - the gate stops failing, which reads
    exactly like a pipeline that stopped copying.
    """
    gate = EvaluationConfig().brief_compression_ceiling
    for silenced in (gate, gate / 2):
        with pytest.raises(ValidationError):
            EvaluationConfig(verbatim_reject_ceiling=silenced)
    assert EvaluationConfig(verbatim_reject_ceiling=gate + 0.01).verbatim_reject_ceiling > gate


def test_the_committed_reject_ceiling_leaves_the_brief_gate_a_live_band() -> None:
    """0.75 against a 0.5 gate, so (0.5, 0.75] is a band the gate can still fail in."""
    evaluation = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).evaluation
    assert evaluation.verbatim_reject_ceiling == 0.75
    assert evaluation.brief_compression_ceiling == 0.5


def test_a_fresh_clone_measures_itself_and_the_committed_config_agrees() -> None:
    """Every instrument is on unconfigured, and the committed file did not turn one off.

    Written as an agreement between two configs rather than as three literals: a
    default that is asserted by value is a test that fails the day somebody
    legitimately changes it, which teaches people to edit the test.

    Tracing is the exception and is asserted by value, because its default is
    the claim: it was off until 2026-09-06, when the owner turned it on by
    default. On or off, the committed file and a fresh clone must agree - the
    point of this test is that the shipped config never silently diverges from
    the defaults the code carries.

    **One age is allowed to diverge, and it is named rather than skipped.**
    `host_fingerprint_keep_months` defaults to null - never delete - because a
    deletion default is a promise (`RetentionConfig`'s own rule), and the
    committed file names the window one step ahead of it. Every other field
    still has to agree, and this one still has to diverge in the one direction
    that is safe: unconfigured keeps everything, committed names a window.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    fresh = AppConfig.model_validate({})

    assert committed.observability.model_dump(
        exclude={"host_fingerprint_keep_months"}
    ) == fresh.observability.model_dump(exclude={"host_fingerprint_keep_months"})
    assert fresh.observability.host_fingerprint_keep_months is None
    assert committed.observability.host_fingerprint_keep_months is not None
    assert fresh.observability.evaluation_enabled
    assert fresh.observability.telemetry_publish
    assert fresh.observability.tracing_enabled


def test_the_item_health_census_is_not_switchable() -> None:
    """The denominator under every rate this project publishes has no off switch.

    Turning the census off would not thin a measurement, it would make every
    other measurement unreadable - a failure rate with no denominator beside it
    is the exact defect the census exists to prevent. The guard is the switch
    list itself, so adding a fifth boolean fails here and has to be argued for.

    `tracing_enabled` was the third, added 2026-08-30 and turned on by default
    2026-09-06. The argument it had to make: it switches an instrument nothing
    else divides by. No page reads a span, no gate consults one, and every rate
    the console prints keeps its denominator whether tracing is on or off - which
    is not true of any of the other three in the same way, and is why it is
    allowed to be a switch at all.

    `host_fingerprint` is the fourth, added 2026-09-16, and it makes the same
    argument. It records what silicon a job drew; nothing divides by it, no
    published page reads it, and every rate keeps its denominator with it off.
    What it costs to switch off is comparability rather than a measurement: a
    throughput figure taken with no fingerprint beside it cannot be set against
    another run's, because the machine moved 3.7x between draws and nothing says
    which one produced the number.
    """
    switches = {
        name
        for name, field in ObservabilityConfig.model_fields.items()
        if field.annotation is bool
    }
    assert switches == {
        "evaluation_enabled",
        "telemetry_publish",
        "tracing_enabled",
        "host_fingerprint",
    }
    assert "census" in (ObservabilityConfig.__doc__ or "")


def test_a_sample_rate_of_zero_is_refused_because_the_toggle_already_says_off() -> None:
    """Two ways to say off is how two ways of saying it end up disagreeing."""
    for refused in (0.0, -0.1, 1.1):
        with pytest.raises(ValidationError):
            ObservabilityConfig(sample_rate=refused)
    assert ObservabilityConfig(sample_rate=1.0).sample_rate == 1.0


def test_the_trace_window_is_a_positive_span_of_days() -> None:
    """The raw-trace window is counted in days, not months.

    A trace is a lookup an operator opens for a recent run, so its window is a
    short span of days rather than a full-grain month count - which is also why
    it is not in `full_grain_months()` above. At least one day, or the day being
    written would have nowhere to land. The value lives in config; this holds the
    floor the model enforces, without asserting a default that would fail the day
    somebody legitimately changes it.
    """
    assert ObservabilityConfig().trace_window_days >= 1
    assert "trace_window_days" not in ObservabilityConfig().full_grain_months()
    with pytest.raises(ValidationError):
        ObservabilityConfig(trace_window_days=0)
    assert ObservabilityConfig(trace_window_days=1).trace_window_days == 1


def test_a_month_may_not_be_deleted_before_it_has_been_downsampled() -> None:
    """A summary has to outlive the full-grain window it replaces, both times."""
    fresh = ObservabilityConfig()
    for summary, full_grain in (
        ("item_health_aggregate_keep_months", "item_health_full_grain_months"),
        ("score_archive_keep_months", "scores_full_grain_months"),
    ):
        keep = getattr(fresh, full_grain)
        for early in (keep, keep - 1):
            with pytest.raises(ValidationError, match=summary):
                ObservabilityConfig(**{summary: early})
        assert ObservabilityConfig(**{summary: keep + 1}) is not None


def test_every_cleanup_age_outlives_the_shards_a_console_read_selects() -> None:
    """The check the old `keep_months` never made, and the reason 13 was wrong.

    `console.max_window_days` is 366, and `ledger.shards_in_window` walks 367
    inclusive days - so a window ending on the first of a month can start on the
    last day of another and open **14** month files. The retired check compared
    `months * 30` against the window, which passed 13 while a reader could still
    ask for a fourteenth shard.
    """
    window = ConsoleConfig().max_window_days
    shards = months_a_window_can_touch(window)
    assert window == 366
    assert shards == 14, "a 366-day read reaches fourteen month shards, not thirteen"
    assert 13 * 30 > window, "the retired check passed 13, which is the whole point"

    fresh = ObservabilityConfig()
    assert set(fresh.full_grain_months()) == {
        "item_health_full_grain_months",
        "feed_health_keep_months",
        "scores_full_grain_months",
        "public_telemetry_keep_months",
        "public_run_days_keep_months",
        "public_day_metrics_keep_months",
        "public_machine_keep_months",
        "public_span_rollup_keep_months",
    }
    # One published payload is held equal to the ledger it projects, so
    # lowering either half has to lower both to reach the shortness check.
    paired = {
        "item_health_full_grain_months": "public_telemetry_keep_months",
        "public_telemetry_keep_months": "item_health_full_grain_months",
    }
    for name, months in fresh.full_grain_months().items():
        assert months >= shards, f"observability.{name} is shorter than a console read"
        short = {name: months - 1}
        partner = paired.get(name)
        if partner is not None:
            short[partner] = months - 1
        with pytest.raises(ValidationError, match=name):
            AppConfig.model_validate({"observability": short})


def test_the_published_copy_lasts_exactly_as_long_as_the_ledger_it_copies() -> None:
    """Either way round leaves a month nothing can answer for."""
    for skew in (-1, 1):
        with pytest.raises(ValidationError, match="public_telemetry_keep_months"):
            ObservabilityConfig(
                item_health_full_grain_months=20, public_telemetry_keep_months=20 + skew
            )
    assert (
        ObservabilityConfig(
            item_health_full_grain_months=20, public_telemetry_keep_months=20
        ).public_telemetry_keep_months
        == 20
    )


def test_a_config_with_no_logging_block_reads_every_flag_at_its_documented_default() -> None:
    """A fresh clone logs everything, because the reason the flags exist is silence.

    Built here rather than read from `config/idhazh.json`, so it proves the
    default and not what somebody happened to commit. The block is absent
    entirely, which is the shape of every config file written before today.

    It cannot settle whether these defaults are right for a quiet production
    run; only a run under them says that.
    """
    fresh = AppConfig.model_validate({"run": {"max_parallel": 2}}).logging
    assert fresh.level is LogLevel.INFO
    assert fresh.item_lines is True
    assert fresh.stage_lines is True
    assert fresh.waiting_heartbeat_seconds == 30
    assert fresh.capture_prompts is True
    assert fresh.capture_replies is True


def test_every_logging_flag_moved_off_its_default_survives_the_round_trip() -> None:
    """The substitution test: the file says it, the contract carries it back.

    Every knob is moved, so a reader that ignored the block and fell back to a
    default fails here rather than passing. `waiting_heartbeat_seconds` is moved
    to 5 rather than to 0, because 0 is the off switch and an off switch that
    reads the same as an unset knob proves nothing.
    """
    payload = {
        "capture_prompts": False,
        "capture_replies": False,
        "item_lines": False,
        "level": "DEBUG",
        "stage_lines": False,
        "waiting_heartbeat_seconds": 5,
    }
    fresh = LoggingConfig()
    for name, moved in payload.items():
        assert getattr(fresh, name) != moved, f"logging.{name} was already {moved!r}"

    once = LoggingConfig.model_validate(payload).model_dump(mode="json")
    assert json.dumps(once, sort_keys=True) == json.dumps(payload, sort_keys=True)
    twice = LoggingConfig.model_validate(once).model_dump(mode="json")
    assert json.dumps(twice, sort_keys=True) == json.dumps(once, sort_keys=True)
    assert AppConfig.model_validate({"logging": payload}).logging.waiting_heartbeat_seconds == 5


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


def test_every_flag_but_the_permanent_one_names_the_reading_that_retires_it() -> None:
    """Guardrail #6: a flag with no removal condition is a second implementation.

    A condition that named a piece of work would be no condition at all, so each
    one has to name a reading. The guard is the word `week`, which is the span
    every one of them is measured over. `item_lines` is the declared exception
    and has to say so; `level` is not a flag and carries no condition either.
    """
    flags = {
        name
        for name, field in LoggingConfig.model_fields.items()
        if name != "level"
    }
    assert flags == {
        "item_lines",
        "stage_lines",
        "waiting_heartbeat_seconds",
        "capture_prompts",
        "capture_replies",
    }
    for name in sorted(flags - {"item_lines"}):
        described = LoggingConfig.model_fields[name].description or ""
        assert "Retire it" in described or "Set it to 0" in described, (
            f"logging.{name} has no removal condition on the line that declares it"
        )
        assert "week" in described, f"logging.{name} names no reading, only an intent"

    permanent = LoggingConfig.model_fields["item_lines"].description or ""
    assert "NO REMOVAL CONDITION" in permanent
    assert "permanent instrument" in permanent

    level = LoggingConfig.model_fields["level"].description or ""
    assert "Unrelated to the flags" in level, "the level is a volume dial, not a sixth flag"


def test_a_band_that_does_not_divide_into_whole_slots_is_refused() -> None:
    """A part-slot at one end holds counts drawn from a smaller catchment than its neighbours.

    The fit would read that as a dip in the judge's verdicts rather than as an
    artefact of the arithmetic. Refused at the config rather than left to the
    record, because the record's own validator fires hours later in CI with
    nothing saying which of three knobs to move.
    """
    with pytest.raises(ValidationError, match="does not divide into whole slots"):
        SimilarityThresholdConfig(bin_width=0.0007)

    assert SimilarityThresholdConfig().bin_width == 0.001, "the committed width still divides"


def test_a_band_that_opens_above_todays_floor_is_refused() -> None:
    """A band above the floor can only ever judge pairs the pass already merges.

    The record then fills with confirmations and the line can never come down,
    while every number in the file still looks legal. This is the one knob
    combination that makes a downward move impossible without failing anything.
    """
    with pytest.raises(ValidationError, match="could only ever rise"):
        SameStoryConfig(
            floor_min=0.94,
            adaptive_dedup_threshold=SimilarityThresholdConfig(band_low=0.95),
        )

    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).assemble.same_story
    assert committed.judging_knobs().band_low < committed.floor_min


def test_a_daily_step_that_outruns_the_band_is_refused() -> None:
    """A step wider than the band can put the line where the record holds no slot.

    This replaced the margin check on 2026-09-19. That one refused a step at or
    above the gap between the line and the nearest pair marked as two stories;
    the 200 labels marked that day put the nearest such pair at 0.9407, above
    the 0.94 line, so there is no gap left for a step to eat.

    The caps are slot counts, so the comparison is a count against the band's own
    slot count rather than one decimal against another.
    """
    band = SimilarityThresholdConfig()
    slots = round((band.band_high - band.band_low) / band.bin_width)
    with pytest.raises(ValidationError, match="outside the record"):
        SimilarityThresholdConfig(max_down_bins=slots)
    with pytest.raises(ValidationError, match="outside the record"):
        SimilarityThresholdConfig(max_up_bins=slots)
    with pytest.raises(ValidationError, match="outside the record"):
        SimilarityThresholdConfig(dead_zone_bins=slots)

    assert band.max_down_step == pytest.approx(band.max_down_bins * band.bin_width)
    assert band.max_up_step == pytest.approx(band.max_up_bins * band.bin_width)
    assert band.dead_zone == pytest.approx(band.dead_zone_bins * band.bin_width)


def test_a_config_that_makes_the_line_rise_faster_than_it_falls_is_refused() -> None:
    """The line falls fast and rises slow, and the config is where that is held.

    Lowering the line publishes less, which is the house rule, so both mechanisms
    - the damping weight and the daily cap - are larger going down than going up.
    The shape reads backwards to anyone who has not been told the rule, and the
    obvious tidy-up is to point it the other way, so the refusal is here rather
    than a comment somebody deletes.
    """
    with pytest.raises(ValidationError, match="meant to be quick"):
        SimilarityThresholdConfig(fall_weight=0.15, rise_weight=0.5)
    with pytest.raises(ValidationError, match="meant to be quick"):
        SimilarityThresholdConfig(max_down_bins=3, max_up_bins=10)

    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    knobs = committed.assemble.same_story.judging_knobs()
    assert knobs.fall_weight > knobs.rise_weight
    assert knobs.max_down_bins > knobs.max_up_bins


def test_a_config_still_spelling_a_retired_threshold_knob_is_refused() -> None:
    """Two knobs changed unit as well as name, and one changed owner.

    `max_down_step` was a score and `max_down_bins` is a count of slots, so an
    operator who moves 0.005 across untouched has written a step two hundred
    times too small. "extra inputs are not permitted" would not have told them.

    `shards` left this block for `council` on 2026-09-21, so its replacement is
    printed as a whole path - a person sent to a block-relative name would be
    sent to a key inside the block the knob just left.
    """
    with pytest.raises(ValidationError, match="max_down_bins"):
        SimilarityThresholdConfig.model_validate({"max_down_step": 0.005})
    with pytest.raises(ValidationError, match="fall_weight"):
        SimilarityThresholdConfig.model_validate({"smoothing_weight": 0.15})
    with pytest.raises(ValidationError, match=re.escape("council.shards")):
        SimilarityThresholdConfig.model_validate({"shards": 4})


def test_a_config_still_spelling_the_judging_bound_under_run_is_refused() -> None:
    """The bound left `run` for `council`, and a stale file is answered by name.

    "extra inputs are not permitted" would leave an operator hunting for a
    number that is still there under another address, and a shard with no bound
    runs to the platform's 6 h ceiling before anything says so.
    """
    with pytest.raises(ValidationError, match=re.escape("council.shard_timeout_minutes")):
        AppConfig.model_validate({"run": {"judge_shard_timeout_minutes": 200}})


def test_a_band_that_cannot_draw_the_hardest_labelled_pair_is_refused() -> None:
    """The pair a wrong line publishes first has to be inside the band the fit judges.

    A band opening above the highest two-story mark draws only pairs nobody has
    marked apart, so the record fills with easy agreements and the line is never
    tested against the case that would prove it wrong. This bites where the
    floor_min check does not: a floor raised above that mark lets a band clear
    the first ceiling and miss the second.
    """
    with pytest.raises(ValidationError, match="the line most has to get right"):
        SameStoryConfig(
            floor_min=0.98,
            adaptive_dedup_threshold=SimilarityThresholdConfig(band_low=0.95),
        )

    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).assemble.same_story
    assert committed.judging_knobs().band_low < HOLDOUT_TWO_STORY_MAX


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
    assert AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")) is not None

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
    assert budget.SECONDS_A_JUDGED_PAIR < 2 * placement.SECONDS_A_CALL, (
        "a measured pair costs less than the derived figure doubled, which is why the "
        "derived one was an unlabelled margin rather than a reading"
    )


def test_the_two_contract_modules_share_one_grid_tolerance() -> None:
    """Two literals for one rule drift the first time somebody loosens one.

    The config and the record have to agree exactly, or a band the knob block
    accepts is a band the record refuses - hours later, in CI, on the first day counted.
    """
    assert placement.GRID_TOLERANCE is story_similarity_distribution.GRID_TOLERANCE


def test_the_committed_defaults_build_a_record_the_contract_accepts() -> None:
    """The knob block and the record are two shapes, and neither may read the other's file.

    So the agreement is held here: the three band knobs, turned into a record the
    way the counting will turn them, produce something the record's own validators
    accept. A test rather than a field rule, because a field rule would need one
    of the two shapes to import the other's on-disk value.
    """
    knobs = SimilarityThresholdConfig()
    slots = round((knobs.band_high - knobs.band_low) / knobs.bin_width)

    record = StorySimilarityDistribution(
        version=StorySimilarityDistribution.schema_version(),
        band_low=knobs.band_low,
        band_high=knobs.band_high,
        bin_width=knobs.bin_width,
        slots=tuple(
            ScoreSlot(bin_low=round(knobs.band_low + i * knobs.bin_width, 3))
            for i in range(slots)
        ),
    )

    assert slots == 120
    assert len(record.slots) == 120
    assert record.counted_dates == ()


def test_the_feature_ships_off_and_a_fresh_clone_publishes_what_it_always_did() -> None:
    """Guardrail #6: a feature in development ships behind a flag, default agreed.

    Nothing reads this block yet, so the switch is the whole of the promise: a
    clone that has never heard of the fitted line publishes exactly the groups
    `floor_min` produced before the block existed. A clone with no judge in it
    has no block at all, which reaches the same day by the shorter road.
    """
    fresh = AppConfig.model_validate({}).assemble.same_story
    committed = AppConfig.from_json(
        read_text(CONFIG_DIR / "idhazh.json")
    ).assemble.same_story.judging_knobs()

    assert fresh.adaptive_dedup_threshold is None
    assert committed.enabled is False
    assert committed == SimilarityThresholdConfig(), "the committed file spells the defaults"

    for name in ("enabled", "step_change_guard_enforced"):
        described = SimilarityThresholdConfig.model_fields[name].description or ""
        assert "Removal condition" in described, (
            f"adaptive_dedup_threshold.{name} has no removal condition on its own line"
        )


def test_a_config_with_no_judge_in_it_validates_and_stays_that_way() -> None:
    """The zero-judge condition, expressed as a config test.

    A block built by a default factory cannot express "no judge is configured":
    absent and present-at-defaults read the same afterwards, so the condition
    would be asserted and never tested. The block is optional and defaults to
    absent, so the absence survives validation and this test can fail.

    The council's own runner numbers are in their own block, so a file with no
    judge in it still says how long a judging shard may run and how many of them
    there are.
    """
    none_at_all = AppConfig.model_validate({})

    assert none_at_all.assemble.same_story.adaptive_dedup_threshold is None
    assert none_at_all.council.shard_timeout_minutes >= 1
    assert none_at_all.council.shards >= 1

    committed = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    del committed["assemble"]["same_story"]["adaptive_dedup_threshold"]
    without_a_judge = AppConfig.model_validate(committed)

    assert without_a_judge.assemble.same_story.adaptive_dedup_threshold is None
    assert without_a_judge.council == AppConfig.model_validate({}).council


def test_the_whole_range_of_the_repair_cap_loads() -> None:
    """A knob whose top half will not load is a lying bound.

    Dates are a PARALLEL axis - one job a date, each under its own
    `shard_timeout_minutes` - so nothing multiplies a per-shard time budget by
    this number. A check that did would refuse a config the knob's own bound
    admits, and would be comparing parallel work against a per-job clock.
    """
    field = CouncilConfig.model_fields["repair_dates_a_night"]
    lowest = next(bound.ge for bound in field.metadata if hasattr(bound, "ge"))
    highest = next(bound.le for bound in field.metadata if hasattr(bound, "le"))

    for value in range(lowest, highest + 1):
        loaded = AppConfig.model_validate({"council": {"repair_dates_a_night": value}})
        assert loaded.council.repair_dates_a_night == value


def test_the_council_carries_its_own_window_its_floor_and_its_cap() -> None:
    """Three knobs the venue owns, because all three price a runner.

    What counts as behind is the tenant's - only it knows what it has read - but
    how far back the council asks, how far back it may reach at all, and how
    many older dates one night repairs are the venue's, because each one is
    another job a tenant a shard.
    """
    committed = AppConfig.model_validate(json.loads(read_text(CONFIG_DIR / "idhazh.json"))).council
    fresh = AppConfig.model_validate({}).council

    assert committed.repair_window_nights == fresh.repair_window_nights
    assert committed.first_night == fresh.first_night
    assert committed.repair_dates_a_night == fresh.repair_dates_a_night
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", committed.first_night), (
        "the floor is a date the window arithmetic can read"
    )
