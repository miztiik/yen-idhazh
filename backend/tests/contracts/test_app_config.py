"""Does the committed config validate, and is every tunable value a knob?"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh import config
from idhazh.classify import dag
from idhazh.classify.calls import call_one_output_tokens, call_two_output_tokens
from idhazh.contracts import canonical_json
from idhazh.contracts.app_config import (
    PAGES_HARD_CAP_MB,
    SUPERSEDED_APP_NAMES,
    SUPERSEDED_COLLECT_NAMES,
    SUPERSEDED_MODELS_NAMES,
    SUPERSEDED_RETENTION_NAMES,
    AppConfig,
    CollectConfig,
    ConsoleConfig,
    EvaluationConfig,
    InferenceConfig,
    ModelsConfig,
    ObservabilityConfig,
    RetentionConfig,
    SystemPlacement,
    UiConfig,
    VisualSide,
    months_a_window_can_touch,
)
from idhazh.contracts.appearance_config import AppearanceConfig, ChartConfig
from idhazh.contracts.call_cost import CallKind
from idhazh.contracts.export import CONTRACTS
from idhazh.contracts.run_manifest import RunManifest
from idhazh.extract import TOKENS_PER_WORD
from idhazh.fingerprint import NOT_DIGESTED, digested_inference_fields
from idhazh.measured import CALL_ONE_BODY_TOKENS_A_WORD as _CALL_ONE_A_WORD
from idhazh.measured import CALL_ONE_MENU_TOKENS_A_ROW as _MENU_A_ROW
from idhazh.measured import CALL_ONE_SCAFFOLD_TOKENS as _CALL_ONE_SCAFFOLD
from idhazh.measured import CALL_TWO_SEAM_TOKENS as _CALL_TWO_SEAM
from idhazh.measured import PROMPT_OVERHEAD_TOKENS as _PROMPT_OVERHEAD
from idhazh.measured import WORST_TOKENS_A_WORD as _WORST_TOKENS

from ._fixtures import (
    APP_CONFIG_EVERY_KNOB_DIFFERS,
    CONFIG_FILES,
    committed_models,
    committed_models_raw,
    copy_config,
    entry_with,
    swapped_summarizer,
)

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("name", sorted(CONFIG_FILES), ids=lambda n: n)
def test_config_file_validates(name: str) -> None:
    CONFIG_FILES[name].from_json(read_text(CONFIG_DIR / name))

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
    """The other arm, and the reason the field is here at all.

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

def test_the_runtime_counters_are_on_without_being_asked_for() -> None:
    """A run that did not count is a run that cannot say how close it came.

    llama-server publishes the context high watermark only under `--metrics`.
    Off by default would mean the number exists on the runs nobody thought to
    switch it on for, which is every ordinary day.

    The fresh-clone arm drops the settings block and the weights digest
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
    nothing has put a 49,152 window in front of them - so it keeps 8,192. That
    is the whole reason the block sits on the entry rather than on `models`:
    a number measured against one model may not be inherited by another.

    Attention is pinned in the same file. `auto` is a runtime autodetect that
    may resolve differently on other silicon, and a run that cannot name the
    kernel it used cannot be compared with one that can (Guardrail #10).
    """
    models = committed_models()

    assert models.summarize.inference.n_ctx == 49152
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
CALL_ONE_SCAFFOLD_TOKENS: Final = int(_CALL_ONE_SCAFFOLD.value)

CALL_ONE_BODY_TOKENS_A_WORD: Final = _CALL_ONE_A_WORD.value

CALL_ONE_MENU_TOKENS_A_ROW: Final = _MENU_A_ROW.value

CALL_TWO_SEAM_TOKENS: Final = int(_CALL_TWO_SEAM.value)

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
    return worst_prompt, worst_prompt + inference.max_output_tokens

def test_the_longest_article_the_cap_allows_still_fits_the_window() -> None:
    """The cap and the window are one decision, and this is where they meet.

    Both sides are read from `config/` (Guardrail #6), so the assertion survives the
    next move of either. It is the guard that was missing on 2026-09-09: the cap
    went from 5,000 to 10,000 tokens that day and could not have, at the 8,192
    window committed the day before - 14,089 tokens against 8,192 is 172 percent
    of it. Nothing in the tree said so. A doc said so, and a doc does not fail.

    The worst case is built from the measured expansion rather than from
    `TOKENS_PER_WORD`. At the committed cap of 10,000 that is 997 + 12,191 + 900
    = 14,088 tokens of 49,152, which is 29 percent. **It is the smaller of the
    two sums this file now holds and it is the one that is retiring**, so read
    `test_the_two_calls_fit_the_window_at_the_cap` before concluding the window
    has room: that one sizes 39,284 over the same cap.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    inference = committed_models().summarize.inference
    worst_prompt, worst_sequence = _worst_sequence_tokens(committed)

    assert worst_sequence <= inference.n_ctx, (
        f"the longest article extract.truncation_cap_tokens "
        f"({committed.extract.truncation_cap_tokens}) lets through is "
        f"{worst_prompt} prompt tokens, and {inference.max_output_tokens} of answer "
        f"puts the sequence at {worst_sequence} against a window of {inference.n_ctx}. "
        "Raise models.summarize.inference.n_ctx beside the cap, or lower the cap."
    )

def _worst_two_call_sequence_tokens(committed: AppConfig) -> tuple[int, int]:
    """Call 1's prompt at the cap, and the whole sequence behind it.

    A second derivation and not a widening of the one above, because the two
    paths render different prompts. The single call sends one system turn and
    the article. Call 1 sends a system turn that carries both jobs, the article
    with an address in front of every sentence, and a menu of every quantity and
    date the extractor already cut - then pays for its own reply twice, once as
    a decode and once again inside call 2's prompt.

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
    guard that change can edit; a row that adds a node has to come here and say
    so as well, which is the point at which ESCALATE trigger 6 of
    `TODO/20260910-23-article-classification-plan.md` section 12a has fired.

    **A labelling row does not add a node.** It adds a field to call 1's reply
    shape, and `call_one_output_tokens` re-derives the budget from the shape's
    own bounds on import.
    """
    assert len(dag.NODES) == dag.NODE_COUNT == 2
    assert [node.name.value for node in dag.NODES] == ["label", "summarize_and_plan"]
    assert {node.name.value for node in dag.NODES} <= {kind.value for kind in CallKind}, (
        "a node the ledger has no CallKind for records its cost as nothing"
    )

def test_the_two_calls_fit_the_window_at_the_cap() -> None:
    """The window has to hold both calls, and nothing sized both until today.

    The test above sizes the single call this plan is replacing and passes with
    room. That is the trap: a green gate over the path being retired reads as
    coverage of the path replacing it. The two-call sequence is 2.8 times the
    single call's, because call 1's reply is paid twice and the candidate menu
    is paid once, and neither term exists on the single-call path at all.

    Both sides come from `config/` (Guardrail #6) and the arithmetic is measured
    rather than assumed: at the committed cap of 10,000 tokens and a menu of 256
    rows the prompt sizes at 28,041 and the sequence at 39,284 tokens, which is
    80 percent of a 49,152 window with 9,868 spare.

    **The 9,868 is a margin with a derivation, which is why it is not wider.**
    It is 25 percent, the size of the one tokenizer miss on record - `measured`
    says 1.585 tokens a word and the densest cap-length build delivered 1.952 -
    rounded up to a whole multiple of 16,384 and of the 512-token batch. A wider
    window costs almost nothing in memory and costs this assertion its reach:
    the gate is the product on this path, and it cannot report a sequence that
    grew until the sequence has outgrown the window. Ruled by Carmack,
    2026-09-13, over the 65,536 this branch first carried.

    **At 32,768 this failed by 6,516 tokens and the failure was not theoretical.**
    Of eight cap-length articles built from committed corpus prose on 2026-09-13,
    three measured over 32,768 on their own and the worst reached 37,495.

    The failure it catches is silent. `--no-context-shift` means a decode that
    runs into the wall stops there on an ordinary HTTP 200, `recovered_completion`
    salvages the summary, and the item publishes with no picture - so what a
    window this sum does not fit produces is not an error but a quiet drop in how
    many items carry a picture at all.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    inference = committed_models().summarize.inference
    prompt, sequence = _worst_two_call_sequence_tokens(committed)

    assert sequence <= inference.n_ctx, (
        f"the longest article extract.truncation_cap_tokens "
        f"({committed.extract.truncation_cap_tokens}) lets through makes a {prompt}-token "
        f"call 1 prompt at elements.max_per_article of "
        f"{committed.elements.max_per_article}. Call 1's {call_one_output_tokens()}-token "
        f"reply, the {CALL_TWO_SEAM_TOKENS}-token seam and call 2's "
        f"{call_two_output_tokens(committed.summarize)}-token reply put the pair at "
        f"{sequence} against a window of {inference.n_ctx}, over by "
        f"{sequence - inference.n_ctx}. Raise models.summarize.inference.n_ctx, or "
        "lower extract.truncation_cap_tokens or elements.max_per_article beside it. "
        "KV is 32 KiB a token on the configured weights, so a doubling is about a "
        "gigabyte and docs/reference/measurements.md says what the runner had free."
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
    """The two halves of row 3's digest decision, in one place.

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

    The out-of-bounds arm names its own `min_window_days` rather than leaning on
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

def test_the_windows_and_the_reading_marks_are_the_spans_the_committed_config_names() -> None:
    """The six spans row 1 of the constant-cost-reads plan settled, read off disk.

    Each is asserted against `config/` rather than against the model, because a
    default and a committed value are two different facts and only the second is
    what ships. The console reads its window out of `config/appearance.json`,
    which is the last merge layer, and `config/idhazh.json` still carries the
    keys it carried before the split - so where both files name a span, both are
    read here and the pair has to agree.

    Why each number is what it is belongs in the field descriptions and in the
    changelog entry dated 2026-09-06T14:00. This test only holds them still.
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

    # The two knobs this row minted. Nothing reads either yet - rows 8 and 25 of
    # TODO/20260906-constant-cost-reads-plan.md do - so the committed value and
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

    The archive gets a window control in row 25 of
    TODO/20260906-constant-cost-reads-plan.md, and it reuses the console's
    presets. So `archive_window_days` names a member of that list rather than
    declaring a second list of day counts, and both documents refuse a file
    where it does not - which is the same rule `console.default_window_days`
    has had since 2026-08-29.

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
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    fresh = AppConfig.model_validate({})

    assert fresh.observability == committed.observability
    assert fresh.observability.evaluation_enabled
    assert fresh.observability.telemetry_publish
    assert fresh.observability.runtime_counters_scrape
    assert fresh.observability.tracing_enabled

def test_the_item_health_census_is_not_switchable() -> None:
    """The denominator under every rate this project publishes has no off switch.

    Turning the census off would not thin a measurement, it would make every
    other measurement unreadable - a failure rate with no denominator beside it
    is the exact defect the census exists to prevent. The guard is the switch
    list itself, so adding a fifth boolean fails here and has to be argued for.

    `tracing_enabled` was the fourth, added 2026-08-30 and turned on by default
    2026-09-06. The argument it had to make: it switches an instrument nothing
    else divides by. No page reads a span, no gate consults one, and every rate
    the console prints keeps its denominator whether tracing is on or off - which
    is not true of any of the other three in the same way, and is why it is
    allowed to be a switch at all.
    """
    switches = {
        name
        for name, field in ObservabilityConfig.model_fields.items()
        if field.annotation is bool
    }
    assert switches == {
        "evaluation_enabled",
        "telemetry_publish",
        "runtime_counters_scrape",
        "tracing_enabled",
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
        "public_scores_keep_months",
        "public_feed_health_keep_months",
        "public_run_days_keep_months",
        "public_day_metrics_keep_months",
        "public_machine_keep_months",
        "public_span_rollup_keep_months",
    }
    # Three published payloads are held equal to the ledger they project, so
    # lowering either half has to lower both to reach the shortness check.
    paired = {
        "item_health_full_grain_months": "public_telemetry_keep_months",
        "public_telemetry_keep_months": "item_health_full_grain_months",
        "scores_full_grain_months": "public_scores_keep_months",
        "public_scores_keep_months": "scores_full_grain_months",
        "feed_health_keep_months": "public_feed_health_keep_months",
        "public_feed_health_keep_months": "feed_health_keep_months",
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

def test_a_config_still_carrying_a_removed_knob_is_refused_by_name() -> None:
    """Decision 2: a removed knob fails loudly and names what to use instead.

    Every model here forbids unknown keys, so all three names already failed -
    with "extra inputs are not permitted", which does not tell an operator where
    their number went. Ignoring the key would be worse still: an edit that takes
    no effect is a value somebody believes.

    The old value is not carried forward either. `keep_months` was set against a
    check that compared `months * 30` against the console window instead of the
    shards that window selects, so honouring it would honour the defect.
    """
    for block, removed, successor in (
        ("observability", "keep_months", "item_health_full_grain_months"),
        ("observability", "hard_delete_after_months", "item_health_aggregate_keep_months"),
        ("collect", "quarantine_after_failures", "availability_strikes_before_rest"),
    ):
        model = ObservabilityConfig if block == "observability" else CollectConfig
        with pytest.raises(ValidationError, match=successor) as raised:
            model.model_validate({removed: 13})
        assert f"{block}.{removed}" in str(raised.value)

def test_the_removed_names_are_the_three_this_row_retired() -> None:
    """The map is what the refusal message reads, so it is the map that is asserted."""
    assert dict(SUPERSEDED_COLLECT_NAMES) == {
        "quarantine_after_failures": "availability_strikes_before_rest"
    }
    assert dict(SUPERSEDED_RETENTION_NAMES) == {
        "keep_months": "item_health_full_grain_months",
        "hard_delete_after_months": "item_health_aggregate_keep_months",
    }

def test_an_unrelated_knob_in_a_block_with_no_removed_name_is_untouched() -> None:
    """The refusal fires on the removed name and on nothing else."""
    assert ObservabilityConfig.model_validate({"sample_rate": 0.5}).sample_rate == 0.5
    assert CollectConfig.model_validate({"max_per_source": 3}).max_per_source == 3

#: Every place `pipeline_fingerprint` may still be named in source a person
#: wrote, and why. The removal cannot be gated on "the name appears nowhere":
#: the read-side migration has to name the key it pops, and one shape still
#: declares the field because the console still reads its column. So the gate is
#: that every mention is one of these, with its reason beside it.
FINGERPRINT_SURVIVORS: Final[dict[str, str]] = {
    "backend/idhazh/contracts/day_metrics.py": (
        "the popper: 23 committed state/day-metrics/ records and both published "
        "month mirrors carry the key, and extra=forbid refuses it"
    ),
    "backend/idhazh/contracts/run_manifest.py": (
        "the popper, spelled plural: all 23 committed run.json files carry "
        "pipeline_fingerprints and a published day is never rewritten"
    ),
    "backend/idhazh/contracts/eval_row.py": (
        "the one field that survives the drop, because the console reads its "
        "state/scores/ column for every day before RECORDED_INPUTS_FROM - the "
        "condition that removes it is on the line that declares it"
    ),
    "backend/idhazh/contracts/app_config.py": "a changelog entry, which is history",
    "backend/idhazh/contracts/score_archive.py": "a changelog entry and a docstring, both history",
    "backend/idhazh/contracts/evidence.py": "a changelog entry, which is history",
    "backend/idhazh/contracts/label_row.py": "a changelog entry, which is history",
    "backend/idhazh/contracts/public_eval.py": "a changelog entry, which is history",
    "backend/idhazh/contracts/qualification.py": "a changelog entry, which is history",
    "backend/idhazh/contracts/summary.py": "a changelog entry, which is history",
    "frontend/src/lib/server/model-work.ts": (
        "the dated historical branch, which reads the months committed before "
        "2026-09-12 and retires on the condition written beside RECORDED_INPUTS_FROM"
    ),
    "frontend/src/lib/console/eval-instruments.ts": (
        "the ledger column's own note, which says why no panel draws it"
    ),
}

#: The two shapes that carry a read-side migration for the retired key, the key
#: each one pops, and the misspelling that must still be refused. `RunRecord`
#: spells it plural, so one shared key constant in `base.py` would have covered
#: neither model honestly. Each misspelling is the key with one letter gone,
#: which is the shape a hand-written payload actually takes.
FINGERPRINT_POPPERS: Final[dict[str, tuple[str, str]]] = {
    "DayMetrics": ("pipeline_fingerprint", "pipeline_fingerprnt"),
    "RunManifest": ("pipeline_fingerprints", "pipeline_fingerprnts"),
}

#: One payload per popped shape, copied out of the committed archive so the
#: oracle reads a fixed file rather than whatever a run last wrote. They sit
#: outside `tests/fixtures/contracts/` on purpose: every file under that tree is
#: asserted to round-trip byte-identically through its own shape, and a payload
#: of the PREVIOUS shape cannot, which is the whole point of it.
FINGERPRINT_FIXTURES: Final[dict[str, Path]] = {
    "DayMetrics": FIXTURES_DIR / "retired-fingerprint" / "day-metrics.json",
    "RunManifest": FIXTURES_DIR / "retired-fingerprint" / "run-manifest.json",
}

def misspell(node: Any, key: str, wrong: str) -> Any:
    """The same payload with one key renamed, wherever in the tree it sits."""
    if isinstance(node, dict):
        return {(wrong if name == key else name): misspell(v, key, wrong) for name, v in node.items()}
    if isinstance(node, list):
        return [misspell(value, key, wrong) for value in node]
    return node

def test_nothing_reads_the_pipeline_fingerprint_except_the_places_named_here() -> None:
    """The stamp stopped gating, and the field is gone from nine of the ten shapes.

    A fixed-size read of code a person wrote, never of data a run appended
    (`CLAUDE.md` section 13). It grows with the codebase and not with the
    archive, so a day that publishes changes nothing here.

    The gate is not "the name appears nowhere", because two shapes have to name
    the key to pop it and one still declares the field. Both are named above,
    which is what makes this a rule rather than a habit.
    """
    roots = (
        (REPO_ROOT / "backend" / "idhazh", ("*.py",)),
        (REPO_ROOT / "frontend" / "src", ("*.ts", "*.svelte", "*.js")),
    )
    found: set[str] = set()
    for root, patterns in roots:
        for pattern in patterns:
            for path in root.rglob(pattern):
                if "pipeline_fingerprint" in path.read_text(encoding="utf-8"):
                    found.add(path.relative_to(REPO_ROOT).as_posix())

    assert found == set(FINGERPRINT_SURVIVORS), (
        "a module names pipeline_fingerprint that is not on the survivor list. "
        "Either it is a reader and has to stop reading, or it is a survivor and "
        "has to say why it survives."
    )

@pytest.mark.parametrize(("name", "key"), [(n, k) for n, (k, _) in FINGERPRINT_POPPERS.items()])
def test_a_payload_carrying_the_retired_key_parses_and_comes_back_without_it(
    name: str, key: str
) -> None:
    """The read-side migration `CLAUDE.md` section 11 owes for a breaking removal.

    Driven from a payload a real run wrote - `state/day-metrics/2026/09/11.json`
    and `frontend/public/digest/2026/09/11/run.json`, copied into
    `tests/fixtures/` so the oracle cannot change when the archive does.
    """
    contract = {model.__name__: model for model in CONTRACTS}[name]
    payload = json.loads(read_text(FINGERPRINT_FIXTURES[name]))
    assert key in canonical_json(payload), f"the fixture no longer carries {key}"

    parsed = contract.model_validate(payload)

    assert key not in canonical_json(parsed.model_dump(mode="json"))
    assert key not in contract.model_fields

@pytest.mark.parametrize(
    ("name", "key", "wrong"), [(n, k, w) for n, (k, w) in FINGERPRINT_POPPERS.items()]
)
def test_the_same_payload_with_the_key_misspelt_is_still_refused(
    name: str, key: str, wrong: str
) -> None:
    """The arm that matters, and the reason the popper names its key.

    A migration written as "drop whatever the model does not declare" passes the
    test above perfectly and turns `extra="forbid"` into `extra="ignore"` for the
    shape it sits on - so a misspelt key in a hand-written payload would parse
    and the value it was meant to carry would simply be absent.

    The misspelling is made here rather than committed as a second fixture,
    because renaming one key of the payload above is what proves the two differ
    in the spelling and in nothing else.
    """
    contract = {model.__name__: model for model in CONTRACTS}[name]
    payload = misspell(json.loads(read_text(FINGERPRINT_FIXTURES[name])), key, wrong)

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        contract.model_validate(payload)

def test_no_other_contract_learned_to_accept_the_retired_key() -> None:
    """The popper is opted into by two shapes and inherited by none.

    Written on `Model` or `Contract` instead, a popper reading a shared key list
    passes both arms above and silently opens every contract in the repository
    to a key only two of them ever held. Nothing else can fail that, which is why
    this arm is not optional.

    Driven from the committed contract fixtures, which are a fixed set of files a
    person wrote (`CLAUDE.md` section 13). `EvalRow` is skipped because it still
    declares the field.
    """
    checked = 0
    for model in CONTRACTS:
        key = "pipeline_fingerprint"
        if model.__name__ in FINGERPRINT_POPPERS or key in model.model_fields:
            continue
        directory = CONTRACT_FIXTURES_DIR / model.__schema_stem__
        for path in sorted(directory.glob("*.json")):
            payload = json.loads(read_text(path))
            if not isinstance(payload, dict):
                continue
            with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
                model.model_validate({**payload, key: "a" * 64})
            checked += 1
            break

    assert checked >= 30, f"only {checked} contracts were offered the retired key"

def test_swapping_the_model_is_one_line_and_reverting_is_the_same_line(tmp_path: Path) -> None:
    """The Oracle for row #6: the pointer is the whole swap, both ways.

    Before 2026-09-14 a swap was eleven lines edited in place in the file every
    other knob lives in, and a revert had to rebuild the previous model's
    measured numbers out of git history. Both models sit on disk now, so this
    moves one string and reads the resolved entry back - then moves it back and
    reads the incumbent.

    The candidate is BUILT rather than copied from a committed second model,
    because there is only one committed model and a test that waited for a
    second one would prove nothing until the day it was needed.
    """
    incumbent = copy_config(tmp_path)
    candidate = "models/other-model-q4km.json"
    other = committed_models_raw()
    other["summarize"] |= {
        "id": "some-other-model-q4-k-m",
        "repo": "someone/Other-GGUF",
        "file": "Other-Q4_K_M.gguf",
        "revision": "f" * 40,
        "sha256": "1" * 64,
        "hf_base_repo": None,
    }
    other["summarize"]["inference"]["declared_for"] = "1" * 64
    other["summarize"]["turns"]["declared_for"] = "1" * 64
    (tmp_path / "config" / candidate).write_text(
        canonical_json(other), encoding="utf-8", newline="\n"
    )
    before = read_text(tmp_path / "config" / "idhazh.json")

    point_at(tmp_path, candidate)
    swapped = config.load(tmp_path / "config")
    assert swapped.models.summarize.id == "some-other-model-q4-k-m"
    assert swapped.models.summarize.sha256 == "1" * 64
    assert changed_lines(before, read_text(tmp_path / "config" / "idhazh.json")) == 1

    point_at(tmp_path, incumbent)
    assert config.load(tmp_path / "config").models == committed_models()
    assert read_text(tmp_path / "config" / "idhazh.json") == before, (
        "the revert is the same one line, so the file comes back byte-identical"
    )

def point_at(root: Path, models_file: str) -> None:
    raw = json.loads(read_text(root / "config" / "idhazh.json"))
    raw["models_file"] = models_file
    (root / "config" / "idhazh.json").write_text(
        canonical_json(raw), encoding="utf-8", newline="\n"
    )

def test_folding_the_system_text_without_a_joiner_is_refused() -> None:
    """Decision 2, first half. The separator is what keeps the two blocks apart.

    Absent, the last instruction and the opening fence of the untrusted block
    render on one line. The prompt is still well formed, the grammar still
    accepts the reply, and the only symptom is a worse summary.
    """
    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(entry_with(system_role="fold_into_first_user"))

    assert "system_joiner is required under system_role='fold_into_first_user'" in str(
        raised.value
    )

def test_a_joiner_declared_beside_a_system_turn_is_refused() -> None:
    """Decision 2, second half. A dead field is a field somebody will trust.

    `own_turn` gives the system text a turn of its own, so nothing joins it to
    anything. A joiner set here is a value an operator chose, a reviewer read,
    and no render ever applied.
    """
    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(entry_with(system_role="own_turn", system_joiner="\n\n"))

    assert "where the system text has a turn of its own" in str(raised.value)

def test_a_fold_that_declares_a_joiner_loads() -> None:
    """The bite proof for both halves: the pair the refusals permit is legal."""
    folded = ModelsConfig.model_validate(
        entry_with(system_role="fold_into_first_user", system_joiner="\n\n")
    )

    assert folded.summarize.turns.system_joiner == "\n\n"

def test_a_template_that_reads_no_keyword_may_not_be_asked_to_think() -> None:
    """Decision 3, second half, and the two halves sit in different blocks.

    A null keyword means the request carries no `chat_template_kwargs` at all,
    so `inference.thinking` true asks for reasoning through a channel nothing
    sends. Neither block can see the other, so the entry is where the pair is
    checked.
    """
    payload = entry_with(thinking_kwarg=None)
    payload["summarize"]["inference"]["thinking"] = True

    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(payload)

    assert "sends no chat_template_kwargs at all" in str(raised.value)

def test_a_template_that_reads_no_keyword_loads_with_reasoning_off() -> None:
    """The bite proof. Null is a legal declaration, not a broken entry."""
    silent = ModelsConfig.model_validate(entry_with(thinking_kwarg=None))

    assert silent.summarize.turns.thinking_kwarg is None
    assert silent.summarize.inference.thinking is False

def test_the_committed_entry_names_the_keyword_rather_than_inheriting_it() -> None:
    """The name is a model fact, so the file that names the weights names it too.

    It was spelled in `backend/idhazh/llm/server.py` and sent to every model
    until 2026-09-14. The default is the incumbent's, which is why this asserts
    the file carries it rather than asserting the default resolves.
    """
    raw = committed_models_raw()

    assert raw["summarize"]["turns"]["thinking_kwarg"] == "enable_thinking"
    assert committed_models().summarize.turns.system_role is SystemPlacement.OWN_TURN

def changed_lines(before: str, after: str) -> int:
    old = before.splitlines()
    new = after.splitlines()
    assert len(old) == len(new), "a swap that adds or removes a line is not a one-line swap"
    return sum(1 for a, b in zip(old, new, strict=True) if a != b)

def test_a_config_that_still_carries_the_old_models_block_is_refused_by_name() -> None:
    """The read-side migration `CLAUDE.md` section 11 owes for the removal.

    Refused rather than lifted onto the new file. A lift would read one model
    out of the old block while `models_file` named another file, and the run
    would stand a server up on whichever won - which is the failure this row
    exists to end, one level up.
    """
    raw = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    raw["models"] = {"summarize": committed_models_raw()["summarize"]}

    with pytest.raises(ValidationError) as raised:
        AppConfig.model_validate(raw)

    assert "config.models is now config.models_file" in str(raised.value)
    assert SUPERSEDED_APP_NAMES["models"] == "models_file"

def test_the_pointer_may_not_leave_the_models_directory() -> None:
    """An operator's edit becomes a path this build opens, so the grammar bounds it.

    Held by the schema rather than checked in the loader, which is what makes it
    a refusal at load rather than a read four hundred seconds into a run.
    """
    for escape in (
        "../secrets.json",
        "models/../../secrets.json",
        "/etc/passwd",
        "models\\qwen.json",
        "models/qwen.txt",
        "idhazh.json",
    ):
        with pytest.raises(ValidationError, match="should match pattern"):
            AppConfig.model_validate({"models_file": escape})

def test_the_model_file_is_digested_with_the_rest_of_the_config() -> None:
    """A run that did not record it could not say which model's numbers it read.

    `models_file` names the file, so the digest of `config/idhazh.json` moves
    when the POINTER moves and says nothing about what the file it points at
    says. Both have to travel or a re-tuned model file is invisible to the
    record.
    """
    settings = config.load(CONFIG_DIR)
    recorded = {digest.path: digest.sha256 for digest in settings.digests}

    assert f"config/{settings.app.models_file}" in recorded
    text = read_text(CONFIG_DIR / settings.app.models_file)
    assert recorded[f"config/{settings.app.models_file}"] == sha256_of(text)

def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def test_a_model_swap_can_no_longer_inherit_settings_nothing_declared_for_it() -> None:
    """The Oracle: new weights under an untouched settings block are refused.

    Every number in an `inference` block is a measurement about one model on one
    runner. Until this gate, `models.summarize` could name a different
    repository, file, revision and digest with the block left exactly where it
    was and `AppConfig.model_validate` raised nothing - so the run stood a server
    up on numbers derived for weights it never opened and published a whole
    plausible day.
    """
    committed = committed_models()
    assert committed.summarize.inference.declared_for == committed.summarize.sha256

    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(swapped_summarizer())
    message = str(raised.value)
    assert "models.summarize.inference" in message, "the message names the block"
    assert "1" * 64 in message, "and the weights the entry now names"

def test_a_refused_model_file_is_named_by_the_loader(tmp_path: Path) -> None:
    """Every model has a file of its own, so a refusal has to say which one.

    The validator cannot: it is handed a payload, not a path. So the loader adds
    the address, and this is the arm that proves it rather than trusting it - an
    operator with two model files on disk and a refusal naming neither has to
    guess which one they broke.
    """
    written = copy_config(tmp_path, models=swapped_summarizer())

    with pytest.raises(ValueError) as raised:
        config.load(tmp_path / "config")

    message = str(raised.value)
    assert f"config/{written}" in message, "the refusal names the file that is wrong"
    assert "models.summarize.inference" in message, "and the block inside it"

def test_an_entry_that_declares_no_settings_of_its_own_is_refused_by_name() -> None:
    """A new entry written with no block of its own does not fall back to one."""
    raw = swapped_summarizer()
    del raw["summarize"]["inference"]
    with pytest.raises(ValidationError, match=re.escape("models.summarize.inference")):
        ModelsConfig.model_validate(raw)

def test_the_one_shared_settings_block_is_refused_by_name() -> None:
    """`models.inference` was one block applied to two models. It is gone.

    Refused rather than lifted onto both entries. A lift is the silent
    inheritance this row exists to end: it would hand a swapped entry the
    numbers the previous weights were measured on and raise nothing.

    It is the one entry in this map with a replacement to name. The other two
    are roles that were retired outright, so they carry an empty string and the
    refusal says so rather than inventing a successor.
    """
    raw = committed_models_raw()
    raw["inference"] = {"n_ctx": 8192}
    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(raw)
    assert "models.inference is now models.<role>.inference" in str(raised.value)
    assert SUPERSEDED_MODELS_NAMES["inference"] == "<role>.inference"
    assert not SUPERSEDED_MODELS_NAMES["visual_planner"]
    assert not SUPERSEDED_MODELS_NAMES["route"]

def test_every_committed_model_entry_declares_the_weights_its_settings_are_for() -> None:
    """The committed file states the pairing rather than implying it."""
    raw = committed_models_raw()
    assert "inference" not in raw
    for role in ModelsConfig.roles():
        entry = raw[role]
        assert entry["inference"]["declared_for"] == entry["sha256"], role

def test_a_run_manifest_written_before_the_settings_moved_still_reads() -> None:
    """The read side: a `model_ref` with no settings block opens on the defaults.

    Nineteen manifests sit under `frontend/public/digest/` with the shape
    `model_ref` had yesterday, and `frontend/src/lib/server/payload.ts` opens
    them at every build. A block that could not default would make each of them
    a payload today's build cannot read (`CLAUDE.md` section 11). Proved by
    removing the key rather than by reading a committed day, so it cannot age
    out of retention.
    """
    current = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    for run in current["runs"]:
        for use in run["models"]:
            del use["model_ref"]["inference"]

    older = RunManifest.model_validate(current)
    entry = older.runs[0].models[0].model_ref
    assert entry.inference.declared_for is None
    assert entry.inference.n_ctx == 8192, "the contract default, not a guess"
