import pytest

from utilities.summarise_bench import NO_READINGS, Throughput, collect, markdown, report


def _run(
    *,
    threads: int,
    prompt: int = 0,
    generated: int = 0,
    tok_s: float,
    draws: int = 3,
) -> dict[str, object]:
    return {
        "model_filename": "backend/models/model.gguf",
        "n_threads": threads,
        "n_prompt": prompt,
        "n_gen": generated,
        "avg_ts": tok_s,
        "stddev_ts": 0.1,
        "samples_ts": [tok_s] * draws,
        "cpu_info": "AMD EPYC 9V74 80-Core Processor",
        "build_number": 10598,
    }


def test_collect_keeps_thread_counts_as_separate_measurements() -> None:
    throughputs = collect(
        [
            _run(threads=4, prompt=730, tok_s=12.0),
            _run(threads=4, generated=250, tok_s=7.0),
            _run(threads=8, prompt=730, tok_s=10.0),
            _run(threads=8, generated=250, tok_s=6.0),
        ]
    )

    assert len(throughputs) == 2
    by_threads = {throughput.threads: throughput for throughput in throughputs}
    assert by_threads[4].prefill == {730: (12.0, 0.1)}
    assert by_threads[4].decode == (7.0, 0.1)
    assert by_threads[8].prefill == {730: (10.0, 0.1)}
    assert by_threads[8].decode == (6.0, 0.1)


def test_report_suppresses_derived_times_without_model_specific_prompt_tokens(
    capsys: pytest.CaptureFixture[str],
) -> None:
    report(
        [Throughput("model.gguf", 4, {730: (12.0, 0.1)}, (7.0, 0.1))],
        n_urls=40,
        parallel=4,
        system_prompt_tokens=None,
        truncation_cap_tokens=None,
    )

    output = capsys.readouterr().out
    assert "derived timings : skipped" in output
    assert "blended/article" not in output


def test_report_uses_the_explicit_prompt_count_and_parallelism(
    capsys: pytest.CaptureFixture[str],
) -> None:
    report(
        [Throughput("model.gguf", 4, {730: (12.0, 0.1)}, (7.0, 0.1))],
        n_urls=40,
        parallel=4,
        system_prompt_tokens=879,
        truncation_cap_tokens=2500,
    )

    output = capsys.readouterr().out
    assert "short       1425" in output
    assert "long        3379" in output
    assert "40 URLs x4 matrix" in output
    assert "(10 wave(s))" in output


def test_the_table_names_the_machine_the_unit_and_what_each_rate_means() -> None:
    """A rate with no unit and no machine is not a reading (CLAUDE.md Guardrail #10).

    `1.055x` is not an answer and neither is a bare `7.28`. The unit is in the
    column heading, the direction is in the sentence above the table, and the
    processor is named because the other half of the same dispatch runs on its
    own runner.
    """
    page = markdown(
        [
            _run(threads=4, prompt=730, tok_s=112.4),
            _run(threads=4, generated=250, tok_s=7.28),
        ],
        candidate="qwen3-5-9b-q4-k-m",
        quantisation="q4_k_m",
    )

    assert "## Model speed: qwen3-5-9b-q4-k-m" in page
    assert "AMD EPYC 9V74 80-Core Processor" in page
    assert "llama.cpp build b10598" in page
    assert "tokens a second, and more is faster" in page
    assert "| Tokens a second |" in page
    assert "Reading a 730-token prompt | 112.40 +/- 0.10 | 3 |" in page
    assert "Writing an answer | 7.28 +/- 0.10 | 3 |" in page
    assert "quantisation `q4_k_m`" in page


def test_one_draw_prints_no_spread_and_says_so() -> None:
    """A spread over a single timing is not a spread, and printing +/- 0.00 claims one."""
    page = markdown([_run(threads=4, generated=250, tok_s=7.28, draws=1)])

    assert "7.28 | 1 draw, no spread |" in page
    assert "+/-" not in page


def test_no_readings_degrades_to_one_sentence_rather_than_an_error() -> None:
    """The step that writes this must not fail the job it is reporting on (section 1a)."""
    assert markdown(None) == NO_READINGS
    assert markdown([]) == NO_READINGS
    assert "backend/var/llm.json" in NO_READINGS
