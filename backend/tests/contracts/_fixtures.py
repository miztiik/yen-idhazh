"""Builders and committed-file readers more than one contract module needs."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Final

from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text

from idhazh.contracts import CONTRACTS, canonical_json
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.appearance_config import AppearanceConfig
from idhazh.contracts.base import Contract
from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.contracts.pipeline_tests import PipelineTestsConfig
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import Watchlist

BY_STEM: dict[str, type[Contract]] = {c.__schema_stem__: c for c in CONTRACTS}

CONFIG_FILES: dict[str, type[Contract]] = {
    "appearance.json": AppearanceConfig,
    "idhazh.json": AppConfig,
    "pipeline-tests.json": PipelineTestsConfig,
    "sources.json": Sources,
    "taxonomy.json": Taxonomy,
    "watchlist.json": Watchlist,
}

#: The three blocks `AppearanceConfig` re-exposes, as (the key
#: `config/idhazh.json` still carries, the key `config/appearance.json` carries).
MOVED_BLOCKS = (("ui", "digest"), ("console", "console"), ("assist", "assist"))

#: Keys `config/idhazh.json` owns although they sit on a moved model, with the
#: reason each one is not the appearance file's to declare. All four are on
#: `AssistConfig` and none is drawn, so the frontend's own `AssistConfig`
#: interface declares none of them. `recall_min` and `eval_corpus_through` are
#: the retrieval gate's inputs, read by `backend/tests/test_retrieval_eval.py`.
#: `max_tokens` and `min_readable_letter_share` are the encoder's, read by
#: `backend/idhazh/embed.py`; the appearance file carried a copy of each with
#: the same value, which was the middle merge layer doing its job until the
#: keep-list stopped the page receiving either - and a copy nothing reads is
#: where `recall_min` was an hour earlier, so both were deleted (2026-09-05).
PIPELINE_OWNED = {
    "recall_min",
    "eval_corpus_through",
    "max_tokens",
    "min_readable_letter_share",
    # Build-owned rather than pipeline-owned, and on this list for the same
    # reason: the published surface does not draw any of them, so
    # `config/appearance.json` has nothing to say about them. `vite.config.ts`
    # and `svelte.config.js` read them from `config/idhazh.json` at build time
    # and put what a tab needs into the bundle, so they never reach an
    # appearance file or a prerendered document at all.
    "model_base_url",
    "model_cdn_origins",
    "model_digests",
    "model_fetch_deadline_ms",
    "model_revision",
}

#: Dotted paths a config file's model declares but the file must NOT name,
#: because another file owns them. Naming a knob in two files is how one of them
#: goes silent: the frontend merges the appearance block over the legacy one, so
#: the loser is edited and nothing happens (`test_appearance_config.py`).
#:
#: `config/idhazh.json` keeps the three moved blocks only as the read-side
#: migration's middle layer - a file written before 2026-08-29 still resolves to
#: what it used to - so it names what it already named and gains nothing.
CONFIG_NOT_OWNED: dict[str, frozenset[str]] = {
    "idhazh.json": frozenset(legacy for legacy, _ in MOVED_BLOCKS),
    "appearance.json": frozenset(f"assist.{key}" for key in PIPELINE_OWNED),
}


#: A digest, at the two widths this project ever writes one: a sha256 is 64 hex
#: characters and a truncated one is 32. The guard used to read `[0-9a-f]{16,}`,
#: which an item id can satisfy by accident - sixteen Crockford base32 symbols
#: all landing inside `[0-9a-f]` is about one item in 65,536, so a width-agnostic
#: guard goes red on a day nobody touched the code and there is nothing to
#: bisect. Matching the width says what the rule always meant.
HEX_DIGEST = re.compile(r"(?<![0-9a-z])(?:[0-9a-f]{64}|[0-9a-f]{32})(?![0-9a-z])")


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


def entry_with(**fields: Any) -> dict[str, Any]:
    """The committed entry with some of its own fields edited, as raw JSON.

    Built off the committed file rather than written out here, so a required
    field added to the entry later fails these tests at the edit that added it
    rather than leaving them asserting against a shape nothing declares.
    """
    payload = committed_models_raw()
    payload["summarizer"] |= fields
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
    raw["summarizer"] |= {
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
