"""Old evidence paths become file names, and dependent identities follow in order."""

import pytest

from utilities.rekey_checkpoint_evidence import (
    Node,
    dependency_order,
    local_path_remains,
    portable_reference,
    rewrite,
    scrub_local_paths,
)


@pytest.mark.parametrize(
    ("path", "name"),
    [
        ("C:\\Users\\someone\\archive\\a.html", "a.html"),
        ("c:/Users/someone/archive/b.html", "b.html"),
        ("\\\\server\\share\\c.html", "c.html"),
        ("/home/someone/archive/d.html", "d.html"),
        ("file:///C:/Users/someone/archive/e.html", "e.html"),
    ],
)
def test_an_absolute_evidence_path_becomes_its_file_name(path: str, name: str) -> None:
    assert portable_reference(path) == name
    assert rewrite({"evidence_reference": path}, {}) == {"evidence_reference": name}
    assert local_path_remains({"source_checks": [{"evidence_reference": path}]})


def test_a_relative_reference_is_kept_and_named_identities_are_renamed() -> None:
    value = {"evidence_reference": "evidence/a.html", "batch_id": "old", "nested": ["old"]}
    assert rewrite(value, {"old": "new"}) == {
        "evidence_reference": "evidence/a.html",
        "batch_id": "new",
        "nested": ["new"],
    }
    assert not local_path_remains(value)


def test_a_local_path_in_prose_keeps_only_a_file_name() -> None:
    text = (
        "read C:\\Users\\someone\\Downloads\\Work\\a.html, then C:\\\\Users\\\\someone\\\\Work"
        " and C:\\Python314\\python.exe"
    )
    scrubbed = scrub_local_paths(text)
    assert scrubbed == "read a.html, then <local folder> and python.exe"
    assert not local_path_remains({"reason": scrubbed})
    assert local_path_remains({"reason": text})


def test_an_object_is_recomputed_after_the_objects_it_names() -> None:
    nodes = {
        "submission": Node("submission", "submission", {"batch_id": "batch"}, None, None),
        "batch": Node("batch", "batch", {"catalog_revision": "revision"}, None, None),
        "review": Node("catalog-review", "review", {}, 1, "revision"),
    }
    producer = {
        "submission": "submission",
        "batch": "batch",
        "review": "review",
        "revision": "review",
    }
    order = dependency_order(nodes, producer)
    assert order.index("review") < order.index("batch") < order.index("submission")


def test_circular_identities_are_refused() -> None:
    nodes = {
        "a": Node("submission", "a", {"supersedes": {"x": "b"}}, None, None),
        "b": Node("submission", "b", {"supersedes": {"x": "a"}}, None, None),
    }
    with pytest.raises(ValueError, match="cycle"):
        dependency_order(nodes, {"a": "a", "b": "b"})
