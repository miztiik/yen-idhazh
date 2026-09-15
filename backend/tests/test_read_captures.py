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

from utilities import read_captures


def capture_of(
    call: str,
    *,
    prompt: str = "system turn\narticle\n",
    reply: str = '{"labels": [], "keyphrases": ["wind"]}',
    cost: dict[str, object] | None = None,
    decode_split: dict[str, object] | None = None,
    finish_reason: str = "stop",
) -> read_captures.Capture:
    """One capture as `idhazh.capture` writes it, read back through `load`."""
    return read_captures.Capture(
        item_id="india-5tnmq7gb",
        call=call,
        prompt=prompt,
        reply=reply,
        prompt_chars=len(prompt),
        reply_chars=len(reply),
        prompt_sha256="a" * 64,
        finish_reason=finish_reason,
        cost=read_captures.cost_of(cost),
        split=read_captures.split_of(decode_split),
    )


def priced_pair() -> dict[str, read_captures.Capture]:
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
    document = read_captures.render(priced_pair(), head=0, tail=0)

    assert "| 1 | label | 12.0 | 6,180 | 5,861 | 3,886 | 0 | 3,886 | 279 |" in document
    assert "| 2 | summary (summarize_and_plan) | 9.4 |" in document
    assert "**2 calls** | **21.4** | **12,394** | **9,049** | **8,100** | **3,886**" in document


def test_the_cache_saving_is_stated_in_tokens_and_in_characters() -> None:
    """A percentage with no numerator is a number nobody can check (Guardrail #10)."""
    document = read_captures.render(priced_pair(), head=0, tail=0)

    assert "reused 3,886 of the summarize-and-plan call's 4,214 prompt tokens (92.2%)" in document
    assert "read 328 of them" in document


def test_the_picture_gets_its_own_share_of_the_second_decode() -> None:
    """Two halves of one decode, and the row says which of them is an estimate."""
    document = read_captures.render(priced_pair(), head=0, tail=0)

    assert "| the summary | 2,010 | 320 | 62.5% |" in document
    assert "| the visual plan | 1,178 | 192 | 37.5% |" in document
    assert "**These two rows are an estimate.**" in document


def test_the_raw_text_comes_after_everything_that_reads_it() -> None:
    """Signal before noise: the bytes are kept whole and are read last."""
    document = read_captures.render(priced_pair(), head=0, tail=0)

    assert document.index("## 2. What the calls cost") < document.index("## 5. The raw text")
    assert document.index("## 3. What the label call sent back") < document.index("## 5. ")
    assert "<details>" in document
    assert "system turn\narticle\nnow summarize" in document


def test_every_heading_carries_its_number_in_order() -> None:
    """A numbered heading a reader can cite, and no gap where a section was skipped."""
    document = read_captures.render(priced_pair(), head=0, tail=0)

    tops = [line for line in headings(document) if line.startswith("## ")]
    assert [line.split(".")[0] for line in tops] == ["## 1", "## 2", "## 3", "## 4", "## 5"]
    assert headings(document)[0] == "# india-5tnmq7gb"


def test_a_reply_that_will_not_parse_says_where_it_broke() -> None:
    """The item worth opening is the one the pipeline could not read, so it renders."""
    pair = priced_pair()
    pair["label"] = capture_of("label", reply='{"labels": [{"element_id": "e1",')

    document = read_captures.render(pair, head=0, tail=0)

    assert "**This reply cannot be read as JSON**" in document
    assert "the JSON stops being readable at character" in document
    assert '{"labels": [{"element_id": "e1",' in document


def test_a_decoder_that_could_not_stop_is_named_at_the_top() -> None:
    """One unbroken lowercase run is what the 2026-09-14 stall looked like."""
    pair = priced_pair()
    pair["label"] = capture_of("label", reply='{"a": "' + "x" * 900 + '"}')

    document = read_captures.render(pair, head=0, tail=0)
    verdict = document.split("## 2.")[0]

    assert "900-character unbroken lowercase run" in verdict


def test_a_cut_reply_is_named_before_any_number() -> None:
    """`length` means the output budget cut the reply rather than the model ending it."""
    pair = priced_pair()
    pair["summary"] = capture_of("summary", finish_reason="length")

    verdict = read_captures.render(pair, head=0, tail=0).split("## 2.")[0]

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

    document = read_captures.render(pair, head=0, tail=0)

    assert "| # | element_id | salience |" in document
    assert "| 1 | e1 | high |" in document
    assert "1. offshore wind" in document
    assert "Nothing came back under `claims`." in document


def test_an_older_capture_fills_its_costs_from_the_day_ledger(tmp_path: Path) -> None:
    """A capture written before costs were recorded still answers what it cost."""
    ledger = tmp_path / "14.csv"
    ledger.write_text(
        "run_id,item_id,label_kind,label_prefill_ms,label_decode_ms,label_input_tokens,"
        "label_output_tokens,label_cached_tokens,label_finish_reason,summary_kind,"
        "summary_prefill_ms,summary_decode_ms,summary_input_tokens,summary_output_tokens,"
        "summary_cached_tokens,summary_finish_reason,visual_plan_ms,visual_plan_tokens_written\n"
        "34852763827,india-5tnmq7gb,label,6180,5861,3886,279,0,stop,summarize_and_plan,"
        "6214,3188,4214,512,3886,length,1178,192\n",
        encoding="utf-8",
        newline="\n",
    )
    pair = {"label": capture_of("label"), "summary": capture_of("summary")}

    filled = read_captures.merged(pair, read_captures.from_ledger(ledger, "india-5tnmq7gb"))
    document = read_captures.render(filled, head=0, tail=0)

    assert "| 1 | label | 12.0 | 6,180 | 5,861 | 3,886 | 0 | 3,886 | 279 |" in document
    assert "| the visual plan | 1,178 | 192 |" in document
    assert "| the summary | 2,010 | 320 |" in document


def test_a_pair_with_no_costs_says_so_and_names_the_flag_that_fixes_it() -> None:
    """A section that silently renders nothing teaches a reader the tool is broken."""
    pair = {"label": capture_of("label"), "summary": capture_of("summary")}

    document = read_captures.render(pair, head=0, tail=0)

    assert "No call in this pair recorded what it cost" in document
    assert "--health state/item-health/<yyyy>/<mm>/<dd>.csv" in document


def test_a_prompt_holding_a_code_fence_does_not_break_out_of_its_block() -> None:
    """Fetched article text reaches this page, so the fence is sized to hold it."""
    pair = priced_pair()
    pair["label"] = capture_of("label", prompt="the article said\n```python\nx = 1\n```\nand ended")

    document = read_captures.render(pair, head=0, tail=0)

    assert "````text" in document
    assert "```python" in document


def test_a_capture_file_round_trips_through_load(tmp_path: Path) -> None:
    """What `idhazh.capture` writes is what this reads, keys and all."""
    path = tmp_path / "india-5tnmq7gb.summary.json"
    path.write_text(
        json.dumps(
            {
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

    loaded = read_captures.load(path)

    assert loaded.cost is not None
    assert loaded.cost.read_tokens == 328
    assert loaded.split is not None
    assert loaded.split.plan_ms == 1178
    assert loaded.finish_reason == "length"
