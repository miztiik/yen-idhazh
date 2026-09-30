"""Does a capture read as a report - the numbers first, the bytes last?

The utility exists because a capture file is one JSON object holding a
15,000-character prompt on one line. A reader opening it by hand sees a wall, so
what is checked here is the reading order: what looks wrong, then what the calls
cost, then each reply read as what it says, and the raw text folded at the end.

Every fixture is built in the test that uses it. None of these read a committed
capture - there are none committed, by design - so nothing here costs more as
the archive grows (CLAUDE.md section 13).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text, seed_item_health

from idhazh.contracts.base import ServerJob, derive_url_key
from idhazh.contracts.item_health import ItemHealthRow
from utilities import pipeline_artifact_analyzer as analyzer

#: The UTC day, the run and the item the census row below is filed under. The
#: item id is one the census accepts; the shorter one `capture_of` uses is not.
DAY = "2026-09-14"
RUN_ID = "2026-09-14-34852763827"
ITEM_ID = "india-5tnmq7gbk3xj9wcd"


def capture_of(
    call: str,
    *,
    prompt: str = "system turn\narticle\n",
    reply: str = '{"labels": [], "keyphrases": ["wind"]}',
    cost: dict[str, object] | None = None,
    decode_split: dict[str, object] | None = None,
    finish_reason: str = "stop",
    about: dict[str, object] | None = None,
) -> analyzer.Capture:
    """One capture as `idhazh.capture` writes it, read back through `load`."""
    return analyzer.Capture(
        item_id="india-5tnmq7gb",
        call=call,
        prompt=prompt,
        reply=reply,
        prompt_chars=len(prompt),
        reply_chars=len(reply),
        prompt_sha256="a" * 64,
        finish_reason=finish_reason,
        cost=analyzer.cost_of(cost),
        split=analyzer.split_of(decode_split),
        about=analyzer.about_of(about),
    )


def priced_pair() -> dict[str, analyzer.Capture]:
    """Both calls, each saying what it cost, as a run writes them today."""
    return {
        "label": capture_of(
            "label",
            cost={
                "kind": "label",
                "prefill_ms": 6180,
                "decode_ms": 5861,
                "input_tokens": 3886,
                "output_tokens": 279,
                "cached_tokens": 0,
            },
        ),
        "summary": capture_of(
            "summary",
            prompt="system turn\narticle\nnow summarize\n",
            reply='{"summary": {"headline": "a headline"}}',
            cost={
                "kind": "summarize_and_plan",
                "prefill_ms": 6214,
                "decode_ms": 3188,
                "input_tokens": 4214,
                "output_tokens": 512,
                "cached_tokens": 3886,
            },
            decode_split={
                "summary_ms": 2010,
                "plan_ms": 1178,
                "summary_tokens": 320,
                "plan_tokens": 192,
                "is_estimate": True,
            },
        ),
    }


def headings(document: str) -> list[str]:
    """Every heading in the document, in the order it is read."""
    return [line for line in document.splitlines() if line.startswith("#")]


def test_the_cost_table_holds_both_calls_and_their_total() -> None:
    """The first question a reader has is what it cost, so it is the first table."""
    document = analyzer.render(priced_pair(), head=0, tail=0)

    assert "| 1 | label | 12.0 s | 6,180 | 5,861 | 3,886 | 0 | 3,886 | 279 |" in document
    assert "| 2 | summary (summarize_and_plan) | 9.4 s |" in document
    assert "**2 calls** | **21.4 s** | **12,394** | **9,049** | **8,100** | **3,886**" in document


def test_a_decode_measured_in_minutes_is_printed_in_minutes() -> None:
    """`1021.0` is a number a reader divides; `17m 07s` is one they read."""
    pair = priced_pair()
    pair["summary"] = capture_of(
        "summary",
        cost={
            "kind": "summarize_and_plan",
            "prefill_ms": 6060,
            "decode_ms": 1020913,
            "input_tokens": 3712,
            "output_tokens": 4735,
            "cached_tokens": 3661,
        },
    )

    document = analyzer.render(pair, head=0, tail=0)

    assert "| 2 | summary (summarize_and_plan) | 17m 07s |" in document


def test_the_cache_saving_is_stated_in_tokens_and_in_characters() -> None:
    """A percentage with no numerator is a number nobody can check (Guardrail #10)."""
    document = analyzer.render(priced_pair(), head=0, tail=0)

    assert "reused 3,886 of the summarize-and-plan call's 4,214 prompt tokens (92.2%)" in document
    assert "read 328 of them" in document


def test_the_picture_gets_its_own_share_of_the_second_decode() -> None:
    """Two halves of one decode, and the row says which of them is an estimate."""
    document = analyzer.render(priced_pair(), head=0, tail=0)

    assert "| the summary | 2,010 | 320 | 62.5% |" in document
    assert "| the visual plan | 1,178 | 192 | 37.5% |" in document
    assert "**These two rows are an estimate.**" in document


def test_the_raw_text_comes_after_everything_that_reads_it() -> None:
    """Signal before noise: the bytes are kept whole and are read last."""
    document = analyzer.render(priced_pair(), head=0, tail=0)

    assert document.index("## 3. What the calls cost") < document.index("## 6. The raw text")
    assert document.index("## 4. What the label call sent back") < document.index("## 6. ")
    assert "<details>" in document
    assert "system turn\narticle\nnow summarize" in document


def test_every_heading_carries_its_number_in_order() -> None:
    """A numbered heading a reader can cite, and no gap where a section was skipped."""
    document = analyzer.render(priced_pair(), head=0, tail=0)

    tops = [line for line in headings(document) if line.startswith("## ")]
    assert [line.split(".")[0] for line in tops] == [
        "## 1",
        "## 2",
        "## 3",
        "## 4",
        "## 5",
        "## 6",
    ]
    assert headings(document)[0] == "# india-5tnmq7gb"


def test_a_reply_that_will_not_parse_says_where_it_broke() -> None:
    """The item worth opening is the one the pipeline could not read, so it renders."""
    pair = priced_pair()
    pair["label"] = capture_of("label", reply='{"labels": [{"element_id": "e1",')

    document = analyzer.render(pair, head=0, tail=0)

    assert "**This reply cannot be read as JSON**" in document
    assert "the JSON stops being readable at character" in document
    assert '{"labels": [{"element_id": "e1",' in document


def test_a_decoder_that_could_not_stop_is_named_at_the_top() -> None:
    """One unbroken lowercase run is what the 2026-09-14 stall looked like."""
    pair = priced_pair()
    pair["label"] = capture_of("label", reply='{"a": "' + "x" * 900 + '"}')

    document = analyzer.render(pair, head=0, tail=0)
    verdict = document.split("## 3.")[0]

    assert "900-character unbroken lowercase run" in verdict


def test_a_cut_reply_is_named_before_any_number() -> None:
    """`length` means the output budget cut the reply rather than the model ending it."""
    pair = priced_pair()
    pair["summary"] = capture_of("summary", finish_reason="length")

    verdict = analyzer.render(pair, head=0, tail=0).split("## 3.")[0]

    assert "stopped on `length`" in verdict


def test_a_list_of_objects_becomes_one_table_and_a_list_of_words_a_list() -> None:
    """The shape of the value decides the shape of the markdown, not a per-key rule."""
    pair = priced_pair()
    pair["label"] = capture_of(
        "label",
        reply=json.dumps(
            {
                "labels": [{"element_id": "e1", "salience": "high"}],
                "keyphrases": ["offshore wind", "auction price"],
                "claims": [],
            }
        ),
    )

    document = analyzer.render(pair, head=0, tail=0)

    assert "| # | element_id | salience |" in document
    assert "| 1 | e1 | high |" in document
    assert "1. offshore wind" in document
    assert "Nothing came back under `claims`." in document


def census_row() -> ItemHealthRow:
    """One item-health row carrying both calls' costs, as a run that recorded them files it.

    Built on the committed published-row fixture, so every cell this report does
    not read keeps a value the contract already accepts.
    """
    published = json.loads(read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json"))
    url = "https://example.org/wind-farm"
    return ItemHealthRow.model_validate(
        {
            **published,
            "date": DAY,
            "run_id": RUN_ID,
            "item_id": ITEM_ID,
            "canonical_url": url,
            "url_key": derive_url_key(url),
            "vertical": "india",
            "source_id": "dna-india",
            "source_words": 353,
            "summary_words": 95,
            "machine_job": ServerJob.WORK,
            "machine_shard": 2,
            "model_calls": 2,
            "label_kind": "label",
            "label_prefill_ms": 6180,
            "label_decode_ms": 5861,
            "label_input_tokens": 3886,
            "label_output_tokens": 279,
            "label_cached_tokens": 0,
            "label_finish_reason": "stop",
            "summary_kind": "summarize_and_plan",
            "summary_prefill_ms": 6214,
            "summary_decode_ms": 3188,
            "summary_input_tokens": 4214,
            "summary_output_tokens": 512,
            "summary_cached_tokens": 3886,
            "summary_finish_reason": "length",
            "prefill_ms": 12394,
            "decode_ms": 9049,
            "input_tokens": 8100,
            "output_tokens": 791,
            "cached_tokens": 3886,
            "visual_plan_ms": 1178,
            "visual_plan_tokens_written": 192,
        }
    )


def census_day(state: Path) -> Path:
    """The day's census filed through the ledger door, the way a finished run leaves it."""
    seed_item_health(state, DAY, [census_row()])
    return state


def test_an_older_capture_fills_its_costs_from_the_day_ledger(tmp_path: Path) -> None:
    """A capture written before costs were recorded still answers what it cost."""
    state = census_day(tmp_path / "state")
    pair = {"label": capture_of("label"), "summary": capture_of("summary")}

    rows = analyzer.from_ledger(state, DAY)
    filled = analyzer.merged(pair, rows[ITEM_ID])
    document = analyzer.render(filled, head=0, tail=0)

    assert "| 1 | label | 12.0 s | 6,180 | 5,861 | 3,886 | 0 | 3,886 | 279 |" in document
    assert "| the visual plan | 1,178 | 192 |" in document
    assert "| the summary | 2,010 | 320 |" in document


def test_the_report_names_the_story_so_the_summary_can_be_checked(tmp_path: Path) -> None:
    """A summary is right or wrong against a source, so the source is section 1."""
    state = census_day(tmp_path / "state")
    pair = {"label": capture_of("label"), "summary": capture_of("summary")}

    rows = analyzer.from_ledger(state, DAY)
    document = analyzer.render(analyzer.merged(pair, rows[ITEM_ID]), head=0, tail=0)

    assert document.index("## 1. The story these calls read") < document.index("## 2. ")
    assert "| link | <https://example.org/wind-farm> |" in document
    assert "| outlet | dna-india |" in document
    assert "| length | 353 words of article, 95 words of summary |" in document
    assert f"| run | {RUN_ID}, shard 2 |" in document
    assert "read section 5 beside it" in document


def test_the_health_flag_names_a_day_and_the_report_fills_from_it(tmp_path: Path) -> None:
    """`--health` takes the run's UTC day and reads that day's census through the door."""
    state = census_day(tmp_path / "state")
    captures = tmp_path / "captures"
    captures.mkdir()
    for call in analyzer.CALL_ORDER:
        (captures / f"{ITEM_ID}.{call}.json").write_text(
            json.dumps({"call": call, "item_id": ITEM_ID, "prompt": "the prompt", "reply": "{}"}),
            encoding="utf-8",
            newline="\n",
        )
    out = tmp_path / "report.md"
    asked = [str(captures), "--item", ITEM_ID, "--health", DAY]

    returned = analyzer.main([*asked, "--state", str(state), "--out", str(out)])

    document = out.read_text(encoding="utf-8")
    assert returned == 0
    assert "| 1 | label | 12.0 s | 6,180 | 5,861 | 3,886 | 0 | 3,886 | 279 |" in document
    assert f"| run | {RUN_ID}, shard 2 |" in document


def test_a_day_the_ledger_holds_no_row_for_is_refused(tmp_path: Path) -> None:
    """A mistyped day must not read as a run that recorded no cost."""
    captures = tmp_path / "captures"
    captures.mkdir()
    (captures / f"{ITEM_ID}.label.json").write_text(
        json.dumps({"call": "label", "item_id": ITEM_ID}), encoding="utf-8", newline="\n"
    )

    with pytest.raises(SystemExit) as refused:
        analyzer.main([str(captures), "--health", DAY, "--state", str(tmp_path / "state")])

    assert refused.value.code == 2


def test_the_capture_keeps_the_link_the_ledger_would_have_been_pruned_of() -> None:
    """The artifact outlives the row, so the link travels with the prompt."""
    pair = priced_pair()
    pair["label"] = capture_of(
        "label",
        about={"canonical_url": "https://example.org/wind-farm", "source_id": "dna-india"},
    )

    document = analyzer.render(pair, head=0, tail=0)

    assert "| link | <https://example.org/wind-farm> |" in document


def test_a_report_with_no_link_says_which_flag_would_find_one() -> None:
    """A section that renders nothing teaches a reader the tool is broken."""
    document = analyzer.render(priced_pair(), head=0, tail=0)

    assert "This capture does not say which story it was about" in document


def test_a_pair_with_no_costs_says_so_and_names_the_flag_that_fixes_it() -> None:
    """A section that silently renders nothing teaches a reader the tool is broken."""
    pair = {"label": capture_of("label"), "summary": capture_of("summary")}

    document = analyzer.render(pair, head=0, tail=0)

    assert "No call in this pair recorded what it cost" in document
    assert "--health <YYYY-MM-DD>" in document


def test_a_prompt_holding_a_code_fence_does_not_break_out_of_its_block() -> None:
    """Fetched article text reaches this page, so the fence is sized to hold it."""
    pair = priced_pair()
    pair["label"] = capture_of("label", prompt="the article said\n```python\nx = 1\n```\nand ended")

    document = analyzer.render(pair, head=0, tail=0)

    assert "````text" in document
    assert "```python" in document


def test_a_capture_file_round_trips_through_load(tmp_path: Path) -> None:
    """What `idhazh.capture` writes is what this reads, keys and all."""
    path = tmp_path / "india-5tnmq7gb.summary.json"
    path.write_text(
        json.dumps(
            {
                "about": {
                    "canonical_url": "https://example.org/wind-farm",
                    "source_id": "dna-india",
                    "title": "A wind farm starts sending power",
                },
                "call": "summary",
                "cost": {
                    "kind": "summarize_and_plan",
                    "prefill_ms": 6214,
                    "decode_ms": 3188,
                    "input_tokens": 4214,
                    "output_tokens": 512,
                    "cached_tokens": 3886,
                },
                "decode_split": {"summary_ms": 2010, "plan_ms": 1178, "is_estimate": True},
                "finish_reason": "length",
                "item_id": "india-5tnmq7gb",
                "prompt": "the prompt",
                "prompt_chars": 10,
                "prompt_sha256": "a" * 64,
                "reply": "{}",
                "reply_chars": 2,
                "reply_sha256": "b" * 64,
            }
        ),
        encoding="utf-8",
        newline="\n",
    )

    loaded = analyzer.load(path)

    assert loaded.cost is not None
    assert loaded.cost.read_tokens == 328
    assert loaded.split is not None
    assert loaded.split.plan_ms == 1178
    assert loaded.finish_reason == "length"
    assert loaded.about.canonical_url == "https://example.org/wind-farm"
