from pathlib import Path

import pytest

from utilities.measure_llm import (
    ModelRef,
    RemoteFile,
    bench_command,
    display_path,
    download,
    parse_model_refs,
    parse_positive_csv,
    remote_file_from_tree,
    sha256,
)


def test_model_refs_are_validated_before_they_become_paths_or_urls() -> None:
    refs = parse_model_refs(
        "Qwen/Qwen3-8B-GGUF@" + "a" * 40 + ":Qwen3-8B-Q4_K_M.gguf,"
        "unsloth/Qwen3.5-9B-GGUF@" + "b" * 40 + ":Qwen3.5-9B-Q4_K_M.gguf"
    )

    assert refs == [
        ModelRef("Qwen/Qwen3-8B-GGUF", "a" * 40, "Qwen3-8B-Q4_K_M.gguf"),
        ModelRef("unsloth/Qwen3.5-9B-GGUF", "b" * 40, "Qwen3.5-9B-Q4_K_M.gguf"),
    ]


def test_a_reference_reaches_hugging_face_only_at_a_pinned_commit() -> None:
    """A branch is re-pointed on every upload, so a bench that names one cannot
    be repeated: the bytes move and no recorded number says they did (Rule #10).
    """
    ref = ModelRef("owner/repo", "c" * 40, "model.gguf")

    assert ref.url == f"https://huggingface.co/owner/repo/resolve/{'c' * 40}/model.gguf"
    assert ref.tree_url == f"https://huggingface.co/api/models/owner/repo/tree/{'c' * 40}"
    assert "/main" not in ref.url + ref.tree_url


@pytest.mark.parametrize(
    "value",
    [
        "../owner/repo@" + "a" * 40 + ":model.gguf",
        "owner/repo@" + "a" * 40 + ":../model.gguf",
        "owner/repo@" + "a" * 40 + ":model.bin",
        "owner/repo@" + "a" * 40 + ":model.gguf,other/repo@" + "b" * 40 + ":model.gguf",
        "owner/repo@" + "a" * 40,
        "owner/repo:model.gguf",
        "owner/repo@main:model.gguf",
        "owner/repo@" + "a" * 39 + ":model.gguf",
    ],
)
def test_model_refs_reject_unsafe_or_ambiguous_values(value: str) -> None:
    with pytest.raises(ValueError):
        parse_model_refs(value)


def test_positive_csv_is_unique_and_sorted() -> None:
    assert parse_positive_csv("8,4,4,1", name="threads") == [1, 4, 8]


@pytest.mark.parametrize("value", ["", "4,-1", "4,0", "4,eight"])
def test_positive_csv_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        parse_positive_csv(value, name="threads")


def test_bench_command_uses_exact_paths_and_thread_count() -> None:
    command = bench_command(
        binary=Path("backend/bin/llama-bench"),
        model=Path("backend/models/model.gguf"),
        prompt_tokens=[730, 1800, 4850],
        generation_tokens=250,
        threads=8,
        repeats=3,
    )

    assert command == [
        str(Path("backend/bin/llama-bench")),
        "-m",
        str(Path("backend/models/model.gguf")),
        "-p",
        "730,1800,4850",
        "-n",
        "250",
        "-t",
        "8",
        "-r",
        "3",
        "-o",
        "json",
    ]


def test_sha256_reads_the_actual_file(tmp_path: Path) -> None:
    file = tmp_path / "model.gguf"
    file.write_bytes(b"exact model bytes")

    assert sha256(file) == "f8ee3ff497d6e851aaaf1be3c1b7013665dc4ff1288dfb04bda5ce98645d4043"


def test_external_paths_are_reduced_before_they_leave_the_process(tmp_path: Path) -> None:
    assert display_path(tmp_path / "model.gguf") == "model.gguf"


def test_remote_file_uses_the_lfs_identity() -> None:
    ref = ModelRef("owner/repo", "a" * 40, "model.gguf")

    assert remote_file_from_tree(
        ref,
        [
            {
                "path": "model.gguf",
                "lfs": {
                    "oid": "f8ee3ff497d6e851aaaf1be3c1b7013665dc4ff1288dfb04bda5ce98645d4043",
                    "size": 17,
                },
            }
        ],
    ) == RemoteFile(
        bytes=17,
        sha256="f8ee3ff497d6e851aaaf1be3c1b7013665dc4ff1288dfb04bda5ce98645d4043",
    )


def test_existing_file_must_match_the_requested_remote_identity(tmp_path: Path) -> None:
    file = tmp_path / "model.gguf"
    file.write_bytes(b"not the requested model")

    with pytest.raises(ValueError, match="existing file does not match"):
        download(
            ModelRef("owner/repo", "a" * 40, "model.gguf"),
            RemoteFile(bytes=17, sha256="0" * 64),
            tmp_path,
        )
