"""Does the address in `config/` decide where a stage posts, with nobody naming one?

Until 2026-09-23 it did not, and no test would have said so. The address was a
default argument bound when `idhazh.llm.server` was imported, at eighteen sites,
and no caller anywhere overrode one - so a config field could have been added,
validated, published in the schema and typed into the frontend, and every item
would still have gone to the module constant.

That is why this runs a whole stage rather than reading a resolver's return
value. A resolver test passes on a tree where nothing calls the resolver.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, RecordedEndpoint, read_text
from pytest import MonkeyPatch

from idhazh import config
from idhazh.contracts.base import canonical_json
from idhazh.stages.work import stage_work

from ._builders import (
    REFUSED_COMPLETION,
    captured_article_fetch,
    isolate_ledgers,
    plan,
)

pytestmark = pytest.mark.slow


def a_config_pointing_at(root: Path, base_url: str) -> config.Settings:
    """A whole `config/` of the test's own, naming one server.

    The whole tree, because `config.load` reads five files and cross-checks two
    of them. The committed file is the starting point rather than the subject:
    what is asserted is the value written here, so this keeps testing the wiring
    on the day an operator points the run at their own server (`CLAUDE.md`
    section 13).
    """
    target = root / "config"
    shutil.copytree(CONFIG_DIR, target)
    payload = json.loads(read_text(target / "idhazh.json"))
    payload["model_server"]["base_url"] = base_url
    (target / "idhazh.json").write_text(canonical_json(payload), encoding="utf-8", newline="\n")
    return config.load(target)


def test_a_stage_nobody_gave_an_address_posts_where_the_config_says(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The oracle the eighteen default arguments defeated.

    `stage_work` is called with no `model_endpoint` at all, which is how every
    production caller calls it. The server it has to reach is on a port the
    operating system picked this second, so no constant in the tree can name it:
    the address can only have come from the config this test wrote.

    The server refuses every completion, because the words are not the subject.
    What is asserted is that the requests arrived at all - they cannot have,
    unless the address travelled from `config/` through the stage to the wire.
    """
    run_plan = plan()
    isolate_ledgers(tmp_path, monkeypatch)

    with RecordedEndpoint(503, REFUSED_COMPLETION.read_bytes()) as server:
        # The port is this second's, so the config is the only place it exists.
        settings = a_config_pointing_at(tmp_path, server.base_url)
        assert settings.app.model_server.base_url == server.base_url

        stage_work(
            run_plan,
            settings=settings,
            scorer=None,
            fetcher=captured_article_fetch,
        )

    assert server.served > 0, (
        "the stage posted nothing to the server the config named, so the address it "
        "used came from somewhere else"
    )


def test_moving_the_address_moves_where_the_stage_posts(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Two configs, two servers, and each one answers only its own run.

    The previous test cannot tell an address that came from config from one that
    happened to match. This one changes the value and nothing else, and the
    second server sees the traffic the first one did not.
    """
    run_plan = plan()
    isolate_ledgers(tmp_path, monkeypatch)

    with RecordedEndpoint(503, REFUSED_COMPLETION.read_bytes()) as named:
        with RecordedEndpoint(503, REFUSED_COMPLETION.read_bytes()) as ignored:
            settings = a_config_pointing_at(tmp_path, named.base_url)
            stage_work(
                run_plan,
                settings=settings,
                scorer=None,
                fetcher=captured_article_fetch,
            )
            assert named.served > 0, "the config named this server and it saw nothing"
            assert ignored.served == 0, "a server the config does not name was posted to"
