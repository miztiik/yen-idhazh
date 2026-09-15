import re
from pathlib import Path

import pytest

from utilities.measure_llm import (
    DOSSIER_SECTIONS,
    GIB,
    IDENTITY_FIELDS,
    ITEM_SECTION,
    MEMORY_SECTION,
    MODEL_LOAD_SECTION,
    THROUGHPUT_SECTION,
    BenchReadings,
    ModelRef,
    Reading,
    RemoteFile,
    bench_command,
    check_declared_digest,
    compare_readings,
    display_path,
    download,
    parse_model_refs,
    parse_positive_csv,
    raw_readings,
    remote_file_from_tree,
    render_dossier,
    server_readings,
    sha256,
    within_spread,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
#: The page this emitter fills. One committed file, read once, so the check
#: costs the same whatever the archive does (Guardrail #12).
INCUMBENT_DOSSIER = REPO_ROOT / "docs" / "reference" / "models" / "qwen3.5-9b-q4km.md"


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
    be repeated: the bytes move and no recorded number says they did (Guardrail #10).
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


def test_the_bench_refuses_bytes_the_dispatch_did_not_declare() -> None:
    """The half `download` cannot cover: what the Hub holds against what was asked for.

    `download` compares what arrived with what the Hub advertised, so a repinned
    reference passes it - the bytes and the advertisement agree, and both are
    the wrong model. A benchmark filed under a model that never ran is worse
    than no benchmark (Guardrail #10).
    """
    ref = ModelRef("owner/repo", "a" * 40, "model.gguf")

    assert check_declared_digest(ref, RemoteFile(bytes=17, sha256="b" * 64), "b" * 64) is None

    refusal = check_declared_digest(ref, RemoteFile(bytes=17, sha256="c" * 64), "b" * 64)
    assert refusal is not None
    assert "c" * 64 in refusal and "b" * 64 in refusal


def _bench_rows(*, threads: int = 4) -> list[dict[str, object]]:
    """One `llama-bench -o json` print, built rather than recorded.

    Built, because the shape that has to hold is a prefill curve with a decode
    row in the same list, and a capture would only ever carry the lengths this
    project happens to sweep today.
    """
    common: dict[str, object] = {
        "n_threads": threads,
        "build_number": 10598,
        "build_commit": "56db501e7",
        "cpu_info": "AMD EPYC 9V74 80-Core Processor",
        "model_filename": "Qwen3.5-9B-Q4_K_M.gguf",
        "samples_ts": [10.13, 10.14, 10.15],
    }
    return [
        {**common, "n_prompt": 730, "n_gen": 0, "avg_ts": 10.14, "stddev_ts": 0.01},
        {**common, "n_prompt": 1800, "n_gen": 0, "avg_ts": 10.06, "stddev_ts": 0.01},
        {**common, "n_prompt": 4850, "n_gen": 0, "avg_ts": 9.84, "stddev_ts": 0.01},
        {**common, "n_prompt": 0, "n_gen": 250, "avg_ts": 6.01, "stddev_ts": 0.11},
    ]


def _runtime_summary(*, startups: tuple[float, ...] = (4158.0, 3789.5, 3820.3)) -> dict[str, object]:
    """What the server case writes: one entry per repeat, each with its own samples."""
    results: list[dict[str, object]] = []
    for index, startup in enumerate(startups, start=1):
        results.append(
            {
                "label": "baseline",
                "repeat": index,
                "startup_ms": startup,
                "server_rss_samples": [
                    {"VmRSS": "12000000 kB", "VmHWM": "12000000 kB"},
                    {"VmRSS": "13500000 kB", "VmHWM": f"{13_000_000 + index * 100_000} kB"},
                ],
                "cgroup_memory_peak_bytes": str(15_000_000_000 + index * 100_000_000),
                "per_item": [
                    {"summarize_ms": value * 1000 + index}
                    for value in (60.0, 90.0, 114.6, 200.0, 800.9)
                ],
            }
        )
    return {"repeats": len(startups), "results": results}


def test_prefill_is_read_at_every_length_and_decode_exactly_once() -> None:
    """One tokens-per-second constant is wrong at both ends, so the page carries a curve."""
    readings = raw_readings(
        _bench_rows(),
        prompt_tokens=[730, 1800, 4850],
        generation_tokens=250,
        threads=4,
        repeats=3,
    )

    assert sorted(readings) == ["decode_250", "prefill_1800", "prefill_4850", "prefill_730"]
    assert readings["prefill_730"] == Reading(
        section=THROUGHPUT_SECTION,
        label="Prefill, 730-token prompt",
        value=10.14,
        spread=0.01,
        unit="tok/s",
        repeats=3,
    )
    assert readings["decode_250"].value == 6.01
    assert readings["decode_250"].label == "Decode, 250 tokens"
    assert {reading.section for reading in readings.values()} == {THROUGHPUT_SECTION}


def test_a_bench_row_at_another_thread_count_is_not_this_reading() -> None:
    with pytest.raises(ValueError, match="no rows at 8 threads"):
        raw_readings(
            _bench_rows(threads=4),
            prompt_tokens=[730],
            generation_tokens=250,
            threads=8,
            repeats=3,
        )


def test_the_cold_model_load_is_the_first_start_and_the_warm_one_is_the_rest() -> None:
    """Nothing in the job had read those weights before the first server start.

    So the first start faults every page in off disk and the ones after it do
    not. That is the shape of the first run after a model swap, on every shard
    at once, and averaging the two would hide it.
    """
    readings = server_readings(_runtime_summary(startups=(4158.0, 3789.5, 3820.3)))

    assert readings["model_load_cold"].value == 4158.0
    assert readings["model_load_cold"].repeats == 1
    assert readings["model_load_cold"].spread == 0.0
    assert readings["model_load_warm"].value == pytest.approx(3804.9)
    assert readings["model_load_warm"].spread == pytest.approx(30.8)
    assert readings["model_load_warm"].repeats == 2

    assert readings["server_rss_peak"].unit == "GiB"
    assert readings["server_rss_peak"].value == pytest.approx(13_200_000 * 1024 / GIB)
    assert readings["tree_rss_peak"].value == pytest.approx(15_200_000_000 / GIB)
    assert readings["summarize_median"].value == pytest.approx(114.602)
    assert readings["summarize_longest"].value == pytest.approx(800.902)
    assert {reading.section for reading in readings.values()} == {
        MEMORY_SECTION,
        MODEL_LOAD_SECTION,
        ITEM_SECTION,
    }


def test_one_repeat_cannot_tell_a_cold_start_from_a_warm_one() -> None:
    with pytest.raises(ValueError, match="under two"):
        server_readings(_runtime_summary(startups=(4158.0,)))


def _page(
    *, offset: float = 0.0, repeats: int = 3, prompt: int = 730, spread: float = 1.0
) -> BenchReadings:
    return BenchReadings(
        identity={
            "id": f"model-{offset:g}",
            "repo": "unsloth/Qwen3.5-9B-GGUF",
            "revision": "a" * 40,
            "file": "Qwen3.5-9B-Q4_K_M.gguf",
            "quantisation": "Q4_K_M",
            "sha256": "b" * 64,
            "bytes": "5,683,073,024",
        },
        context={
            "measured_at": "2026-09-14T04:05:06Z",
            "runner": "ubuntu-latest",
            "cpu": "AMD EPYC 9V74 80-Core Processor",
            "threads": "4",
            "llama_build": "b10598",
            "llama_commit": "56db501e7",
            "bench_repeats": str(repeats),
            "server_repeats": str(repeats),
            "corpus": "Five articles",
        },
        readings={
            f"prefill_{prompt}": Reading(
                THROUGHPUT_SECTION,
                f"Prefill, {prompt:,}-token prompt",
                10.14 + offset,
                0.01 * spread,
                "tok/s",
                repeats,
            ),
            "model_load_cold": Reading(
                MODEL_LOAD_SECTION,
                "Cold, the first start of the job",
                4158.0 + offset,
                0.0,
                "ms",
                1,
            ),
            "summarize_median": Reading(
                ITEM_SECTION,
                "A summarize call, median",
                114.6 + offset,
                0.5 * spread,
                "s",
                repeats,
            ),
        },
    )


def test_the_emitted_body_is_the_shape_of_the_page_it_fills() -> None:
    """Every heading the emitter writes is a heading the committed dossier carries.

    The point of the case is that adopting a model is a paste rather than a
    transcription, and a body whose headings do not match the page it replaces
    is a transcription with extra steps.
    """
    committed = INCUMBENT_DOSSIER.read_text(encoding="utf-8").splitlines()
    headings = {line.strip() for line in committed if line.startswith("#")}
    assert set(DOSSIER_SECTIONS) <= headings, "the emitter writes a heading the page does not have"

    body = render_dossier(_page())

    assert body.splitlines()[0].startswith("# ")
    assert "**Last Updated**: 2026-09-14" in body
    assert "## Identity" in body
    for _, title in IDENTITY_FIELDS:
        assert f"| {title} |" in body
    for section in (THROUGHPUT_SECTION, MODEL_LOAD_SECTION, ITEM_SECTION):
        assert f"\n{section}\n" in body
    assert MEMORY_SECTION not in body, "a section with no reading prints no empty table"
    assert "n = 1, spread unavailable" in body, "a reading taken once says so"
    assert "56db501e7" in body and "AMD EPYC 9V74 80-Core Processor" in body


def test_the_emitter_invents_no_number() -> None:
    """Two renders of two different reading sets share no number in any reading row.

    A hardcoded figure would appear in both. This is the check that a page
    "already filled in" is filled in from the measurement and not from the
    emitter's own memory of what the last model read.
    """
    first = render_dossier(_page(offset=0.0, repeats=3, prompt=730, spread=1.0))
    second = render_dossier(_page(offset=7.0, repeats=5, prompt=999, spread=3.0))

    def numbers(body: str) -> set[str]:
        """Every number in a reading's own label and value, and nothing else.

        Not the run count: two readings taken once both say `n = 1`, and that is
        the reading talking, not the emitter.
        """
        found: set[str] = set()
        section = ""
        for line in body.splitlines():
            if line.startswith("#"):
                section = line.strip()
                continue
            if section not in DOSSIER_SECTIONS or not line.startswith("| ") or "---" in line:
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            found.update(re.findall(r"[0-9][0-9,.]*", " ".join(cells[:2])))
        return found

    shared = numbers(first) & numbers(second)
    assert not shared, f"the emitter prints these whatever it measured: {sorted(shared)}"


def test_the_emitter_refuses_a_page_with_a_blank_in_it() -> None:
    """A page that invented a number would be worse than a page that refused."""
    page = _page()
    page.identity.pop("quantisation")
    page.context.pop("llama_commit")

    with pytest.raises(ValueError, match="llama_commit, quantisation"):
        render_dossier(page)


def test_a_reading_inside_the_two_spreads_reproduces_the_page() -> None:
    """The tolerance is both spreads added, not either alone.

    A run that lands inside its own noise and inside the page's noise has not
    disagreed with the page, and holding it to one spread would fail the bench
    on noise the page itself already declared.
    """
    observed = Reading(THROUGHPUT_SECTION, "Decode, 250 tokens", 6.01, 0.11, "tok/s", 3)
    declared = Reading(THROUGHPUT_SECTION, "Decode, 250 tokens", 6.15, 0.05, "tok/s", 3)

    assert within_spread("decode_250", observed, declared) is None


def test_a_reading_outside_the_two_spreads_names_both_numbers() -> None:
    """The failure has to be readable without opening either artifact."""
    observed = Reading(THROUGHPUT_SECTION, "Decode, 250 tokens", 6.01, 0.11, "tok/s", 3)
    declared = Reading(THROUGHPUT_SECTION, "Decode, 250 tokens", 6.44, 0.20, "tok/s", 3)

    assert within_spread("decode_250", observed, declared) == (
        "decode_250: the bench read 6.01 +/- 0.11 tok/s and the page declares "
        "6.44 +/- 0.2 tok/s; they are 0.43 tok/s apart and the two spreads allow 0.31"
    )


def test_a_reading_taken_once_is_reported_rather_than_judged() -> None:
    """Its spread is unavailable, not zero, so an exact match is not the bar."""
    failures, abstained = compare_readings(_page(offset=0.0), _page(offset=5.0))

    assert any(line.startswith("model_load_cold: ") for line in abstained)
    assert not any(line.startswith("model_load_cold: ") for line in failures)
    assert any(line.startswith("summarize_median: ") for line in failures), (
        "a reading with a spread is still judged"
    )


def test_a_quantity_only_one_side_read_is_a_failure_and_not_a_pass() -> None:
    observed = _page()
    declared = _page()
    declared.readings.pop("summarize_median")

    failures, _ = compare_readings(observed, declared)

    assert failures == ["summarize_median: the bench read it and the page declares nothing"]


def test_readings_survive_the_round_trip_through_the_artifact(tmp_path: Path) -> None:
    page = _page()
    path = tmp_path / "readings.json"

    page.write(path)

    assert BenchReadings.read(path) == page
