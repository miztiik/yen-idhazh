"""Which actual Python populations and sample coverage belong to each native window?"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from uuid import UUID

from idhazh.contracts.host_events import (
    HostEvent,
    LegacyJobSample,
    LegacyProcessRollcall,
    MonitorReadyBody,
    StoppedBody,
    WindowBegunBody,
    WindowBody,
    WindowResultBody,
    WorkerBody,
)
from idhazh.contracts.host_evidence import (
    EvidenceSession,
    ReferenceSample,
    SamplerCompletion,
    WindowSampleCoverage,
    WorkloadResult,
)
from idhazh.telemetry.host_evidence_inputs import ComparisonSettings, read_bytes, read_model


def resource_chain(workspace: Path, session: EvidenceSession) -> tuple[UUID, ...]:
    manifest = session.manifest
    maximum = manifest.limits.max_result_bytes
    ready = read_model(workspace / "ready.json", HostEvent, maximum)
    observed = tuple(
        read_model(workspace / f"observed/{index}.json", HostEvent, maximum)
        for index in range(1 + len(manifest.windows) * 2)
    )
    stopped = read_model(workspace / "drained.json", HostEvent, maximum)
    events = (ready, *observed, stopped)
    if any(
        any(
            getattr(event, name) != getattr(manifest, name)
            for name in ("date", "run_id", "attempt", "job", "shard", "session_id")
        )
        or event.emitter_id != manifest.monitor_emitter_id
        for event in events
    ):
        raise ValueError("received resource event identity differs from its session")
    if (
        ready.sequence != 1
        or len({event.event_id for event in events}) != len(events)
        or any(left.sequence >= right.sequence for left, right in pairwise(events))
    ):
        raise ValueError("received resource emitter ordering is duplicated or reversed")
    if (
        not isinstance(ready.body, MonitorReadyBody)
        or ready.body.boot_id != manifest.boot_id
        or not isinstance(stopped.body, StoppedBody)
        or stopped.body.aborted_window_ids
        or not isinstance(observed[0].body, WorkerBody)
        or observed[0].body.target != manifest.cpu_target
    ):
        raise ValueError("resource readiness, registration or drain evidence differs")
    for index, result in enumerate(observed):
        if result.reply_to is None:
            raise ValueError("resource result lacks triggering command")
        command = read_model(
            workspace / f"commands/{result.reply_to}.json",
            HostEvent,
            manifest.limits.max_command_bytes,
        )
        expected_kind = (
            "worker.register" if index == 0 else ("window.begin" if index % 2 else "window.end")
        )
        if (
            command.kind != expected_kind
            or command.sequence != index + 1
            or command.emitter_id != manifest.workers[0].emitter_id
            or command.session_id != manifest.session_id
        ):
            raise ValueError("resource result contradicts the declared triggering command")
        if index == 0 and command.body != result.body:
            raise ValueError("registration ACK changed the actual worker declaration")
        if index:
            window = manifest.windows[(index - 1) // 2]
            if (
                not isinstance(result.body, (WindowBegunBody, WindowResultBody))
                or result.body.window_id != window.window_id
                or result.body.item_id != window.item_id
                or result.body.target != manifest.cpu_target
                or result.body.server is not None
            ):
                raise ValueError("resource result differs from its actual selected window")
            if (
                not isinstance(command.body, WindowBody)
                or command.body.model_dump()
                != result.body.model_dump(include=set(WindowBody.model_fields))
                or result.kind != ("window.begun" if index % 2 else "window.result")
            ):
                raise ValueError("window ACK changed its triggering window declaration")
    stop = read_model(workspace / "stop.json", HostEvent, manifest.limits.max_command_bytes)
    if stopped.reply_to != stop.event_id or stop.kind != "monitor.stop":
        raise ValueError("resource drain lacks its triggering stop command")
    return tuple(event.event_id for event in events)


def sample_coverage(
    workspace: Path,
    windows: tuple[WindowResultBody, ...],
    config: ComparisonSettings,
) -> tuple[int, tuple[WindowSampleCoverage, ...]]:
    samples = [
        LegacyJobSample.model_validate_json(line)
        for line in read_bytes(
            workspace / "native-artifacts/rss-samples.jsonl", config.max_artifact_bytes
        ).splitlines()
    ]
    roster = [
        LegacyProcessRollcall.model_validate_json(line)
        for line in read_bytes(
            workspace / "native-artifacts/python-procs.jsonl", config.max_artifact_bytes
        ).splitlines()
    ]
    populations: list[set[int]] = []
    cursor = 0
    for sample in samples:
        rows = roster[cursor : cursor + sample.python_procs]
        cursor += sample.python_procs
        if len(rows) != sample.python_procs or any(
            row.ts != sample.ts or not row.comm.startswith("python") for row in rows
        ):
            raise ValueError("native sample population disagrees with its rollcall")
        if len({row.pid for row in rows}) != len(rows):
            raise ValueError("native rollcall counts a process twice")
        if sum(row.vmrss_kb for row in rows) != sample.python_vmrss_kb:
            raise ValueError("native sample RSS differs from its actual Python population")
        if sum(row.vmhwm_kb or row.vmrss_kb for row in rows) != sample.python_vmhwm_kb:
            raise ValueError("native HWM differs from its actual Python population")
        populations.append({row.pid for row in rows})
    if cursor != len(roster):
        raise ValueError("unaccounted native population records")
    coverage: list[WindowSampleCoverage] = []
    for window in windows:
        if window.opened_at is None or window.closed_at is None:
            raise ValueError("required native window endpoints are absent")
        indices = [
            index
            for index, sample in enumerate(samples)
            # Second-resolution legacy clocks cannot assign boundary samples.
            if window.opened_at < sample.ts < window.closed_at
        ]
        if len(indices) < config.min_window_samples:
            raise ValueError("required unambiguous native window sample coverage is absent")
        pids = set().union(*(populations[index] for index in indices))
        if window.target.pid not in pids:
            raise ValueError(
                "the selected live worker is absent from the sampled Python population"
            )
        coverage.append(
            WindowSampleCoverage(
                window_id=window.window_id,
                samples=len(indices),
                python_pids=tuple(sorted(pids)),
            )
        )
    return len(samples), tuple(coverage)


def reference_coverage(
    workspace: Path,
    rows: tuple[WorkloadResult, ...],
    config: ComparisonSettings,
) -> None:
    for row in rows:
        if row.mode != "reference":
            continue
        root = workspace / f"reference/samples-{row.sequence}"
        count = read_model(root / "count.json", SamplerCompletion, config.max_command_output_bytes)
        if (
            count.samples != row.samples
            or count.samples > 1 + config.worker_timeout_seconds / config.sample_interval_seconds
        ):
            raise ValueError("reference sample count differs from bounded completion evidence")
        first: ReferenceSample | None = None
        for index in range(count.samples):
            sample = read_model(
                root / f"sample-{index}.json", ReferenceSample, config.max_command_output_bytes
            )
            if first is None:
                first = sample
            pids = {target.pid for target in sample.population}
            if (
                row.target not in sample.population
                or pids != {record.pid for record in sample.rollcall}
                or len(pids) != len(sample.population)
                or sample.record.python_procs != len(pids)
                or any(record.ts != sample.record.ts for record in sample.rollcall)
                or any(not record.comm.startswith("python") for record in sample.rollcall)
                or sum(record.vmrss_kb for record in sample.rollcall)
                != sample.record.python_vmrss_kb
                or sum(record.vmhwm_kb or record.vmrss_kb for record in sample.rollcall)
                != sample.record.python_vmhwm_kb
            ):
                raise ValueError("retained reference sample contradicts its actual population")
        if first is None or first.population != row.population:
            raise ValueError("reported reference population differs from retained first sample")
