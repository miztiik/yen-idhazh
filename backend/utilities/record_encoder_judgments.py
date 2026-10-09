"""Append reasoned pair judgments without relying on session memory."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import TypeAdapter

from idhazh.contracts.encoder_judgment import (
    EncoderJudgment,
    JudgmentFrame,
    JudgmentPair,
    PairDecision,
)


def pair_hash(pair: JudgmentPair) -> str:
    content = {"a": pair.a.model_dump(), "b": pair.b.model_dump()}
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def read_frame(path: Path) -> tuple[JudgmentFrame, str]:
    raw = path.read_bytes()
    if b"\r\n" in raw:
        raise ValueError("the pair frame must use LF before judgments are recorded")
    frame = JudgmentFrame.model_validate_json(raw)
    if len(frame.rows) != frame.pairs_to_read:
        raise ValueError("the pair-frame count differs from its rows")
    if len({pair.id for pair in frame.rows}) != len(frame.rows):
        raise ValueError("the pair frame contains repeated ids")
    return frame, hashlib.sha256(raw).hexdigest()


def read_judgments(
    path: Path, frame: JudgmentFrame, frame_hash: str
) -> list[EncoderJudgment]:
    if not path.is_file():
        return []
    pairs = {pair.id: pair for pair in frame.rows}
    records = [
        EncoderJudgment.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    for record in records:
        if record.frame_sha256 != frame_hash:
            raise ValueError(f"{record.pair_id}: judgment belongs to a different frame")
        if record.pair_id not in pairs:
            raise ValueError(f"{record.pair_id}: not in this frame")
        if record.pair_sha256 != pair_hash(pairs[record.pair_id]):
            raise ValueError(f"{record.pair_id}: the judged article content differs")
    return records


def append_decisions(
    frame_path: Path,
    output: Path,
    decisions_path: Path,
    labeler: str,
    label_source: str,
    correction: bool = False,
) -> int:
    frame, frame_hash = read_frame(frame_path)
    previous = read_judgments(output, frame, frame_hash)
    decisions = TypeAdapter(dict[str, PairDecision]).validate_json(
        decisions_path.read_bytes()
    )
    if not decisions:
        raise ValueError("the judgment batch is empty")
    pairs = {pair.id: pair for pair in frame.rows}
    already = {record.pair_id for record in previous}
    human_reviewed = {record.pair_id for record in previous if record.label_source == "human"}
    added = []
    for pair_id, decision in decisions.items():
        if pair_id not in pairs:
            raise ValueError(f"{pair_id}: not in this frame")
        if pair_id in already and not correction:
            raise ValueError(f"{pair_id}: already judged; use --correction to append a revision")
        if pair_id in human_reviewed and label_source == "model":
            raise ValueError(f"{pair_id}: a model cannot replace a person's review")
        added.append(EncoderJudgment.model_validate({
            **decision.model_dump(),
            "pair_id": pair_id,
            "frame_sha256": frame_hash,
            "pair_sha256": pair_hash(pairs[pair_id]),
            "label_source": label_source,
            "labeler": labeler,
            "recorded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "human_verdict": decision.verdict if label_source == "human" else None,
        }))

    original = output.read_bytes() if output.is_file() else b""
    if original and not original.endswith(b"\n"):
        raise ValueError(f"{output}: the last judgment line is incomplete")
    delta = "".join(record.model_dump_json() + "\n" for record in added).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    temporary.write_bytes(original + delta)
    temporary.replace(output)
    return len(added)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--judgments", type=Path, required=True)
    parser.add_argument("--records", type=Path)
    parser.add_argument("--labeler")
    parser.add_argument("--label-source", choices=("model", "human"), default="model")
    parser.add_argument("--correction", action="store_true")
    parser.add_argument("--show", type=int, default=0)
    args = parser.parse_args()

    if args.records:
        if not args.labeler:
            parser.error("--records requires --labeler")
        added = append_decisions(
            args.pairs, args.judgments, args.records,
            args.labeler, args.label_source, args.correction,
        )
        print(f"appended {added} judgments")
    frame, frame_hash = read_frame(args.pairs)
    records = read_judgments(args.judgments, frame, frame_hash)
    latest = {record.pair_id: record for record in records}
    print(f"{len(latest)} of {len(frame.rows)} judged; {len(records)} history rows")
    print(f"{sum(record.human_verdict is not None for record in latest.values())} human-reviewed")
    waiting = [pair for pair in frame.rows if pair.id not in latest]
    for pair in waiting[:args.show]:
        print(f"\n== {pair.id}")
        for name, article in (("A", pair.a), ("B", pair.b)):
            print(f"{name} [{article.day}] {article.title}\n{article.summary}")


if __name__ == "__main__":
    main()
