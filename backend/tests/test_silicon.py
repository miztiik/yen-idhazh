"""What the silicon probe reads, driven from built text rather than from this machine."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.run_plan import RunPlan
from idhazh.stages import compact as compact_stage
from idhazh.telemetry import silicon

#: One committed capture of llama-server's own log, so the four-field stamp the
#: load time is decoded from is a real one rather than a shape somebody typed.
SERVER_LOG = FIXTURES_DIR / "runtime" / "2026-08-29-3-shard-0.server-head.txt"

#: One committed capture of the same server's `GET /metrics` body. The two
#: prompt counters on the host row are read from a real scrape for the same
#: reason: the wire names are llama.cpp's, not ours.
SERVER_METRICS = FIXTURES_DIR / "runtime" / "2026-08-26-5-shard-0.prom"

#: Every committed scrape of one run, and every committed server head of
#: another. The oracles below are parametrized over them, so an empty glob would
#: be a green test that collected no cases - which is what the first spelling of
#: the server head did, because `.gitignore` carries `*.log`.
METRICS_CAPTURES = sorted((FIXTURES_DIR / "runtime").glob("2026-08-26-5-shard-*.prom"))

SERVER_LOG_CAPTURES = sorted(
    (FIXTURES_DIR / "runtime").glob("2026-08-29-3-shard-*.server-head.txt")
)


def a_plan() -> RunPlan:
    """The smallest plan this stage needs: a date and a run id."""
    return RunPlan.model_validate(
        {
            "date": "2026-09-16",
            "run_id": "2026-09-16-1",
            "generated_at": "2026-09-16T00:00:00Z",
            "items": [],
        }
    )


def a_probe() -> config.Settings:
    """The probe switched on with the bandwidth reading switched off.

    The bandwidth probe allocates a gigabyte and times a copy of it, which is a
    second of a test's life for a cell none of these tests reads.
    """
    settings = config.load()
    settings.app.observability.host_fingerprint = True
    settings.app.observability.host_fingerprint_bandwidth_mib = 0
    return settings


CPUINFO_XEON = """processor\t: 0
vendor_id\t: GenuineIntel
cpu family\t: 6
model\t\t: 207
model name\t: INTEL(R) XEON(R) PLATINUM 8573C
stepping\t: 2
microcode\t: 0x21000283
cpu MHz\t\t: 2300.000
cpu cores\t: 2
flags\t\t: fpu vme de avx2 avx512f avx512_bf16 amx_tile amx_bf16 amx_int8 fma f16c sse4_2
processor\t: 1
vendor_id\t: GenuineIntel
cpu family\t: 6
model\t\t: 207
model name\t: INTEL(R) XEON(R) PLATINUM 8573C
stepping\t: 2
cpu MHz\t\t: 2100.000
cpu cores\t: 2
flags\t\t: fpu vme de avx2 avx512f avx512_bf16 amx_tile amx_bf16 amx_int8 fma f16c sse4_2
"""

CPUINFO_MILAN = """processor\t: 0
vendor_id\t: AuthenticAMD
cpu family\t: 25
model\t\t: 1
model name\t: AMD EPYC 7763 64-Core Processor
stepping\t: 1
cpu MHz\t\t: 2445.424
cpu cores\t: 2
flags\t\t: fpu vme de avx2 fma f16c sse4_2
"""


def test_only_the_watched_flags_are_recorded_and_they_are_sorted() -> None:
    """A free-text flags line is 200 words. The column is the handful we read back."""
    found = silicon.watched_flags(CPUINFO_XEON)

    assert found == "amx_bf16 amx_int8 amx_tile avx2 avx512_bf16 avx512f f16c fma sse4_2"
    assert "fpu" not in found, "an unwatched flag would make the column unbounded"


def test_a_machine_with_no_watched_flags_records_an_empty_string() -> None:
    """Absent is a reading here: the Milan draw has no AVX-512 at all."""
    found = silicon.watched_flags(CPUINFO_MILAN)

    assert found == "avx2 f16c fma sse4_2"
    assert "avx512" not in found


def test_the_fingerprint_ignores_everything_that_moves_between_two_jobs() -> None:
    """Two draws of one machine type have to carry one id, or the column counts nothing."""
    first = {"cpu_vendor": "GenuineIntel", "cpu_family": 6, "flags": "avx512f"}
    second = dict(first)

    assert silicon.fingerprint_of(first) == silicon.fingerprint_of(second)
    assert len(silicon.fingerprint_of(first)) == 16


def test_a_different_instruction_set_is_a_different_fingerprint() -> None:
    """The flags are the cell that explains the throughput, so they must change the id."""
    milan = {"cpu_vendor": "AuthenticAMD", "flags": "avx2"}
    genoa = {"cpu_vendor": "AuthenticAMD", "flags": "avx2 avx512f"}

    assert silicon.fingerprint_of(milan) != silicon.fingerprint_of(genoa)


def test_the_row_reads_family_model_stepping_off_the_text_it_is_given() -> None:
    """The generation comes from the host, never from a codename somebody remembered."""
    row = silicon.read_row(
        date="2026-09-16",
        run_id="2026-09-16-1",
        job=ServerJob.WORK,
        shard=0,
        probe_mib=0,
        ask_placement=False,
        cpuinfo=CPUINFO_XEON,
    )

    assert row.cpu_family == 6
    assert row.cpu_model_number == 207
    assert row.cpu_stepping == 2
    assert row.cpu_vendor == "GenuineIntel"
    assert row.microcode == "0x21000283"


def test_the_clock_is_the_mean_across_processors_and_threads_is_their_count() -> None:
    """One processor's clock is not the machine's, and the count comes from the same lines."""
    row = silicon.read_row(
        date="2026-09-16",
        run_id="2026-09-16-1",
        job=ServerJob.WORK,
        shard=0,
        probe_mib=0,
        ask_placement=False,
        cpuinfo=CPUINFO_XEON,
    )

    assert row.threads == 2
    assert row.mhz_at_probe == 2200.0


def test_a_probe_size_of_zero_switches_the_bandwidth_reading_off() -> None:
    """The knob has to be able to cost nothing, and an absent reading is not a zero."""
    assert silicon.memcpy_gib_s(0) is None

    row = silicon.read_row(
        date="2026-09-16",
        run_id="2026-09-16-1",
        job=ServerJob.WORK,
        shard=0,
        probe_mib=0,
        ask_placement=False,
        cpuinfo=CPUINFO_MILAN,
    )

    assert row.memcpy_gib_s is None
    assert row.memcpy_probe_mib == 0


def test_the_bandwidth_probe_returns_a_rate_when_it_is_asked_for_one() -> None:
    """Small on purpose - this checks the arithmetic runs, never what this laptop is worth."""
    rate = silicon.memcpy_gib_s(1)

    assert rate is not None
    assert rate > 0


def test_a_metadata_service_that_is_not_there_records_nothing_and_does_not_raise() -> None:
    """Every developer machine is this case, and it degrades the row rather than the run."""
    where = silicon.placement(url="http://127.0.0.1:1/never", timeout=0.05)

    assert where.vm_size is None
    assert where.location is None


def test_a_cache_directory_that_is_not_there_reads_as_unknown(tmp_path: Path) -> None:
    """Unknown is not zero: a machine with no reported L3 is not a machine with none."""
    assert silicon.cache_bytes(root=tmp_path / "absent") is None


def test_a_reported_cache_size_is_read_in_the_units_the_kernel_wrote(tmp_path: Path) -> None:
    """The kernel writes `260M`, and a reader that takes that for 260 bytes is worse than none."""
    level = tmp_path / "index3"
    level.mkdir(parents=True)
    (level / "level").write_text("3\n", encoding="utf-8")
    (level / "size").write_text("260M\n", encoding="utf-8")

    assert silicon.cache_bytes(root=tmp_path) == 260 * 1024 * 1024


def test_uptime_is_the_first_field_and_a_missing_file_is_not_a_zero() -> None:
    """A pooled machine and a fresh one are different facts; unknown is a third."""
    assert silicon.boot_seconds("1234.56 9876.54\n") == 1234.56
    assert silicon.boot_seconds("") is None


def test_the_bench_can_ask_for_the_model_name_on_its_own() -> None:
    """The server case records which machine it drew, so a dossier can name it."""
    assert silicon.host_cpu_model(CPUINFO_MILAN) == "AMD EPYC 7763 64-Core Processor"
    assert silicon.host_cpu_model("") is None


def test_the_stage_writes_this_job_its_own_segment_and_never_the_day_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ten jobs of one run record a machine, so none of them may open one file.

    `state/host-fingerprint/2026/09/16.csv` is header-only in this repository
    because they did. A segment is named for the run, the attempt, the job and
    the shard, so two writers cannot take one path and the compaction is what
    turns them back into the day a reader opens.

    The attempt is set here rather than left to the environment: this suite runs
    on Actions too, and a re-run of the CI job would otherwise put a 2 in a name
    this test spells out.
    """
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    row = silicon.stage_fingerprint(
        a_plan(), settings=a_probe(), state_root=tmp_path, shard=2, job=ServerJob.WORK
    )

    assert row is not None
    assert not ledger.host_fingerprint_path(tmp_path, "2026-09-16").exists(), (
        "the probe writes a segment; the head has one writer and it is the compaction"
    )
    written = ledger.segment_files(tmp_path, ledger.SegmentLedger.HOST_FINGERPRINT)
    assert [path.name for path in written] == ["2026-09-16-1-1-work-02.csv"]

    compact_stage.stage_compact(tmp_path)
    head = ledger.host_fingerprint_path(tmp_path, "2026-09-16")
    assert head.exists(), "a fingerprint nobody stored answers nothing next month"
    assert head.parts[-3:] == ("2026", "09", "16.csv"), "the tree has to be day sharded"
    assert not ledger.segment_files(tmp_path), "a folded segment is removed, not left behind"


def test_a_second_attempt_at_one_shard_writes_beside_the_first_and_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GitHub keeps the run id and increments the attempt, so the attempt is in the name.

    Without it the second try takes the path the first already took - in exactly
    the case where the two disagree, because the first attempt is the one that
    died. Both files survive to the fold, and the fold keeps the higher attempt.
    """
    plan, settings = a_plan(), a_probe()
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    silicon.stage_fingerprint(plan, settings=settings, state_root=tmp_path, shard=0)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    silicon.stage_fingerprint(plan, settings=settings, state_root=tmp_path, shard=0)

    written = ledger.segment_files(tmp_path, ledger.SegmentLedger.HOST_FINGERPRINT)
    assert [path.name for path in written] == [
        "2026-09-16-1-1-work-00.csv",
        "2026-09-16-1-2-work-00.csv",
    ]

    compact_stage.stage_compact(tmp_path)
    lines = ledger.host_fingerprint_path(tmp_path, "2026-09-16").read_text(encoding="utf-8")
    assert lines.count("\n") == 2, "one machine, one row, however many attempts drew it"


def test_a_second_call_in_one_attempt_rewrites_the_one_segment(tmp_path: Path) -> None:
    """A machine counted twice is exactly what would make the distribution lie."""
    plan, settings = a_plan(), a_probe()

    silicon.stage_fingerprint(
        plan, settings=settings, state_root=tmp_path, shard=0, job=ServerJob.WORK
    )
    silicon.stage_fingerprint(
        plan, settings=settings, state_root=tmp_path, shard=0, job=ServerJob.WORK
    )

    assert len(ledger.segment_files(tmp_path)) == 1, "one writer, one path, one file"
    compact_stage.stage_compact(tmp_path)
    lines = ledger.host_fingerprint_path(tmp_path, "2026-09-16").read_text(encoding="utf-8")
    assert lines.count("\n") == 2, "one header and one row, however many times the stage ran"


def test_the_switch_being_off_writes_nothing_and_still_returns(tmp_path: Path) -> None:
    """Guardrail #6: the behaviour has to change from config with no source edit."""
    settings = config.load()
    settings.app.observability.host_fingerprint = False

    row = silicon.stage_fingerprint(a_plan(), settings=settings, state_root=tmp_path, shard=0)

    assert row is None
    assert not ledger.segment_files(tmp_path)
    assert not ledger.host_fingerprint_path(tmp_path, "2026-09-16").exists()


def test_a_row_survives_the_round_trip_through_the_ledger_shape(tmp_path: Path) -> None:
    """An empty cell has to read back as absent, never as a zero bandwidth.

    Read off the segment rather than off the head, because the segment is where
    the writer's own rendering lands: a head has been through the fold, so a cell
    the writer never filled and a cell the fold dropped would look the same.
    """
    silicon.stage_fingerprint(a_plan(), settings=a_probe(), state_root=tmp_path, shard=0)

    path = ledger.segment_files(tmp_path, ledger.SegmentLedger.HOST_FINGERPRINT)[0]
    header, body = path.read_text(encoding="utf-8").splitlines()[:2]
    read = HostFingerprintRow.from_csv_row(
        dict(zip(header.split(","), body.split(","), strict=True))
    )

    assert read.memcpy_gib_s is None, "a probe that did not run is absent, not zero"
    assert read.memcpy_probe_mib == 0
    assert len(read.fingerprint or "") == 16


def test_a_day_file_written_before_the_two_prompt_cells_still_folds(tmp_path: Path) -> None:
    """The read-side migration, proved on a file that is missing the columns.

    Yesterday's run wrote a head two columns narrower than today's contract, and
    a build that could not read it would be a contract break rather than a
    widening. The settlement re-files the head on the next fold and the two cells
    come back empty - which says the reading was not taken, not that the server
    read nothing.

    Built here rather than read off `state/`: a committed head is re-filed by the
    first fold that touches it, so a test that read one would pass today by
    accident and answer nothing later (`CLAUDE.md` section 13).
    """
    narrow = tuple(
        name
        for name in HostFingerprintRow.csv_columns()
        if name not in ("server_prompt_tokens", "server_prompt_seconds")
    )
    yesterday = HostFingerprintRow(
        version="2026-09-18",
        date="2026-09-16",
        run_id="2026-09-16-1",
        shard=0,
        cpu_model="AMD EPYC 7763 64-Core Processor",
        job_seconds=5550,
    )
    path = ledger.host_fingerprint_path(tmp_path, "2026-09-16")
    path.parent.mkdir(parents=True, exist_ok=True)
    cells = yesterday.csv_row()
    path.write_text(
        ",".join(narrow) + "\n" + ",".join(cells[name] for name in narrow) + "\n",
        encoding="utf-8",
        newline="",
    )
    silicon.stage_job_clock(
        a_plan(),
        settings=a_probe(),
        state_root=tmp_path,
        shard=1,
        metrics_path=SERVER_METRICS,
    )

    compact_stage.stage_compact(tmp_path)

    header, *body = path.read_text(encoding="utf-8").splitlines()
    columns = header.split(",")
    assert columns == list(HostFingerprintRow.csv_columns())
    rows = {
        cells["shard"]: cells
        for cells in (dict(zip(columns, line.split(","), strict=True)) for line in body)
    }
    assert rows["0"]["server_prompt_tokens"] == "", "a reading nobody took is empty, not zero"
    assert rows["0"]["job_seconds"] == "5550", "the widening may not cost the cells already there"
    assert rows["1"]["server_prompt_tokens"] == "30538"
    assert HostFingerprintRow.from_csv_row(rows["0"]).server_prompt_seconds is None


def _head_row(state_dir: Path, date: str = "2026-09-16") -> dict[str, str]:
    """The one row of the compacted day file, by column name."""
    path = ledger.host_fingerprint_path(state_dir, date)
    header, *body = path.read_text(encoding="utf-8").splitlines()
    assert len(body) == 1, f"one machine, one row, and the head holds {len(body)}"
    return dict(zip(header.split(","), body[0].split(","), strict=True))


def test_the_probe_and_the_job_clock_fold_into_one_row(tmp_path: Path) -> None:
    """The Oracle: two halves of one key, no cell filled twice, one row in the head.

    The probe runs before the model server because the bandwidth reading wants an
    idle machine, and the job's own clock is only knowable once the job is over.
    Both write a row of the same shape under `HOST_FINGERPRINT_KEY`, filling
    columns the other left empty, so the fold takes the union rather than
    choosing between them.

    It is the Join case of the settlement that makes this work, and Join only
    fires because the key columns are excluded from what counts as contested -
    `date`, `run_id`, `job` and `shard` are equal by construction, which is what
    made the two rows one record in the first place.
    """
    plan, settings = a_plan(), a_probe()
    probe = silicon.stage_fingerprint(
        plan, settings=settings, state_root=tmp_path, shard=2, job=ServerJob.WORK
    )
    clock = silicon.stage_job_clock(
        plan,
        settings=settings,
        state_root=tmp_path,
        shard=2,
        job=ServerJob.WORK,
        job_started_at=int(time.time()) - 5550,
        server_log_path=SERVER_LOG,
        metrics_path=SERVER_METRICS,
    )

    assert probe is not None and clock is not None
    contested = [
        name
        for name, value in clock.csv_row().items()
        if value and probe.csv_row()[name] and name not in ledger.HOST_FINGERPRINT_KEY
    ]
    assert contested == ["version"], (
        "the two halves must fill different cells, or the fold has to choose between them"
    )

    compact_stage.stage_compact(tmp_path)
    row = _head_row(tmp_path)

    assert row["fingerprint"] == probe.fingerprint
    assert row["measured_at"] == probe.measured_at
    assert row["job_seconds"] == "5550"
    assert float(row["model_load_ms"]) == clock.model_load_ms
    assert row["server_prompt_tokens"] == "30538"
    assert row["server_prompt_seconds"] == "2795.15"
    assert HostFingerprintRow.from_csv_row(row).shard == 2


def test_a_job_that_died_before_its_clock_leaves_a_usable_half_row(tmp_path: Path) -> None:
    """The degrade path, named: two empty cells rather than a row nobody can read.

    A shard killed at `run.shard_timeout_minutes` never reaches the clock step,
    and everything the probe measured about the machine is still true.
    """
    silicon.stage_fingerprint(a_plan(), settings=a_probe(), state_root=tmp_path, shard=0)

    compact_stage.stage_compact(tmp_path)
    row = _head_row(tmp_path)

    assert row["job_seconds"] == ""
    assert row["model_load_ms"] == ""
    assert HostFingerprintRow.from_csv_row(row).job_seconds is None


def test_a_clock_with_no_stamp_and_no_log_reports_absence_rather_than_zero(
    tmp_path: Path,
) -> None:
    """An empty cell says the reading was not taken. A zero claims a job that was free.

    Both readings come from the workflow: the stamp from a step before the
    checkout, the log from the server this job started. A run of this stage
    anywhere else - a developer machine, a shard whose server never came up - has
    neither.
    """
    clock = silicon.stage_job_clock(
        a_plan(), settings=a_probe(), state_root=tmp_path, shard=0, server_log_path=None
    )

    assert clock is not None
    assert clock.job_seconds is None
    assert clock.model_load_ms is None
    assert clock.server_prompt_tokens is None
    assert clock.server_prompt_seconds is None
    assert clock.csv_row()["job_seconds"] == ""
    assert clock.fingerprint is None, "the clock half measured no machine and may not claim one"


def test_the_clock_half_lands_in_the_probes_own_segment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One job, one writer, one file - the grammar names the job and not the step.

    `state/segments/<ledger>/<run>-<attempt>-<job>-<shard>.csv` has no element a
    second step of one job could differ in, so a second file is not something
    this store can express. The two halves are two rows of the file this job
    owns, and neither is ever edited.
    """
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    plan, settings = a_plan(), a_probe()
    silicon.stage_fingerprint(plan, settings=settings, state_root=tmp_path, shard=0)
    silicon.stage_job_clock(
        plan, settings=settings, state_root=tmp_path, shard=0, job_started_at=int(time.time()) - 60
    )

    written = ledger.segment_files(tmp_path, ledger.SegmentLedger.HOST_FINGERPRINT)
    assert [path.name for path in written] == ["2026-09-16-1-1-work-00.csv"]
    assert written[0].read_text(encoding="utf-8").count("\n") == 3, "one header and two halves"


def test_the_switch_being_off_records_no_clock_either(tmp_path: Path) -> None:
    """Guardrail #6: one knob answers for the whole record, not for half of it."""
    settings = config.load()
    settings.app.observability.host_fingerprint = False

    clock = silicon.stage_job_clock(
        a_plan(), settings=settings, state_root=tmp_path, shard=0, job_started_at=1
    )

    assert clock is None
    assert not ledger.segment_files(tmp_path)


def test_the_two_job_cells_are_decoded_from_a_real_capture() -> None:
    """The four-field llama-server stamp is what a second copy of this would get wrong.

    `model_load_ms` is the gap between the two lines llama-server brackets its
    load with, and `job_seconds` is the job's own clock against its scrape. Both
    are driven over a real capture rather than a hand-typed line, because the
    stamp's last field is microseconds and reads as milliseconds to anyone who
    guesses.
    """
    text = SERVER_LOG.read_text(encoding="utf-8")

    loaded = silicon.model_load_ms(text)

    assert loaded is not None and 1000 < loaded < 60_000
    assert silicon.job_seconds("2026-09-16T04:11:02Z", 1789531312) == 5550
    assert silicon.job_seconds("2026-09-16T04:11:02Z", None) is None
    assert silicon.model_load_ms("load_model: loading model\n") is None, (
        "one end of the bracket is not a load that took no time"
    )


def test_the_two_prompt_counters_are_read_off_one_table_and_never_a_second_copy() -> None:
    """The host row's second instrument, over a real scrape.

    Both readings come off one table of wire names, so a llama.cpp rename is one
    edit and shows up as two empty cells rather than as two numbers that disagree
    with the item rows beside them.
    """
    text = SERVER_METRICS.read_text(encoding="utf-8")

    tokens, seconds = silicon.server_prompt_totals(text)

    assert (tokens, seconds) == (30538, 2795.15)


def test_every_runtime_capture_an_oracle_reads_is_committed() -> None:
    """A parametrized oracle over an empty glob is green and proves nothing.

    `.gitignore` carries `*.log`, so the first spelling of the server-log
    capture was ignored the moment it was named after the file it came from -
    and the test over it collected zero cases without saying so.
    """
    assert len(METRICS_CAPTURES) == 4
    assert len(SERVER_LOG_CAPTURES) == 4


@pytest.mark.parametrize("path", METRICS_CAPTURES, ids=lambda p: p.stem)
def test_the_server_agrees_with_itself_about_what_a_prompt_token_is(path: Path) -> None:
    """The Oracle for the definition: the server's own rate over its own counters.

    llama-server publishes `prompt_tokens_seconds` as well as the two counters it
    is made of. If `prompt_tokens_total` counted cached tokens too, the published
    gauge and the counters would disagree - so this reproduces the gauge from the
    counters and proves the field means what the host row says it means: prompt
    tokens the model actually read, which is the item ledger's
    `input_tokens - cached_tokens`.
    """
    text = path.read_text(encoding="utf-8")
    tokens, seconds = silicon.server_prompt_totals(text)
    published = {
        line.split(" ")[0]: float(line.split(" ")[1])
        for line in text.splitlines()
        if line.startswith("llamacpp:")
    }

    assert tokens is not None and seconds is not None
    # The gauge is printed to six significant figures, so the comparison is too.
    assert tokens / seconds == pytest.approx(published["llamacpp:prompt_tokens_seconds"], rel=1e-5)
    assert published["llamacpp:prompt_tokens_cached_total"] > 0, (
        "a capture with no cache hits proves nothing here"
    )


@pytest.mark.parametrize("path", SERVER_LOG_CAPTURES, ids=lambda p: p.name)
def test_the_model_load_time_is_the_gap_between_the_servers_own_two_lines(path: Path) -> None:
    """The Oracle for `model_load_ms`: llama.cpp's stamp decoded from a real job.

    The stamp is four dot-separated numbers and no page says what they are. The
    third field reaches 809 on a real line, so it cannot be seconds-in-a-minute;
    the last field steps by 15 between two lines printed back to back, and the
    first field of the last line of a 99-minute job reads 99. That fixes it as
    minutes, seconds, milliseconds, microseconds - and only a capture of a job
    whose length is known settles it.
    """
    text = path.read_text(encoding="utf-8")
    stamps: dict[str, int] = {}
    for line in text.splitlines():
        for marker in ("load_model: loading model", "llama_server: model loaded"):
            if marker in line and marker not in stamps:
                minutes, seconds, milli, micro = (int(p) for p in line.split(" ")[0].split("."))
                stamps[marker] = (((minutes * 60) + seconds) * 1000 + milli) * 1000 + micro
    assert len(stamps) == 2, f"{path.name} does not bracket a model load"

    loaded = silicon.model_load_ms(text)

    expected = stamps["llama_server: model loaded"] - stamps["load_model: loading model"]
    assert loaded == expected / 1000
    # Seconds, not minutes and not microseconds. A unit slip is the one mistake
    # a gap between two stamps can make and still look plausible.
    assert 1000 < loaded < 60_000


def test_a_scrape_the_server_was_already_gone_for_reports_absence_rather_than_zero() -> None:
    """Empty is not zero. A job whose server died read some tokens; nobody knows how many.

    A zero here would be averaged into a rate by the next reader, and a rate over
    a denominator nobody measured is the defect this instrument exists to catch.
    """
    assert silicon.server_prompt_totals(None) == (None, None)
    assert silicon.server_prompt_totals("") == (None, None)
    assert silicon.server_prompt_totals("# HELP nothing\n") == (None, None)


def test_a_renamed_series_leaves_the_cells_empty_and_a_broken_one_is_loud() -> None:
    """Two failures, two answers, and the difference is whether we can see it.

    A series llama.cpp renamed is simply absent, which reads as unknown. A series
    that is there and unreadable is a format change, and a count that arrives
    fractional is not truncated into a number a later reader would average.
    """
    renamed = "llamacpp:prompt_tokens_read_total 5\nllamacpp:prompt_seconds_total 2.5\n"

    assert silicon.server_prompt_totals(renamed) == (None, 2.5)

    with pytest.raises(ValueError, match="prompt_tokens_total"):
        silicon.server_prompt_totals("llamacpp:prompt_tokens_total 5.5\n")
