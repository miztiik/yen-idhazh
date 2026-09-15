"""Plan 28 row #13a. The budget reader's rules, proved without a socket.

Every case is driven by a committed fixture or a built value and nothing here
touches the network (Guardrail #7). Every rule has both halves: it passes on the
agreeing value and refuses on a changed one, with the message naming both sides.
A check nobody has made fail is a check nobody has tested.

**The token counts are not a vocabulary.** `tests/fixtures/llm/budget-probe.json`
records a fixed characters-a-token rate and says so, so what these cases prove is
the probe construction, the arithmetic, the paste block and the refusals - this
repository's rules, none of them the tokenizer's. Tokenizer agreement is proved
solely by `measure_budgets.py read` against a live server, which is row #13b.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh import config
from idhazh.contracts.taxonomy import LifecycleStatus
from idhazh.contracts.visual import PlanEncodings
from idhazh.measured import (
    SIZED_BY_A_READING_HERE,
    readings_awaiting_a_retake,
)
from idhazh.sanitize import FENCE_CLOSE, FENCE_OPEN
from utilities.measure_budgets import (
    PLAN_PROBES,
    ServerSilentError,
    corpus_bodies,
    definition_probe,
    empty_role_fragment,
    main,
    plan_roles,
    read_definition_budget,
    read_empty_role_budget,
    read_tokens_a_word,
    render_check,
    render_paste,
    take_every_reading,
    tokens_in_reply,
)

PROBE: Final = FIXTURES_DIR / "llm" / "budget-probe.json"
PLAN_FIXTURES: Final = FIXTURES_DIR / "contracts" / "visual-plan"
CORPUS_ROW_FIXTURE: Final = FIXTURES_DIR / "contracts" / "corpus-row" / "harvested.json"
STAMP: Final = {
    "subject": "a" * 64,
    "runner": "a box with no weights on it",
    "taken_on": "2026-09-14",
}


def probe() -> dict[str, Any]:
    """The fixture, refused unless it says where it came from.

    The same three fields `test_summarize.probe_fixture` enforces, checked here
    too rather than imported: this module has to fail on its own when a later
    edit strips the provenance out of the file it reads.
    """
    loaded: dict[str, Any] = json.loads(read_text(PROBE))
    missing = [key for key in ("recorded", "why_not_recorded", "how_to_record") if key not in loaded]
    if missing:
        raise ValueError(f"{PROBE.name} declares no provenance: it is missing {', '.join(missing)}")
    if not loaded["recorded"] and not str(loaded["how_to_record"]).strip():
        raise ValueError(
            f"{PROBE.name} says it was not captured and does not say how to capture it, "
            "so nobody can ever replace it with the real thing"
        )
    return loaded


class RecordedTokenizer:
    """A tokenizer whose counts come off the fixture, not off a vocabulary.

    Not a mock: it replays a recorded rate rather than asserting that it was
    called. The rate is fixed and the fixture says so, which is what makes every
    count below a deterministic function of the probe text and the arithmetic
    checkable by hand.
    """

    def __init__(self, characters_a_token: float) -> None:
        self.characters_a_token = characters_a_token
        self.seen: list[str] = []

    def count(self, text: str) -> int:
        self.seen.append(text)
        return max(1, math.ceil(len(text) / self.characters_a_token))


@pytest.fixture
def tokenizer() -> RecordedTokenizer:
    return RecordedTokenizer(float(probe()["characters_a_token"]))


# --- The fixture says where it came from -------------------------------------


def test_a_probe_fixture_that_hides_where_it_came_from_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proved by writing a file that hides it, never by asserting the committed one is fine."""
    silent = tmp_path / "silent.json"
    silent.write_text('{"characters_a_token": 4}\n', encoding="utf-8")
    monkeypatch.setattr("test_measure_budgets.PROBE", silent)
    with pytest.raises(ValueError, match="declares no provenance"):
        probe()

    mute = tmp_path / "mute.json"
    mute.write_text(
        json.dumps({"recorded": False, "why_not_recorded": "no weights", "how_to_record": " "})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("test_measure_budgets.PROBE", mute)
    with pytest.raises(ValueError, match="does not say how to capture it"):
        probe()


# --- The reply shape ---------------------------------------------------------


def test_a_tokenize_reply_is_counted_and_one_without_tokens_is_refused() -> None:
    """A reply with no `tokens` array is not a count of zero - it is not a count."""
    recorded = probe()
    assert tokens_in_reply(recorded["tokenize_reply"], base="http://h") == 3

    with pytest.raises(ServerSilentError) as refusal:
        tokens_in_reply(recorded["tokenize_reply_without_tokens"], base="http://h")

    said = str(refusal.value)
    assert "http://h" in said, "the refusal does not say which server answered"
    assert "no vocabulary loaded" in said, "the refusal does not quote what the server said"


# --- Probe one: the definition sentences -------------------------------------


def test_the_definition_probe_is_the_block_the_prompt_really_carries() -> None:
    """Not a join written beside it: the two would part the first time the layout moved."""
    taxonomy = config.load(CONFIG_DIR).taxonomy

    block, offered = definition_probe(CONFIG_DIR)

    assert block == taxonomy.definition_block()
    assert offered == sum(
        1
        for group in (taxonomy.verticals, taxonomy.lenses, taxonomy.events)
        for entry in group
        if entry.status is LifecycleStatus.ACTIVE
    )
    for entry in taxonomy.verticals + taxonomy.lenses + taxonomy.events:
        if entry.status is LifecycleStatus.ACTIVE:
            assert entry.definition in block


def test_a_draft_entry_costs_a_labelling_prompt_nothing(tmp_path: Path) -> None:
    """The other half: a word no prompt carries may not weigh on the bound that sizes it."""
    live = json.loads(read_text(CONFIG_DIR / "taxonomy.json"))
    drafted = json.loads(read_text(CONFIG_DIR / "taxonomy.json"))
    drafted["lenses"][0]["status"] = "draft"

    block, offered = definition_probe(a_config_dir(tmp_path / "live", live))
    quieter, fewer = definition_probe(a_config_dir(tmp_path / "drafted", drafted))

    assert fewer == offered - 1
    assert live["lenses"][0]["definition"] not in quieter
    assert len(quieter) < len(block)


def test_the_definition_reading_divides_by_what_it_counted(
    tokenizer: RecordedTokenizer,
) -> None:
    reading = read_definition_budget(tokenizer, config_dir=CONFIG_DIR, stamp=STAMP)
    block, offered = definition_probe(CONFIG_DIR)

    assert reading.record == "DEFINITION_SENTENCE_TOKENS"
    assert reading.working["entries_offered"] == offered
    assert reading.value == tokenizer.count(block)
    assert reading.working["tokens_an_entry"] == pytest.approx(reading.value / offered)
    assert reading.working["characters"] == len(block)


def a_config_dir(root: Path, taxonomy: dict[str, Any]) -> Path:
    """A whole config tree with one file replaced, because `config.load` reads them all."""
    root.mkdir(parents=True, exist_ok=True)
    for name in ("idhazh.json", "sources.json", "watchlist.json", "appearance.json"):
        (root / name).write_bytes((CONFIG_DIR / name).read_bytes())
    (root / "models").mkdir(exist_ok=True)
    for model in (CONFIG_DIR / "models").iterdir():
        (root / "models" / model.name).write_bytes(model.read_bytes())
    (root / "taxonomy.json").write_text(json.dumps(taxonomy), encoding="utf-8")
    return root


def test_a_vocabulary_that_offers_nothing_yields_no_reading(
    tokenizer: RecordedTokenizer, tmp_path: Path
) -> None:
    """The refusing half: a bound sized on nothing would be a number with no method."""
    drafted = json.loads(read_text(CONFIG_DIR / "taxonomy.json"))
    for group in ("verticals", "lenses", "events"):
        for entry in drafted[group]:
            entry["status"] = "draft"
            entry.pop("retired_on", None)

    with pytest.raises(ValueError, match="offers no definition to any prompt"):
        read_definition_budget(
            tokenizer, config_dir=a_config_dir(tmp_path, drafted), stamp=STAMP
        )


# --- Probe two: the empty encoding roles -------------------------------------


def test_the_roles_come_off_the_shape_and_not_off_the_fixture() -> None:
    """A role a fixture omits is an empty role, and a decoder emits it either way."""
    assert plan_roles() == tuple(PlanEncodings.model_fields)

    declined = json.loads(read_text(PLAN_FIXTURES / "declined.json"))
    fragment = empty_role_fragment(declined, plan_roles())

    assert fragment.count("[]") == len(plan_roles()), (
        "the declining plan fills no role, so every declared role has to appear in the "
        "fragment even where the fixture has no key for it"
    )
    for role in plan_roles():
        assert f'"{role}":[],' in fragment


def test_a_filled_role_is_not_counted_as_an_empty_one() -> None:
    """The other half: the fragment shrinks by exactly the roles a plan fills."""
    roles = plan_roles()
    filled = {"encodings": {roles[0]: ["quantity-1-2"]}}

    fragment = empty_role_fragment(filled, roles)

    assert fragment.count("[]") == len(roles) - 1
    assert f'"{roles[0]}":[],' not in fragment


def test_the_empty_role_reading_takes_the_wider_of_the_two_plans(
    tokenizer: RecordedTokenizer,
) -> None:
    reading = read_empty_role_budget(tokenizer, fixtures=PLAN_FIXTURES, stamp=STAMP)

    per_plan = [reading.working[f"{name}_tokens"] for name in PLAN_PROBES]
    assert reading.value == max(per_plan), (
        "the widest is what a window has to hold; an average of the two would be a "
        "number no plan actually costs"
    )
    assert reading.working["roles_declared"] == len(plan_roles())


# --- Probe three: the tokens-a-word ratio ------------------------------------


def a_corpus(tmp_path: Path, *, rows: int) -> Path:
    """A corpus file of `rows` harvested rows, built from the committed fixture.

    The template is the real harvested row, so the fenced shape `corpus_bodies`
    has to find its way through is the shape the harvest writes - a dict composed
    here would drift from it. Only the body varies, and each body is a different
    length so a sample of three and a sample of six cannot be confused.

    Built rather than read off `corpus/corpus.jsonl`. The question is whether the
    sampler samples, and the real corpus made the answer depend on a prune - a
    schedule nobody sets in a commit (`CLAUDE.md` section 13).
    """
    template: dict[str, Any] = json.loads(read_text(CORPUS_ROW_FIXTURE))
    turn = next(one for one in template["messages"] if one["role"] == "user")["content"]
    head = turn[: turn.index(FENCE_OPEN) + len(FENCE_OPEN)]
    tail = turn[turn.index(FENCE_CLOSE) :]

    path = tmp_path / "corpus.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for n in range(rows):
            words = " ".join(f"word{n}x{w}" for w in range(20 + n))
            row = json.loads(json.dumps(template))
            row["url_key"] = f"{n:064d}"
            for message in row["messages"]:
                if message["role"] == "user":
                    message["content"] = f"{head}\nTitle: Story {n}\n\n{words}\n{tail}"
            handle.write(json.dumps(row) + "\n")
    return path


def test_the_corpus_probe_is_bounded_by_the_sample_count(tmp_path: Path) -> None:
    """A probe whose cost rises because a run appended is the defect Guardrail #12 names."""
    corpus = a_corpus(tmp_path, rows=10)

    few = corpus_bodies(corpus, samples=3)
    more = corpus_bodies(corpus, samples=6)

    assert len(few) == 3
    assert len(more) == 6
    assert more[:3] == few, "the sample is the first rows in file order, so it is stable"
    assert len(set(more)) == 6, "six identical bodies would hide a sampler that reread one row"


def test_the_ratio_is_the_two_totals_divided_and_not_a_mean_of_ratios(
    tokenizer: RecordedTokenizer, tmp_path: Path
) -> None:
    corpus = a_corpus(tmp_path, rows=8)
    bodies = corpus_bodies(corpus, samples=5)
    words = sum(len(one.split()) for one in bodies)
    tokens = sum(tokenizer.count(one) for one in bodies)

    reading = read_tokens_a_word(tokenizer, corpus=corpus, samples=5, stamp=STAMP)

    assert reading.value == pytest.approx(round(tokens / words, 4))
    assert reading.working == {"articles": len(bodies), "words": words, "tokens": tokens}


def test_no_article_text_reaches_the_reading(
    tokenizer: RecordedTokenizer, tmp_path: Path
) -> None:
    """The corpus is fetched text, so counts of it may leave and characters of it may not.

    Guardrail #11 in one case: every corpus body is checked against the whole
    serialised reading, so a future edit that quoted an article into `probe` or
    into `working` fails here rather than in a published artifact.
    """
    corpus = a_corpus(tmp_path, rows=8)
    bodies = corpus_bodies(corpus, samples=5)

    emitted = json.dumps(
        read_tokens_a_word(tokenizer, corpus=corpus, samples=5, stamp=STAMP).as_json()
    )

    for body in bodies:
        longest = max(body.split("\n"), key=len)
        assert longest[:60] not in emitted, "a fetched article reached the reading"


def test_a_corpus_with_no_article_body_yields_no_ratio(
    tokenizer: RecordedTokenizer, tmp_path: Path
) -> None:
    empty = tmp_path / "corpus.jsonl"
    empty.write_text("\n", encoding="utf-8")

    with pytest.raises(ValueError, match="nothing here to take a ratio over"):
        read_tokens_a_word(tokenizer, corpus=empty, samples=5, stamp=STAMP)


# --- What it prints ----------------------------------------------------------


def test_every_reading_states_a_spread_rather_than_omitting_it(
    tokenizer: RecordedTokenizer, tmp_path: Path
) -> None:
    """Zero and present, because a tokenizer over fixed text has no run-to-run variance."""
    readings = take_every_reading(
        tokenizer,
        config_dir=CONFIG_DIR,
        fixtures=PLAN_FIXTURES,
        corpus=a_corpus(tmp_path, rows=8),
        samples=5,
        stamp=STAMP,
    )

    assert [one.record for one in readings] == [
        "DEFINITION_SENTENCE_TOKENS",
        "EMPTY_ROLE_TOKENS",
        "TOKENS_A_WORD_AT_THE_CUT",
    ], "the reader takes one reading for each constant sized by one"
    assert {one.record for one in readings} == {
        site.reading_name for site in SIZED_BY_A_READING_HERE
    }, "a reading here that no site is sized by is a reading nobody will paste"
    for reading in readings:
        assert reading.spread == 0.0
        assert "spread" in reading.as_json()
        assert reading.subject == STAMP["subject"]
        assert reading.runner == STAMP["runner"]
        assert reading.taken_on == STAMP["taken_on"]
        assert reading.why_that_probe.strip(), f"{reading.record} does not say why that text"


def test_the_paste_block_names_the_record_and_stamps_the_configured_weights(
    tokenizer: RecordedTokenizer, tmp_path: Path
) -> None:
    """Three lines an editor can drop in, and the constant name they belong to."""
    readings = take_every_reading(
        tokenizer,
        config_dir=CONFIG_DIR,
        fixtures=PLAN_FIXTURES,
        corpus=a_corpus(tmp_path, rows=8),
        samples=5,
        stamp=STAMP,
    )

    paste = render_paste(readings)

    for reading in readings:
        assert f"\n{reading.record}\n" in paste
    assert "taken_on=date(2026, 9, 14)," in paste
    assert "date(2026, 09, 14)" not in paste, (
        "a zero-padded month is an invalid Python literal, so the paste would not compile"
    )
    assert STAMP["subject"] in paste, "the paste does not say which weights these came from"
    assert "subject=QWEN35_9B_Q4_K_M," not in paste, (
        "this tool can be pointed at a candidate, so a guessed constant name would hand "
        "somebody a line that names the wrong vocabulary and still compiles"
    )
    assert "Guardrail #10" in paste, (
        "the paste does not say the old reading goes; a retake that kept both would "
        "leave two answers to one question"
    )


# --- The staleness check -----------------------------------------------------


def test_the_check_names_every_stale_site_and_both_digests() -> None:
    """What it prints when a reading is stale, built rather than found.

    All three were stale until row #13b retook them on 2026-09-14, so the check
    now says nothing on the committed tree and this test drives it off a digest
    no entry names instead. Asserting the committed state would have made this
    test a clock: green only while somebody had not done the work.
    """
    configured = config.load(CONFIG_DIR).models.summarize.sha256
    assert configured is not None
    assert readings_awaiting_a_retake(configured_sha256=configured) == (), (
        "row #13b retook all three; a stale one here means a reading moved without "
        "its subject"
    )

    swapped = "0" * 64
    stale = readings_awaiting_a_retake(configured_sha256=swapped)
    assert len(stale) == len(SIZED_BY_A_READING_HERE) == 3

    said = render_check(stale, swapped)

    assert swapped in said, "the check does not say which weights are configured"
    for site in stale:
        assert site.module in said
        assert site.constant in said
        assert site.reading.subject in said, "the check does not say what it was sized on"
    assert "measure_budgets.py read" in said, "the check does not say how to fix it"


def test_the_check_says_so_when_nothing_is_stale() -> None:
    """The other half, and on the committed tree this is the case that fires."""
    subject = SIZED_BY_A_READING_HERE[0].reading.subject

    assert readings_awaiting_a_retake(configured_sha256=subject) == ()
    said = render_check((), subject)
    assert "Every constant sized by a reading names the configured weights" in said


def test_check_exits_non_zero_while_a_reading_is_stale(capsys: pytest.CaptureFixture[str]) -> None:
    """An operator surface rather than a test, so the loudest thing it can do is exit 1.

    It is not a pytest case and no workflow runs it, so a red exit code costs no
    CI run and reaches the one person who asked (`CLAUDE.md` section 13). Driven
    against a config naming weights no reading was taken on, because on the
    committed tree since row #13b nothing is stale and the interesting case is
    the one that fires.
    """
    assert main(["check", "--config", str(CONFIG_DIR)]) == 0
    assert "names the configured weights" in capsys.readouterr().out

    swapped = SIZED_BY_A_READING_HERE[0].reading.subject.replace("0", "1", 1)
    assert "no longer runs" in render_check(
        readings_awaiting_a_retake(configured_sha256=swapped), swapped
    )


def test_read_refuses_rather_than_guessing_when_no_server_answers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The port is one nothing listens on, so this opens no connection anybody keeps."""
    code = main(
        [
            "read",
            "--base",
            "http://127.0.0.1:1",
            "--runner",
            "a box with no weights on it",
            "--samples",
            "1",
        ]
    )

    assert code == 2
    assert "did not answer /tokenize" in capsys.readouterr().err


def test_every_site_the_check_names_still_declares_its_constant() -> None:
    """A list of what to retake is worth nothing once a rename has made it a lie."""
    measured = read_text(REPO_ROOT / "backend" / "idhazh" / "measured.py")
    for site in SIZED_BY_A_READING_HERE:
        module = REPO_ROOT / site.module
        assert module.is_file(), f"{site.module} has moved and the list now points at nothing"
        assert site.constant in read_text(module), (
            f"{site.module} no longer declares {site.constant}"
        )
        assert f"\n{site.reading_name}: Final = TokenizerMeasured(" in measured, (
            f"{site.reading_name} is the heading the reader prints over three lines to "
            "paste, and measured.py no longer declares a record by that name"
        )


def test_the_ratio_the_pipeline_cuts_with_is_the_record_and_not_a_second_copy() -> None:
    """One number, one place. A literal beside the record is the drift this removes."""
    from idhazh.extract import TOKENS_PER_WORD
    from idhazh.measured import TOKENS_A_WORD_AT_THE_CUT

    assert TOKENS_PER_WORD == TOKENS_A_WORD_AT_THE_CUT.value
    assert "TOKENS_PER_WORD: Final = 1.3" not in read_text(
        REPO_ROOT / "backend" / "idhazh" / "extract.py"
    ), "the literal came back, and now there are two answers to one question"


def test_a_definition_longer_than_the_bound_is_still_refused() -> None:
    """The bound did not move. #13a ships no new number, and this is what says so.

    Read off the entry rather than off the alias, because the alias is a typing
    construct and a test that unwrapped it would be checking the annotation
    rather than the rule a payload meets.
    """
    from idhazh.contracts.taxonomy import VocabularyEntry

    with pytest.raises(ValidationError, match="at most 240 characters"):
        VocabularyEntry(display_name="x", definition="x" * 241)

    VocabularyEntry(display_name="x", definition="x" * 240)


def test_the_plan_reply_ceiling_did_not_move() -> None:
    from idhazh.contracts.visual import WORST_CASE_REPLY_CHARACTERS

    assert WORST_CASE_REPLY_CHARACTERS == 3767


def test_the_ratio_is_the_retaken_one() -> None:
    """1.3 was a judgement nobody counted; 1.3628 came off the model's tokenizer.

    Pinned rather than derived, because the point of the pin is that the value
    moves only when somebody retakes the reading and says so.
    """
    from idhazh.extract import TOKENS_PER_WORD

    assert TOKENS_PER_WORD == 1.3628


def test_this_surface_writes_nothing_a_commit_would_carry() -> None:
    """`read` prints and saves where the caller says; it never reaches for a repo path.

    The rejected option on row #13 was a workflow writing a measurement into a
    commit. The defence is that nothing here has a committed destination: every
    write goes to a `--readings` or `--page` path the caller names.
    """
    source = read_text(REPO_ROOT / "backend" / "utilities" / "measure_budgets.py")

    assert "write_text" in source, "if the writes went, this case is checking nothing"
    for forbidden in ("REPO_ROOT / \"docs\"", "REPO_ROOT / \"config\" /", "git commit"):
        assert forbidden not in source, f"{forbidden} is a committed destination"
