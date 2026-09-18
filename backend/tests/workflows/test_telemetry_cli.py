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

import re
from pathlib import Path
from typing import Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text, seed_item_health, seed_span_rollup

from idhazh import assemble, cli, ledger
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.span_rollup import SpanRollupRow
from idhazh.telemetry import cli as telemetry_cli
from idhazh.telemetry import inventory

from ._harness import SCRIPTS_DIR, _load_workflows, _run_bodies

pytestmark = pytest.mark.workflow

#: How a step spells a call into the pipeline. The verb has to be separated from
#: `idhazh` by a space, so `python -m idhazh.contracts.export` is a call into a
#: module rather than a verb and is correctly not matched.
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
    for script in sorted(SCRIPTS_DIR.glob("*.sh")):
        for verb in _verbs(read_text(script)):
            found.setdefault(script.name, set()).add(verb)
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
    day = DigestDay.from_json(read_text(next((CONTRACT_FIXTURES_DIR / "digest-day").glob("*.json"))))
    manifest = RunManifest.from_json(
        read_text(next((CONTRACT_FIXTURES_DIR / "run-manifest").glob("*.json")))
    )
    assert day.date == manifest.date, (
        "the digest-day and run-manifest fixtures are about different days, so a "
        "publication driven from the pair would file one day's projections under "
        f"another: {day.date} against {manifest.date}"
    )
    run_id = manifest.runs[-1].run_id

    digest_root = tmp_path / "digest"
    target = assemble.day_dir(digest_root, day.date)
    assemble.write_atomic(target / "digest.json", day.to_json())
    assemble.write_atomic(target / "run.json", manifest.to_json())

    state_root = tmp_path / "state"
    item = ItemHealthRow.from_json(
        read_text(next((CONTRACT_FIXTURES_DIR / "item-health-row").glob("*.json")))
    )
    seed_item_health(
        state_root, day.date, [item.model_copy(update={"date": day.date, "run_id": run_id})]
    )
    span = SpanRollupRow.from_json(
        read_text(next((CONTRACT_FIXTURES_DIR / "span-rollup-row").glob("*.json")))
    )
    seed_span_rollup(
        state_root, day.date, [span.model_copy(update={"date": day.date, "run_id": run_id})]
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
        "prune": ["--target", ledger.ITEM_HEALTH_DIRNAME, "--since", date, "--until", date]
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
    before = sorted(path.relative_to(state_root).as_posix() for path in state_root.rglob("*.csv"))

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
                ledger.PUBLISHED_DIRNAME,
                "--since",
                date,
                "--until",
                date,
            ]
        )

    assert exit_code.value.code == 2
    assert ledger.PUBLISHED_DIRNAME in capsys.readouterr().err
    assert (
        sorted(path.relative_to(state_root).as_posix() for path in state_root.rglob("*.csv"))
        == before
    )


def test_show_names_the_day_shard_and_the_month_shard(tmp_path: Path) -> None:
    """The instrument shards at two grains, and a listing that sees one is half blind.

    A day shard is `<store>/<YYYY>/<MM>/<DD>` and a month fold is
    `<store>/<YYYY-MM>` - a different depth, not a different suffix. A single
    glob finds one of them, and the one it misses is silently absent rather than
    reported empty. Both paths are asked of the ledger rather than spelled here,
    so a store that moves takes this with it.
    """
    state_root, _digest_root, date = _a_published_day(tmp_path)

    report = "\n".join(inventory.files(state_root, date=date))

    day_shard = ledger.item_health_path(state_root, date).relative_to(state_root).as_posix()
    month_shard = (
        ledger.span_rollup_path(state_root, assemble.month_of(date))
        .relative_to(state_root)
        .as_posix()
    )
    assert day_shard in report, f"the day shard is missing from the listing: {report}"
    assert month_shard in report, f"the month shard is missing from the listing: {report}"


def test_a_store_that_nests_is_listed_rather_than_silently_missed(tmp_path: Path) -> None:
    """A one-segment glob omits a nested store and reports success either way.

    `state/` root already holds 13 directories, so a store that groups its files
    under a parent is the ordinary next shape rather than an exotic one. The
    listing globbed `*/<Y>/<M>/<D>*`, which is one segment, so
    `<group>/<store>/<Y>/<M>/<D>` was absent from a report that said nothing
    about the absence - the failure mode this test exists to hold shut.

    Built here rather than read from the archive, so it holds on a tree the
    pipeline has never produced (CLAUDE.md section 13).
    """
    state_root, _digest_root, date = _a_published_day(tmp_path)
    year, month, day = date.split("-")
    nested = state_root / "a-group" / "a-store" / year / month
    nested.mkdir(parents=True)
    (nested / f"{day}.csv").write_text("version\n", encoding="utf-8", newline="\n")
    month_fold = state_root / "a-group" / "a-store" / f"{year}-{month}.csv"
    month_fold.write_text("version\n", encoding="utf-8", newline="\n")

    report = "\n".join(inventory.files(state_root, date=date))

    assert "a-group/a-store" in report, f"the nested day shard is missing: {report}"
    assert month_fold.relative_to(state_root).as_posix() in report
