"""Where does a capture land when one article is read more than once?"""

from __future__ import annotations

import logging
from pathlib import Path

from conftest import CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.article import Article
from idhazh.contracts.call_cost import CallKind
from idhazh.llm.server import Completion
from idhazh.stages import two_calls
from idhazh.telemetry.record import Flags, ItemRecorder


def a_recorder() -> ItemRecorder:
    """Both capture flags on, which is what a run with default config has."""
    return ItemRecorder(
        run_id="2026-09-18-qualify-0-1",
        flags=Flags(
            item_lines=False,
            stage_lines=False,
            capture_prompts=True,
            capture_replies=True,
        ),
        now=lambda: "2026-09-18T00:00:00Z",
        log=logging.getLogger("test"),
    )


def an_article() -> Article:
    """The contract fixture, read inside the test that wants it (section 13)."""
    return Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))


def keep_one(root: Path, prompt: str) -> None:
    two_calls._kept_call(
        a_recorder(),
        "2026-09-18",
        an_article(),
        call="summary",
        kind=CallKind.SUMMARIZE_AND_PLAN,
        prompt=prompt,
        reply=Completion(content='{"summary": "x"}', finish_reason="stop"),
        capture_root=root,
    )


def test_two_readings_of_one_article_do_not_overwrite_each_other(tmp_path: Path) -> None:
    """A capture is named for the item and the call, so nothing in the name says
    which reading it was. On the pair the second prompt replays the first call's
    reply, so two readings of one article do not even share a prompt - the one
    that survived an overwrite would be evidence about a reading nobody chose.
    """
    keep_one(tmp_path / "repeat-1", "first reading")
    keep_one(tmp_path / "repeat-2", "second reading")

    kept = sorted(tmp_path.rglob("*.json"))
    assert len(kept) == 2
    assert {path.parent.name for path in kept} == {"repeat-1", "repeat-2"}
    assert "first reading" in kept[0].read_text(encoding="utf-8")
    assert "second reading" in kept[1].read_text(encoding="utf-8")


def test_a_caller_that_names_no_root_still_writes_under_the_run(tmp_path: Path) -> None:
    """The digest reads each article once and passes no root. Its captures have
    to keep landing where `pipeline_artifact_analyzer` and the workflow expect."""
    keep_one(tmp_path, "the digest's own reading")

    kept = sorted(tmp_path.rglob("*.json"))
    assert len(kept) == 1
    assert kept[0].parent == tmp_path
