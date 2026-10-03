"""Can every verb a workflow invokes still be routed, and does each one run?

A workflow run is pinned to the commit that triggered it, so a scheduled run
that started before a merge calls the verb the old line spells, halfway through
a pipeline. A verb that stopped resolving is therefore not a failed command: it
is a published day that never finishes. The first test holds both sides of that
- the verbs the committed workflows actually spell, read out of the workflow
YAML and the shipped scripts, against the tuple the router accepts.

Reading the verbs rather than listing them is the whole point. A hand-written
list here would be a second place a verb is written down, and the one that
drifts is always the copy nobody is looking at.

The second test runs every subcommand `idhazh telemetry` declares against a day
built in the test's own tree. It cannot settle whether the subcommand NAMES are
the right ones - whether `census` should have been called `items`, or whether
four is the right number of them. That is a person's call and no test can take
it. What it settles is that each name the router declares reaches a body that
runs to completion over a real day.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Final

import pytest
from conftest import (
    CONTRACT_FIXTURES_DIR,
    read_text,
    seed_feed_health,
    seed_item_health,
)

from idhazh import assemble, atomic_write, cli, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.observation_index import ObservationIndexRow
from idhazh.contracts.run_manifest import RunManifest
from idhazh.telemetry import cli as telemetry_cli
from idhazh.telemetry import inventory

from ._harness import _load_workflows, _run_bodies

pytestmark = pytest.mark.workflow

#: How a step spells a call into the pipeline. The verb has to be separated from
#: `idhazh` by a space, so `python -m idhazh.council.run` is a call into a module
#: rather than a verb and is correctly not matched.
INVOCATION: Final = re.compile(r"python3?\s+-m\s+idhazh\s+(?P<verb>[a-z][a-z0-9-]*)")


def _verbs(text: str) -> list[str]:
    """Every verb a shell body invokes. A commented line names nothing."""
    return [
        match.group("verb")
        for line in text.splitlines()
        if not line.lstrip().startswith("#")
        for match in INVOCATION.finditer(line)
    ]


def _invoked() -> dict[str, set[str]]:
    """Every verb the committed automation spells, by the file that spells it."""
    found: dict[str, set[str]] = {}
    for filename, workflow in sorted(_load_workflows().items()):
        for body in _run_bodies(workflow):
            for verb in _verbs(body):
                found.setdefault(filename, set()).add(verb)
    return found


def test_every_verb_a_workflow_invokes_resolves() -> None:
    """A verb a step spells and the router does not accept is a dead pipeline."""
    invoked = _invoked()
    assert invoked, "no workflow invoked the pipeline, so this test proves nothing"

    unrouted = sorted(
        f"{filename} calls `idhazh {verb}`"
        for filename, verbs in invoked.items()
        for verb in verbs
        if verb not in cli.STAGES
    )
    assert not unrouted, (
        "a committed workflow step invokes a verb the router does not accept. A run "
        "pinned to that commit would die mid-pipeline rather than at the command "
        "line: " + "; ".join(unrouted)
    )


def _a_published_day(tmp_path: Path) -> tuple[Path, Path, str]:
    """One day on disk, from the committed payloads, with the ledger rows it earned.

    A built tree rather than the committed archive: the archive grows, so a test
    that read it would cost more every month for the same answer (Guardrail #12,
    CLAUDE.md section 13). The payloads are the real contract fixtures, so the
    day that publishes here is the shape a run writes.
    """
    day = DigestDay.from_json(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    manifest = RunManifest.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json")
    )
    assert day.date == manifest.date, (
        "the digest-day and run-manifest fixtures are about different days, so a "
        "publication driven from the pair would file one day's projections under "
        f"another: {day.date} against {manifest.date}"
    )
    run_id = manifest.runs[-1].run_id

    digest_root = tmp_path / "digest"
    target = assemble.day_dir(digest_root, day.date)
    atomic_write.write_atomic(target / "digest.json", day.to_json())
    atomic_write.write_atomic(target / "run.json", manifest.to_json())

    state_root = tmp_path / "state"
    item = ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json")
    )
    seed_item_health(
        state_root, day.date, [item.model_copy(update={"date": day.date, "run_id": run_id})]
    )
    feed = FeedHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "feed-health-row" / "answered.json")
    )
    seed_feed_health(
        state_root,
        day.date,
        [
            feed.model_copy(
                update={
                    "date": day.date,
                    "run_id": run_id,
                    "checked_at": f"{day.date}T06:00:00Z",
                }
            )
        ],
        run_id=run_id,
    )
    return state_root, digest_root, day.date


@pytest.mark.parametrize("subcommand", [each.name for each in telemetry_cli.SUBCOMMANDS])
def test_every_telemetry_subcommand_runs_against_a_day(
    subcommand: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Each declared subcommand reaches a body and that body finishes.

    Driven off `SUBCOMMANDS` rather than a list here, so a subcommand added to
    the router without a body cannot pass this file by being left out of it.

    A subcommand that takes flags of its own is driven with the ones it requires
    and no others. `prune` is the first of those, and it runs on its own default:
    a dry run over the built day, which names that day and removes nothing.
    """
    state_root, digest_root, date = _a_published_day(tmp_path)
    extra = {
        "prune": ["--target", LedgerName.FEED_HEALTH, "--since", date, "--until", date],
        "item": ["ai-01"],
    }

    exit_code = cli.main(
        [
            telemetry_cli.VERB,
            subcommand,
            "--date",
            date,
            "--state-root",
            str(state_root),
            "--digest-root",
            str(digest_root),
            *extra.get(subcommand, []),
        ]
    )

    assert exit_code == 0
    assert date in capsys.readouterr().out, "a subcommand that printed nothing answered nothing"


def test_a_prune_the_router_refuses_names_the_store_and_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A refused target leaves the command line, not the file system.

    Through `cli.main` rather than through `prune.prune_range`, because the two
    can disagree: the body raises and the router has to turn that into a usage
    error with the reason attached rather than a traceback. Exit 2 is what
    argparse gives a command line nobody can act on, which is what this is.
    """
    state_root, digest_root, date = _a_published_day(tmp_path)
    before = sorted(
        path.relative_to(state_root).as_posix() for path in state_root.rglob("*") if path.is_file()
    )

    with pytest.raises(SystemExit) as exit_code:
        cli.main(
            [
                telemetry_cli.VERB,
                "prune",
                "--date",
                date,
                "--state-root",
                str(state_root),
                "--digest-root",
                str(digest_root),
                "--target",
                LedgerName.PUBLISHED,
                "--since",
                date,
                "--until",
                date,
            ]
        )

    assert exit_code.value.code == 2
    assert LedgerName.PUBLISHED in capsys.readouterr().err
    assert (
        sorted(
            path.relative_to(state_root).as_posix()
            for path in state_root.rglob("*")
            if path.is_file()
        )
        == before
    )


def _files_under(state_root: Path) -> set[str]:
    """Every file in a state tree, by its path under that tree."""
    return {
        path.relative_to(state_root).as_posix() for path in state_root.rglob("*") if path.is_file()
    }


def _prune(state_root: Path, digest_root: Path, date: str, target: str, *extra: str) -> int:
    """`idhazh telemetry prune` over one day of one ledger, as an operator types it."""
    return cli.main(
        [
            telemetry_cli.VERB,
            "prune",
            "--date",
            date,
            "--state-root",
            str(state_root),
            "--digest-root",
            str(digest_root),
            "--target",
            target,
            "--since",
            date,
            "--until",
            date,
            *extra,
        ]
    )


def test_a_live_prune_on_the_door_needs_the_run_and_the_commit_its_files_will_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without `--run-id` and `--commit` it is a usage error, and the tree is as it was.

    A file the prune rebuilds names its writer, and the router reports the
    missing flags the way argparse reports any other: the reason and exit 2.
    """
    state_root, digest_root, date = _a_published_day(tmp_path)
    before = _files_under(state_root)

    with pytest.raises(SystemExit) as exit_code:
        _prune(state_root, digest_root, date, LedgerName.ITEM_HEALTH, "--no-dry-run")

    assert exit_code.value.code == 2
    assert "--run-id" in capsys.readouterr().err
    assert _files_under(state_root) == before


def test_a_live_prune_on_the_door_takes_the_day_out_of_that_ledger_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The census day goes, each file is printed by name, and no other ledger loses a file."""
    state_root, digest_root, date = _a_published_day(tmp_path)
    before = _files_under(state_root)
    assert ledger.load_days(state_root, LedgerName.ITEM_HEALTH, [date], model=ItemHealthRow)

    exit_code = _prune(
        state_root,
        digest_root,
        date,
        LedgerName.ITEM_HEALTH,
        "--no-dry-run",
        "--run-id",
        f"{date}-9",
        "--commit",
        "c" * 40,
    )

    assert exit_code == 0
    assert ledger.load_days(state_root, LedgerName.ITEM_HEALTH, [date], model=ItemHealthRow) == []
    after = _files_under(state_root)
    gone = before - after
    assert gone and after <= before
    assert all(path.startswith(f"raw/{LedgerName.ITEM_HEALTH}/") for path in gone), gone
    printed = capsys.readouterr().out
    assert all(f"  remove {ledger.STATE_DIRNAME}/{path}" in printed for path in gone)


def test_the_eval_ledger_is_refused_through_the_router_with_its_declaration_s_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The reason a person reads is the sentence beside the eval ledger's windows."""
    state_root, digest_root, date = _a_published_day(tmp_path)
    before = _files_under(state_root)

    with pytest.raises(SystemExit) as exit_code:
        _prune(state_root, digest_root, date, LedgerName.SUMMARY_QUALITY_EVALS)

    assert exit_code.value.code == 2
    refusal = capsys.readouterr().err
    assert f"{LedgerName.SUMMARY_QUALITY_EVALS} is refused" in refusal
    assert "kept for ever" in refusal
    assert _files_under(state_root) == before


def test_show_names_the_day_shard_and_the_month_shard(tmp_path: Path) -> None:
    """The instrument files at two grains, and a listing that sees one is half blind.

    A day is `<ledger>/<YYYY>/<MM>/<DD>` in a writer-owned tree and one or two
    folders deeper under the ledger door - `raw/<ledger>/<YYYY>/<MM>/<DD>/` for
    the files a run filed, `compact/<ledger>/daily/<YYYY>/<MM>/<DD>` once the
    day is packed - and a month fold is `<ledger>/<YYYY-MM>`: a different
    depth, not a different suffix. A single glob finds one of them, and the one
    it misses is silently absent rather than reported empty. Every path is asked
    of the ledger rather than spelled here, so a ledger that moves takes this
    with it. The listing reads names alone, so the packed day and the month fold
    are placed as files and never opened.
    """
    state_root, _digest_root, date = _a_published_day(tmp_path)
    packed = ledger.compact_path(state_root, LedgerName.ITEM_HEALTH, Period.DAILY, date)
    packed.parent.mkdir(parents=True, exist_ok=True)
    packed.write_bytes(b"")
    month_fold = ledger.path(state_root, LedgerName.ITEM_HEALTH_SUMMARY, assemble.month_of(date))
    month_fold.parent.mkdir(parents=True, exist_ok=True)
    month_fold.write_text("version\n", encoding="utf-8", newline="\n")
    ids = LedgerName.SUMMARY_QUALITY_EVALS_INDEX
    digest = hashlib.sha256(date.encode("ascii")).hexdigest()
    ledger.write_segment(
        state_root,
        ids,
        [ObservationIndexRow(version=ObservationIndexRow.schema_version(), observation_digest=digest)],
        run_id=f"{date}-1",
        attempt=1,
        job=ServerJob.WORK,
        shard=0,
        date=date,
    )

    report = "\n".join(inventory.files(state_root, date=date))

    raw_files = [
        held.path.relative_to(state_root).as_posix()
        for held in ledger.list_raw_files(state_root, LedgerName.ITEM_HEALTH, days=[date])
    ]
    assert raw_files, "the built day filed no census, so the listing proves nothing about it"
    for relpath in raw_files:
        assert relpath in report, f"a raw day file is missing from the listing: {report}"
    tree_day = ledger.path(state_root, ids, date).relative_to(state_root)
    assert f"{tree_day.as_posix()}/" in report, (
        f"the writer-owned day is missing from the listing: {report}"
    )
    assert packed.relative_to(state_root).as_posix() in report, (
        f"the packed day is missing from the listing: {report}"
    )
    assert month_fold.relative_to(state_root).as_posix() in report, (
        f"the month fold is missing from the listing: {report}"
    )


def test_a_store_that_nests_is_listed_rather_than_silently_missed(tmp_path: Path) -> None:
    """A one-segment glob omits a nested ledger and reports success either way.

    `state/` root already holds 13 directories, so a ledger that groups its files
    under a parent is the ordinary next shape rather than an exotic one. The
    listing globbed `*/<Y>/<M>/<D>*`, which is one segment, so
    `<group>/<ledger>/<Y>/<M>/<D>` was absent from a report that said nothing
    about the absence - the failure mode this test exists to hold shut.

    Built here rather than read from the archive, so it holds on a tree the
    pipeline has never produced (CLAUDE.md section 13).
    """
    state_root, _digest_root, date = _a_published_day(tmp_path)
    year, month, day = date.split("-")
    nested = state_root / "a-group" / "a-ledger" / year / month
    nested.mkdir(parents=True)
    (nested / f"{day}.csv").write_text("version\n", encoding="utf-8", newline="\n")
    month_fold = state_root / "a-group" / "a-ledger" / f"{year}-{month}.csv"
    month_fold.write_text("version\n", encoding="utf-8", newline="\n")

    report = "\n".join(inventory.files(state_root, date=date))

    assert "a-group/a-ledger" in report, f"the nested day shard is missing: {report}"
    assert month_fold.relative_to(state_root).as_posix() in report
