"""Does model reference validation preserve complete, safe file declarations?"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

from idhazh.contracts.base import SLUG_PATTERN
from utilities import measure_llm, model_refs

pytestmark = pytest.mark.workflow


def _an_entry(**extra: object) -> dict[str, object]:
    return {
        "repo": "publisher/Model-GGUF",
        "revision": "0" * 40,
        "file": "model-Q4_K_M.gguf",
        "sha256": "a" * 64,
        "id": "model-q4-k-m",
        "quantisation": "Q4_K_M",
        **extra,
    }


def _digest_of(*entries: Mapping[str, object]) -> str:
    return hashlib.sha256(
        b"\n".join(
            b"\t".join(
                str(entry[field]).encode("ascii")
                for field in ("repo", "revision", "file", "sha256")
            )
            for entry in entries
        )
    ).hexdigest()


def _a_config_tree(tmp_path: Path, summarize: dict[str, object]) -> Path:
    models = tmp_path / "config" / "models"
    models.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "idhazh.json").write_text(
        json.dumps({"models_file": "models/candidate.json"}) + "\n", encoding="utf-8"
    )
    (models / "candidate.json").write_text(
        json.dumps({"summarizer": summarize}) + "\n", encoding="utf-8"
    )
    return tmp_path / "config"


def _published(rows: list[str]) -> dict[str, str]:
    return dict(row.split("=", 1) for row in rows)


def test_a_draft_head_must_declare_its_complete_identity(tmp_path: Path) -> None:
    root = _a_config_tree(
        tmp_path,
        _an_entry(
            companion_files=[
                {
                    "repo": "publisher/head-GGUF",
                    "revision": "8c5a9e4fd5482e2be20fe0bf013b4c262a8f4265",
                    "file": "head.gguf",
                    "sha256": "",
                }
            ]
        ),
    )
    with pytest.raises(SystemExit, match=re.escape("summarizer.companion_files[0].sha256")):
        model_refs.pinned_rows(root)


def test_an_absent_draft_head_remains_valid(tmp_path: Path) -> None:
    assert model_refs.pinned_rows(_a_config_tree(tmp_path, _an_entry()))


def test_a_declared_draft_head_is_published_and_named_in_the_cache_key(
    tmp_path: Path,
) -> None:
    draft = {
        "repo": "publisher/Model-GGUF",
        "revision": "0" * 40,
        "file": "mtp-model.gguf",
        "sha256": "b" * 64,
    }
    entry = _an_entry(companion_files=[draft])
    published = _published(
        model_refs.trial_rows(_a_config_tree(tmp_path, entry), "", prefix="candidate_")
    )
    for field, value in draft.items():
        assert published[f"candidate_draft_{field}"] == value
    assert published["candidate_cache_key"] == _digest_of(_an_entry(), draft)


def test_the_key_moves_when_the_declared_set_moves(tmp_path: Path) -> None:
    alone = _published(
        model_refs.trial_rows(_a_config_tree(tmp_path / "alone", _an_entry()), "", prefix="")
    )
    draft = {
        "repo": "publisher/Model-GGUF",
        "revision": "0" * 40,
        "file": "mtp-model.gguf",
        "sha256": "b" * 64,
    }
    with_companion = _published(
        model_refs.trial_rows(
            _a_config_tree(
                tmp_path / "with-companion",
                _an_entry(companion_files=[draft]),
            ),
            "",
            prefix="",
        )
    )
    assert alone["cache_key"] != with_companion["cache_key"]
    assert alone["cache_key"] == _digest_of(_an_entry())
    assert len(alone["cache_key"]) == 64


def test_two_config_roots_holding_one_entry_render_one_key(tmp_path: Path) -> None:
    entry = _an_entry()
    one = _published(
        model_refs.trial_rows(_a_config_tree(tmp_path / "one", entry), "", prefix="")
    )
    two = _published(
        model_refs.trial_rows(_a_config_tree(tmp_path / "two", entry), "", prefix="")
    )
    assert one["cache_key"] == two["cache_key"] == _digest_of(entry)
    assert one["weights_path"] == two["weights_path"] == f"{model_refs.MODELS_DIR}/{entry['file']}"


def test_the_pinned_keys_and_trial_keys_do_not_collide(tmp_path: Path) -> None:
    root = _a_config_tree(tmp_path, _an_entry())
    pinned = set(_published(model_refs.pinned_rows(root)))
    trial = set(_published(model_refs.trial_rows(root, "", prefix="")))
    assert pinned
    assert pinned & trial == set()


def test_the_reader_and_measurement_module_use_the_same_validation_grammar() -> None:
    for name in ("REPO_RE", "REVISION_RE", "GGUF_RE"):
        here = getattr(model_refs, name)
        there = getattr(measure_llm, name)
        assert here.pattern == there.pattern
        assert here.flags == there.flags
    assert model_refs.SLUG_RE.pattern == SLUG_PATTERN


@pytest.mark.parametrize(
    ("field", "value", "says"),
    [
        ("file", "../../etc/passwd.gguf", "not a .gguf filename"),
        ("file", "x$(id).gguf", "not a .gguf filename"),
        ("file", "model.txt", "not a .gguf filename"),
        ("repo", "publisher/Model GGUF", "not a Hugging Face repository"),
        ("revision", "main", "not a 40-character commit"),
        ("sha256", "", "not a 64-character digest"),
        ("id", "Model_Q4", "not a slug"),
        ("quantisation", "Q4 K M", "not a quantisation"),
        ("byte_count", "0", "not a count of bytes"),
    ],
)
def test_invalid_model_values_are_refused(
    field: str, value: str, says: str, tmp_path: Path
) -> None:
    root = _a_config_tree(tmp_path, _an_entry(**{field: value}))
    with pytest.raises(SystemExit) as refused:
        model_refs.trial_rows(root, "", prefix="")
    said = str(refused.value)
    assert "models/candidate.json" in said
    assert f"summarizer.{field}:" in said
    assert says in said
    assert repr(value) in said


@pytest.mark.parametrize("filename", ["mmproj-model-f16", "MTP/mmproj-model-f16"])
def test_a_companion_preserves_safe_segments_without_a_suffix_rule(
    tmp_path: Path, filename: str
) -> None:
    """A companion may be a projector, an adapter or a vocoder, so it carries no suffix.
    Directory segments are preserved; traversal cannot escape `backend/models`.
    """
    projector = {
        "repo": "publisher/Model-GGUF",
        "revision": "0" * 40,
        "file": filename,
        "sha256": "b" * 64,
        "flag": "-md",
    }
    entry = _an_entry(byte_count=4215695776, companion_files=[projector])
    files = model_refs.list_model_files(_a_config_tree(tmp_path / "good", entry))
    assert [one.file for one in files] == ["model-Q4_K_M.gguf", filename]
    assert files[1].landed_path == f"{model_refs.MODELS_DIR}/{filename}"
    assert files[1].flag == "-md", "one leading dash is llama.cpp's short draft-model flag"
    assert files[0].flag == "", "the weights are named by the launcher, not by config"
    assert files[0].byte_count == "4215695776", "the declared size, as the string its rule reads"
    assert files[1].byte_count == "", "a companion that declares no size skips the cross-check"
    escaping = dict(projector, file="../../x.gguf")
    with pytest.raises(SystemExit, match=re.escape("not a safe relative POSIX path")):
        model_refs.list_model_files(
            _a_config_tree(tmp_path / "bad", _an_entry(companion_files=[escaping]))
        )


def test_two_declared_files_cannot_land_on_one_name(tmp_path: Path) -> None:
    twin = {
        "repo": "publisher/Model-GGUF",
        "revision": "0" * 40,
        "file": "model-Q4_K_M.gguf",
        "sha256": "b" * 64,
    }
    root = _a_config_tree(tmp_path, _an_entry(companion_files=[twin]))
    with pytest.raises(SystemExit) as refused:
        model_refs.list_model_files(root)
    assert "two files land on one name" in str(refused.value)
    assert "summarizer.file 'model-Q4_K_M.gguf'" in str(refused.value)
    assert "summarizer.companion_files[0].file 'model-Q4_K_M.gguf'" in str(refused.value)


def test_a_second_companion_is_not_dropped(tmp_path: Path) -> None:
    companions = [
        {
            "repo": "publisher/Model-GGUF",
            "revision": "0" * 40,
            "file": f"companion-{index}.gguf",
            "sha256": f"{index}" * 64,
        }
        for index in (1, 2)
    ]
    root = _a_config_tree(tmp_path, _an_entry(companion_files=companions))
    assert len(model_refs.list_model_files(root)) == 3
    with pytest.raises(SystemExit) as refused:
        model_refs.trial_rows(root, "", prefix="")
    assert "(2)" in str(refused.value)
    assert "companion-1.gguf" in str(refused.value)
    assert "companion-2.gguf" in str(refused.value)


def test_a_key_over_seven_files_stays_within_the_cache_key_limit(tmp_path: Path) -> None:
    companions = [
        {
            "repo": "publisher/Model-GGUF",
            "revision": "0" * 40,
            "file": f"companion-{index}.gguf",
            "sha256": f"{index}" * 64,
        }
        for index in range(1, 8)
    ]
    files = model_refs.list_model_files(
        _a_config_tree(tmp_path, _an_entry(companion_files=companions))
    )
    assert len(files) == 8
    key = _digest_of(_an_entry(), *companions)
    assert len(key) == 64
    assert key != _digest_of(_an_entry(), *companions[:6])
