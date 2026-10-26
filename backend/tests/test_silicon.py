"""What the silicon probe reads, driven from built text rather than from this machine."""

from __future__ import annotations

import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType

import pytest
from _host_placement import refuse_external_placement
from support.ledger import SEED_COMMIT
from support.paths import FIXTURES_DIR

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import FileEnvelope, WriterIdentity
from idhazh.contracts.host_fingerprint import HostFingerprintRow, fingerprint_v2
from idhazh.contracts.ledger_name import LedgerName
from idhazh.telemetry import silicon, task_telemetry

#: One committed capture of llama-server's own log, so the four-field stamp the
#: load time is decoded from is a real one rather than a shape somebody typed.
SERVER_LOG = FIXTURES_DIR / "runtime" / "2026-08-29-3-shard-0.server-head.txt"

#: One committed capture of the same server's `GET /metrics` body. The two
#: prompt counters on the host row are read from a real scrape for the same
#: reason: the wire names are llama.cpp's, not ours.
SERVER_METRICS = FIXTURES_DIR / "runtime" / "2026-08-26-5-shard-0.prom"

#: The day every plan below runs on, so the day the files land under and the day
#: the reader is asked for cannot drift apart.
FINGERPRINT_DAY = "2026-09-16"

#: The run that day. The stage needs this and the day, and reads no plan: a
#: machine reading is about the job rather than about the work the job did,
#: which is what lets a workflow that plans nothing still take one.
A_RUN_ID = f"{FINGERPRINT_DAY}-1"


def raw_files(state: Path) -> list[ledger.RawFile]:
    """Every raw file of the fingerprint day, oldest first, each with the envelope of its writer."""
    return ledger.list_raw_files(state, LedgerName.HOST_FINGERPRINT, days={FINGERPRINT_DAY})


def fingerprint_envelopes(files: list[ledger.RawFile]) -> list[FileEnvelope]:
    """Keep the fingerprint family's original identity protocol explicit."""
    envelopes = []
    for held in files:
        assert isinstance(held.envelope, FileEnvelope)
        envelopes.append(held.envelope)
    return envelopes


def settled(state: Path) -> list[HostFingerprintRow]:
    """The fingerprint day as every reader reads it: its raw files, settled."""
    return ledger.load_days(
        state, LedgerName.HOST_FINGERPRINT, [FINGERPRINT_DAY], model=HostFingerprintRow
    )


def a_probe() -> config.Settings:
    """The probe switched on with the bandwidth reading switched off.

    The bandwidth probe allocates a gigabyte and times a copy of it, which is a
    second of a test's life for a cell none of these tests reads.
    """
    settings = config.load()
    settings.app.observability.host_fingerprint = True
    settings.app.observability.host_fingerprint_bandwidth_floor_mib = 0
    return settings


def test_only_the_jobs_config_names_take_the_bandwidth_reading(tmp_path: Path) -> None:
    """Guardrail #6: which jobs read bandwidth moves from config, with no source edit.

    The reading wants a gigabyte and an idle machine, so the bench takes it and a
    production job does not - a job that allocated twice the cache it drew would
    time a copy against whatever else it had already started, which measures the
    run rather than the host.

    Driven over a one-mebibyte floor rather than the committed one, because what
    is under test is whether the job was asked at all. A row that skipped the
    reading says so with `memcpy_probe_mib` of zero, which is a different fact
    from a machine that copied nothing.
    """
    settings = config.load()
    settings.app.observability.host_fingerprint = True
    settings.app.observability.host_fingerprint_bandwidth_floor_mib = 1
    settings.app.observability.host_fingerprint_bandwidth_jobs = ("runtime",)

    took = silicon.stage_fingerprint(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        settings=settings,
        state_root=tmp_path / "bench",
        commit_sha=SEED_COMMIT,
        job=ServerJob.RUNTIME,
    )
    skipped = silicon.stage_fingerprint(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        settings=settings,
        state_root=tmp_path / "wake",
        commit_sha=SEED_COMMIT,
        job=ServerJob.RUN_TASKS,
    )

    assert took is not None and skipped is not None
    assert took.memcpy_probe_mib and took.memcpy_probe_mib > 0, "the named job read nothing"
    assert skipped.memcpy_probe_mib == 0, "a job config did not name took the reading anyway"
    assert skipped.memcpy_gib_s is None, "an untaken reading is absent, never a zero rate"
    assert skipped.fingerprint == took.fingerprint, (
        "one machine, two rows: skipping the reading may not change what the host is"
    )


def test_the_committed_config_requests_no_bandwidth_jobs() -> None:
    """The committed empty job list requests no bandwidth benchmark."""
    named = config.load().app.observability.host_fingerprint_bandwidth_jobs

    assert named == ()


@pytest.mark.parametrize(
    ("placement_enabled", "ask_placement"),
    [(False, True), (True, False)],
    ids=["config-off", "caller-off"],
)
def test_placement_off_keeps_a_real_local_machine_row(
    tmp_path: Path,
    placement_enabled: bool,
    ask_placement: bool,
) -> None:
    settings = config.load()
    settings.app.observability.host_telemetry_enabled = True
    settings.app.observability.host_fingerprint = True
    settings.app.observability.host_fingerprint_bandwidth_floor_mib = 0
    settings.app.observability.host_fingerprint_placement_enabled = placement_enabled
    before = datetime.now(UTC)

    with refuse_external_placement():
        row, paths = silicon.file_machine_row(
            date=FINGERPRINT_DAY,
            run_id=A_RUN_ID,
            settings=settings,
            state_root=tmp_path,
            commit_sha=SEED_COMMIT,
            pipeline_name="placement-test",
            task_name="record-machine",
            ask_placement=ask_placement,
        )

    after = datetime.now(UTC)
    assert row is not None
    assert paths and all(path.is_file() for path in paths)
    saved = settled(tmp_path)
    assert len(saved) == 1
    assert saved[0] == row
    assert (row.pipeline_name, row.task_name, row.run_id) == (
        "placement-test",
        "record-machine",
        A_RUN_ID,
    )
    assert row.measured_at is not None
    measured_at = datetime.fromisoformat(row.measured_at.replace("Z", "+00:00"))
    assert before.replace(microsecond=0) <= measured_at <= after
    assert row.cpu_target_measured_at == row.measured_at


def test_default_config_reaches_real_placement_before_any_network_call(
    tmp_path: Path,
) -> None:
    settings = config.load()
    assert settings.app.observability.host_fingerprint_placement_enabled is True
    requested: list[FrameType] = []

    class PlacementRequestedError(Exception):
        pass

    def stop_before_network(frame: FrameType, event: str, argument: object) -> None:
        if event == "call" and frame.f_code is silicon.placement.__code__:
            requested.append(frame)
            raise PlacementRequestedError

    previous = sys.getprofile()
    sys.setprofile(stop_before_network)
    try:
        with pytest.raises(PlacementRequestedError):
            with task_telemetry.record(
                date=FINGERPRINT_DAY,
                run_id=A_RUN_ID,
                settings=settings,
                state_root=tmp_path,
                commit_sha=SEED_COMMIT,
                job=ServerJob.WORK,
            ):
                pass
    finally:
        sys.setprofile(previous)
    assert len(requested) == 1


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


def cpu_topology(
    root: Path, topology: dict[int, tuple[int, int]]
) -> Path:
    for cpu_id, (package, core) in topology.items():
        cpu = root / f"cpu{cpu_id}"
        directory = cpu / "topology"
        directory.mkdir(parents=True)
        (directory / "physical_package_id").write_text(f"{package}\n", encoding="ascii")
        (directory / "core_id").write_text(f"{core}\n", encoding="ascii")
        frequency = cpu / "cpufreq"
        frequency.mkdir()
        (frequency / "cpuinfo_max_freq").write_text("3500000\n", encoding="ascii")
    return root


def test_the_row_reads_family_model_stepping_off_the_text_it_is_given() -> None:
    """The generation comes from the host, never from a codename somebody remembered."""
    row = silicon.read_row(
        date="2026-09-16",
        run_id="2026-09-16-1",
        job=ServerJob.WORK,
        shard=0,
        probe_floor_mib=0,
        probe_cache_multiple=2,
        ask_placement=False,
        cpuinfo=CPUINFO_XEON,
    )

    assert row.cpu_family == 6
    assert row.cpu_model_number == 207
    assert row.cpu_stepping == 2
    assert row.cpu_vendor == "GenuineIntel"
    assert row.microcode == "0x21000283"
    assert row.cpu_observed_mhz is None
    assert row.cpu_reported_max_mhz is None


def test_missing_frequency_does_not_reduce_visible_cpu_count(tmp_path: Path) -> None:
    """Online CPU IDs, not frequency rows, determine logical processor count."""
    row = silicon.read_row(
        date="2026-09-16",
        run_id="2026-09-16-1",
        job=ServerJob.WORK,
        shard=0,
        frequency_enabled=True,
        probe_floor_mib=0,
        probe_cache_multiple=2,
        ask_placement=False,
        cpuinfo=CPUINFO_XEON.replace("cpu MHz\t\t: 2100.000\n", ""),
        online_cpu_list="0,2",
        cpu_root=cpu_topology(tmp_path, {0: (0, 0), 2: (0, 1)}),
    )

    assert row.cpu_logical_processors == 2
    assert row.cpu_physical_cores == 2
    assert row.cpu_observed_mhz == 2300.0
    assert row.cpu_reported_max_mhz == 3500.0
    assert row.fingerprint_version == 2
    assert row.fingerprint == fingerprint_v2(row)


def test_sparse_online_ids_and_incomplete_topology_keep_unknowns_explicit(
    tmp_path: Path,
) -> None:
    topology = cpu_topology(tmp_path, {1: (0, 0), 3: (0, 0), 8: (1, 2)})
    row = silicon.read_row(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        job=ServerJob.WORK,
        shard=0,
        probe_floor_mib=0,
        probe_cache_multiple=2,
        ask_placement=False,
        cpuinfo=CPUINFO_XEON,
        online_cpu_list="1,3,8",
        cpu_root=topology,
    )
    missing_topology = silicon.read_row(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        job=ServerJob.WORK,
        shard=0,
        probe_floor_mib=0,
        probe_cache_multiple=2,
        ask_placement=False,
        cpuinfo=CPUINFO_XEON,
        online_cpu_list="1,3,8",
        cpu_root=tmp_path / "missing-topology",
    )

    assert row.cpu_logical_processors == 3
    assert row.cpu_physical_cores == 2
    assert missing_topology.cpu_logical_processors == 3
    assert missing_topology.cpu_physical_cores is None


def test_target_capacity_uses_affinity_and_the_tightest_visible_cgroup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = 71
    proc = tmp_path / "proc"
    (proc / str(pid)).mkdir(parents=True)
    (proc / str(pid) / "cgroup").write_text("0::/slice/job\n", encoding="ascii")
    cgroups = tmp_path / "cgroup"
    for name, value in (
        ("cpu.max", "max 100000\n"),
        ("slice/cpu.max", "250000 100000\n"),
        ("slice/job/cpu.max", "400000 100000\n"),
    ):
        target = cgroups / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding="ascii")
    monkeypatch.setattr(os, "sched_getaffinity", lambda _pid: {1, 8}, raising=False)

    row = silicon.read_row(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        job=ServerJob.WORK,
        shard=0,
        probe_floor_mib=0,
        probe_cache_multiple=2,
        ask_placement=False,
        cpuinfo=CPUINFO_XEON,
        online_cpu_list="1,3,8",
        cpu_root=cpu_topology(tmp_path / "sys-cpu", {1: (0, 0), 3: (0, 0), 8: (1, 2)}),
        proc_root=proc,
        cgroup_root=cgroups,
        target_pid=pid,
    )

    assert row.cpu_allowed_processors == 2
    assert row.cpu_quota_cores == 2.5
    assert row.cpu_quota_state == "finite"
    assert row.cpu_target_measured_at == row.measured_at


def test_fingerprint_v2_ignores_counts_capacity_and_frequency() -> None:
    """New identities use only stable hardware facts, not job placement."""
    base = silicon.read_row(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        job=ServerJob.WORK,
        shard=0,
        probe_floor_mib=0,
        probe_cache_multiple=2,
        ask_placement=False,
        cpuinfo=CPUINFO_XEON,
        online_cpu_list="0-1",
    )
    changed = base.model_copy(
        update={
            "cpu_physical_cores": 1,
            "cpu_logical_processors": 1,
            "cpu_allowed_processors": 1,
            "cpu_observed_mhz": 9999.0,
            "cpu_reported_max_mhz": 9999.0,
        }
    )
    other_flags = silicon.read_row(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        job=ServerJob.WORK,
        shard=0,
        probe_floor_mib=0,
        probe_cache_multiple=2,
        ask_placement=False,
        cpuinfo=CPUINFO_XEON.replace("avx512f", "avx2"),
        online_cpu_list="0-1",
    )

    assert base.fingerprint_version == 2
    assert base.fingerprint == fingerprint_v2(base)
    assert changed.fingerprint == base.fingerprint
    assert other_flags.fingerprint != base.fingerprint


def test_a_probe_size_of_zero_switches_the_bandwidth_reading_off() -> None:
    """The knob has to be able to cost nothing, and an absent reading is not a zero."""
    assert silicon.memcpy_gib_s(0) is None

    row = silicon.read_row(
        date="2026-09-16",
        run_id="2026-09-16-1",
        job=ServerJob.WORK,
        shard=0,
        probe_floor_mib=0,
        probe_cache_multiple=2,
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


def a_cache_tree(root: Path, size: str) -> Path:
    """One L3 directory laid out the way the kernel lays it out."""
    level = root / "index3"
    level.mkdir(parents=True)
    (level / "level").write_text("3\n", encoding="utf-8")
    (level / "size").write_text(f"{size}\n", encoding="utf-8")
    return root


def test_a_reported_cache_size_is_read_in_the_units_the_kernel_wrote(tmp_path: Path) -> None:
    """The kernel writes `260M`, and a reader that takes that for 260 bytes is worse than none."""
    assert silicon.cache_bytes(root=a_cache_tree(tmp_path, "260M")) == 260 * 1024 * 1024


def test_a_cache_larger_than_the_floor_raises_the_buffer_clear_of_it() -> None:
    """A 512 MiB buffer against 480 MiB of L3 is a 1.07x margin, which settles nothing.

    Both figures are drawn machines: 480 MiB is the Xeon 6973P-C and 260 MiB the
    Xeon 8573C, and a 512 MiB constant covers neither by twice.
    """
    assert silicon.probe_buffer_mib(512, 480 * 1024 * 1024, 2) == 960
    assert silicon.probe_buffer_mib(512, 260 * 1024 * 1024, 2) == 520


def test_the_cache_margin_is_the_knob_and_the_buffer_moves_with_it() -> None:
    """The substitution test on the margin itself (CLAUDE.md Guardrail #6).

    The console grades a committed row by this same value, so a probe that held
    its own copy of it could size a buffer the page then refused.
    """
    assert silicon.probe_buffer_mib(1, 260 * 1024 * 1024, 1) == 260
    assert silicon.probe_buffer_mib(1, 260 * 1024 * 1024, 4) == 1040


def test_a_small_cache_keeps_the_configured_floor_and_the_floor_still_decides_it() -> None:
    """The machine drawn most reports 32 MiB, and 64 MiB is not a memory reading.

    The second pair is the substitution test: the floor is the only input that
    moved, and the answer moved with it (CLAUDE.md Guardrail #6).
    """
    assert silicon.probe_buffer_mib(512, 32 * 1024 * 1024, 2) == 512
    assert silicon.probe_buffer_mib(1024, 32 * 1024 * 1024, 2) == 1024


def test_a_machine_that_reports_no_cache_keeps_the_floor_rather_than_losing_the_probe() -> None:
    """An unknown cache is not a small one, and there is nothing else to derive from."""
    assert silicon.probe_buffer_mib(512, None, 2) == 512


def test_the_off_switch_survives_a_machine_with_a_large_cache() -> None:
    """Zero says do not probe. A derivation that overrode it would take the knob away."""
    assert silicon.probe_buffer_mib(0, 480 * 1024 * 1024, 2) == 0


def test_a_cache_that_is_not_a_whole_number_of_mib_is_still_cleared() -> None:
    """Rounding down would leave the buffer inside the cache, which is the whole defect."""
    odd = 3 * 1024 * 1024 + 1

    assert silicon.probe_buffer_mib(1, odd, 2) * 1024 * 1024 >= 2 * odd


def test_the_row_records_the_buffer_it_probed_and_not_the_floor_it_was_handed(
    tmp_path: Path,
) -> None:
    """`memcpy_probe_mib` is what says whether a rate measured memory or cache.

    Small sizes on purpose: this checks the derived figure reached both the copy
    and the column, never what this machine is worth.
    """
    row = silicon.read_row(
        date="2026-09-16",
        run_id="2026-09-16-1",
        job=ServerJob.WORK,
        shard=0,
        probe_floor_mib=1,
        probe_cache_multiple=2,
        ask_placement=False,
        cpuinfo=CPUINFO_MILAN,
        cache_root=a_cache_tree(tmp_path, "4M"),
    )

    assert row.l3_cache_bytes == 4 * 1024 * 1024
    assert row.memcpy_probe_mib == 8, "the 1 MiB floor it was handed would have measured cache"
    assert row.memcpy_gib_s is not None


def test_uptime_is_the_first_field_and_a_missing_file_is_not_a_zero() -> None:
    """A pooled machine and a fresh one are different facts; unknown is a third."""
    assert silicon.boot_seconds("1234.56 9876.54\n") == 1234.56
    assert silicon.boot_seconds("") is None


def test_the_bench_can_ask_for_the_model_name_on_its_own() -> None:
    """The server case records which machine it drew, so a dossier can name it."""
    assert silicon.host_cpu_model(CPUINFO_MILAN) == "AMD EPYC 7763 64-Core Processor"
    assert silicon.host_cpu_model("") is None


def test_the_stage_files_this_job_its_own_raw_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ten jobs of one run record a machine, so none of them may open one file.

    The row goes through the ledger door, which names the file for its writer:
    the run, the attempt, the job, the shard and the module that wrote it travel
    in the file's own envelope, so two writers cannot take one path and every
    reader settles them back into one day.

    The attempt is set here rather than left to the environment: this suite runs
    on Actions too, and a re-run of the CI job would otherwise put a 2 in the
    identity this test spells out.
    """
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    row = silicon.stage_fingerprint(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        settings=a_probe(),
        state_root=tmp_path,
        commit_sha=SEED_COMMIT,
        shard=2,
        job=ServerJob.WORK,
    )

    assert row is not None
    (written,) = raw_files(tmp_path)
    who = fingerprint_envelopes([written])[0].identity
    assert (who.run_id, who.attempt, who.job, who.shard) == ("2026-09-16-1", 1, ServerJob.WORK, 2)
    assert who.producer == silicon.PRODUCER
    assert who.git_sha == SEED_COMMIT, "a file says which commit wrote it"
    day = written.path.parent.relative_to(ledger.raw_root(tmp_path, LedgerName.HOST_FINGERPRINT))
    assert day.parts == ("2026", "09", "16"), "the tree has to be day sharded"
    assert settled(tmp_path) == [row], "a fingerprint nobody stored answers nothing next month"


def test_a_second_attempt_at_one_shard_writes_beside_the_first_and_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GitHub keeps the run id and increments the attempt, so the attempt is in the identity.

    Without it the second try would be read as the first - in exactly the case
    where the two disagree, because the first attempt is the one that died. Both
    files survive on disk, one work unit between them, and every reader keeps the
    higher attempt.
    """
    settings = a_probe()
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    silicon.stage_fingerprint(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        settings=settings,
        state_root=tmp_path,
        commit_sha=SEED_COMMIT,
        shard=0,
    )
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    second = silicon.stage_fingerprint(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        settings=settings,
        state_root=tmp_path,
        commit_sha=SEED_COMMIT,
        shard=0,
    )

    written = raw_files(tmp_path)
    assert sorted(envelope.identity.attempt for envelope in fingerprint_envelopes(written)) == [
        1, 2
    ]
    assert len({envelope.unit_id for envelope in fingerprint_envelopes(written)}) == 1, (
        "two tries at one work unit"
    )
    assert settled(tmp_path) == [second], "one machine, one row, however many attempts drew it"


def test_a_second_call_in_one_attempt_is_read_as_one_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A machine counted twice is exactly what would make the distribution lie.

    The two calls are one writer's two writes of one work unit in one attempt,
    and a reader keeps the later of those, never both.
    """
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    settings = a_probe()

    for _ in range(2):
        silicon.stage_fingerprint(
            date=FINGERPRINT_DAY,
            run_id=A_RUN_ID,
            settings=settings,
            state_root=tmp_path,
            commit_sha=SEED_COMMIT,
            shard=0,
            job=ServerJob.WORK,
        )

    assert len({envelope.unit_id for envelope in fingerprint_envelopes(raw_files(tmp_path))}) == 1, (
        "one writer, one work unit"
    )
    assert len(settled(tmp_path)) == 1, "one row, however many times the stage ran"


def test_the_switch_being_off_writes_nothing_and_still_returns(tmp_path: Path) -> None:
    """Guardrail #6: the behaviour has to change from config with no source edit."""
    settings = config.load()
    settings.app.observability.host_fingerprint = False

    row = silicon.stage_fingerprint(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        settings=settings,
        state_root=tmp_path,
        commit_sha=SEED_COMMIT,
        shard=0,
    )

    assert row is None
    assert not raw_files(tmp_path)
    assert not settled(tmp_path)


def test_a_row_survives_the_round_trip_through_the_ledger_shape(tmp_path: Path) -> None:
    """An empty cell has to read back as absent, never as a zero bandwidth.

    Read off the one raw file the writer left rather than through the settled
    reader, because that file is where the writer's own rendering lands.
    """
    row = silicon.read_row(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        job=ServerJob.WORK,
        shard=0,
        probe_floor_mib=0,
        probe_cache_multiple=2,
        ask_placement=False,
        cpuinfo=CPUINFO_XEON,
        online_cpu_list="0,1",
        cpu_root=cpu_topology(tmp_path / "sys-cpu", {0: (0, 0), 1: (0, 1)}),
        cache_root=a_cache_tree(tmp_path / "sys-cache", "4M"),
    )
    paths = ledger.persist(
        tmp_path,
        [row],
        ledger=LedgerName.HOST_FINGERPRINT,
        covers=FINGERPRINT_DAY,
        identity=WriterIdentity(
            run_id=A_RUN_ID,
            attempt=1,
            job=ServerJob.WORK,
            shard=0,
            producer="telemetry.silicon",
            git_sha=SEED_COMMIT,
        ),
    )

    (read,) = ledger.load(paths, model=HostFingerprintRow)

    assert read.memcpy_gib_s is None, "a probe that did not run is absent, not zero"
    assert read.memcpy_probe_mib == 0
    assert len(read.fingerprint or "") == 16


def test_the_probe_and_the_job_clock_settle_into_one_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Oracle: two halves of one key, no cell filled twice, one row a reader sees.

    The probe runs before the model server because the bandwidth reading wants an
    idle machine, and the job's own clock is only knowable once the job is over.
    The clock step reads back the row its own probe filed, fills the four cells
    only it can know, and files the whole row again as the same writer, so the
    reader keeps that later row in place of the half.

    What the clock adds is exactly its four cells: a cell the probe measured
    that came back changed would be the clock overwriting the machine.
    """
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    settings = a_probe()
    probe = silicon.stage_fingerprint(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        settings=settings,
        state_root=tmp_path,
        commit_sha=SEED_COMMIT,
        shard=2,
        job=ServerJob.WORK,
    )
    whole = silicon.stage_job_clock(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        settings=settings,
        state_root=tmp_path,
        commit_sha=SEED_COMMIT,
        shard=2,
        job=ServerJob.WORK,
        job_started_at=int(time.time()) - 5550,
        server_log_path=SERVER_LOG,
        metrics_path=SERVER_METRICS,
    )

    assert probe is not None and whole is not None
    changed = sorted(
        name for name, value in whole.csv_row().items() if value != probe.csv_row()[name]
    )
    assert changed == sorted(silicon.CLOCK_CELLS), (
        "the clock fills its own four cells and leaves every cell the probe measured alone"
    )

    (row,) = settled(tmp_path)

    assert row == whole
    assert row.fingerprint == probe.fingerprint
    assert row.measured_at == probe.measured_at
    assert row.job_seconds == 5550
    assert row.model_load_ms is not None and row.model_load_ms > 0
    assert row.server_prompt_tokens == 30538
    assert row.server_prompt_seconds == 2795.15
    assert row.shard == 2


def test_a_job_that_died_before_its_clock_leaves_a_usable_half_row(tmp_path: Path) -> None:
    """The degrade path, named: four empty cells rather than a row nobody can read.

    A shard killed at `run.shard_timeout_minutes` never reaches the clock step,
    and everything the probe measured about the machine is still true.
    """
    silicon.stage_fingerprint(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        settings=a_probe(),
        state_root=tmp_path,
        commit_sha=SEED_COMMIT,
        shard=0,
    )

    (row,) = settled(tmp_path)

    assert row.job_seconds is None
    assert row.model_load_ms is None
    assert row.csv_row()["job_seconds"] == ""


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
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        settings=a_probe(),
        state_root=tmp_path,
        commit_sha=SEED_COMMIT,
        shard=0,
        server_log_path=None,
    )

    assert clock is not None
    assert clock.job_seconds is None
    assert clock.model_load_ms is None
    assert clock.server_prompt_tokens is None
    assert clock.server_prompt_seconds is None
    assert clock.csv_row()["job_seconds"] == ""
    assert clock.fingerprint is None, "the clock half measured no machine and may not claim one"


def test_the_clock_is_a_later_write_of_the_probes_own_work_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One job, one writer, one work unit - the identity names the job and not the step.

    The door never edits a file, so the clock step files the whole row again
    under the identity its probe filed with. Every file of the day is then one
    work unit of one attempt, and a reader keeps the later write of it: one row
    a job, never a half-row beside a whole one.
    """
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    settings = a_probe()
    probe = silicon.stage_fingerprint(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        settings=settings,
        state_root=tmp_path,
        commit_sha=SEED_COMMIT,
        shard=0,
    )
    whole = silicon.stage_job_clock(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        settings=settings,
        state_root=tmp_path,
        commit_sha=SEED_COMMIT,
        shard=0,
        job_started_at=int(time.time()) - 60,
    )

    written = raw_files(tmp_path)
    assert len({envelope.unit_id for envelope in fingerprint_envelopes(written)}) == 1, (
        "one writer, one work unit"
    )
    assert {envelope.identity.attempt for envelope in fingerprint_envelopes(written)} == {1}
    assert probe is not None and whole is not None
    assert whole.fingerprint == probe.fingerprint, "the clock carries the probe's machine"
    assert settled(tmp_path) == [whole]


def test_the_switch_being_off_records_no_clock_either(tmp_path: Path) -> None:
    """Guardrail #6: one knob answers for the whole record, not for half of it."""
    settings = config.load()
    settings.app.observability.host_fingerprint = False

    clock = silicon.stage_job_clock(
        date=FINGERPRINT_DAY,
        run_id=A_RUN_ID,
        settings=settings,
        state_root=tmp_path,
        commit_sha=SEED_COMMIT,
        shard=0,
        job_started_at=1,
    )

    assert clock is None
    assert not raw_files(tmp_path)


def test_the_job_clock_and_the_model_load_are_decoded_off_a_real_capture() -> None:
    """The four-field llama-server stamp is what a hand-written decoder gets wrong.

    Driven over a real capture rather than a built string: the stamp is minutes,
    seconds, milliseconds and microseconds since the server's own process
    started, and it was decoded from a capture in the first place because the
    source does not say so.
    """
    text = SERVER_LOG.read_text(encoding="utf-8")

    loaded = silicon.model_load_ms(text)

    assert loaded is not None and loaded > 0
    assert silicon.job_seconds("2026-09-16T04:11:02Z", 1789531312) == 550
    assert silicon.job_seconds("2026-09-16T04:11:02Z", None) is None


def test_the_two_prompt_counters_are_read_off_one_table_and_never_a_second_copy() -> None:
    """The host row's second instrument, read off the wire names llama.cpp uses.

    Both readings come off `_SERIES`, so a llama.cpp rename is one edit and shows
    up as two empty cells rather than as two numbers that disagree with the row
    beside them. Driven over a real scrape: the wire names are llama.cpp's.
    """
    text = SERVER_METRICS.read_text(encoding="utf-8")

    assert silicon.server_prompt_totals(text) == (30538, 2795.15)


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
