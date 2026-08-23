from utilities.summarise_bench import Throughput, collect, report


def _run(*, threads: int, prompt: int = 0, generated: int = 0, tok_s: float) -> dict[str, object]:
    return {
        "model_filename": "backend/models/model.gguf",
        "n_threads": threads,
        "n_prompt": prompt,
        "n_gen": generated,
        "avg_ts": tok_s,
        "stddev_ts": 0.1,
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
    capsys,
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


def test_report_uses_the_explicit_prompt_count_and_parallelism(capsys) -> None:
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
