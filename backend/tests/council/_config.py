"""Which named config files does a council command-line fixture need?"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from support.paths import CONFIG_DIR

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.council_invocation import SelectedJudge, Selection
from idhazh.contracts.knobs.council import CouncilConfig
from idhazh.council import night_plan, registry

RUN_ID = "2026-09-21-456"
COMMIT = "a" * 40


def selection(
    council: CouncilConfig,
    *,
    date: str,
    run_id: str = RUN_ID,
    commit_sha: str = COMMIT,
    attempt: int = 1,
) -> Selection:
    """Authorize the test's explicit date and actual registered plugin widths."""
    return Selection(
        version=Selection.schema_version(),
        run_id=run_id,
        attempt=attempt,
        git_sha=commit_sha,
        mode="manual" if council.running() else "scheduled",
        anchor_date=date,
        window=(date,)
        if council.running()
        else (
            date,
            *night_plan.window_before(council, tonight=date),
        ),
        judges=tuple(
            SelectedJudge(
                tenant=host.judge_id,
                status=council.declaration(host.judge_id).lifecycle_status,
                dates=(date,),
                shards=min(council.shards, host.shard_count),
            )
            for host in registry.tenants(council.running(), council=council)
        ),
    )


def prepared_selection(
    config_root: Path, *, dates: tuple[str, ...], run_id: str, commit_sha: str
) -> Selection:
    """Prepare a bounded batch before a publication test collects its actual files."""
    from idhazh import config, run_context
    from idhazh.council import session

    council = config.load_council(config_root)
    anchor = max(dates)
    selected = selection(
        council,
        date=anchor,
        run_id=run_id,
        commit_sha=commit_sha,
        attempt=run_context.run_attempt(),
    )
    selected = Selection(
        version=Selection.schema_version(),
        run_id=run_id,
        attempt=selected.attempt,
        git_sha=commit_sha,
        mode="scheduled",
        anchor_date=anchor,
        window=(anchor, *night_plan.window_before(council, tonight=anchor)),
        judges=tuple(judge.model_copy(update={"dates": dates}) for judge in selected.judges),
    )
    session.prepare(council, date=None, run_id=run_id, selection=selected)
    return selected


def copy_config(root: Path) -> Path:
    """Copy the loader's named inputs and the active model file, never the tree."""
    target = root / "config"
    target.mkdir(parents=True)
    for name in (
        "idhazh.json",
        "llm_council.json",
        "sources.json",
        "taxonomy.json",
        "watchlist.json",
        "appearance.json",
        "ledgers.json",
    ):
        shutil.copyfile(CONFIG_DIR / name, target / name)
    app = AppConfig.from_json((target / "idhazh.json").read_text(encoding="utf-8"))
    model = target / app.models_file
    model.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CONFIG_DIR / app.models_file, model)
    council = CouncilConfig.model_validate_json(
        (target / "llm_council.json").read_text(encoding="utf-8")
    )
    for name in council.judge_names:
        (target / "judges").mkdir(exist_ok=True)
        shutil.copyfile(CONFIG_DIR / "judges" / f"{name}.json", target / "judges" / f"{name}.json")
    return target


def set_host_fingerprint_placement(target: Path, enabled: bool) -> None:
    path = target / "idhazh.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["observability"].update(
        {
            "host_telemetry_enabled": True,
            "host_fingerprint": True,
            "host_fingerprint_bandwidth_jobs": [],
            "host_fingerprint_placement_enabled": enabled,
        }
    )
    path.write_text(json.dumps(raw, indent=2), encoding="utf-8", newline="\n")


def write_declarations(target: Path, slugs: tuple[str, ...]) -> None:
    """Write explicit active, model-free declarations for the test's registered judges."""
    (target / "judges").mkdir(exist_ok=True)
    for slug in slugs:
        (target / "judges" / f"{slug}.json").write_text(
            json.dumps({"lifecycle_status": "active", "runs_model": False}),
            encoding="utf-8",
            newline="\n",
        )
