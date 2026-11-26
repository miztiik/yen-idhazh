"""Does the model runtime fetch every declared file, prove it, and refuse the rest?"""

from __future__ import annotations

import hashlib
import http.client
import json
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
from contracts._fixtures import copy_config, entry_with
from support.paths import FIXTURES_DIR, read_text
from support.server import RecordedEndpoint

from idhazh.contracts.model_server_pin import MODEL_SERVER_PIN_VERSION, ModelServerPin
from idhazh.llm.server import ProbeRefusedError
from idhazh.telemetry.host import process_start_ticks
from utilities import model_refs, model_runtime, own_native_model

WEIGHTS = b"the weights, as bytes"
COMPANION = b"a draft head"

#: Where a fetched file lands, read off the reader rather than spelled again.
MODELS_DIR = Path(model_refs.MODELS_DIR)


def test_startup_refuses_a_runtime_that_does_not_hold_the_response_schema(tmp_path: Path) -> None:
    copy_config(tmp_path)
    config_root = tmp_path / "config"
    pointer_path = config_root / "idhazh.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    recorded = read_text(FIXTURES_DIR / "completions" / "ok.json").encode("utf-8")
    with RecordedEndpoint(200, recorded) as runtime:
        pointer["model_server"]["base_url"] = runtime.base_url
        pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
        with pytest.raises(ProbeRefusedError, match="decoder is not held"):
            model_runtime.describe_request(config_root, prove_runtime=True)
        assert runtime.served == 1


def _entry(**extra: object) -> dict[str, object]:
    """A summarize entry whose two files are the bytes below, not a real model."""
    return {
        "repo": "publisher/Model-GGUF",
        "revision": "0" * 40,
        "file": "model-Q4_K_M.gguf",
        "sha256": hashlib.sha256(WEIGHTS).hexdigest(),
        "id": "model-q4-k-m",
        "quantisation": "Q4_K_M",
        "byte_count": len(WEIGHTS),
        "companion_files": [
            {
                "repo": "publisher/Model-GGUF",
                "revision": "0" * 40,
                "file": "mtp-model.gguf",
                "sha256": hashlib.sha256(COMPANION).hexdigest(),
                "byte_count": len(COMPANION),
            }
        ],
        **extra,
    }


def _a_config_root(tmp_path: Path, entry: dict[str, object]) -> Path:
    root = tmp_path / "config"
    (root / "models").mkdir(parents=True, exist_ok=True)
    (root / "idhazh.json").write_text(
        json.dumps({"models_file": "models/candidate.json"}) + "\n", encoding="utf-8"
    )
    (root / "models" / "candidate.json").write_text(
        json.dumps({"summarizer": entry}) + "\n", encoding="utf-8"
    )
    return root


class _Served:
    """What the transport hands back, instead of a network this must never touch."""

    def __init__(self, bodies: dict[str, bytes]) -> None:
        self.bodies = bodies
        self.asked: list[str] = []

    def __call__(self, url: str, timeout: float = 0.0) -> Any:
        self.asked.append(url)
        body = self.bodies[url.split("?", 1)[0]]
        return _Body(body)


class _Body:
    def __init__(self, body: bytes) -> None:
        self._left = body

    def read(self, size: int) -> bytes:
        chunk, self._left = self._left[:size], self._left[size:]
        return chunk

    def __enter__(self) -> _Body:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def _serving(monkeypatch: pytest.MonkeyPatch, entry: dict[str, object]) -> _Served:
    """Both declared files at the addresses the program composes for them."""
    files = entry["companion_files"]
    assert isinstance(files, list)
    served = _Served(
        {
            model_runtime.HUB_RESOLVE.format(
                repo=entry["repo"], revision=entry["revision"], file=entry["file"]
            ).split("?", 1)[0]: WEIGHTS,
            model_runtime.HUB_RESOLVE.format(
                repo=files[0]["repo"], revision=files[0]["revision"], file=files[0]["file"]
            ).split("?", 1)[0]: COMPANION,
        }
    )
    monkeypatch.setattr(urllib.request, "urlopen", served)
    return served


def test_explicit_download_and_verify_use_the_same_named_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _a_config_root(tmp_path, _entry())
    selected = "models/selected.json"
    (root / "models" / "candidate.json").rename(root / selected)
    monkeypatch.chdir(tmp_path)
    MODELS_DIR.mkdir(parents=True)
    (MODELS_DIR / "model-Q4_K_M.gguf").write_bytes(WEIGHTS)
    (MODELS_DIR / "mtp-model.gguf").write_bytes(COMPANION)

    model_runtime.download_model_files(root, models_file=selected)
    model_runtime.verify_model_files(root, models_file=selected)
    with pytest.raises(SystemExit, match="explicitly name one file"):
        model_runtime.verify_model_files(root, models_file="")


def test_owned_startup_validates_the_named_bytes_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = copy_config(tmp_path)
    root = tmp_path / "config"
    selected = "models/selected.json"
    (root / legacy).unlink()
    entry = _entry(declared_for=hashlib.sha256(WEIGHTS).hexdigest())
    (root / selected).write_text(json.dumps(entry_with(**entry)), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    MODELS_DIR.mkdir(parents=True)
    (MODELS_DIR / "model-Q4_K_M.gguf").write_bytes(WEIGHTS[::-1])
    (MODELS_DIR / "mtp-model.gguf").write_bytes(COMPANION)

    with (
        pytest.raises(SystemExit, match="hashes"),
        model_runtime.own_native_model(root, models_file=selected, startup_seconds=1),
    ):
        pytest.fail("damaged bytes must not start a child")


def test_native_props_must_identify_the_full_path_and_alias(tmp_path: Path) -> None:
    pin = ModelServerPin(
        version=MODEL_SERVER_PIN_VERSION, pid=1, start_ticks=1, started_at="2026-11-26T00:00:00Z",
    )
    weights = tmp_path / "model.gguf"
    model = own_native_model.OwnedNativeModel(
        pin, "http://127.0.0.1:8080", "ours", weights, "a" * 64, True,
    )

    def check(path: str, alias: str) -> None:
        body = json.dumps({"model_path": path, "model_alias": alias}).encode()
        own_native_model._require_loaded_model(body, model)

    check(str(weights), "ours")
    for path, alias in [(weights.name, "ours"), (str(weights), "other")]:
        with pytest.raises(RuntimeError, match="selected model path and alias"):
            check(path, alias)


def test_reap_owned_child_waits_for_the_actual_process() -> None:
    with subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.buffer.read()"],
        stdin=subprocess.PIPE,
    ) as child:
        forced = own_native_model.reap_owned_child(child, shutdown_seconds=3, forced_exit_seconds=3)
        assert not forced and child.returncode is not None


@pytest.mark.skipif(sys.platform != "linux", reason="Native ownership uses Linux process evidence.")
def test_owned_model_observes_recorded_counters_before_cancel_reaps_the_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    # Replay the native wire boundary in a real child, without running model inference.
    serve_recording = dedent("""\
        import json
        import sys
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from pathlib import Path

        port, weights, metrics = sys.argv[1:]
        responses = {
            "/health": b'{"status":"ok"}',
            "/props": json.dumps({"model_path": weights, "model_alias": "selected"}).encode(),
            "/metrics": Path(metrics).read_bytes(),
        }

        class NativeRecording(BaseHTTPRequestHandler):
            def do_GET(self):
                body = responses[self.path]
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        HTTPServer(("127.0.0.1", int(port)), NativeRecording).serve_forever()
    """)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
    weights = tmp_path / "selected.gguf"
    recorded = FIXTURES_DIR / "runtime" / "2026-08-26-5-shard-0.prom"
    command = own_native_model.parent_bound_command([
        sys.executable, "-c", serve_recording, str(port), str(weights), str(recorded),
    ])
    monkeypatch.chdir(tmp_path)

    with pytest.raises(KeyboardInterrupt), own_native_model._own_native_child(
        command, f"http://127.0.0.1:{port}", "selected", weights, "a" * 64, True,
        startup_seconds=10, library_dir=tmp_path,
    ) as model:
        pin = model.pin
        assert process_start_ticks(pin.pid) == pin.start_ticks
        measurement = model.observe("cancelled")
        assert measurement is not None
        assert measurement["subject_id"] == "selected"
        assert measurement["server_prompt_tokens"] == 30538
        assert own_native_model.SERVING_COUNTERS_PATH.read_bytes() == recorded.read_bytes()
        # Sampling does not close the listener or release ownership.
        model.assert_owned()
        raise KeyboardInterrupt

    assert process_start_ticks(pin.pid) is None
    events = [json.loads(line) for line in capsys.readouterr().err.splitlines()
              if line.startswith("{")]
    assert [event["data"]["action"] for event in events] == ["started", "ready", "stopped"]
    assert all(event["specversion"] == "1.0" and event["source"] == "/llama-server"
               for event in events)


@pytest.mark.parametrize("filename", ["mtp-model.gguf", "MTP/mtp-model.gguf"])
def test_the_download_fetches_every_file_the_entry_declares(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str
) -> None:
    """The cache key digests every declared file, so a download of fewer is a broken entry.

    An entry that keyed on two files and fetched one would save complete and
    restore complete, and llama-server then exits at load rather than at fetch -
    on a different machine, hours later, with nothing between the two saying so.
    """
    entry = _entry()
    companions = entry["companion_files"]
    assert isinstance(companions, list)
    companions[0]["file"] = filename
    served = _serving(monkeypatch, entry)
    monkeypatch.chdir(tmp_path)

    model_runtime.download_model_files(_a_config_root(tmp_path, entry))

    assert len(served.asked) == 2, served.asked
    landed = MODELS_DIR
    assert (landed / "model-Q4_K_M.gguf").read_bytes() == WEIGHTS
    assert (landed / filename).read_bytes() == COMPANION
    assert not (landed / "model-Q4_K_M.gguf.part").exists()
    assert not (landed / (filename + ".part")).exists()
    model_runtime.verify_model_files(_a_config_root(tmp_path, entry))


def test_a_file_whose_digest_is_wrong_is_refused_and_not_left_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bytes that arrived are not the bytes the entry named, so nothing may keep them.

    A `.part` left under the cache path would be saved with the entry and
    restored by every later run, which is the failure writing to a part file
    exists to prevent.
    """
    entry = _entry(sha256="a" * 64)
    _serving(monkeypatch, entry)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit, match="its entry declares"):
        model_runtime.download_model_files(_a_config_root(tmp_path, entry))

    assert not list(MODELS_DIR.glob("*")), "nothing may survive"


def test_a_file_that_is_already_here_and_wrong_is_refused_rather_than_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file under the cache path that is not what the entry declares is a finding.

    Overwriting would hide it. The run that put it there is the run worth
    knowing about, and a silent repair means nobody ever does.
    """
    entry = _entry()
    _serving(monkeypatch, entry)
    monkeypatch.chdir(tmp_path)
    landed = MODELS_DIR
    landed.mkdir(parents=True)
    (landed / "model-Q4_K_M.gguf").write_bytes(b"something else entirely")

    with pytest.raises(SystemExit, match="is already here"):
        model_runtime.download_model_files(_a_config_root(tmp_path, entry))

    assert (landed / "model-Q4_K_M.gguf").read_bytes() == b"something else entirely"


def test_a_file_that_is_already_correct_is_kept_rather_than_fetched_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A retry after a half-finished download pays for what is missing and nothing else."""
    entry = _entry()
    served = _serving(monkeypatch, entry)
    monkeypatch.chdir(tmp_path)
    landed = MODELS_DIR
    landed.mkdir(parents=True)
    (landed / "model-Q4_K_M.gguf").write_bytes(WEIGHTS)

    model_runtime.download_model_files(_a_config_root(tmp_path, entry))

    assert len(served.asked) == 1, "the file already here must not be downloaded again"


def test_the_check_covers_every_declared_file_on_a_cache_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one check that runs when nothing was downloaded, so it reads the declaration.

    It was handed two filenames through the environment - the weights and one
    companion - while the key digested every file the entry declared. An entry
    with two companions keyed on three and checked two.
    """
    entry = _entry()
    monkeypatch.chdir(tmp_path)
    landed = MODELS_DIR
    landed.mkdir(parents=True)
    (landed / "model-Q4_K_M.gguf").write_bytes(WEIGHTS)
    root = _a_config_root(tmp_path, entry)

    with pytest.raises(SystemExit, match="declared and is not here"):
        model_runtime.verify_model_files(root)

    (landed / "mtp-model.gguf").write_bytes(COMPANION)
    model_runtime.verify_model_files(root)

    (landed / "mtp-model.gguf").write_bytes(COMPANION + b"!")
    with pytest.raises(SystemExit, match="its entry declares"):
        model_runtime.verify_model_files(root)


def test_a_declared_size_that_disagrees_with_the_file_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The size checks the document, where the digest checks the bytes.

    A digest settles what arrived. It says nothing about whether the entry a
    person edited describes the model they meant, and a byte count in the wrong
    entry is the cheapest way to notice.
    """
    entry = _entry(byte_count=len(WEIGHTS) + 1)
    monkeypatch.chdir(tmp_path)
    landed = MODELS_DIR
    landed.mkdir(parents=True)
    (landed / "model-Q4_K_M.gguf").write_bytes(WEIGHTS)
    (landed / "mtp-model.gguf").write_bytes(COMPANION)

    with pytest.raises(SystemExit, match="bytes"):
        model_runtime.verify_model_files(_a_config_root(tmp_path, entry))


@pytest.mark.parametrize(
    ("error", "again"),
    [
        (urllib.error.URLError("reset"), True),
        (ConnectionResetError("reset"), True),
        (http.client.IncompleteRead(b"half"), True),
        (TimeoutError("slow"), True),
        (urllib.error.HTTPError("u", 503, "busy", {}, None), True),  # type: ignore[arg-type]
        (urllib.error.HTTPError("u", 429, "slow down", {}, None), True),  # type: ignore[arg-type]
        (urllib.error.HTTPError("u", 404, "gone", {}, None), False),  # type: ignore[arg-type]
        (urllib.error.HTTPError("u", 403, "no", {}, None), False),  # type: ignore[arg-type]
    ],
)
def test_only_a_failure_another_connection_could_fix_is_retried(
    error: Exception, again: bool
) -> None:
    """A 4xx is the server saying the request was wrong, and asking again is the same request.

    `IncompleteRead` is in the retried set and is not an `OSError`, which is the
    one that a catch written from memory drops.
    """
    assert model_runtime._retriable(error) is again


def test_the_byte_download_sends_no_request_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CPython copies a header onto a cross-host redirect target with no host check.

    Both the hub and the release CDN redirect, so a token added here would
    follow the redirect to somebody else's server. Only the release lookup sets
    one, and it is the only call in the module that may.
    """
    seen: list[object] = []

    def watching(url: object, timeout: float = 0.0) -> Any:
        seen.append(url)
        return _Body(WEIGHTS)

    monkeypatch.setattr(urllib.request, "urlopen", watching)
    model_runtime._download("https://example.invalid/w.gguf", tmp_path / "w.gguf")

    assert seen == ["https://example.invalid/w.gguf"], "the download must pass a bare address"

    source = Path(model_runtime.__file__).read_text(encoding="utf-8")
    holders = [
        line for line in source.splitlines() if "Authorization" in line and "#" not in line.strip()[:1]
    ]
    assert len(holders) == 1, f"exactly one call may set a header: {holders}"
