"""How does exact completed work land on fresh main without changing a checkout?"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from utilities.publication_git import Repository
from utilities.publication_request import Entry, IntegrityError, PublicationRequest, contains
from utilities.push_retry import PushRetry


class Status(StrEnum):
    LANDED = "landed"
    ALREADY_ON_MAIN = "already-on-main"
    NO_CHANGES = "no-changes"
    STALE = "stale"
    LOST = "lost"
    INTEGRITY_REFUSED = "integrity-refused"
    REFUSED = "refused"
    PREPARATION_FAILURE = "preparation-failure"


@dataclass(frozen=True, slots=True)
class PublicationResult:
    status: Status
    candidate: str | None = None
    base: str | None = None
    observed_tip: str | None = None
    push_count: int = 0
    refusal_paths: tuple[str, ...] = ()
    prepared: bool = False
    detail: str = ""

    @property
    def exit_code(self) -> int:
        if self.status is Status.INTEGRITY_REFUSED:
            return 2
        return (
            0
            if self.status
            in {
                Status.LANDED,
                Status.ALREADY_ON_MAIN,
                Status.NO_CHANGES,
            }
            else 1
        )


def _matches(
    git: Repository, tip: str, request: PublicationRequest, entries: dict[str, Entry]
) -> bool:
    return all(git.entry(tip, path) == entry for path, entry in entries.items()) and all(
        git.entry(tip, path) is None for path in request.deletions
    )


def _unchanged_evidence(git: Repository, request: PublicationRequest) -> None:
    for path, write in request.writes.items():
        git.parents_safe(write.baseline_tip or request.source_tip, path)
        if git.entry(write.baseline_tip or request.source_tip, path) != write.baseline:
            raise IntegrityError("write baseline is not the declared source entry", (path,))
    for path, delete in request.deletions.items():
        git.parents_safe(request.source_tip, path)
        if git.entry(request.source_tip, path) != delete.baseline:
            raise IntegrityError("delete baseline is not the declared source entry", (path,))


def _stale(
    git: Repository, tip: str, request: PublicationRequest, entries: dict[str, Entry]
) -> tuple[str, ...]:
    stale: list[str] = []
    for path, write in request.writes.items():
        current = git.entry(tip, path)
        git.parents_safe(tip, path)
        if current is not None and current.mode != write.mode:
            raise IntegrityError("target mode is not a plain data file", (path,))
        if write.immutable:
            if current is not None and current != entries[path]:
                raise IntegrityError("immutable identity already contains different bytes", (path,))
        elif current != write.baseline:
            stale.append(path)
    for path, delete in request.deletions.items():
        git.parents_safe(tip, path)
        current = git.entry(tip, path)
        if current is not None and current.mode != delete.baseline.mode:
            raise IntegrityError("deletion target mode changed", (path,))
        if current != delete.baseline:
            stale.append(path)
    return tuple(sorted(stale))


def _verify_preparation(
    original: PublicationRequest, prepared: PublicationRequest, base: str
) -> None:
    if (
        prepared.identity != original.identity
        or prepared.message != original.message
        or prepared.source_tip != base
        or prepared.write_permissions != original.write_permissions
        or prepared.delete_permissions != original.delete_permissions
    ):
        raise IntegrityError("preparation changed identity or authority")
    scopes = original.preparation_scopes
    for path in set(original.writes) | set(prepared.writes):
        if not any(contains(scope, path) for scope in scopes):
            before, after = original.writes.get(path), prepared.writes.get(path)
            if (
                before is None
                or after is None
                or (before.sha256, before.mode, before.immutable)
                != (after.sha256, after.mode, after.immutable)
            ):
                raise IntegrityError("preparation changed completed artifact", (path,))
    for path in set(original.deletions) | set(prepared.deletions):
        if not any(contains(scope, path) for scope in scopes):
            old_delete, new_delete = original.deletions.get(path), prepared.deletions.get(path)
            if old_delete is None or new_delete is None or not new_delete.completed:
                raise IntegrityError("preparation changed completed deletion", (path,))


def publish(
    request: PublicationRequest,
    *,
    repo: Path,
    retry: PushRetry,
    max_pushes: int | None = None,
) -> PublicationResult:
    """One ordinary pusher; retry builds candidates, never replays producer work."""
    git = Repository(repo)
    candidate: str | None = None
    base: str | None = None
    observed: str | None = None
    pushes = 0
    prepared = False
    active = request
    deadline = time.monotonic() + retry.deadline_for(request.identity.job)

    def result(status: Status, paths: tuple[str, ...] = (), detail: str = "") -> PublicationResult:
        return PublicationResult(status, candidate, base, observed, pushes, paths, prepared, detail)

    try:
        if max_pushes is not None and max_pushes < 1:
            raise IntegrityError("max_pushes must be positive")
        request.validate(repo)
        git.prime(request.source_tip, set(request.writes) | set(request.deletions))
        _unchanged_evidence(git, request)
        if not request.writes and not request.deletions:
            return result(Status.NO_CHANGES)
        entries = git.objects(request)
        while time.monotonic() < deadline and (max_pushes is None or pushes < max_pushes):
            observed = git.fetch()
            git.prime(observed, set(active.writes) | set(active.deletions))
            if _matches(git, observed, active, entries):
                return result(Status.LANDED if candidate else Status.ALREADY_ON_MAIN)
            stale = _stale(git, observed, active, entries)
            if active.prepare is not None and (observed != active.source_tip or stale):
                try:
                    fresh = active.prepare(observed, active)
                    _verify_preparation(request, fresh, observed)
                    fresh.validate(repo)
                    git.prime(fresh.source_tip, set(fresh.writes) | set(fresh.deletions))
                    _unchanged_evidence(git, fresh)
                    entries = git.objects(fresh)
                    active = fresh
                    prepared = True
                except (ValueError, OSError, RuntimeError) as error:
                    if isinstance(error, IntegrityError):
                        return result(Status.INTEGRITY_REFUSED, error.paths, str(error))
                    return result(Status.PREPARATION_FAILURE, detail=str(error))
                stale = _stale(git, observed, active, entries)
            if stale:
                return result(Status.STALE, stale)
            base = observed
            active.validate(repo)
            entries = git.objects(active)
            candidate = git.candidate(base, active, entries)
            if time.monotonic() >= deadline:
                break
            pushes += 1
            accepted = git.push(candidate)
            observed = git.fetch()
            git.prime(observed, set(active.writes) | set(active.deletions))
            if _matches(git, observed, active, entries):
                return result(Status.LANDED)
            if accepted:
                # A later writer changed the exact operations before verification.
                return result(Status.LOST, detail="accepted candidate is no longer visible")
            remaining = deadline - time.monotonic()
            if remaining > 0 and (max_pushes is None or pushes < max_pushes):
                time.sleep(min(remaining, retry.backoff_seconds(pushes) * random.uniform(0.5, 1.5)))
        observed = git.fetch()
        git.prime(observed, set(active.writes) | set(active.deletions))
        if _matches(git, observed, active, entries):
            return result(Status.LANDED if candidate else Status.ALREADY_ON_MAIN)
        return result(Status.LOST if base is not None and observed != base else Status.REFUSED)
    except IntegrityError as error:
        return result(Status.INTEGRITY_REFUSED, error.paths, str(error))
    except (OSError, RuntimeError) as error:
        # A transport error is not proof that a push failed.
        if candidate is not None:
            try:
                observed = git.fetch()
                if _matches(git, observed, active, git.objects(active)):
                    return result(Status.LANDED)
            except (OSError, RuntimeError, ValueError):
                pass
        return result(Status.REFUSED, detail=str(error))
