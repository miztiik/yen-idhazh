"""The arithmetic `measure_two_calls` prints, checked without a model.

The tool itself needs a multi-gigabyte GGUF and runs a real server for minutes,
so it is an operator tool and never a test (`CLAUDE.md` section 13). What IS
testable is the part that can be quietly wrong: the split of one item's
re-prefilled tokens into three causes. A decomposition whose parts do not add up
is a guess with three decimal places.

Every completion below is a **recorded** reply rather than a stub - the numbers
are the 2026-09-10 reading written up in
`docs/architecture/summarize/prompt.md`, so every case is one a server really
produced (Guardrail #7). Nothing here touches the network and nothing reads a
collection a run appends to (Guardrail #12).
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR

from idhazh import config, summarize
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.article import Article
from idhazh.llm.server import Completion
from idhazh.sanitize import untrusted_block
from utilities.measure_two_calls import (
    Break,
    Sample,
    WrongWeightsError,
    article_from_user_turn,
    check,
    common_prefix,
    decompose,
    prefilled,
    refuse_undeclared_weights,
    sample_at_the_cap,
)

ARTICLE: Final = CONTRACT_FIXTURES_DIR / "article" / "ok.json"

#: The 2026-09-10 reading, verbatim: one item, two calls, a cold cache slot.
#: `Qwen3-8B-Q4_K_M.gguf` on a developer laptop, one run, no spread. It is here
#: because it is the case this tool was built to explain, not because the
#: numbers are a target.
RECORDED_ONE: Final = Completion(
    content="", prompt_tokens=1497, completion_tokens=205, cached_tokens=0
)
RECORDED_TWO: Final = Completion(
    content="", prompt_tokens=2389, completion_tokens=567, cached_tokens=1493
)


def loaded_app() -> AppConfig:
    return config.load(CONFIG_DIR).app


@pytest.mark.parametrize(
    ("one", "two"),
    [
        (RECORDED_ONE, RECORDED_TWO),
        (RECORDED_ONE, Completion(content="", prompt_tokens=2389, cached_tokens=1702)),
        (RECORDED_ONE, Completion(content="", prompt_tokens=2389, cached_tokens=2000)),
        (
            Completion(content="", prompt_tokens=9, completion_tokens=0, cached_tokens=9),
            Completion(content="", prompt_tokens=9, cached_tokens=9),
        ),
    ],
)
def test_the_three_causes_always_sum_and_that_is_why_they_are_not_the_oracle(
    one: Completion, two: Completion
) -> None:
    """The sum holds for every input, so a check on it proves nothing.

    `boundary` cancels out of the two call-2 causes in both branches of the
    `max`, so they come to `two.prompt_tokens - two.cached_tokens` whatever the
    numbers are. It is here as documentation: a reader who takes the printed
    total for a verification would trust a number they should not. What the run
    fails on is `check`, below.
    """
    assert decompose(one, two).total == prefilled(one, two)


def test_the_recorded_reading_splits_the_way_the_write_up_says() -> None:
    """209 behind the template break and the rest behind the article.

    The write-up reached the 209 by hand - 1,493 cached against the 1,702 call
    1's prompt and its reply come to. This is the same arithmetic in code, so
    the two cannot drift apart, and it shows what the write-up never named: the
    trailing turn is the larger share by a factor of three.
    """
    spend = decompose(RECORDED_ONE, RECORDED_TWO)
    assert spend.article_changed == 1497
    assert spend.template_broke == 209
    assert spend.trailing_turn == 687
    assert spend.template_broke + spend.trailing_turn == 896


def test_the_template_cause_is_everything_behind_the_break_not_the_break() -> None:
    """A four-token divergence does not cost four tokens.

    Hold the divergence at four and grow call 1's reply: the cause grows with
    the reply, because a prefix cache stops at the first difference and reads
    the rest again. That is the whole argument for row #3c and it is the one
    thing a reader of the old boolean could not see.
    """
    short = decompose(
        Completion(content="", prompt_tokens=1497, completion_tokens=10, cached_tokens=0),
        Completion(content="", prompt_tokens=2200, cached_tokens=1493),
    )
    long = decompose(RECORDED_ONE, RECORDED_TWO)
    assert short.template_broke == 14
    assert long.template_broke == 209
    assert long.template_broke - short.template_broke == 205 - 10


def test_a_prefix_that_survives_leaves_only_the_trailing_turn() -> None:
    """What row #3c buys: the template cause goes to zero and the parts still sum."""
    kept = Completion(content="", prompt_tokens=2389, cached_tokens=1702)
    spend = decompose(RECORDED_ONE, kept)
    assert spend.template_broke == 0
    assert spend.trailing_turn == 687
    assert spend.total == prefilled(RECORDED_ONE, kept)


def test_a_cache_reaching_past_call_ones_reply_still_sums() -> None:
    """The good-news branch, which today never fires.

    A cache that served more than call 1's prompt and reply would mean part of
    the trailing turn was cached too. It cannot make a cause negative and it
    cannot break the identity.
    """
    generous = Completion(content="", prompt_tokens=2389, cached_tokens=2000)
    spend = decompose(RECORDED_ONE, generous)
    assert spend.template_broke == 0
    assert spend.trailing_turn == 389
    assert spend.total == prefilled(RECORDED_ONE, generous)


def test_an_item_that_reused_everything_spends_nothing() -> None:
    idle = Completion(content="", prompt_tokens=1497, completion_tokens=0, cached_tokens=1497)
    spend = decompose(idle, Completion(content="", prompt_tokens=1497, cached_tokens=1497))
    assert spend.total == 0


def test_common_prefix_stops_at_the_first_difference() -> None:
    assert common_prefix([1, 2, 3, 4], [1, 2, 9, 4]) == 2
    assert common_prefix([1, 2, 3], [1, 2, 3]) == 3
    assert common_prefix([1, 2, 3], [1, 2]) == 2
    assert common_prefix([], [1]) == 0


#: The rendered reading that matches the recorded completions: call 1's prompt
#: renders to the 1,497 tokens the server charged for, and the two prompts
#: diverge at 1,493, which is where the cache stopped.
AGREES: Final = Break(at=1493, rendered_one=1497, rendered_two=2389, tail="", replay_tokens=205)


def test_the_checks_hold_when_the_render_and_the_cache_agree() -> None:
    spend = decompose(RECORDED_ONE, RECORDED_TWO)
    assert check(RECORDED_ONE, RECORDED_TWO, spend, AGREES).hold


def test_a_prompt_that_renders_to_another_length_fails() -> None:
    """The check that catches a diagnostic describing a prompt nobody sent.

    Rendering without the thinking flag every real request carries drops the
    empty think block, so the rendered prompt is four tokens short of the one
    the server charged for - and the tool would then report that the prefix
    never broke while the cache reading says it broke and cost 209 tokens.
    """
    spend = decompose(RECORDED_ONE, RECORDED_TWO)
    wrong = check(
        RECORDED_ONE, RECORDED_TWO, spend, replace(AGREES, rendered_one=1493, at=1493)
    )
    assert not wrong.hold
    assert wrong.failures() == [
        "call 1's rendered prompt is not the length the server charged for"
    ]


def test_a_cache_that_stopped_somewhere_else_fails() -> None:
    spend = decompose(RECORDED_ONE, RECORDED_TWO)
    wrong = check(RECORDED_ONE, RECORDED_TWO, spend, replace(AGREES, at=1200))
    assert not wrong.hold
    assert wrong.failures() == ["the cache did not stop where the rendered prompts diverge"]


def test_a_replay_shorter_than_the_reply_fails() -> None:
    """A runtime that splits reasoning out of `content` replays less than it wrote.

    `build_call_two_request` sends `one.content`, and a llama.cpp build this
    repository already names empties that field for a template whose generation
    prompt ends in a closing think tag. The assistant turn would then be empty,
    and every token of call 1's reply would be charged to the template cause
    where no row would remove it.
    """
    spend = decompose(RECORDED_ONE, RECORDED_TWO)
    wrong = check(RECORDED_ONE, RECORDED_TWO, spend, replace(AGREES, replay_tokens=0))
    assert not wrong.hold
    assert wrong.failures() == [
        "call 1's replayed turn is shorter than the reply it generated"
    ]


def test_an_unread_diagnostic_is_unread_and_not_a_failure() -> None:
    """A server that would not render is a missing reading, never a finding."""
    spend = decompose(RECORDED_ONE, RECORDED_TWO)
    assert check(RECORDED_ONE, RECORDED_TWO, spend, Break()).hold


def a_sample(key: str, words: int) -> Sample:
    article = Article.from_json(ARTICLE.read_text(encoding="utf-8"))
    body = " ".join(f"word{index}" for index in range(words))
    return Sample(
        url_key=key,
        article=Article.model_validate(
            article.model_dump(mode="json")
            | {"text": body, "word_count": words, "source_word_count": words}
        ),
    )


def test_the_cap_arm_is_built_to_the_cap_and_names_the_rows_it_joined() -> None:
    """The corpus cannot supply an article at the cap, so one is built.

    Driven from two built samples rather than from `corpus/corpus.jsonl`, which
    a run appends to (Guardrail #12). What is under test is the joining and the
    cut, and a fixed pair shows both: neither row alone reaches the cap.
    """
    cap = 1300
    allowed = cap // 13 * 10
    built = sample_at_the_cap([a_sample("first", 600), a_sample("second", 600)], cap_tokens=cap)
    assert built.article.word_count == allowed
    assert built.article.truncated
    assert built.article.truncated_at_tokens == cap
    assert built.url_key == "built from first+second"


def test_the_cap_arm_stops_joining_once_it_has_enough() -> None:
    """A row past the cap is not read, so the arm names only what it used."""
    built = sample_at_the_cap(
        [a_sample("first", 5000), a_sample("second", 5000)], cap_tokens=1300
    )
    assert built.url_key == "built from first"


def test_the_title_and_the_body_come_back_out_of_a_user_turn() -> None:
    """The corpus holds rendered turns, so an article has to be read back out.

    Round-tripped through the real `summarize.user_turn`, so a change to how the
    fence or the title line is written breaks this rather than silently handing
    the model a body with `Title: ` glued to its front.
    """
    article = Article.from_json(ARTICLE.read_text(encoding="utf-8"))
    title, body = article_from_user_turn(summarize.user_turn(article))
    assert title == article.title
    assert body == article.text


def test_a_turn_whose_first_line_is_not_a_title_keeps_its_first_paragraph() -> None:
    """The guard that stops the parser eating a paragraph it mistook for a title.

    `Article` refuses an ok article with no title, so this turn cannot come off
    the corpus today. The branch is here because without it the split on the
    first blank line would quietly drop the opening paragraph of any turn that
    ever did arrive that way, and a body one paragraph short is a prompt nobody
    would look at twice.
    """
    body = "The first paragraph, which is not a title.\n\nThe second."
    title, kept = article_from_user_turn(f"Source form: article\n\n{untrusted_block(body)}")
    assert title is None
    assert kept == body


def declaring(app: AppConfig, digest: str) -> AppConfig:
    """The same config, declaring a different set of summarizer weights.

    Both cells move, because `ModelsConfig` refuses a block whose `declared_for`
    is not its own entry's `sha256` - which is exactly why the tool has to hash
    the bytes on disk rather than reading either cell.
    """
    raw: dict[str, Any] = app.model_dump(mode="json")
    raw["models"]["summarize"]["sha256"] = digest
    raw["models"]["summarize"]["inference"]["declared_for"] = digest
    return AppConfig.model_validate(raw)


def test_the_harness_accepts_the_weights_config_declares(tmp_path: Path) -> None:
    """The accepting arm, so the refusal below is not a function that always raises."""
    weights = tmp_path / "declared.gguf"
    weights.write_bytes(b"GGUF the config names")
    digest = hashlib.sha256(weights.read_bytes()).hexdigest()
    assert refuse_undeclared_weights(weights, declaring(loaded_app(), digest)) == digest


def test_the_harness_refuses_weights_config_does_not_declare(tmp_path: Path) -> None:
    """Point it at the wrong file on purpose.

    This is how the reading that started row #3d came to be taken on a retired
    model without anybody noticing: the tool read the inference block from
    config and the weights from the command line, and never compared them.
    """
    app = loaded_app()
    impostor = tmp_path / "not-the-weights.gguf"
    impostor.write_bytes(b"GGUF, but not the right ones")
    with pytest.raises(WrongWeightsError) as refusal:
        refuse_undeclared_weights(impostor, app)
    assert str(app.models.summarize.inference.declared_for) in str(refusal.value)
    assert hashlib.sha256(impostor.read_bytes()).hexdigest() in str(refusal.value)
