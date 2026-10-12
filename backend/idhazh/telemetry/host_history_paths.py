"""Are the named historical inputs and isolated destinations physically separate and unique?"""

from __future__ import annotations

import ctypes
import stat
import sys
from pathlib import Path
from typing import ClassVar

from idhazh.contracts.host_migration import HistoryManifest
from idhazh.telemetry.host_output_verify import _safe_path

type FileIdentity = tuple[int, int]
type PathAddress = tuple[FileIdentity, tuple[str, ...]]


def _missing_names(anchor: Path, names: tuple[str, ...]) -> tuple[str, ...]:
    if sys.platform == "win32" and names:
        # Windows directories can opt into case-sensitive names. Query the real
        # parent read-only; only a missing suffix needs prospective name comparison.
        class CaseSensitiveInfo(ctypes.Structure):
            _fields_: ClassVar = [("flags", ctypes.c_uint32)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = (
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        )
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.GetFileInformationByHandleEx.argtypes = (
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32
        )
        kernel.GetFileInformationByHandleEx.restype = ctypes.c_int
        kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
        kernel.CloseHandle.restype = ctypes.c_int
        # Win32 ABI: FILE_READ_ATTRIBUTES, all share modes, OPEN_EXISTING and
        # FILE_FLAG_BACKUP_SEMANTICS admit a directory handle without creating it.
        handle = kernel.CreateFileW(str(anchor), 0x80, 0x7, None, 3, 0x02000000, None)
        if handle is None or handle == ctypes.c_void_p(-1).value:
            raise ValueError(
                "history path cannot open directory case information"
            ) from ctypes.WinError()
        try:
            info = CaseSensitiveInfo()
            # FileCaseSensitiveInfo is class 23; bit 1 is CASE_SENSITIVE_DIR.
            if not kernel.GetFileInformationByHandleEx(
                handle, 23, ctypes.byref(info), ctypes.sizeof(info)
            ):
                raise ValueError(
                    "history path cannot establish directory case semantics"
                ) from ctypes.WinError()
            return names if info.flags & 1 else tuple(name.lower() for name in names)
        finally:
            kernel.CloseHandle(handle)
    return names


def preflight_path(workspace: Path, target: Path) -> PathAddress:
    """Admit existing ancestors before resolving their spelling and missing suffix."""
    if not target.is_relative_to(workspace):
        raise ValueError("history path is outside the workspace")
    anchor = workspace
    for path in (*reversed(target.parents), target):
        if path == workspace or path.is_relative_to(workspace):
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            _safe_path(workspace, path)
            if path != target and not stat.S_ISDIR(info.st_mode):
                raise ValueError("history path ancestor is not a directory")
            anchor = path
    resolved = anchor.resolve(strict=True)
    info = resolved.stat()
    # Stat identity handles casing, hard links and filesystem-specific aliases.
    # Comparison of missing names follows this actual parent's case semantics.
    # These comparison keys never replace the operator's persisted path labels.
    return (info.st_dev, info.st_ino), _missing_names(
        resolved, target.parts[len(anchor.parts) :]
    )


def _contains(workspace: Path, parent: Path, child: Path) -> bool:
    parent_address = preflight_path(workspace, parent)
    child_address = preflight_path(workspace, child)
    identity, suffix = parent_address
    if child_address[0] == identity:
        return child_address[1][: len(suffix)] == suffix
    if suffix:
        return False
    for ancestor in (child, *child.parents):
        if not ancestor.is_relative_to(workspace):
            break
        try:
            info = ancestor.stat()
        except FileNotFoundError:
            continue
        if (info.st_dev, info.st_ino) == identity:
            return True
    return False


def preflight_history(manifest: HistoryManifest, *, workspace: Path) -> None:
    """Reject root aliases, repeated physical sources and output/history overlap."""
    isolated = workspace / manifest.isolated_root
    preflight_path(workspace, isolated)
    locations: set[PathAddress] = set()
    for root in manifest.roots:
        state = workspace / root.state_root
        for tier in ("raw", "compact"):
            location = preflight_path(workspace, state.joinpath(tier, *root.prefix))
            if location in locations:
                raise ValueError(f"{root.name}: duplicate physical history root")
            locations.add(location)
        if _contains(workspace, state, isolated) or _contains(workspace, isolated, state):
            raise ValueError(f"{root.name}: isolated output overlaps a historical state root")
    sources: set[FileIdentity] = set()
    for source in manifest.sources:
        try:
            path = _safe_path(workspace, workspace / source.path)
            info = path.stat()
        except OSError as error:
            raise ValueError(
                f"{source.path}: missing or unreadable source ({type(error).__name__})"
            ) from error
        identity = (info.st_dev, info.st_ino)
        if identity in sources:
            raise ValueError(f"{source.path}: duplicate physical source")
        sources.add(identity)
        if _contains(workspace, isolated, path):
            raise ValueError(f"{source.path}: source overlaps the isolated report root")


def preflight_targets(
    manifest: HistoryManifest, *, workspace: Path, targets: tuple[Path, ...]
) -> None:
    """Check every finite bundle target, including hard-linked partial retries."""
    preflight_history(manifest, workspace=workspace)
    source_identities = {
        preflight_path(workspace, workspace / source.path)[0] for source in manifest.sources
    }
    isolated = workspace / manifest.isolated_root
    addresses: set[PathAddress] = set()
    for target in targets:
        address = preflight_path(workspace, target)
        if address in addresses:
            raise ValueError("duplicate physical bundle target")
        addresses.add(address)
        if address[0] in source_identities:
            raise ValueError("bundle target overlaps a historical source")
        if not _contains(workspace, isolated, target):
            raise ValueError("bundle target is outside the isolated report root")
