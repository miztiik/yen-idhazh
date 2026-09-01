"""The evidence package: what it writes, and every way it refuses to be read.

The label queue exists to measure the faithfulness bands against a human
(`CLAUDE.md` Rule #10). That measurement is worth nothing if the person and the
scorer read different text, so most of what is asserted here is refusal: a row
with no recorded premise, a row the package does not hold, a file whose text was
edited, and a file that names a premise the ledger row was not scored on.

No mocks and no network (Rule #7). The premise, the summary and the identity
come from committed fixtures that other contract tests already read, and the
"a row with no premise digest" case runs over the real committed ledger.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, REPO_ROOT, STATE_DIR, read_text
from pydantic import ValidationError

from idhazh import cli
from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.evidence import EvidenceItem
from idhazh.contracts.label_row import LabelTag, LabelVerdict
from idhazh.contracts.summary import Summary
from idhazh.evals import evidence, writer
from utilities import label_queue

EVIDENCE_FIXTURE = CONTRACT_FIXTURES_DIR / "evidence-item" / "premise-recorded.json"
ROW_FIXTURE = CONTRACT_FIXTURES_DIR / "eval-row" / "premise-recorded.json"
DIGEST_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "digest.yml"


def an_item() -> EvidenceItem:
    return EvidenceItem.from_json(read_text(EVIDENCE_FIXTURE))


def a_row() -> EvalRow:
    return EvalRow.from_json(read_text(ROW_FIXTURE))


def a_queue_row() -> dict[str, str]:
    """One drawn row, spelled the way the CSV reader hands it to the tool."""
    return {name: str(value) for name, value in a_row().model_dump(mode="json").items()}


def _no_input(*_: object) -> str:
    raise AssertionError("a refused row must not be asked about")


def ledger() -> list[dict[str, str]]:
    """Every committed row, oldest month first. The ledger is a directory of shards."""
    return list(writer.records(STATE_DIR))


def written(directory: Path, item: EvidenceItem) -> Path:
    path = evidence.path_for(directory, item)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(item.to_json(), encoding="utf-8", newline="\n")
    return path


def edited(payload: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    return {**payload, **overrides}


class TestTheTextSurvivesTheRun:
    def test_the_writer_hands_back_the_text_it_was_given(self, tmp_path: Path) -> None:
        """Byte for byte. A premise that is nearly the one the scorer read is not it."""
        article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
        summary = Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))
        item = evidence.of(a_row(), premise=article.text or "", summary=summary.summary or "")

        reread = EvidenceItem.from_json(read_text(written(tmp_path, item)))

        assert reread.premise == article.text
        assert reread.summary == summary.summary
        assert reread.source_digest == derive_text_digest(article.text or "")

    def test_the_digest_is_the_one_the_eval_row_carries(self) -> None:
        """One digest convention. Two would let a row and its evidence both be right."""
        assert an_item().source_digest == a_row().source_digest

    def test_a_ledger_row_finds_its_evidence_with_no_lookup_table(self, tmp_path: Path) -> None:
        """The file name is the measurement, rebuilt from the row's own four fields."""
        item = an_item()
        path = written(tmp_path, item)
        record = a_queue_row()

        assert path.stem == evidence.key_of(record)
        assert evidence.index(tmp_path)[evidence.key_of(record)] == path

    def test_a_run_that_scored_nothing_leaves_an_empty_package(self, tmp_path: Path) -> None:
        """A missing directory is a package with nothing in it, not a crash."""
        assert evidence.index(tmp_path / "never-ran") == {}

    def test_a_package_downloaded_one_directory_per_shard_is_one_package(
        self, tmp_path: Path
    ) -> None:
        """Eight shards upload eight artifacts. A labeller downloads them into one place."""
        item = an_item()
        written(tmp_path / "evidence-0", item)

        assert list(evidence.index(tmp_path)) == [evidence.key_of(item.model_dump(mode="json"))]

    def test_the_run_files_one_item_under_the_day_it_scored_it(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The stage writes it once, beside every other item of that run-day."""
        monkeypatch.setattr(cli, "EVIDENCE_ROOT", tmp_path)
        row = a_row()

        path = cli._write_evidence(row, premise=an_item().premise, summary="Some words.")

        assert path.parent == tmp_path / row.date
        assert evidence.look_up(evidence.index(tmp_path), a_queue_row()).refusal is None

    def test_the_work_stage_writes_evidence_for_what_it_scores(self) -> None:
        """A writer nobody calls is a package nobody gets."""
        tree = ast.parse(read_text(REPO_ROOT / "backend" / "idhazh" / "cli.py"))
        stage = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "stage_work"
        )
        called = {
            node.func.id
            for node in ast.walk(stage)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

        assert "_write_evidence" in called


class TestARowNobodyCanJudgeIsRefused:
    def test_a_row_scored_before_the_premise_was_recorded_says_so(self, tmp_path: Path) -> None:
        found = evidence.look_up(
            evidence.index(tmp_path), a_queue_row() | {"source_digest": ""}
        )

        assert found.item is None
        assert found.refusal == evidence.NO_DIGEST

    def test_every_committed_row_with_no_premise_digest_is_refused(self, tmp_path: Path) -> None:
        """The ledger held 2,232 such rows on 2026-08-27. None of them may be labelled."""
        package = evidence.index(tmp_path)
        older = [row for row in ledger() if not (row.get("source_digest") or "").strip()]

        assert older, "the ledger no longer has a row that predates source_digest"
        assert {evidence.look_up(package, row).refusal for row in older} == {evidence.NO_DIGEST}

    def test_a_row_the_package_does_not_hold_says_so(self, tmp_path: Path) -> None:
        found = evidence.look_up(evidence.index(tmp_path), a_queue_row())

        assert found.item is None
        assert found.refusal == evidence.NOT_HELD

    def test_an_edited_premise_will_not_load_at_all(self) -> None:
        """The digest is rebuilt on read, so a changed article fails before a labeller sees it."""
        payload = edited(json.loads(read_text(EVIDENCE_FIXTURE)), premise="something else entirely")

        with pytest.raises(ValidationError):
            EvidenceItem.model_validate(payload)

    def test_an_edited_premise_is_refused_by_name(self, tmp_path: Path) -> None:
        item = an_item()
        path = evidence.path_for(tmp_path, item)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(edited(json.loads(item.to_json()), premise="something else entirely")),
            encoding="utf-8",
            newline="\n",
        )

        found = evidence.look_up(evidence.index(tmp_path), a_queue_row())

        assert found.item is None
        assert found.refusal == evidence.UNREADABLE

    def test_evidence_for_a_different_premise_is_refused(self, tmp_path: Path) -> None:
        """Same address, same words out, different text in. That is the case worth catching."""
        elsewhere = evidence.of(
            a_row(), premise="A different article altogether.", summary="Words."
        )
        written(tmp_path, elsewhere)

        found = evidence.look_up(evidence.index(tmp_path), a_queue_row())

        assert found.item is None
        assert found.refusal == evidence.DIFFERENT_TEXT

    def test_a_matching_row_is_handed_over(self, tmp_path: Path) -> None:
        item = an_item()
        written(tmp_path, item)

        found = evidence.look_up(evidence.index(tmp_path), a_queue_row())

        assert found.refusal is None
        assert found.item is not None
        assert found.item.premise == item.premise


class TestPathsThatLeaveTheProcess:
    """`CLAUDE.md` section 2: relative, POSIX-separated, minimal."""

    def test_the_evidence_root_is_relative_and_posix(self) -> None:
        assert evidence.EVIDENCE_ROOT_RELPATH == "backend/var/evidence"

    def test_a_file_the_run_wrote_is_spelled_relative_to_the_repository(self) -> None:
        day = REPO_ROOT / evidence.EVIDENCE_ROOT_RELPATH / "2026-08-27"
        spelled = evidence.posix_relpath(evidence.path_for(day, an_item()), base=REPO_ROOT)

        assert spelled.startswith("backend/var/evidence/2026-08-27/")
        assert "\\" not in spelled
        assert ":" not in spelled
        assert not spelled.startswith("/")

    def test_a_package_outside_the_repository_keeps_no_drive_letter(self, tmp_path: Path) -> None:
        spelled = evidence.posix_relpath(tmp_path / "downloaded", base=REPO_ROOT)

        assert spelled == "downloaded"
        assert "\\" not in spelled
        assert ":" not in spelled


class TestTheArticleBodyIsNeverCommitted:
    """Republishing an article body is a project non-goal (`CLAUDE.md` section 0a)."""

    def test_the_evidence_root_is_gitignored(self) -> None:
        ignored = read_text(REPO_ROOT / ".gitignore").splitlines()

        assert "backend/var/" in ignored

    def test_the_workflow_uploads_it_and_never_commits_it(self) -> None:
        workflow = read_text(DIGEST_WORKFLOW)

        assert "name: evidence-${{ matrix.shard }}" in workflow
        assert "path: backend/var/evidence/${{ needs.plan.outputs.date }}/" in workflow
        for line in workflow.splitlines():
            if "commit-and-push.sh" in line or line.strip().startswith("state/"):
                assert "evidence" not in line, "an uncommittable path reached the commit step"


class TestWhatALabellerSees:
    """The tool's whole job: put the article and the summary in front of a person."""

    def test_the_prompt_shows_the_article_and_the_summary(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        item = an_item()
        monkeypatch.setattr("builtins.input", lambda *_: "n")

        answer = label_queue._prompt(
            a_queue_row(), evidence.Evidence(item, None), index=1, total=1
        )
        shown = capsys.readouterr().out

        assert answer == (LabelVerdict.SUPPORTED, LabelTag.NONE)
        assert item.premise in shown
        assert item.summary in shown

    def test_a_refused_row_is_skipped_and_the_reason_is_printed(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No question is asked, so no keystroke can record a verdict on unseen text."""
        monkeypatch.setattr("builtins.input", _no_input)

        answer = label_queue._prompt(
            a_queue_row(), evidence.Evidence(None, evidence.NO_DIGEST), index=1, total=1
        )
        shown = capsys.readouterr().out

        assert answer is label_queue.SKIP
        assert evidence.NO_DIGEST in shown

    def test_the_draw_says_up_front_how_much_of_it_can_be_judged(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        holdable = a_queue_row()
        written(tmp_path, an_item())
        older = holdable | {"source_digest": ""}

        label_queue.package_report([holdable, older], evidence.index(tmp_path), where="somewhere")
        shown = capsys.readouterr().out

        assert "labellable       1 of 2" in shown
        assert evidence.NO_DIGEST in shown

    def test_the_package_flag_is_not_a_bulk_path(self) -> None:
        """`--evidence` supplies reading material. It can never supply a verdict."""
        source = read_text(REPO_ROOT / "backend" / "utilities" / "label_queue.py")

        for forbidden in ('"--from-file"', '"--model"', "sys.stdin", "readlines("):
            assert forbidden not in source
        assert source.count("labels.append(") == 1

