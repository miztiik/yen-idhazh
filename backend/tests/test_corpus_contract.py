"""Contract-tier tests for the training window.

No mocks and no network (Rule #7): every input is a committed fixture or a row
this module builds from one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh import corpus
from idhazh.contracts.app_config import AppConfig, FinetuneConfig
from idhazh.contracts.article import Article
from idhazh.contracts.corpus import ChatRole, ChatTurn, CorpusMeta, CorpusRow
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.summary import Summary

pytestmark = pytest.mark.contract

#: Every character that has ever broken a hand-built JSON writer, in one string.
#: A lone `\r` is in here because it is the one that survives a naive reader and
#: lands inside the last field; `\n` and `\t` are here because a row that breaks
#: in two stops being a row at all.
NASTY = (
    "quote \" backslash \\ slash / apostrophe ' "
    "newline \n tab \t carriage \r nul \x00 "
    "<script>alert(1)</script> ${x} {{y}} \\u0041 "
    "emoji \U0001f4c8 cjk \u4e2d\u6587 accents \u00e9\u00fc"
)


def contract_fixture(stem: str, name: str) -> str:
    return read_text(CONTRACT_FIXTURES_DIR / stem / f"{name}.json")


@pytest.fixture
def settings() -> AppConfig:
    return AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))


def a_row(content: str = "hello") -> CorpusRow:
    return CorpusRow(
        version=CorpusRow.schema_version(),
        messages=[
            ChatTurn(role=ChatRole.SYSTEM, content=content),
            ChatTurn(role=ChatRole.USER, content=content),
            ChatTurn(role=ChatRole.ASSISTANT, content=content),
        ],
        url_key="a" * 64,
        date="2026-08-28",
        model_id="qwen3-5-9b-q4-k-m",
        vertical="ai",
    )


# --- The Oracle: escaping --------------------------------------------------


def test_a_row_carrying_every_dangerous_character_survives_the_round_trip(
    tmp_path: Path,
) -> None:
    """`json.dumps` in, `json.loads` out, and nothing in between builds a string.

    The assertion is on BYTES and on the physical line count together. Bytes
    alone would pass a file whose row silently became two rows, and a line count
    alone would pass a file that mangled a quote.
    """
    row = a_row(NASTY)
    written = corpus.to_line(row)

    assert written.count("\n") == 1, "one row is one physical line, whatever it contains"
    assert corpus.from_line(written) == row
    assert corpus.to_line(corpus.from_line(written)) == written

    path = tmp_path / "corpus.jsonl"
    corpus.write(tmp_path, [row, row.model_copy(update={"url_key": "b" * 64})], CorpusMeta(version=CorpusMeta.schema_version()))
    raw = path.read_bytes()

    assert raw.count(b"\n") == 2
    assert b"\r\n" not in raw, "a CRLF host must not rewrite bytes inside a training row"
    assert corpus.read_rows(tmp_path) == [row, row.model_copy(update={"url_key": "b" * 64})]


def test_the_nasty_string_comes_back_character_for_character(tmp_path: Path) -> None:
    """Not just loadable - equal. A silently dropped NUL still parses as JSON."""
    corpus.write(tmp_path, [a_row(NASTY)], CorpusMeta(version=CorpusMeta.schema_version()))
    read_back = corpus.read_rows(tmp_path)[0]

    assert read_back.system == NASTY
    assert read_back.user == NASTY
    assert read_back.assistant == NASTY


# --- The Oracle: a trainer can read it -------------------------------------


def test_the_file_is_the_conversational_sft_shape_a_trainer_loads(tmp_path: Path) -> None:
    """One JSON object per line, each carrying a `messages` array of role/content.

    Asserted structurally rather than by calling `datasets.load_dataset`. That
    library is the reader this shape exists for, but it is not a dependency of
    this project and adding it for one test costs pyarrow and several hundred
    megabytes against a beneficiary that is one assertion (Rule #8). What every
    one of TRL, Unsloth, Axolotl and LLaMA-Factory actually requires is written
    out here instead, so a change that breaks them fails here.
    """
    rows = [a_row(NASTY), a_row("plain")]
    corpus.write(tmp_path, rows, CorpusMeta(version=CorpusMeta.schema_version()))

    lines = (tmp_path / "corpus.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(rows)
    for line in lines:
        payload = json.loads(line)
        assert isinstance(payload["messages"], list)
        assert [turn["role"] for turn in payload["messages"]] == ["system", "user", "assistant"]
        assert all(isinstance(turn["content"], str) for turn in payload["messages"])
        assert set(payload["messages"][0]) == {"role", "content"}


def test_the_extra_columns_are_the_five_that_earn_their_place() -> None:
    """Five, and every removal has a reason that is checkable from the row itself."""
    payload = json.loads(corpus.to_line(a_row()))

    assert set(payload) == {"messages", "url_key", "date", "model_id", "vertical", "version"}
    assert "prompt_fingerprint" not in payload, "it is sha256 of messages[0]"
    assert "source_words" not in payload, "it is a word count of messages[1]"
    assert "written_by" not in payload, "which file a row lives in already says so"


# --- The Oracle: the turns are the three a trainer expects -----------------


def test_a_row_whose_turns_are_reordered_does_not_load() -> None:
    """A trainer masks everything before the assistant turn.

    So a reordered row trains on the article instead of on the summary, produces
    a plausible loss curve, and says nothing at all. It has to fail at the
    contract or it never fails.
    """
    with pytest.raises(ValidationError, match="system, user, assistant"):
        CorpusRow(
            version=CorpusRow.schema_version(),
            messages=[
                ChatTurn(role=ChatRole.USER, content="x"),
                ChatTurn(role=ChatRole.SYSTEM, content="x"),
                ChatTurn(role=ChatRole.ASSISTANT, content="x"),
            ],
            url_key="a" * 64,
            date="2026-08-28",
            model_id="m",
            vertical="ai",
        )


@pytest.mark.parametrize("count", [2, 4])
def test_a_row_that_is_not_three_turns_does_not_load(count: int) -> None:
    turns = [ChatTurn(role=ChatRole.SYSTEM, content="x")] * count
    with pytest.raises(ValidationError):
        CorpusRow(
            version=CorpusRow.schema_version(),
            messages=turns,
            url_key="a" * 64,
            date="2026-08-28",
            model_id="m",
            vertical="ai",
        )


# --- The committed fixture is what the shipped stage produces --------------


def test_the_committed_fixture_is_what_the_harvest_really_writes(settings: AppConfig) -> None:
    """Re-derived, not trusted.

    A hand-written fixture can agree with a wrong reader. This one is rebuilt
    from three committed payloads by the shipped function, so it fails the day
    the prompt, the decoder rail or the assistant-turn spelling moves - which is
    exactly when a corpus stops matching the pipeline it claims to come from.
    """
    article = Article.from_json(contract_fixture("article", "ok"))
    summary = Summary.from_json(contract_fixture("summary", "titled")).model_copy(
        update={"url_key": article.url_key, "item_id": article.item_id}
    )
    row = EvalRow.from_json(contract_fixture("eval-row", "high")).model_copy(
        update={"url_key": article.url_key, "item_id": article.item_id}
    )

    built = corpus.harvest_rows(
        [corpus.Scored(article, summary, row)],
        date="2026-08-28",
        prompt_config=settings.summarize,
        evaluation=settings.evaluation,
    )

    assert len(built) == 1
    assert built[0].to_json() == contract_fixture("corpus-row", "harvested")


def test_the_assistant_turn_is_spelled_in_decode_order(settings: AppConfig) -> None:
    """Field order is decode order under a grammar.

    `canonical_json` sorts keys, which would put `key_points` first and teach a
    sequence the constrained decoder is not allowed to emit. So the target is
    dumped in the model's own field order, and this is the assertion that keeps
    it there.
    """
    row = CorpusRow.from_json(contract_fixture("corpus-row", "harvested"))
    target = json.loads(row.assistant)

    assert list(target) == ["title", "summary", "key_points"]


# --- Config ----------------------------------------------------------------


def test_a_session_cannot_be_asked_to_draw_more_rows_than_the_window_holds() -> None:
    """600 rows satisfies `min_rows: 500` and cannot satisfy `train_rows: 1000`.

    Training on 600 while every note says 1000 makes the result unattributable,
    which is the one thing the comparison this corpus exists for cannot tolerate.
    """
    with pytest.raises(ValidationError, match="train_rows cannot exceed"):
        FinetuneConfig(corpus_rows=500, train_rows=1000)
    with pytest.raises(ValidationError, match="min_rows cannot exceed"):
        FinetuneConfig(corpus_rows=100, train_rows=100, min_rows=500)


def test_a_finetune_role_that_names_no_model_fails_at_startup() -> None:
    """Not on a GPU somebody is paying for, three hours later."""
    payload = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    payload["finetune"]["teacher"] = "sumarize"

    with pytest.raises(ValidationError, match=r"finetune\.teacher must name one of models"):
        AppConfig.model_validate(payload)


def test_the_committed_config_names_a_base_repo_for_every_model_we_would_tune() -> None:
    """One entry, both strings.

    Held in two blocks the GGUF repo and the safetensors repo drift on a model
    swap, and a LoRA adapter loads onto a mismatched base without raising - so
    the damage arrives later as a quality drop nobody can attribute.
    """
    config = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    for role in (config.finetune.teacher, config.finetune.student):
        ref = getattr(config.models, role)
        assert ref.hf_base_repo, f"models.{role} is a fine-tune target with no base repository"
        assert ref.hf_base_repo != ref.repo, "the GGUF repo is not the safetensors repo"
