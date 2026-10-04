"""Do build inventories count every deployed byte without substituting source totals?"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from idhazh import assemble, publication, site_weight
from idhazh.build_publication import inventory_path, read_build_inventory, record_build_inventory
from idhazh.contracts.publication_inventory import PublicationInventory
from idhazh.stages.common import published_days


def write_tree(root: Path, files: dict[str, bytes]) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def test_every_deployed_file_counts_but_the_external_inventory_does_not(tmp_path: Path) -> None:
    tree = tmp_path / "build"
    files = {
        "index.html": b"<h1>A generated page</h1>\n",
        "_app/immutable/chunks/main.js": b"export const ready = true;\n",
        "state/compact/item-health/daily/2026/10/03.parquet": b"copied ledger bytes",
        "state/compact/item-health/index.json": b'{"entries":[]}',
        "digest/2026/10/03/digest.json": json.dumps(
            {"date": "2026-10-03", "items": [{"item_id": "ai-01"}, {"item_id": "ai-02"}]}
        ).encode(),
    }
    write_tree(tree, files)
    inventory = record_build_inventory(tree)
    assert inventory_path(tree).parent == tree.parent
    assert not (tree / "publication.json").exists()
    assert inventory.total_bytes == sum(map(len, files.values()))
    assert inventory.total_items == 2
    assert {entry.path for entry in inventory.entries} == set(files)
    assert read_build_inventory(tree) == inventory
    measured = site_weight.measure(tree)
    assert measured.bytes_used == sum(map(len, files.values()))
    assert measured.files == len(files)
    assert measured.published_items == site_weight.count_published_items(tree) == 2
    assert measured.by_directory["state"] == sum(
        len(content) for name, content in files.items() if name.startswith("state/")
    )
    # Readers ask the inventory, not the digest payload again.
    (tree / "digest/2026/10/03/digest.json").write_bytes(b"not JSON")
    assert site_weight.measure(tree) == measured
    assert site_weight.count_published_items(tree) == 2


@pytest.mark.parametrize("reader", [site_weight.measure, site_weight.count_published_items])
def test_missing_and_invalid_build_inventories_fail(
    tmp_path: Path, reader: Callable[[Path], object]
) -> None:
    tree = tmp_path / "build"
    write_tree(tree, {"index.html": b"an existing output is not an inventory"})
    with pytest.raises(FileNotFoundError, match="run npm run build"):
        reader(tree)
    inventory_path(tree).write_text(
        json.dumps({"version": PublicationInventory.schema_version()}), encoding="utf-8"
    )
    with pytest.raises(ValidationError):
        reader(tree)


@pytest.mark.parametrize(
    "content",
    [b"not JSON", b'{"date":"2026-10-02","items":[]}', b'{"date":"2026-10-03"}'],
)
def test_invalid_built_digests_do_not_write_a_success_inventory(
    tmp_path: Path, content: bytes
) -> None:
    tree = tmp_path / "build"
    write_tree(tree, {"digest/2026/10/03/digest.json": content})
    with pytest.raises(ValueError):
        record_build_inventory(tree)
    assert not inventory_path(tree).exists()


def test_source_consumers_read_only_source_inventory_names_and_counts(tmp_path: Path) -> None:
    public = tmp_path / "public"
    digest = public / "digest"
    files = {
        "digest/2026/10/03/digest.json": b"a named payload",
        "digest/2026/10/02/digest.json": b"another named payload",
        "digest/2026/10/03/ai-01.json": b"named visual",
        "telemetry/2026-10.csv": b"not digest bytes",
    }
    write_tree(public, files)
    publication.initialize_inventory(
        public,
        seed=PublicationInventory(version=PublicationInventory.schema_version(), dates=[]),
    )
    publication.record_files(
        public, dates=["2026-10-03", "2026-10-02"], paths=files,
        item_counts={
            "digest/2026/10/03/digest.json": 0,
            "digest/2026/10/02/digest.json": 0,
        },
    )
    write_tree(public, {"digest/2000/01/01/digest.json": b"unlisted stray"})
    assert assemble.site_size(digest) == (
        sum(len(content) for name, content in files.items() if name.startswith("digest/")), 3
    )
    assert published_days(digest) == [
        digest / "2026/10/02/digest.json", digest / "2026/10/03/digest.json",
    ]
    # Missing named payloads stay named, so the publication gate reports them.
    (digest / "2026/10/02/digest.json").unlink()
    assert len(published_days(digest)) == 2


def test_missing_source_inventory_does_not_discover_existing_days(tmp_path: Path) -> None:
    public = tmp_path / "public"
    write_tree(public, {"digest/2026/10/03/digest.json": b"an unregistered day"})
    with pytest.raises(FileNotFoundError, match="initialize"):
        assemble.site_size(public / "digest")
    with pytest.raises(FileNotFoundError, match="initialize"):
        published_days(public / "digest")
