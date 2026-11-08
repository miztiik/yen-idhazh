"""Exercise the actual Python-to-Bun machine helper and its owned loopback Hono application."""

import contextlib
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from local_api_host.propagate_trace_context import (
    OperationMetadata,
    create_child_operation,
    create_root_operation,
    read_trace_context,
)
from pydantic import ValidationError
from starlette.datastructures import Headers
from summary_eval_pipeline.control import (
    MACHINE_STARTUP_VERSION,
    HostReady,
    MachineStartup,
    MachineStartupPacket,
    ServiceStopped,
    encode_control_packet,
)
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.host_reader import MachineUsage, measurement_complete
from summary_eval_pipeline.services import OwnedService
from summary_evaluator.shared.bound_operation_metadata import maximum_worker_operation_metadata
from summary_evaluator_cases.contract_examples import REPOSITORY

from summary_eval_tests.machine_task_cases import (
    reserved_loopback_listener,
    stage_machine_run,
)
from summary_eval_tests.test_host_profile_reader_parity import (
    compare_projection,
    mapping,
    required_bun,
    resolve,
)
from summary_eval_tests.test_pipeline_control import full_startup
from summary_eval_tests.test_pipeline_lifetime import CHILD_STARTUP_MS


def test_real_machine_wrapper_reader_and_native_metadata_schema_match_python() -> None:
    startup = full_startup()
    packet = MachineStartupPacket(
        version=MACHINE_STARTUP_VERSION, startup=startup,
        operation_metadata=maximum_worker_operation_metadata(),
    )
    current = packet.model_dump(mode="json")
    metadata = packet.operation_metadata.model_dump(mode="json")
    missing_links = {key: value for key, value in metadata.items() if key != "links"}
    vectors = [
        current,
        startup.model_dump(mode="json"),
        {**current, "version": "2026-11-09"},
        {**current, "operation_metadata": None},
        {**current, "operation_metadata": missing_links},
        {**current, "operation_metadata": {**metadata, "traceState": None}},
        {**current, "operation_metadata": {**metadata, "parentSpanId": None}},
        {**current, "operation_metadata": {**metadata, "spanId": metadata["parentSpanId"]}},
        {**current, "operation_metadata": {**metadata, "traceState": "PrivateTraceCanary"}},
        {**current, "scorer": "hhem"},
        {**startup.model_dump(mode="json"), "operation_metadata": metadata},
        {key: value for key, value in current.items() if key != "operation_metadata"},
    ]
    script = (
        'import {z} from "./services/serve-pipeline-apis/node_modules/zod";'
        'import {MachineStartupSchema,readMachineStartup}'
        ' from "./tools/summary-eval/machine-task.ts";'
        "const vectors=await Bun.stdin.json();"
        "const values=vectors.map(value=>{"
        "try{return {accepted:true,value:readMachineStartup(value)}}"
        "catch(error){if(!(error instanceof z.ZodError))throw error;return {accepted:false}}});"
        "console.log(JSON.stringify({schema:z.toJSONSchema(MachineStartupSchema),values}));"
    )
    result = subprocess.run(
        [required_bun(), "-e", script], cwd=REPOSITORY,
        input=json.dumps(vectors), text=True, capture_output=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    native = mapping(json.loads(result.stdout))
    schema = mapping(native["schema"])
    assert schema["version"] == packet.version == "2026-11-08"
    python_schema = packet.model_json_schema()
    required = schema["required"]
    assert isinstance(required, list)
    assert set(required) == set(python_schema["required"])
    native_fields = mapping(schema["properties"])
    python_fields = mapping(python_schema["properties"])
    assert native_fields.keys() == python_fields.keys()
    compare_projection(
        native_fields["operation_metadata"], python_fields["operation_metadata"],
        schema, python_schema, "operation_metadata",
    )
    assert resolve(native_fields["operation_metadata"], schema)["version"] == "2026-11-03"
    values = native["values"]
    assert isinstance(values, list) and len(values) == len(vectors)
    for vector, returned in zip(vectors, values, strict=True):
        actual = mapping(returned)
        try:
            accepted = MachineStartup.model_validate_json(json.dumps(vector)).root
        except ValidationError:
            assert actual["accepted"] is False
        else:
            assert actual["accepted"] is True
            assert accepted.model_dump(mode="json") == actual["value"]
    legacy = mapping(values[1])
    assert "operation_metadata" not in mapping(legacy["value"])


@pytest.mark.parametrize("over_limit", [False, True])
def test_real_machine_packet_reader_checks_the_complete_escaped_wrapper_and_newline(
    over_limit: bool,
) -> None:
    packet = MachineStartupPacket(
        version=MACHINE_STARTUP_VERSION, startup=full_startup(),
        operation_metadata=maximum_worker_operation_metadata(),
    )
    line = encode_control_packet(packet, len(packet.model_dump_json().encode()) + 1)
    limit = len(line) - int(over_limit)
    script = (
        'import {Readable} from "node:stream";'
        'import {readPackets,readMachineStartup} from "./tools/summary-eval/machine-task.ts";'
        "const bytes=await Bun.stdin.bytes();"
        f"for await(const value of readPackets(Readable.from([Buffer.from(bytes)]),{limit}))"
        "console.log(JSON.stringify(readMachineStartup(value)));"
    )
    result = subprocess.run(
        [required_bun(), "-e", script], cwd=REPOSITORY, input=line,
        capture_output=True, timeout=30, check=False,
    )
    if over_limit:
        assert result.returncode != 0 and result.stdout == b""
        assert b"byte allowance" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == packet.model_dump(mode="json")


@pytest.mark.skipif(
    sys.platform != "linux", reason="The native machine collector requires Linux proc."
)
def test_serialized_python_packet_starts_stops_and_retains_native_http_machine_results(
    tmp_path: Path, capfd: pytest.CaptureFixture[str],
) -> None:
    packet, pipeline = stage_machine_run(tmp_path)
    assert packet.run is not None
    assert json.loads(packet.model_dump_json())["run"]["git_sha"] == packet.git_sha
    launch = create_child_operation(create_root_operation(trace_state="first=value"))
    issued = MachineStartupPacket(
        version=MACHINE_STARTUP_VERSION, startup=packet, operation_metadata=launch,
    )
    script = REPOSITORY / "tools" / "summary-eval" / "machine-task.ts"
    child = OwnedService(
        "host",
        [required_bun(), "run", "--no-install", str(script), str(tmp_path)],
        tmp_path,
        issued,
        None,
        pipeline,
    )
    try:
        ready = child.wait_ready(CHILD_STARTUP_MS)
        assert isinstance(ready, HostReady)
        assert ready.pid == child.process.pid and ready.profile_started
        assert ready.hardware.status == "collected"
        controls = json.loads(
            (tmp_path / pipeline.output_directory / "config" / "host-probes.json").read_bytes()
        )
        time.sleep(controls["task_profile"]["cpu_window_ms"] / 1000)
        child.finish_measurement("success")
        stopped = child.close(ready.lifecycle_timeout_ms + pipeline.host_stop_grace_ms)
        assert isinstance(stopped, ServiceStopped)
        assert stopped.clean and child.process.returncode == 0
        assert measurement_complete(stopped.machine)
        assert stopped.machine is not None and stopped.machine.outcome == "success"
        assert stopped.machine.end_reason == "explicit_stop"
        assert stopped.server is not None and stopped.server.startup == "ready"
        assert stopped.server.shutdown == "stopped" and stopped.server.exit_code == 0
        evidence = tmp_path / pipeline.output_directory / "logs" / "hono-server-machine.json"
        with evidence.open("rb") as stream:
            encoded = stream.read(pipeline.max_response_bytes + 1)
        assert len(encoded) <= pipeline.max_response_bytes
        native = json.loads(encoded)
        assert native["group"] == "machine" and native["run_id"] == packet.run.run_id
        profile = MachineUsage.model_validate_json(json.dumps(native["reported_profiles"][-1]))
        expected = profile.model_copy(update={"samples": (profile.samples[0], profile.samples[-1])})
        assert stopped.machine == expected
        native_events = [
            mapping(json.loads(line)) for line in capfd.readouterr().err.splitlines()
        ]
        contexts = [
            read_trace_context(Headers({
                key: value for key, value in event.items()
                if key in ("traceparent", "tracestate") and isinstance(value, str)
            }))
            for event in native_events if "traceparent" in event
        ]
        assert contexts and all(
            isinstance(context, OperationMetadata)
            and context.trace_id == launch.trace_id
            and context.trace_state == launch.trace_state
            for context in contexts
        )
        assert any(
            context is not None and context.span_id == launch.span_id for context in contexts
        )
    finally:
        if not child.closed:
            with contextlib.suppress(WorkflowError):
                child.close(pipeline.host_shutdown_timeout_ms)
        assert child.process.poll() is not None


@pytest.mark.parametrize(
    "failure",
    [
        "invalid_settings",
        pytest.param(
            "occupied_listener",
            marks=pytest.mark.skipif(
                sys.platform != "linux",
                reason="The native machine collector requires Linux proc.",
            ),
        ),
    ],
)
def test_real_helper_startup_failure_retains_safe_cause_without_adopting_another_listener(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    packet, pipeline = stage_machine_run(tmp_path)
    path = tmp_path / pipeline.output_directory / "config" / "hono-server.json"
    controls = json.loads(path.read_bytes())
    with reserved_loopback_listener() as (port, unrelated):
        controls["listeners"]["machine"]["port"] = (
            "PrivateMachineSettingsCanary" if failure == "invalid_settings" else port
        )
        path.write_text(json.dumps(controls), encoding="utf-8")
        script = REPOSITORY / "tools" / "summary-eval" / "machine-task.ts"
        child = OwnedService(
            "host",
            [required_bun(), "run", "--no-install", str(script), str(tmp_path)],
            tmp_path,
            packet,
            None,
            pipeline,
        )
        try:
            with pytest.raises(WorkflowError) as original:
                child.wait_ready(CHILD_STARTUP_MS)
            assert original.value.error.code == "STARTUP_FAILED"
            assert original.value.error.source_code == (
                "MACHINE_API_STARTUP_INVALID"
                if failure == "invalid_settings"
                else "TYPESCRIPT_API_BIND_FAILED"
            )
        finally:
            if not child.closed:
                with pytest.raises(WorkflowError):
                    child.close(pipeline.host_shutdown_timeout_ms)
        assert child.process.returncode == 1 and child.stopped is not None
        assert isinstance(child.stopped, ServiceStopped)
        assert child.stopped.error_code == original.value.error.source_code
        assert unrelated.poll() is None
    captured = capfd.readouterr()
    assert captured.out == ""
    assert "summary_machine_failed" in captured.err
    assert "PrivateMachineSettingsCanary" not in captured.err
    assert "ZodError" not in captured.err
    assert child.stopped.machine is None


@pytest.mark.skipif(
    sys.platform != "linux", reason="The native machine collector requires Linux proc."
)
def test_invalid_private_close_retains_native_cancelled_measurement_and_safe_failure(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    packet, pipeline = stage_machine_run(tmp_path)
    script = REPOSITORY / "tools" / "summary-eval" / "machine-task.ts"
    child = OwnedService(
        "host",
        [required_bun(), "run", "--no-install", str(script), str(tmp_path)],
        tmp_path,
        packet,
        None,
        pipeline,
    )
    try:
        assert isinstance(child.wait_ready(CHILD_STARTUP_MS), HostReady)
        assert child.process.stdin is not None
        child.process.stdin.write(b'{"kind":"stop","outcome":"PrivateInvalidCloseCanary"}\n')
        child.process.stdin.flush()
        with pytest.raises(WorkflowError) as failure:
            child.close(pipeline.host_shutdown_timeout_ms + pipeline.host_forced_stop_ms)
        assert failure.value.error.source_code
        assert isinstance(child.stopped, ServiceStopped) and child.stopped.error_code
        assert child.stopped.machine is not None
        assert child.stopped.machine.outcome == "cancelled"
        assert child.stopped.machine.end_reason == "service_stopped"
        assert not measurement_complete(child.stopped.machine)
    finally:
        if not child.closed:
            with contextlib.suppress(WorkflowError):
                child.close(pipeline.host_shutdown_timeout_ms)
        assert child.process.poll() is not None
    captured = capfd.readouterr()
    assert captured.out == "" and "summary_machine_failed" in captured.err
    assert "PrivateInvalidCloseCanary" not in captured.err


@pytest.mark.parametrize(
    "change",
    [{"version": "2026-11-04"}, {"version": "2026-11-07"}, {"scorer": "hhem"}],
)
def test_real_machine_bridge_rejects_other_families_and_scorer_fields(
    tmp_path: Path, change: dict[str, str],
) -> None:
    packet, pipeline = stage_machine_run(tmp_path)
    previous = {**packet.model_dump(mode="json"), **change}
    script = REPOSITORY / "tools" / "summary-eval" / "machine-task.ts"
    result = subprocess.run(
        [required_bun(), "run", "--no-install", str(script), str(tmp_path)],
        input=(json.dumps(previous) + "\n").encode("utf-8"),
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 1 and result.stdout == b""
    assert b"MACHINE_SETUP_FAILED" in result.stderr
    assert not (tmp_path / pipeline.output_directory / "logs" / "hono-server-machine.json").exists()
