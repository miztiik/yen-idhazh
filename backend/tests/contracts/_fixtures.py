"""Builders and committed-file readers more than one contract module needs."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Final

from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text

from idhazh.contracts import canonical_json
from idhazh.contracts.app_config import AppConfig, ModelsConfig
from idhazh.contracts.base import Contract
from idhazh.contracts.export import CONTRACTS
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import Watchlist

BY_STEM: dict[str, type[Contract]] = {c.__schema_stem__: c for c in CONTRACTS}

CONFIG_FILES: dict[str, type[Contract]] = {
    "idhazh.json": AppConfig,
    "sources.json": Sources,
    "taxonomy.json": Taxonomy,
    "watchlist.json": Watchlist,
}

#: A digest, at the two widths this project ever writes one: a sha256 is 64 hex
#: characters and a truncated one is 32. The guard used to read `[0-9a-f]{16,}`,
#: which an item id can satisfy by accident - sixteen Crockford base32 symbols
#: all landing inside `[0-9a-f]` is about one item in 65,536, so a width-agnostic
#: guard goes red on a day nobody touched the code and there is nothing to
#: bisect. Matching the width says what the rule always meant.
HEX_DIGEST = re.compile(r"(?<![0-9a-z])(?:[0-9a-f]{64}|[0-9a-f]{32})(?![0-9a-z])")

#: Four real `GET /metrics` bodies, one per work shard of run `2026-08-26-5`,
#: pulled from that run's `runtime-log-*` artifacts before they expired. Real
#: captures rather than hand-written text (Guardrail #7): the upstream README at tag
#: b10598 lists neither `prompt_tokens_cached_total` nor the wording that says
#: what `prompt_tokens_total` counts, so only the binary's own output settles it.
METRICS_CAPTURES = sorted((FIXTURES_DIR / "runtime").glob("2026-08-26-5-shard-*.prom"))

#: The memory sampler's own files and the head of llama-server's own log, one
#: pair per work shard of run `2026-08-29-3`, pulled from that run's
#: `runtime-log-*` artifacts before they expired. Real captures for the same
#: reason the metrics bodies are: the timestamp llama.cpp stamps a log line with
#: is four dot-separated numbers whose units no page states, and only a real
#: capture of a job whose length is known settles which is which.
RSS_CAPTURES = sorted((FIXTURES_DIR / "runtime").glob("2026-08-29-3-shard-*.rss-samples.tsv"))

SERVER_LOG_CAPTURES = sorted((FIXTURES_DIR / "runtime").glob("2026-08-29-3-shard-*.server-head.txt"))

#: One real `/proc/stat` pair, twenty seconds apart, captured on a GitHub-hosted
#: `ubuntu-latest` runner on 2026-08-30. The gap is what makes it an oracle: the
#: tick delta has to reproduce twenty seconds of four processors at 100 Hz, and
#: no hand-written file can be checked that way.
PROC_STAT_AT_START = FIXTURES_DIR / "runtime" / "2026-08-30-probe-proc-stat-at-start.txt"

PROC_STAT_AT_END = FIXTURES_DIR / "runtime" / "2026-08-30-probe-proc-stat-at-end.txt"

#: What the probe slept for, what the runner reported to `nproc`, and the
#: kernel's tick rate. Guardrail #2 fixes the second at 4.
PROBE_SECONDS = 20

PROBE_PROCESSORS = 4

USER_HZ = 100

#: The two pages that spell the item-health failure vocabulary out by hand.
DOC_ITEM_HEALTH = REPO_ROOT / "docs" / "architecture" / "sources" / "item-health.md"

DOC_ONE_URL = REPO_ROOT / "docs" / "how-to" / "troubleshoot-one-url.md"

def backticked(text: str) -> set[str]:
    return set(re.findall(r"`([a-z_]+)`", text))

def paragraph_after(text: str, lead: str) -> str:
    _, found, rest = text.partition(lead)
    assert found, f"the page no longer says {lead!r}"
    return rest.split("\n\n", 2)[1]

# The one `app-config` fixture. Its name is its invariant: every knob in it holds
# a value the committed `config/idhazh.json` does not, so a reader that ignored
# the file and fell back to a default would fail rather than pass.
APP_CONFIG_EVERY_KNOB_DIFFERS: Final = (
    CONTRACT_FIXTURES_DIR / "app-config" / "every-knob-differs-from-the-committed-config.json"
)

def committed_models_raw() -> dict[str, Any]:
    """The active model's file as bytes on disk, found by following the pointer.

    Never by naming the file. `config/idhazh.json` says which model is active
    and a test that spelled the filename instead would keep passing on the day
    somebody pointed the pointer somewhere else.
    """
    app = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    payload: dict[str, Any] = json.loads(read_text(CONFIG_DIR / app.models_file))
    return payload

def committed_models() -> ModelsConfig:
    """The same file, validated - what `config.load` puts on `Settings.models`."""
    return ModelsConfig.model_validate(committed_models_raw())

def fixture_paths() -> list[Path]:
    return sorted(CONTRACT_FIXTURES_DIR.glob("*/*.json"))

def fixture_id(path: Path) -> str:
    return f"{path.parent.name}/{path.stem}"

def load(path: Path) -> Contract:
    return BY_STEM[path.parent.name].from_json(read_text(path))

def copy_config(root: Path, *, models: dict[str, Any] | None = None) -> str:
    """A whole `config/` in a temp directory, with the active model file replaced.

    The whole tree, because `config.load` reads five files and cross-checks two
    of them - a test that wrote only the file it cares about would be driving a
    config that cannot load for a reason it did not mean to test.

    Returns the pointer the copy carries, which is the path a refusal has to
    name and the value a swap has to move.
    """
    target = root / "config"
    shutil.copytree(CONFIG_DIR, target)
    pointer = str(AppConfig.from_json(read_text(target / "idhazh.json")).models_file)
    if models is not None:
        (target / pointer).write_text(canonical_json(models), encoding="utf-8", newline="\n")
    return pointer

def entry_with(**turns: Any) -> dict[str, Any]:
    """The committed entry with its turn envelope edited, as raw JSON.

    Built off the committed file rather than written out here, so a required
    field added to the entry later fails these tests at the edit that added it
    rather than leaving them asserting against a shape nothing declares.
    """
    payload = committed_models_raw()
    payload["summarize"]["turns"] |= turns
    return payload

def swapped_summarizer() -> dict[str, Any]:
    """The committed model file with `summarize` pointed at other weights.

    Every field an operator edits to swap a model IN PLACE, and nothing else.
    Since 2026-09-14 that is no longer the swap an operator makes - a swap is a
    second file and one pointer line - but it is still the edit this refusal
    exists to catch, because it is what somebody does when they mean to move
    fast in the file they already have open.
    """
    raw = committed_models_raw()
    raw["summarize"] |= {
        "id": "some-other-model-q4-k-m",
        "repo": "someone/Other-GGUF",
        "file": "Other-Q4_K_M.gguf",
        "revision": "f" * 40,
        "sha256": "1" * 64,
        "hf_base_repo": None,
    }
    return raw

def desk(**overrides: Any) -> dict[str, Any]:
    """One vertical of a plan, spelled the way an earlier build wrote it."""
    return {"id": "ai", "considered": 40, "planned": 5, "live_feeds": 3, **overrides}

def taxonomy_fixture(stem: str) -> Taxonomy:
    """One of the two fixture vocabularies the definition oracle is driven from."""
    return Taxonomy.from_json(read_text(FIXTURES_DIR / "taxonomy" / f"{stem}.json"))

def mutate(path: Path, **changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(read_text(path))
    payload.update(changes)
    return payload

#: The five the planning step computes and the day payload started carrying on
#: 2026-08-31. Every day published before that omits all five.
RANKING_SIGNAL = ("carried_by", "watchlist_hit", "on_front_page", "rank_score", "time_source")

def a_day_missing(names: tuple[str, ...], where: str = "items") -> tuple[str, int]:
    """The committed-day fixture with `names` removed from every `where` entry.

    The read-side migration each of these checks is a property of one payload
    (`CLAUDE.md` section 11), and the committed tree was parsed once per
    published day to re-ask it. Worse, each of those walks counted how many
    entries still LACK the field and failed at zero - a fuse timed to the day the
    last unmigrated payload ages out of retention, which is a date rather than a
    change. Removing the keys here cannot age out.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    stripped = 0
    for entry in payload[where]:
        for name in names:
            entry.pop(name, None)
        stripped += 1
    return json.dumps(payload), stripped
