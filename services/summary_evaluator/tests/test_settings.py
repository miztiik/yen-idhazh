"""Prove startup-only validation and request default resolution from one named file."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError
from summary_evaluator_cases.contract_examples import (
    API_SETTINGS_FILE,
    REPOSITORY,
    SETTINGS_FILE,
    read_contract,
)

from summary_evaluator.hhem.contracts.error_detail import project_request_error
from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.hhem.load_settings import SettingsLoadError
from summary_evaluator.hhem.resolve_request import RequestResolutionError, resolve_request
from summary_evaluator.serve_http.api_settings import (
    ApiSettingsLoadError,
    load_api_settings,
    load_scorer_api_settings,
)
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent, ApiSettings
from summary_evaluator.serve_http.load_scorer_settings import load_hhem_settings as load_settings
from summary_evaluator.shared.contracts.service_settings import StartupContext


def test_committed_settings_are_complete_and_do_not_install_the_backend_or_model() -> None:
    settings = load_settings(SETTINGS_FILE)
    assert settings.version == "2026-11-02"
    assert settings.enabled
    assert settings.scoring.chunk_words == 5000
    assert settings.scoring.chunk_overlap_words == 500
    assert settings.scoring.max_windows_per_comparison == 256
    assert not settings.response.hhem_full
    assert not settings.response.include_window_details
    assert settings.listener.host == "127.0.0.1"
    assert settings.listener.port == 3010
    assert settings.listener.max_body_bytes == 1048576
    assert settings.listener.body_read_timeout_ms == 5000
    assert settings.queue.capacity == 8
    assert settings.queue.wait_timeout_ms == 60000
    assert settings.queue.retry_after_seconds == 2
    assert settings.evaluation.timeout_ms == 120000
    assert settings.worker.startup_timeout_ms == 600000
    assert settings.worker.replacement_timeout_ms == 120000
    assert settings.worker.stop_grace_ms == 5000
    assert settings.worker.forced_stop_ms == 5000
    assert settings.worker.shutdown_timeout_ms == 15000
    assert settings.worker.max_proc_identity_bytes == 4096
    assert settings.logging.level == "INFO"
    assert settings.logging.max_event_bytes == 4096
    assert settings.hhem.cache_directory == "services/summary_evaluator/var/model-cache"
    assert settings.hhem.model.revision == "8e4a2e6e96c708cc76c2344f7e4757df2515292c"
    assert settings.hhem.foundation.revision == "7bcac572ce56db69c1ea7c8af255c5d7c9672fc2"
    assert settings.hhem.model.files == (
        "config.json",
        "configuration_hhem_v2.py",
        "modeling_hhem_v2.py",
        "model.safetensors",
    )
    assert settings.hhem.foundation.files == (
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "spiece.model",
    )
    assert importlib.util.find_spec("torch") is None
    isolated = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import importlib.util; import io; import sys; "
            "from pathlib import Path; "
            "from summary_evaluator.serve_http.api_settings import load_scorer_api_settings; "
            "from summary_evaluator.serve_http.emit_events import EventWriter; "
            "from summary_evaluator.serve_http.load_scorer_settings import load_hhem_settings; "
            "from summary_evaluator.serve_http.serve_api import create_app; "
            "assert importlib.util.find_spec('idhazh') is None; "
            "assert importlib.util.find_spec('torch') is None; "
            "api = load_scorer_api_settings(Path(sys.argv[1]),'hhem'); "
            "root = Path(sys.argv[2]); "
            "settings = load_hhem_settings(Path(sys.argv[3]), api); "
            "writer = EventWriter(api.logging, io.StringIO()); "
            "app = create_app(api, settings, root, writer=writer); "
            "assert app.state.controller.worker.process is None; "
            "assert app.state.unieval is None; "
            "assert not {'torch', 'transformers', 'nltk'} & sys.modules.keys()",
            str(API_SETTINGS_FILE),
            str(REPOSITORY),
            str(SETTINGS_FILE),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert isolated.returncode == 0, isolated.stderr


@pytest.mark.parametrize(
    ("module", "forbidden"),
    [
        (
            "summary_evaluator.shared.queue_evaluations",
            ("summary_evaluator.hhem", "summary_evaluator.unieval", "summary_evaluator.serve_http"),
        ),
        (
            "summary_evaluator.hhem.control_service",
            ("summary_evaluator.unieval", "summary_evaluator.serve_http"),
        ),
        (
            "summary_evaluator.unieval.control_unieval",
            ("summary_evaluator.hhem", "summary_evaluator.serve_http"),
        ),
        (
            "summary_evaluator.shared.create_api_component",
            (
                "summary_evaluator.hhem",
                "summary_evaluator.unieval",
                "summary_evaluator.serve_http",
            ),
        ),
        (
            "summary_evaluator.hhem.create_api_component",
            (
                "summary_evaluator.unieval",
                "summary_evaluator.serve_http",
            ),
        ),
        (
            "summary_evaluator.unieval.create_api_component",
            (
                "summary_evaluator.hhem",
                "summary_evaluator.serve_http",
            ),
        ),
    ],
)
def test_installed_children_import_only_their_declared_dependencies(
    module: str, forbidden: tuple[str, ...]
) -> None:
    isolated = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import importlib,sys; importlib.import_module(sys.argv[1]); "
            "assert not any(name.startswith(tuple(sys.argv[2:])) for name in sys.modules)",
            module,
            *forbidden,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert isolated.returncode == 0, isolated.stderr


def test_settings_freeze_the_effective_snapshot_not_the_file(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_bytes(SETTINGS_FILE.read_bytes())
    api = load_scorer_api_settings(API_SETTINGS_FILE, "hhem")
    settings = load_settings(path, api)
    changed = settings.model_dump(mode="json", exclude={"enabled", "listener", "logging"})
    changed["scoring"]["chunk_words"] = 1500
    changed["response"]["include_window_details"] = True
    changed["response"]["hhem_full"] = True
    path.write_text(json.dumps(changed), encoding="utf-8")
    request = EvaluateRequest(
        source_text=" Source. ", summary_text="Summary.", full_source_text=" Full source. "
    )
    original = resolve_request(request, settings)
    current = resolve_request(request, load_settings(path, api))
    assert original.chunk_words == 5000
    assert not original.hhem_full
    assert not original.include_window_details
    assert current.chunk_words == 1500
    assert current.hhem_full
    assert current.include_window_details


@pytest.mark.parametrize("field", ["chunk_words", "chunk_overlap_words"])
def test_nested_startup_settings_are_frozen(field: str) -> None:
    settings = load_settings(SETTINGS_FILE)
    with pytest.raises(ValidationError, match="frozen"):
        setattr(settings.scoring, field, 2000)


def test_defaults_resolve_before_geometry_validation_and_text_is_not_substituted() -> None:
    settings = load_settings(SETTINGS_FILE)
    override = EvaluateRequest(
        source_text=" Source. ",
        summary_text="\nSummary. ",
        chunk_words=1500,
        chunk_overlap_words=900,
        hhem_full=False,
        include_window_details=True,
        full_source_text=" An unused full source. ",
    )
    effective = resolve_request(override, settings)
    assert (effective.chunk_words, effective.chunk_overlap_words) == (1500, 900)
    assert not effective.hhem_full
    assert effective.include_window_details
    assert override.source_text == " Source. "
    assert override.summary_text == "\nSummary. "
    assert override.full_source_text == " An unused full source. "
    with pytest.raises(RequestResolutionError) as failure:
        resolve_request(
            EvaluateRequest(source_text="Source.", summary_text="Summary.", chunk_words=100),
            settings,
        )
    assert failure.value.error.field == "chunk_overlap_words"
    with pytest.raises(RequestResolutionError) as failure:
        resolve_request(
            EvaluateRequest(
                source_text="Source.", summary_text="Summary.", chunk_overlap_words=5000
            ),
            settings,
        )
    assert failure.value.error.field == "chunk_overlap_words"


@pytest.mark.parametrize(("size", "overlap"), [(0, 0), (-1, 0), (1, -1), (100, 100), (100, 101)])
def test_invalid_resolved_geometry_is_a_safe_refusal(size: int, overlap: int) -> None:
    with pytest.raises((RequestResolutionError, ValidationError)) as failure:
        request = EvaluateRequest(
            source_text="Source.",
            summary_text="Summary.",
            chunk_words=size,
            chunk_overlap_words=overlap,
        )
        resolve_request(request, load_settings(SETTINGS_FILE))
    if isinstance(failure.value, RequestResolutionError):
        error = failure.value.error
    else:
        assert isinstance(failure.value, ValidationError)
        error = project_request_error(failure.value)
    assert error.code == "INVALID_REQUEST"
    assert error.phase == "request"


def test_full_comparison_never_substitutes_primary_source() -> None:
    request = EvaluateRequest(
        source_text="Primary source.", summary_text="Summary.", hhem_full=True
    )
    with pytest.raises(RequestResolutionError) as failure:
        resolve_request(request, load_settings(SETTINGS_FILE))
    assert failure.value.error.field == "full_source_text"
    configured = load_settings(SETTINGS_FILE).model_dump(mode="json")
    configured["response"]["hhem_full"] = True
    settings = read_contract(ServiceSettings, configured)
    with pytest.raises(RequestResolutionError):
        resolve_request(EvaluateRequest(source_text="Source.", summary_text="Summary."), settings)
    effective = resolve_request(
        EvaluateRequest(
            source_text="Source.",
            summary_text="Summary.",
            full_source_text="Full source.",
            hhem_full=False,
        ),
        settings,
    )
    assert not effective.hhem_full


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("scoring", "chunk_words"), "900"),
        (("scoring", "chunk_words"), True),
        (("scoring", "chunk_overlap_words"), 5000),
        (("scoring", "max_windows_per_comparison"), 0),
        (("hhem", "model", "revision"), "main"),
        (("hhem", "foundation", "revision"), "short"),
        (("hhem", "model", "files"), ["../config.json"]),
        (("hhem", "foundation", "files"), ["config.json", "config.json"]),
        (("hhem", "cache_directory"), "C:\\cache"),
        (("hhem", "cache_directory"), "/tmp/cache"),
        (("hhem", "cache_directory"), "cache/../model"),
        (("listener", "host"), "0.0.0.0"),
        (("listener", "host"), "localhost"),
        (("listener", "port"), 65536),
        (("listener", "max_body_bytes"), 0),
        (("listener", "body_read_timeout_ms"), 0),
        (("queue", "capacity"), -1),
        (("queue", "wait_timeout_ms"), None),
        (("queue", "retry_after_seconds"), False),
        (("evaluation", "timeout_ms"), 0),
        (("worker", "startup_timeout_ms"), 0),
        (("worker", "shutdown_timeout_ms"), 9999),
        (("worker", "max_proc_identity_bytes"), 0),
        (("worker", "compute_threads"), 1),
        (("worker", "interop_threads"), 1),
        (("worker", "memory_limit_bytes"), 1048576),
        (("worker", "cpu_affinity"), [0]),
        (("logging", "max_event_bytes"), 0),
        (("logging", "level"), "verbose"),
        (("response", "hhem_full"), 1),
    ],
)
def test_invalid_settings_fail_with_the_setting_named(
    path: tuple[str, ...], value: object, tmp_path: Path
) -> None:
    shared = load_scorer_api_settings(API_SETTINGS_FILE, "hhem")
    is_shared = path[0] in ("listener", "logging")
    payload = (
        shared.model_dump(mode="json")
        if is_shared
        else load_settings(SETTINGS_FILE).model_dump(
            mode="json", exclude={"enabled", "listener", "logging"}
        )
    )
    current = payload
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = value
    file = tmp_path / "settings.json"
    file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises((SettingsLoadError, ApiSettingsLoadError)) as failure:
        if is_shared:
            load_api_settings(file)
        else:
            load_settings(file, shared)
    assert path[0] in str(failure.value)
    assert str(tmp_path) not in str(failure.value)


def test_missing_settings_have_no_source_or_environment_fallback(tmp_path: Path) -> None:
    shared = load_scorer_api_settings(API_SETTINGS_FILE, "hhem")
    payload = load_settings(SETTINGS_FILE).model_dump(
        mode="json", exclude={"enabled", "listener", "logging"}
    )
    del payload["hhem"]["model"]["reference"]
    file = tmp_path / "settings.json"
    file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SettingsLoadError, match="hhem.model.reference"):
        load_settings(file, shared)
    with pytest.raises(SettingsLoadError, match="Could not read"):
        load_settings(tmp_path / "absent.json", shared)
    file.write_text("{", encoding="utf-8")
    with pytest.raises(SettingsLoadError, match="settings"):
        load_settings(file, shared)


@pytest.mark.parametrize("routes", [("hhem",), ()])
def test_selected_listener_is_the_only_authority_and_disabled_snapshots_are_explicit(
    routes: tuple[str, ...],
) -> None:
    shared = load_scorer_api_settings(API_SETTINGS_FILE, "hhem")
    assert shared.listener.host == "127.0.0.1" and shared.listener.port == 3010
    assert shared.enabled_routes == ("hhem",)
    selected = ApiSettings.model_validate_json(
        shared.model_copy(
            update={
                "enabled_routes": routes,
                "listener": shared.listener.model_copy(update={"port": 3011}),
            }
        ).model_dump_json()
    )
    frozen = load_settings(SETTINGS_FILE, selected)
    assert frozen.enabled == ("hhem" in routes)
    assert frozen.listener.port == 3011
    assert load_settings(SETTINGS_FILE).listener.port == 3010


@pytest.mark.parametrize(
    "change",
    [
        {"enabled_routes": ["llama"]},
        {"enabled_routes": ["hhem", "llama"]},
        {"enabled_routes": ["coverage"]},
        {"llama": {"connect_timeout_ms": 5000}},
        {"version": "2026-11-04"},
    ],
)
def test_retired_generation_settings_and_previous_application_version_are_refused(
    change: dict[str, object],
) -> None:
    shared = load_scorer_api_settings(API_SETTINGS_FILE, "hhem")
    with pytest.raises(ValidationError):
        ApiSettings.model_validate_json(json.dumps({**shared.model_dump(mode="json"), **change}))


@pytest.mark.parametrize(
    "options",
    [["--routes", "llama"], ["--routes", "coverage"], ["--model-config", "retired.json"]],
)
def test_retired_generation_cli_values_are_refused_before_configuration_reads(
    options: list[str], tmp_path: Path
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "summary_evaluator",
            "--root",
            str(tmp_path),
            "--settings",
            str(tmp_path / "absent.json"),
            *options,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 2
    assert "invalid choice" in result.stderr or "unrecognized arguments" in result.stderr
    assert "INVALID_SERVER_SETTINGS" not in result.stderr


@pytest.mark.parametrize("component", get_args(ApiComponent))
def test_declared_cli_choices_reach_settings_validation(
    component: ApiComponent, tmp_path: Path
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "summary_evaluator",
            "--root",
            str(tmp_path),
            "--routes",
            component,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 2
    assert "INVALID_SERVER_SETTINGS" in result.stderr
    assert "invalid choice" not in result.stderr


@pytest.mark.parametrize("field", ["enabled", "listener", "logging"])
def test_old_authored_listener_and_flag_fields_are_refused(field: str, tmp_path: Path) -> None:
    payload = json.loads(SETTINGS_FILE.read_bytes())
    payload[field] = load_settings(SETTINGS_FILE).model_dump(mode="json")[field]
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SettingsLoadError, match=field):
        load_settings(path, load_scorer_api_settings(API_SETTINGS_FILE, "hhem"))


@pytest.mark.parametrize("value", ["", "two words", "../run", "run\nid", "r" * 129, "\u00e9"])
def test_startup_context_accepts_only_bounded_ascii_identities(value: str) -> None:
    with pytest.raises(ValidationError):
        StartupContext(run_id=value)


def test_optional_context_is_separate_from_scoring_configuration() -> None:
    assert StartupContext().model_dump() == {
        "run_id": None,
        "pipeline_name": None,
        "task_name": None,
    }
    context = StartupContext(run_id="12345", pipeline_name="hhem-evaluation", task_name="score")
    assert context.run_id == "12345"
    with pytest.raises(ValidationError):
        ServiceSettings.model_validate_json(
            json.dumps({**load_settings(SETTINGS_FILE).model_dump(mode="json"), "run_id": "12345"})
        )
