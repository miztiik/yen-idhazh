"""Do the known-answer pairs reach the night's row as the runners answered them, and nowhere else?

Two halves. The runner's: `judge_canary_pairs` judges the pairs it was dealt through the real
reader, compares each answer with the known one by code, logs a wrong one by id and stores every
answer as the judge gave it. The collecting job's: each runner ships its answers in its own
reading, and the night's row carries them gathered into one text.

The model is the only thing not real. It is an in-memory transport at the completion boundary
(`ProtocolReplies`), so the request a pair makes is the request the production reader builds, and
every answer is a protocol reply the production parser reads.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import time
from datetime import date as date_type
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

import pytest
from pydantic import TypeAdapter
from support.config import canary_config
from support.judge_reader import ProtocolReplies, native_reply
from support.judged_pairs import (
    CONFIG_VERSIONS,
    DATE,
    a_night_of_pairs,
    a_reading,
    a_saver,
    a_verdict_file,
)
from support.models import a_markers
from support.paths import CONFIG_DIR, read_text
from support.threshold_nights import LOOKBACK, RULES

from idhazh import atomic_write, config
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.content_similarity_judge.ledger_reads import load_threshold_history
from idhazh.content_similarity_judge.model_reader import ModelReader
from idhazh.content_similarity_judge.tenant import JUDGE_ID
from idhazh.contracts.knobs.content_similarity_canaries import CanaryPair
from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.contracts.story_similarity_runner_report import StorySimilarityRunnerReport
from idhazh.contracts.story_similarity_threshold_history_row import (
    CanaryAnswersText,
    StorySimilarityThresholdHistoryRow,
    canary_answers_text,
)
from idhazh.council import metrics_sink
from idhazh.llm.server import Completion, parse_completion
from idhazh.similarity import judge
from idhazh.similarity.canary_diagnostics import canary_columns
from idhazh.similarity.night_totals import merged_canary_answers, runner_columns
from idhazh.stages import judge_canary_pairs
from idhazh.stages.review_thresholds import build_threshold_row, stage_review_thresholds

CANARIES: Final = canary_config()
PAIRS: Final = CANARIES.pairs


def an_hour_away() -> float:
    """Nothing here is about a deadline unless it says so, and an hour is further than a test runs."""
    return time.monotonic() + 3600.0


def a_settings() -> config.Settings:
    """The committed settings, judging in one span so that one call is one reading."""
    settings = config.load(CONFIG_DIR, models_file=config.load_app(CONFIG_DIR).models_file)
    raw = settings.models.model_dump(mode="json")
    raw["summarizer"] |= {"thinking_close": None, "thinking_kwarg": "reasoning"}
    return dataclasses.replace(settings, models=ModelsConfig.model_validate(raw | {"judge": None}))


def a_reply(word: str) -> bytes:
    """What the transport hands back for one reading that answers `word` inside the grammar."""
    return native_reply(
        word,
        pieces=("UN", "CLEAR") if word == "UNCLEAR" else (word,),
        alternatives=((word[:2], -0.01), ("YES" if word == "NO" else "NO", -4.7)),
    )


def a_perfect_judge() -> tuple[bytes, ...]:
    """Both orders of each test pair, answered as the key says, in file order."""
    return tuple(a_reply(pair.expected.value) for pair in PAIRS for _ in range(2))


def judge_them(
    *replies: bytes,
    date: str = "2026-11-20",
    shard: int = 0,
    shards: int = 1,
    pairs: tuple[CanaryPair, ...] | list[CanaryPair] = PAIRS,
    deadline: float | None = None,
) -> tuple[judge_canary_pairs.CanaryReport, list[dict[str, Any]]]:
    """One runner's known-answer pairs through the real stage, and the requests it made."""
    with ProtocolReplies(*replies) as server:
        report = judge_canary_pairs.stage_judge_canary_pairs(
            date,
            shard=shard,
            shards=shards,
            settings=a_settings(),
            deadline=an_hour_away() if deadline is None else deadline,
            reader=server.reader,
            canary_pairs=pairs,
        )
        return report, server.decodes


def warnings_of(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING and "judge-canary-pairs" in record.getMessage()
    ]


def test_a_right_answer_is_stored_in_six_cells_and_logs_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One runner dealt every pair: each id once, with its own words, margins and tokens."""
    with caplog.at_level(logging.WARNING, logger="idhazh"):
        report, decodes = judge_them(*a_perfect_judge())

    assert report.answers is not None
    answers = json.loads(report.answers)
    margin = judge.margin_of(parse_completion(a_reply("YES").decode("utf-8")).first_token_choices)
    assert margin is not None and 0.9 < margin < 1.0
    assert list(answers) == sorted(pair.id for pair in PAIRS)
    assert answers["same-1"] == ["YES", "YES", margin, margin, 7, 0]
    assert answers["different-2"][:2] == ["NO", "NO"]
    assert answers["unclear-1"][:2] == ["UNCLEAR", "UNCLEAR"]
    assert (report.owned, report.judged, report.wrong) == (len(PAIRS), len(PAIRS), 0)
    assert len(decodes) == 2 * len(PAIRS), "two readings per pair"
    assert warnings_of(caplog) == []
    assert TypeAdapter(CanaryAnswersText).validate_python(report.answers) == report.answers


def test_a_wrong_answer_is_logged_by_id_and_stored_as_the_judge_gave_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The judge calls the first pair a different story in both orders; nothing else moves."""
    replies = (a_reply("NO"), a_reply("NO"), *a_perfect_judge()[2:])

    with caplog.at_level(logging.WARNING, logger="idhazh"):
        report, decodes = judge_them(*replies)

    assert report.answers is not None
    assert json.loads(report.answers)["same-1"][:2] == ["NO", "NO"], "stored as given"
    assert (report.judged, report.wrong) == (len(PAIRS), 1), "the run judged every pair"
    assert len(decodes) == 2 * len(PAIRS)
    assert warnings_of(caplog) == [
        "judge-canary-pairs shard=0 date=2026-11-20 canary=same-1 expected=YES answered=NO,NO"
    ]


def test_orders_that_disagree_are_stored_as_given_and_count_as_wrong(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A split between the two orders is not the expected answer in both."""
    replies = (a_reply("YES"), a_reply("NO"), *a_perfect_judge()[2:])

    with caplog.at_level(logging.WARNING, logger="idhazh"):
        report, _ = judge_them(*replies)

    assert report.answers is not None
    assert json.loads(report.answers)["same-1"][:2] == ["YES", "NO"]
    assert report.wrong == 1
    assert warnings_of(caplog)[0].endswith("canary=same-1 expected=YES answered=YES,NO")


def test_a_reading_outside_the_grammar_is_stored_as_null_and_logged_as_refused(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A refused reading is no verdict, so it is never the expected one, and the cell stays null."""
    refused = native_reply("The answer is YES.")
    replies = (refused, refused, *a_perfect_judge()[2:])

    with caplog.at_level(logging.WARNING, logger="idhazh"):
        report, _ = judge_them(*replies)

    assert report.answers is not None
    answer = json.loads(report.answers)["same-1"]
    assert answer[:2] == [None, None]
    assert answer[4] == 7, "the call was made and cost what it cost, whatever it said"
    assert report.wrong == 1
    assert warnings_of(caplog)[-1].endswith("canary=same-1 expected=YES answered=refused,refused")


def test_a_call_that_raises_stores_nothing_for_its_pair_and_the_rest_go_on(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """This runs before the night's own pairs, so one pair's fault must not cost the night.

    The transport fails on the first call of the second pair. That pair is logged as an error
    naming its id, left out of the answers, and the remaining pairs are still judged.
    """
    perfect = iter(a_perfect_judge())
    calls: list[int] = []

    def transport(_body: dict[str, Any]) -> Completion:
        calls.append(len(calls))
        if len(calls) == 3:
            raise RuntimeError("the server dropped the connection")
        return parse_completion(next(perfect).decode("utf-8"))

    with caplog.at_level(logging.ERROR, logger="idhazh"):
        report = judge_canary_pairs.stage_judge_canary_pairs(
            "2026-11-20",
            shard=0,
            shards=1,
            settings=a_settings(),
            deadline=an_hour_away(),
            reader=ModelReader(transport, a_markers()),
            canary_pairs=PAIRS,
        )

    assert report.answers is not None
    assert "same-2" not in json.loads(report.answers)
    assert (report.owned, report.judged) == (len(PAIRS), len(PAIRS) - 1)
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1 and "canary=same-2" in errors[0]


def test_a_runner_dealt_none_judges_nothing_and_answers_null_never_an_empty_object() -> None:
    """Two pairs over four runners leaves two runners with none; they still report."""
    report, decodes = judge_them(a_reply("YES"), shard=3, shards=4, pairs=PAIRS[:2])

    assert (report.owned, report.judged, report.wrong) == (0, 0, 0)
    assert report.answers is None
    assert decodes == []
    assert (report.model_calls, report.tokens_in, report.tokens_out, report.model_seconds) == (
        0,
        0,
        0,
        0.0,
    )


def test_a_deadline_that_has_passed_leaves_every_pair_unjudged() -> None:
    """A pair is never begun after the instant the runner must stop by."""
    report, decodes = judge_them(a_reply("YES"), deadline=time.monotonic() - 1.0)

    assert (report.owned, report.judged) == (len(PAIRS), 0)
    assert report.answers is None
    assert decodes == []


def test_the_calls_are_counted_for_the_venue_and_nowhere_else() -> None:
    """Two calls a pair at 7 prompt and 2 generated tokens each, counted at the seam."""
    report, _ = judge_them(*a_perfect_judge())

    assert (report.model_calls, report.tokens_in, report.tokens_out) == (
        2 * len(PAIRS),
        14 * len(PAIRS),
        4 * len(PAIRS),
    )
    assert report.model_seconds > 0.0


#: The pairs each of four runners is dealt, worked by hand from the date's ordinal: 2026-11-19 is
#: 739939 and 2026-11-20 is 739940, which are 3 and 0 over four runners, so the pair at position i
#: goes to runner (i + 3) mod 4 on the first night and i mod 4 on the second.
DEALT: Final = {
    "2026-11-19": {
        0: ["same-2"],
        1: ["different-1"],
        2: ["different-2"],
        3: ["same-1", "unclear-1"],
    },
    "2026-11-20": {
        0: ["same-1", "unclear-1"],
        1: ["same-2"],
        2: ["different-1"],
        3: ["different-2"],
    },
}


@pytest.mark.parametrize("date", sorted(DEALT))
def test_the_runner_for_pair_i_is_i_plus_the_dates_ordinal_over_the_runners(date: str) -> None:
    ordinal = date_type.fromisoformat(date).toordinal()
    assert ordinal % 4 == {"2026-11-19": 3, "2026-11-20": 0}[date], "the table was worked by hand"

    for runner in range(4):
        report, _ = judge_them(a_reply("YES"), date=date, shard=runner, shards=4)
        answers = {} if report.answers is None else json.loads(report.answers)
        assert sorted(answers) == sorted(DEALT[date][runner]), f"runner {runner} on {date}"
        assert all(cells[5] == runner for cells in answers.values())


def test_every_pair_is_judged_once_a_night_and_moves_one_runner_a_night() -> None:
    """Over four nights each pair has run on every one of four runners, and never twice a night."""
    seen: dict[str, list[int]] = {pair.id: [] for pair in PAIRS}
    for day in ("2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22"):
        night: list[str] = []
        for runner in range(4):
            report, _ = judge_them(a_reply("YES"), date=day, shard=runner, shards=4)
            for canary_id in {} if report.answers is None else json.loads(report.answers):
                night.append(canary_id)
                seen[canary_id].append(runner)
        assert sorted(night) == sorted(pair.id for pair in PAIRS), f"once on {day}"

    assert all(sorted(runners) == [0, 1, 2, 3] for runners in seen.values())
    assert all(
        later == (earlier + 1) % 4
        for runners in seen.values()
        for earlier, later in pairwise(runners)
    )


def an_answer(runner: int, word: str = "YES") -> list[Any]:
    """One pair's six cells: both orders' answer, both margins, the prompt tokens, the runner."""
    return [word, word, 0.9810234, 0.993, 812, runner]


def a_runner(shard: int, answers: dict[str, list[Any]]) -> StorySimilarityRunnerReport:
    """One runner's reading of its own instrument, having judged the pairs named in `answers`."""
    reading = a_reading(shard=shard, dealt=2, date=DATE, run_id=f"{DATE}-9")
    return StorySimilarityRunnerReport.model_validate(
        reading.model_dump(mode="json") | {"canary_answers": canary_answers_text(answers)}
    )


def test_the_runners_answers_are_gathered_into_the_nights_one_text() -> None:
    """Each pair went to one runner, so the night's text is the union, sorted by pair id."""
    readings = [
        a_runner(2, {"different-1": an_answer(2, "NO")}),
        a_runner(0, {"same-1": an_answer(0), "unclear-1": an_answer(0, "UNCLEAR")}),
        a_runner(1, {}),
    ]

    text = merged_canary_answers(readings)

    assert text is not None
    assert list(json.loads(text)) == ["different-1", "same-1", "unclear-1"]
    assert json.loads(text)["different-1"] == an_answer(2, "NO")
    assert TypeAdapter(CanaryAnswersText).validate_python(text) == text
    assert runner_columns(readings, expected_shards=4)["canary_answers"] == text


def test_no_runner_having_judged_a_pair_leaves_the_text_empty_and_never_an_empty_object() -> None:
    """An empty object would read as pairs that ran and had nothing to say."""
    assert merged_canary_answers([]) is None
    assert merged_canary_answers([a_runner(0, {}), a_runner(1, {})]) is None
    assert canary_answers_text({}) is None


def test_a_pair_two_runners_both_answered_keeps_the_lower_runners_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """It is a fault of the artifacts and not a wrong answer, so the night is not held for it."""
    lower, higher = an_answer(0, "YES"), an_answer(1, "NO")
    readings = [a_runner(1, {"same-1": higher}), a_runner(0, {"same-1": lower})]

    with caplog.at_level(logging.WARNING, logger="idhazh"):
        text = merged_canary_answers(readings)

    assert text is not None
    assert json.loads(text) == {"same-1": lower}
    assert "same-1 was answered by runner 0 and by runner 1" in caplog.text


def test_the_nights_row_carries_the_answers_as_the_runners_gave_them_and_no_count_moves() -> None:
    """The row the night files holds the text, and a pair that is not the night's own adds to no count."""
    rows = a_night_of_pairs([(0.80, "YES"), (0.60, "NO")])
    readings = [
        a_runner(0, {"same-1": an_answer(0)}),
        a_runner(1, {"unclear-1": an_answer(1, "NO")}),
    ]

    row = build_threshold_row(
        DATE,
        run_id=f"{DATE}-9",
        window=rows,
        history=[],
        draw_rows=[],
        readings=readings,
        expected_shards=4,
        rules=RULES,
        lookback_days_of_the_draw=LOOKBACK,
        versions=CONFIG_VERSIONS,
    )

    assert row is not None
    assert row.canary_answers == '{"same-1":["YES","YES",0.9810234,0.993,812,0],' \
        '"unclear-1":["NO","NO",0.9810234,0.993,812,1]}'
    assert (row.runners_reported, row.pairs_dealt) == (2, 4), "only the night's own pairs are counted"
    assert StorySimilarityThresholdHistoryRow.model_validate_json(row.to_json()) == row


def test_four_runners_ship_their_share_and_the_night_names_every_pair_exactly_once(
    tmp_path: Path,
) -> None:
    """The shipped runner readings file the actual answers, the key and agreement in history."""
    date = "2026-11-19"
    run_id = f"{date}-9"
    config_dir = tmp_path / "config"
    atomic_write.write_atomic(
        config_dir / judge_settings.JUDGE_FILE, read_text(CONFIG_DIR / judge_settings.JUDGE_FILE)
    )
    atomic_write.write_atomic(
        config_dir / judge_settings.CANARY_FILE, CANARIES.model_dump_json(exclude_none=True)
    )
    draw_path, state = tmp_path / "draw.csv", tmp_path / "state"
    draw = a_night_of_pairs(
        [(0.80, "YES")] * 4,
        date=date,
        answered=False,
        config_versions=judge_settings.config_versions(config_dir),
    )
    atomic_write.write_atomic(
        draw_path,
        a_verdict_file(
            [row.model_copy(update={"work_part_index": shard}) for shard, row in enumerate(draw)]
        ),
    )
    for runner in range(4):
        replies = [
            a_reply("NO" if pair.id == "unclear-1" else pair.expected.value)
            for pair in PAIRS
            if pair.id in DEALT[date][runner]
            for _ in range(2)
        ]
        report, _ = judge_them(*replies, date=date, shard=runner, shards=4)
        reading = StorySimilarityRunnerReport(
            version=StorySimilarityRunnerReport.schema_version(),
            date=date,
            run_id=run_id,
            work_part_index=runner,
            pairs_dealt=1,
            pairs_valid=0,
            pairs_agreed=0,
            pairs_unreadable=0,
            pairs_refused=0,
            pairs_abandoned=1,
            canary_answers=report.answers,
        )
        metrics_sink.ship_judge_metrics(
            reading, judge_id=JUDGE_ID, name=str(runner), out_dir=tmp_path
        )

    reviewed = stage_review_thresholds(
        date,
        run_id=run_id,
        judge_id=JUDGE_ID,
        shipped_root=tmp_path,
        draw_path=draw_path,
        filed_rows=(),
        identity=a_saver(run_id),
        expected_shards=4,
        state_dir=state,
        config_dir=config_dir,
    )

    (filed,) = load_threshold_history(state, [date])
    assert reviewed.filed and filed == reviewed.row
    assert (filed.runners_reported, filed.pairs_abandoned, filed.pairs_returned) == (4, 4, 0)
    assert filed.canary_expectations is not None
    assert json.loads(filed.canary_expectations) == {pair.id: pair.expected.value for pair in PAIRS}
    assert filed.canary_answers is not None
    answers = json.loads(filed.canary_answers)
    assert sorted(answers) == sorted(pair.id for pair in PAIRS), "every id, once"
    assert {canary_id: cells[5] for canary_id, cells in answers.items()} == {
        canary_id: runner for runner, ids in DEALT[date].items() for canary_id in ids
    }
    assert answers["unclear-1"][:2] == ["NO", "NO"], "keep the answer, not what the key wanted"
    assert filed.canary_kappa_pairs == len(PAIRS)
    assert filed.canary_kappa == 2 / 3, "four of five matches, with chance agreement 2/5"


@pytest.mark.parametrize(
    "orders", [None, (None, "YES"), ("YES", "NO")], ids=["lost", "refused", "split"]
)
def test_incomplete_canary_answers_keep_support_but_do_not_score_kappa(
    orders: tuple[str | None, str] | None,
) -> None:
    answers = {pair.id: an_answer(0, pair.expected.value) for pair in PAIRS if pair.id != "same-1"}
    if orders is not None:
        answers["same-1"] = [*orders, None, None, 812, 0]

    columns = canary_columns(PAIRS, canary_answers_text(answers))

    assert columns["canary_kappa_pairs"] == len(PAIRS) - 1
    assert columns["canary_kappa"] is None


def test_kappa_has_no_value_when_chance_agreement_is_one() -> None:
    only = PAIRS[:1]
    columns = canary_columns(only, canary_answers_text({only[0].id: an_answer(0)}))

    assert columns["canary_kappa_pairs"] == 1
    assert columns["canary_kappa"] is None
