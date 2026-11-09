"""Do council utilities read configured bounds and registered paths safely?"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from support.paths import CONFIG_DIR, REPO_ROOT

from idhazh import ledger
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain
from idhazh.ledger import staging
from utilities import council_matrix, shard_bound

pytestmark = pytest.mark.workflow

TIMEOUT_KEY = "shard_timeout_minutes"
TIMEOUT_FILE = "llm_council.json"


@pytest.mark.parametrize("value", [200.0, "200", 0, -1, True])
def test_an_unreadable_timeout_is_refused_before_the_job_starts(
    value: object, tmp_path: Path
) -> None:
    (tmp_path / TIMEOUT_FILE).write_text(
        json.dumps({TIMEOUT_KEY: value}), encoding="utf-8", newline="\n"
    )
    with pytest.raises(SystemExit):
        shard_bound.minutes(tmp_path, key=TIMEOUT_KEY, config_file=TIMEOUT_FILE)


def test_a_missing_configured_bound_is_refused_rather_than_traced() -> None:
    stale = "run.judge_shard_timeout_minutes"
    with pytest.raises(SystemExit, match=re.escape(stale)):
        shard_bound.minutes(CONFIG_DIR, key=stale)


def test_the_bound_reader_answers_its_configured_callers() -> None:
    assert shard_bound.minutes(CONFIG_DIR) >= 1
    assert shard_bound.minutes(CONFIG_DIR, key=TIMEOUT_KEY, config_file=TIMEOUT_FILE) >= 1


def test_every_path_a_registered_tenant_names_exists_in_a_fresh_checkout() -> None:
    door_folders = {
        staging.staged_path(which)
        for which in LedgerName
        if ledger.entry(which).grain is Grain.RAW_AND_COMPACT
    }
    missing = [
        path
        for path in council_matrix.committed_paths(CONFIG_DIR)
        if path not in door_folders and not (REPO_ROOT / path).exists()
    ]
    assert not missing, f"a tenant names paths a fresh checkout does not have: {missing}"
