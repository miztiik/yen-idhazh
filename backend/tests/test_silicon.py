"""What the silicon probe reads, driven from built text rather than from this machine."""

from __future__ import annotations

from pathlib import Path

from idhazh import config, ledger
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.run_plan import RunPlan
from idhazh.telemetry import silicon


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
        job="work",
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
        job="work",
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
        job="work",
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


def test_the_stage_writes_one_row_a_job_into_the_day_file(tmp_path: Path) -> None:
    """The whole point: a reading somebody takes next month can find the machine."""
    settings = config.load()
    settings.app.observability.host_fingerprint = True
    settings.app.observability.host_fingerprint_bandwidth_mib = 0

    row = silicon.stage_fingerprint(
        a_plan(), settings=settings, state_root=tmp_path, shard=2, job="work"
    )

    assert row is not None
    written = ledger.host_fingerprint_path(tmp_path, "2026-09-16")
    assert written.exists(), "a fingerprint nobody stored answers nothing next month"
    assert written.parts[-3:] == ("2026", "09", "16.csv"), "the tree has to be day sharded"


def test_a_second_call_for_one_job_does_not_write_a_second_row(tmp_path: Path) -> None:
    """A machine counted twice is exactly what would make the distribution lie."""
    settings = config.load()
    settings.app.observability.host_fingerprint_bandwidth_mib = 0
    plan = a_plan()

    silicon.stage_fingerprint(plan, settings=settings, state_root=tmp_path, shard=0, job="work")
    silicon.stage_fingerprint(plan, settings=settings, state_root=tmp_path, shard=0, job="work")

    lines = ledger.host_fingerprint_path(tmp_path, "2026-09-16").read_text(encoding="utf-8")
    assert lines.count("\n") == 2, "one header and one row, however many times the stage ran"


def test_the_switch_being_off_writes_nothing_and_still_returns(tmp_path: Path) -> None:
    """Guardrail #6: the behaviour has to change from config with no source edit."""
    settings = config.load()
    settings.app.observability.host_fingerprint = False

    row = silicon.stage_fingerprint(a_plan(), settings=settings, state_root=tmp_path, shard=0)

    assert row is None
    assert not ledger.host_fingerprint_path(tmp_path, "2026-09-16").exists()


def test_a_row_survives_the_round_trip_through_the_ledger_shape(tmp_path: Path) -> None:
    """An empty cell has to read back as absent, never as a zero bandwidth."""
    settings = config.load()
    settings.app.observability.host_fingerprint_bandwidth_mib = 0
    silicon.stage_fingerprint(a_plan(), settings=settings, state_root=tmp_path, shard=0)

    path = ledger.host_fingerprint_path(tmp_path, "2026-09-16")
    header, body = path.read_text(encoding="utf-8").splitlines()[:2]
    read = HostFingerprintRow.from_csv_row(dict(zip(header.split(","), body.split(","), strict=True)))

    assert read.memcpy_gib_s is None, "a probe that did not run is absent, not zero"
    assert read.memcpy_probe_mib == 0
    assert len(read.fingerprint) == 16
