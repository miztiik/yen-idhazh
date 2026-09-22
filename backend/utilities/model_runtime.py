"""What does a runner need to serve the model its config names, and is it here and correct?

Five verbs, one program. They were four shell scripts and a fifth module, and
every one of the boundaries between them invented a format so the next one
could read it: the pin was shell variables two scripts sourced, and the server
command line was written NUL-joined to a file four workflow blocks read back
with `mapfile -d ''`. A program has no boundary to invent a format at.

A step calls a verb. It spells no URL, no flag, no digest and no filename.

Two things this module may not do, and both are load-bearing.

It imports nothing from `idhazh` at module scope. `install-runtime` and
`download-model-files` run in jobs that have not installed the package yet -
they are what makes the package installable at all on a cold cache - so a name
resolved at import time would take the download down. `start-server` runs after
the install and imports what it needs inside itself.

And only the release lookup sets a request header. CPython's redirect handler
copies every header onto a cross-host redirect target with no host check, and
both the hub and the release CDN redirect - so a bearer token added to the byte
download would follow the redirect to a third party. Today that is safe by
accident, because the shell used two separate `curl` calls and only authed the
first.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import IO, Final

from utilities import model_refs

#: The pin: which llama.cpp build, which asset of that release, and the digest
#: of the archive that asset is. One home, because it used to be written in six
#: places that had to change together - five workflow `env:` blocks and nothing
#: that read them against each other. Miss one on an upgrade and a case runs on
#: a build production does not run, which is a measurement about a binary
#: nobody ships (Guardrail #10).
#:
#: The digest is the release API's own `digest` for that asset. It was confirmed
#: on 2026-08-25 by downloading the 16,377,727-byte archive and hashing it.
PIN_FILE: Final = Path("config/llama-cpp-pin.json")

#: What a cache key names the build as, and the key a step publishes it under.
PIN_OUTPUT_KEY: Final = "llama_cpp_build"

#: Where the runtime lands. It is a cache path beside the weights, so the two
#: restore together and a job never holds a binary without the bytes it decodes.
BIN_DIR: Final = Path("backend/bin")

SERVER_BINARY: Final = BIN_DIR / "llama-server"

#: The release this project installs from, named once.
RELEASE_API: Final = "https://api.github.com/repos/ggml-org/llama.cpp/releases/tags"

#: Where a model file is fetched from. `?download=true` asks the hub for the
#: bytes rather than the page about them, and the revision is a commit rather
#: than a branch - a branch is re-pointed on every upload, so a run that named
#: one could not be repeated.
HUB_RESOLVE: Final = "https://huggingface.co/{repo}/resolve/{revision}/{file}?download=true"

#: The loopback port, read back rather than written. A server on one port and a
#: stage posting to another is every item of a shard failing (Guardrail #6).
PORT_ENV: Final = "LLAMA_PORT"

#: One blocking read. It is not a bound on the transfer, and the two clauses
#: below exist because it is not: a connection handing back one byte every
#: twenty seconds never trips this.
READ_TIMEOUT_SECONDS: Final = 60

#: How much of a file one read asks for. `shutil.copyfileobj` is correct on
#: memory and gives no progress line, no deadline hook and no throughput floor,
#: which are the three things a 5.68 GB transfer on a shared runner needs.
CHUNK_BYTES: Final = 1 << 20

#: Attempts per file, each from byte zero. That is parity rather than a loss:
#: the `curl` call this replaces carried no `--continue-at`, so it already
#: restarted from zero after a mid-transfer reset.
DOWNLOAD_ATTEMPTS: Final = 3

#: The whole-file bound, and the reason it is a bound rather than a setting: a
#: shard is killed at `run.shard_timeout_minutes`, 200 today, and a download
#: that holds it to that ceiling costs the day a shard of stories. The slowest
#: fetch this repository has recorded is 338 s for 4.28 GB, so thirty minutes
#: is about five times the worst measurement and still an eighth of the bound.
DOWNLOAD_DEADLINE_SECONDS: Final = 1800

#: The stall detector, and what it catches that the deadline cannot: a transfer
#: that ran at full speed and then stopped keeps a healthy average for a long
#: time, so the floor is measured over the last window rather than over the
#: whole file. One megabyte a second is seventeen times below the slowest rate
#: ever measured here, so a transfer that is working never sees it.
FLOOR_BYTES_PER_SECOND: Final = 1_000_000

FLOOR_WINDOW_SECONDS: Final = 30

#: How long a new connection gets before the floor applies at all. A hub
#: redirect and a TLS handshake move no bytes and are not a stall.
FLOOR_GRACE_SECONDS: Final = 60

#: The row of `/proc/self/limits` that says what `ulimit -l` says.
LOCKED_MEMORY_ROW: Final = "Max locked memory"

#: What a retry is for. A 4xx is the server saying the request was wrong, and
#: asking again three times is three ways to be wrong about the same thing.
RETRIABLE_STATUS: Final = frozenset({408, 429})

#: The transport failures worth another connection. `IncompleteRead` is in it
#: and is not an `OSError`, which is why the catch below names two bases.
RETRIABLE_ERRORS: Final = (
    urllib.error.URLError,
    ConnectionResetError,
    http.client.IncompleteRead,
    TimeoutError,
)


def _pin() -> dict[str, str]:
    """The three pinned values, refused by name rather than read as whatever is there."""
    declared = json.loads(PIN_FILE.read_text(encoding="utf-8"))
    values = {}
    for key, rule, says in (
        ("build", model_refs.SEGMENT_RE, "not one path segment"),
        ("asset", model_refs.SEGMENT_RE, "not one path segment"),
        ("sha256", model_refs.SHA256_RE, "not a 64-character digest"),
    ):
        value = str(declared.get(key, ""))
        if not rule.fullmatch(value):
            raise SystemExit(f"{PIN_FILE.as_posix()}: {key}:\n  {says}: {value!r}")
        values[key] = value
    return values


def _elapsed(started: float) -> float:
    return time.monotonic() - started


def _say(message: str) -> None:
    """One line a person reading a run log can act on."""
    print(message, flush=True)


class _StalledError(OSError):
    """The connection is alive and moving too slowly to be worth waiting on.

    Retried, because it fires in about ninety seconds and a fresh connection is
    the answer - it is the case `curl` handled as a reset.
    """


class _OutOfTimeError(OSError):
    """The file has taken the whole bound it was given.

    Not retried. The budget is already spent, and three attempts at half an
    hour each is the shard's own ceiling.
    """


def _read_into(response: IO[bytes], part: Path, url: str) -> int:
    """One attempt: every byte of the body onto disk, under both bounds.

    The socket timeout above bounds one read. These two bound the transfer: a
    deadline for the whole file, and a floor measured over the last window so a
    connection that stalls after a fast start is caught in thirty seconds rather
    than in whatever its average takes to decay.
    """
    started = time.monotonic()
    window_started = started
    window_bytes = 0
    total = 0
    with part.open("wb") as landing:
        while True:
            chunk = response.read(CHUNK_BYTES)
            if not chunk:
                return total
            landing.write(chunk)
            total += len(chunk)
            window_bytes += len(chunk)

            spent = _elapsed(started)
            if spent > DOWNLOAD_DEADLINE_SECONDS:
                raise _OutOfTimeError(
                    f"{url} has taken {spent:.0f}s for {total} bytes, "
                    f"past the {DOWNLOAD_DEADLINE_SECONDS}s a file may take"
                )
            window = time.monotonic() - window_started
            if spent < FLOOR_GRACE_SECONDS or window < FLOOR_WINDOW_SECONDS:
                continue
            if window_bytes < FLOOR_BYTES_PER_SECOND * window:
                raise _StalledError(
                    f"{url} moved {window_bytes} bytes in {window:.0f}s, below the "
                    f"{FLOOR_BYTES_PER_SECOND} bytes a second a transfer must hold"
                )
            window_started = time.monotonic()
            window_bytes = 0


def _retriable(error: BaseException) -> bool:
    if isinstance(error, urllib.error.HTTPError):
        # The body is a file object, and an unread one holds the connection.
        error.close()
        return error.code >= 500 or error.code in RETRIABLE_STATUS
    if isinstance(error, _OutOfTimeError):
        return False
    return isinstance(error, (_StalledError, *RETRIABLE_ERRORS))


def _download(url: str, destination: Path) -> tuple[Path, int]:
    """Every byte of one address onto one path, and the only thing here that fetches bytes.

    One function, so a change of transport is a change to one function rather
    than a revert of the row that introduced it.

    It sets no request header at all - see this module's own docstring for the
    redirect that makes that load-bearing - and `urlopen` raises on any non-2xx,
    which is `curl -f` for free: an HTTP error body can never be written into a
    weights file and then saved under a cache key.

    The bytes land on a `.part` and the caller renames. `curl -o` wrote straight
    to the destination, so a job killed mid-transfer left half a file under the
    cache key for every later run to restore.
    """
    part = destination.with_name(destination.name + ".part")
    destination.parent.mkdir(parents=True, exist_ok=True)
    last: BaseException | None = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(url, timeout=READ_TIMEOUT_SECONDS) as response:
                return part, _read_into(response, part, url)
        except (OSError, http.client.HTTPException) as error:
            last = error
            part.unlink(missing_ok=True)
            if attempt == DOWNLOAD_ATTEMPTS or not _retriable(error):
                break
            _say(f"::warning::attempt {attempt} of {url} failed: {error}")
    raise SystemExit(f"{url} could not be downloaded in {DOWNLOAD_ATTEMPTS} attempts: {last}")


def _digest_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as reading:
        while chunk := reading.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _asset_url(build: str, asset: str) -> str:
    """Where the release API says that asset is.

    Authenticated, and it is the one place in this module that sets a header:
    every shard asks at once and anonymous `api.github.com` allows sixty
    requests an hour, which a ceiling of eight shards on a cold cache would
    spend on retries.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise SystemExit("GITHUB_TOKEN must be set to look the pinned release up")
    ask = urllib.request.Request(
        f"{RELEASE_API}/{build}", headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(ask, timeout=READ_TIMEOUT_SECONDS) as response:
        release = json.load(response)
    assets = {
        str(one.get("name")): str(one.get("browser_download_url")) for one in release["assets"]
    }
    if asset not in assets:
        raise SystemExit(
            f"the pinned llama.cpp asset is not in release {build}: {asset!r}\n"
            f"  the release carries: {sorted(assets)}"
        )
    return assets[asset]


def _unpacked_server(root: Path) -> Path:
    """The directory holding `llama-server`, found by walking every entry.

    These builds ship their versioned shared objects as symlinks, and a symlink
    is not a file - which is why the shell used `cp -a` over `find -type f`. A
    walk that only looked at files would find the binary and leave its libraries
    behind, and the binary then dies at exec with a 127 naming a library rather
    than the mistake.
    """
    for path in root.rglob(SERVER_BINARY.name):
        return path.parent
    raise SystemExit(f"the unpacked archive holds no {SERVER_BINARY.name}: {root.as_posix()}")


def install_runtime() -> None:
    """Put the pinned llama.cpp build on this runner, and nothing else."""
    pin = _pin()
    url = _asset_url(pin["build"], pin["asset"])
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch)
        started = time.monotonic()
        archive, size = _download(url, work / "llama.tar.gz")
        _say(f"llama.cpp {pin['build']}: {size} bytes in {_elapsed(started):.1f}s")

        found = _digest_of(archive)
        if found != pin["sha256"]:
            raise SystemExit(
                f"{pin['asset']} hashes {found}\n"
                f"  and {PIN_FILE.as_posix()} declares {pin['sha256']}"
            )
        unpacked = work / "llama"
        with tarfile.open(archive) as tar:
            # Named rather than defaulted: CI pins 3.12, where the default is
            # `fully_trusted` plus a warning, and 3.14 defaults to `data`. Same
            # call, two behaviours, and the developer box is the one that
            # differs. `tar` is the faithful equivalent of `tar -xzf`.
            tar.extractall(path=unpacked, filter="tar")

        # The rmtree is load-bearing. `dirs_exist_ok` permits an existing
        # DIRECTORY; an existing destination symlink makes `os.symlink` raise
        # `FileExistsError`, and `cp -a` overwrote. Latent on a cache miss and
        # live on any retry.
        shutil.rmtree(BIN_DIR, ignore_errors=True)
        shutil.copytree(_unpacked_server(unpacked), BIN_DIR, symlinks=True, dirs_exist_ok=True)

    SERVER_BINARY.chmod(0o755)
    if not SERVER_BINARY.is_file():
        raise SystemExit(f"{SERVER_BINARY.as_posix()} is not a regular file after the install")
    broken = sorted(
        path.as_posix() for path in BIN_DIR.rglob("*") if path.is_symlink() and not path.exists()
    )
    if broken:
        raise SystemExit(f"the install left links pointing at nothing: {broken}")
    _say(f"llama.cpp {pin['build']} installed into {BIN_DIR.as_posix()}")


def _declared(config_root: Path) -> list[model_refs.ModelFile]:
    files = model_refs.list_model_files(config_root)
    if not files:
        raise SystemExit(f"{config_root.as_posix()} declares no model file to fetch")
    return files


def _matches(one: model_refs.ModelFile, landed: Path) -> bool:
    """Whether what is on disk is what the entry declares, size first then bytes."""
    if one.byte_count and landed.stat().st_size != int(one.byte_count):
        return False
    return _digest_of(landed) == one.sha256


def download_model_files(config_root: Path) -> None:
    """Fetch every file the model declares, and prove each one before it counts.

    Every file, in declared order, because the cache key names every one of
    them: an entry that keyed on three files and fetched one restores complete
    and llama-server exits at load rather than at fetch. The counts are compared
    at the end for the same reason - a download that exits 0 having fetched
    fewer files than the entry declares is the one door the cache's own
    `post-if: success()` cannot see.
    """
    files = _declared(config_root)
    downloaded = 0
    kept = 0
    for one in files:
        landed = Path(one.landed_path)
        if landed.exists():
            if not _matches(one, landed):
                raise SystemExit(
                    f"{one.landed_path} is already here and is not what "
                    f"{config_root.as_posix()} declares"
                )
            _say(f"kept {one.landed_path}")
            kept += 1
            continue

        url = HUB_RESOLVE.format(repo=one.repo, revision=one.revision, file=one.file)
        started = time.monotonic()
        part, size = _download(url, landed)
        spent = max(_elapsed(started), 1e-6)
        # The instrument. It is the only reading this repository will ever take
        # of the transport on a real runner, so it says the address, the bytes,
        # the seconds and the rate on one line (Guardrail #10).
        _say(f"fetched {url}: {size} bytes in {spent:.1f}s, {size / spent / 1e6:.1f} MB/s")

        found = _digest_of(part)
        if found != one.sha256:
            part.unlink(missing_ok=True)
            raise SystemExit(
                f"{one.landed_path} hashes {found}\n  and its entry declares {one.sha256}"
            )
        if one.byte_count and size != int(one.byte_count):
            part.unlink(missing_ok=True)
            raise SystemExit(
                f"{one.landed_path} is {size} bytes\n  and its entry declares {one.byte_count}"
            )
        part.replace(landed)
        downloaded += 1

    if downloaded + kept != len(files):
        raise SystemExit(
            f"{config_root.as_posix()} declares {len(files)} files and this "
            f"downloaded {downloaded} and kept {kept}"
        )
    _say(f"{len(files)} declared, {downloaded} downloaded, {kept} already here")


def verify_model_files(config_root: Path) -> None:
    """Check every declared file against its recorded digest and its declared size.

    This is the half that runs on a cache hit, where nothing was downloaded and
    nobody watched the bytes arrive. It reads the declaration rather than being
    handed a filename, so it cannot cover fewer files than the key digested.
    """
    files = _declared(config_root)
    for one in files:
        landed = Path(one.landed_path)
        if not landed.is_file():
            raise SystemExit(f"{one.landed_path} is declared and is not here")
        size = landed.stat().st_size
        if one.byte_count and size != int(one.byte_count):
            raise SystemExit(
                f"{one.landed_path} is {size} bytes\n  and its entry declares {one.byte_count}"
            )
        found = _digest_of(landed)
        if found != one.sha256:
            raise SystemExit(
                f"{one.landed_path} hashes {found}\n  and its entry declares {one.sha256}"
            )
        _say(f"checked {one.landed_path}: {size} bytes, {found}")
    _say(f"{len(files)} declared files check out against {config_root.as_posix()}")


def _locked_memory_limit() -> str:
    """What `ulimit -l` would print, read from the kernel rather than from a library.

    `/proc/self/limits` rather than the `resource` module, because this file is
    read under pytest on a developer machine that has no such module - and the
    line is the same one the shell printed.
    """
    limits = Path("/proc/self/limits")
    if not limits.exists():
        return "unreadable on this host"
    for line in limits.read_text(encoding="utf-8").splitlines():
        if line.startswith(LOCKED_MEMORY_ROW):
            return " ".join(line.removeprefix(LOCKED_MEMORY_ROW).split())
    return f"{limits.as_posix()} names no locked-memory row"


def _raise_the_locked_memory_limit() -> None:
    """Ask for unlimited locked memory, say what happened, and carry on either way.

    The live model's entry asks for `mmap+mlock`, and the candidate-config
    action copies that block onto every candidate - so four jobs have been
    starting an mlock-requesting server at the default limit. Doing it here
    fixes them for free and cannot make anything worse.

    `sudo -n` so a machine that would prompt for a password gives an instant
    non-zero the warning below absorbs, rather than a hang to the job timeout.
    `os.getpid()` is the right process: the server is a child of this one and
    inherits the limit at fork, exactly as it inherited the shell's. A process
    can only raise itself to its own hard limit, which is why the shell needed
    sudo for this and why nothing here tries to do it in-process.
    """
    _say(f"locked-memory limit before: {_locked_memory_limit()}")
    raised = subprocess.run(
        ["sudo", "-n", "prlimit", "--memlock=unlimited", "--pid", str(os.getpid())],
        check=False,
    )
    if raised.returncode:
        _say("::warning::Could not raise the locked-memory limit; model memory may stay unlocked.")
    # The pair is the proof the call landed. One line alone says what was asked
    # for rather than what happened.
    _say(f"locked-memory limit after: {_locked_memory_limit()}")


def start_server(config_root: Path, name: str) -> None:
    """Start llama-server against one config root and prove the process survived.

    Everything `idhazh` is imported here rather than at module scope, because
    the two verbs above run in a job that has not installed the package yet.

    The weights are derived rather than handed over: the config root's own entry
    already names the file, and the flags come from that same entry - so the
    server this starts is the server that config describes, with no second
    answer to which bytes it opened.
    """
    from idhazh import config
    from idhazh.llm.server import refuse_a_server_that_died_at_startup, server_argv

    _raise_the_locked_memory_limit()
    SERVER_BINARY.chmod(0o755)
    Path("backend/var").mkdir(parents=True, exist_ok=True)

    entry = config.load(config_root).models.summarize
    argv = server_argv(
        binary=SERVER_BINARY,
        weights=Path(_declared(config_root)[0].landed_path),
        model=entry,
        server=entry.server,
        port=int(os.environ[PORT_ENV]),
    )
    _say(f"starting: {' '.join(argv)}")

    log_path = Path(f"{name}.log")
    with log_path.open("wb") as log:
        # Every one of these is load-bearing. The shell form was a prefix
        # assignment, so everything else in the environment survived and a bare
        # dict here would take `PATH` and `HOME` with it. A detached child
        # holding the step's stdio pipe is the classic way an Actions step hangs
        # at completion, so all three streams are set. `start_new_session`
        # calls `setsid`, which is strictly more detached than `nohup`: with no
        # controlling terminal, SIGHUP is never delivered at all.
        server = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "LD_LIBRARY_PATH": BIN_DIR.as_posix()},
            start_new_session=True,
            close_fds=True,
        )
    Path(f"{name}.pid").write_text(str(server.pid), encoding="utf-8")
    refuse_a_server_that_died_at_startup(server, log_path)
    _say(f"{name} is up as pid {server.pid}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    verbs = parser.add_subparsers(dest="verb", required=True)

    def rooted(name: str, help_text: str) -> argparse.ArgumentParser:
        verb = verbs.add_parser(name, help=help_text)
        verb.add_argument(
            "--config-root",
            type=Path,
            default=model_refs.DEFAULT_CONFIG_ROOT,
            help="Directory holding the pointer file and the model it names.",
        )
        return verb

    verbs.add_parser("print-pinned-build", help="Say which llama.cpp build this run installs.")
    verbs.add_parser("install-runtime", help="Put the pinned llama.cpp build on this runner.")
    rooted("download-model-files", "Fetch every file the model declares.")
    rooted("verify-model-files", "Check every declared file against what the entry records.")
    start = rooted("start-server", "Start llama-server and prove it survived the start.")
    start.add_argument(
        "--name",
        default="llama-server",
        help="The stem for <name>.log and <name>.pid, which later steps read back.",
    )
    args = parser.parse_args(argv)

    ran: dict[str, Callable[[], None]] = {
        "print-pinned-build": lambda: _say(f"{PIN_OUTPUT_KEY}={_pin()['build']}"),
        "install-runtime": install_runtime,
        "download-model-files": lambda: download_model_files(args.config_root),
        "verify-model-files": lambda: verify_model_files(args.config_root),
        "start-server": lambda: start_server(args.config_root, args.name),
    }
    ran[args.verb]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
