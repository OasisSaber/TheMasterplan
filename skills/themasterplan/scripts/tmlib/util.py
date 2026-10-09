"""Utility helpers for the /TheMasterplan executor: path safety, hashing, atomic writes.

Only the Python standard library is used; no third-party dependencies.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = 1


class TheMasterplanError(Exception):
    """Base error for the /TheMasterplan executor; message is user-facing."""


class PathSafetyError(TheMasterplanError):
    """Raised when a target path escapes the repository root."""


def is_volatile_executor_artifact(relative: str) -> bool:
    """Return whether a state path is disposable Python bytecode.

    State paths are serialized with forward slashes. Only bytecode inside
    `.themasterplan/bin` is ignored; source files and other unexpected executor files
    remain subject to normal integrity checks.
    """
    if not isinstance(relative, str):
        return False
    path = PurePosixPath(relative)
    parts = path.parts
    return (
        len(parts) >= 3
        and parts[:2] == (".themasterplan", "bin")
        and (
            "__pycache__" in parts
            or path.suffix in {".pyc", ".pyo"}
        )
    )


def validate_relative_path(relative: str) -> PurePosixPath:
    """Validate portable path syntax without consulting CWD or the filesystem."""
    if (not isinstance(relative, str) or not relative or relative == "."
            or "\\" in relative or ":" in relative or "\x00" in relative):
        raise PathSafetyError(f"invalid relative path: {relative!r}")
    rel = PurePosixPath(relative)
    if rel.as_posix() != relative:
        raise PathSafetyError(f"noncanonical relative path: {relative}")
    if rel.is_absolute():
        raise PathSafetyError(f"absolute path not allowed: {relative}")
    parts = rel.parts
    if any(part == ".." for part in parts):
        raise PathSafetyError(f"path traversal not allowed: {relative}")
    for part in parts:
        stem = part.split(".", 1)[0].rstrip(" ").upper()
        if (part.endswith((".", " "))
                or any(ord(char) < 32 or char in '<>"|?*' for char in part)
                or stem in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
                or re.fullmatch(r"(?:COM|LPT)[1-9¹²³]", stem)):
            raise PathSafetyError(f"nonportable filename component: {relative}")
    return rel


def validate_target_paths(paths) -> None:
    """Reject case aliases (including directory aliases) and file/parent overlap.

    Conservatively use case-folded names on every platform so a plan cannot
    acquire different target identities when transferred to Windows.
    """
    prefixes = {}
    terminals = set()
    for relative in paths:
        parts = validate_relative_path(relative).parts
        for index in range(1, len(parts) + 1):
            prefix = "/".join(parts[:index])
            key = prefix.casefold()
            previous = prefixes.get(key)
            if previous is not None and previous != prefix:
                raise PathSafetyError(f"case-alias target collision: {previous}, {prefix}")
            if index < len(parts) and key in terminals:
                raise PathSafetyError(f"file/parent target collision: {relative}")
            prefixes[key] = prefix
        key = relative.casefold()
        if key in terminals or any(p.startswith(key + "/") for p in prefixes):
            raise PathSafetyError(f"duplicate or file/parent target collision: {relative}")
        terminals.add(key)


def safe_join(root: Path, relative: str) -> Path:
    """Validate syntax, then reject descendant links/escapes beneath the real root."""
    parts = validate_relative_path(relative).parts
    root_resolved = root.resolve()
    target = root_resolved
    for index, part in enumerate(parts):
        target = target / part
        if target.is_symlink() or (hasattr(target, "is_junction") and target.is_junction()):
            raise PathSafetyError(f"link component not allowed: {relative}")
        try:
            attributes = getattr(target.lstat(), "st_file_attributes", 0)
        except FileNotFoundError:
            attributes = 0
        if attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT, also on older Python.
            raise PathSafetyError(f"reparse component not allowed: {relative}")
        if index < len(parts) - 1 and target.exists() and not target.is_dir():
            raise PathSafetyError(f"non-directory path component: {relative}")
    target = target.resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError:
        raise PathSafetyError(f"target escapes repository root: {relative}")
    return target


BLOCK_BEGIN = b"<!-- THEMASTERPLAN:BEGIN MANAGED -->"
BLOCK_END = b"<!-- THEMASTERPLAN:END MANAGED -->"


def sha256_of_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 of a file's bytes."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_of_block(path: Path) -> str:
    """Return the SHA-256 of a file's managed block (BEGIN..END markers).

    Returns "" when the block markers are missing, duplicated or malformed
    so the hash can never accidentally match a recorded value.
    """
    return sha256_of_block_bytes(path.read_bytes())


def sha256_of_block_bytes(data: bytes) -> str:
    if data.count(BLOCK_BEGIN) != 1 or data.count(BLOCK_END) != 1:
        return ""
    begin = data.find(BLOCK_BEGIN)
    end = data.find(BLOCK_END)
    if end < begin:
        return ""
    return hashlib.sha256(data[begin : end + len(BLOCK_END)]).hexdigest()


def read_json(path: Path) -> object:
    """Read a JSON file; raises TheMasterplanError with a readable message on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise TheMasterplanError(f"file not found: {path}")
    except json.JSONDecodeError as exc:
        raise TheMasterplanError(f"invalid JSON in {path}: {exc}")
    except (OSError, UnicodeError) as exc:
        raise TheMasterplanError(f"cannot read JSON in {path}: {exc}") from exc


def validate_state(state: object) -> dict:
    """Validate state shape before any caller accesses nested values.

    Legacy executor source labels and absent optional metadata remain supported.
    This validates records, not the authenticity of a user-controlled State.
    """
    if not isinstance(state, dict):
        raise TheMasterplanError("state.json must be an object")
    if state.get("schema_version") != SCHEMA_VERSION:
        raise TheMasterplanError("state.json schema_version is unsupported")
    source = state.get("source")
    if not isinstance(source, dict):
        raise TheMasterplanError("state.json source must be an object")
    for key in ("repository", "version", "commit"):
        if not isinstance(source.get(key), str) or not source[key]:
            raise TheMasterplanError(f"state.json source.{key} missing or malformed")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source["repository"]):
        raise TheMasterplanError("state.json source.repository malformed")
    if not re.fullmatch(r"[0-9a-f]{40}", source["commit"]):
        raise TheMasterplanError("state.json source.commit malformed")
    selection = state.get("selection")
    if not isinstance(selection, dict):
        raise TheMasterplanError("state.json selection must be an object")
    if selection.get("profile") not in ("git", "jj"):
        raise TheMasterplanError("state.json selection.profile must be git or jj")
    for key in ("validation_path", "default_branch"):
        value = selection.get(key)
        if not isinstance(value, str) or not value:
            raise TheMasterplanError(f"state.json selection.{key} missing or malformed")
    validate_relative_path(selection["validation_path"])
    managed = state.get("managed_files")
    if not isinstance(managed, dict):
        raise TheMasterplanError("state.json managed_files must be an object")
    validate_target_paths(managed)
    for relative, record in managed.items():
        if is_volatile_executor_artifact(relative):
            continue
        if not isinstance(record, dict):
            raise TheMasterplanError(f"malformed state entry: {relative}")
        if record.get("ownership") not in ("managed-replace", "managed-block"):
            raise TheMasterplanError(f"invalid state ownership: {relative}")
        if not isinstance(record.get("installed_sha256"), str) or not re.fullmatch(
                r"[0-9a-f]{64}", record["installed_sha256"]):
            raise TheMasterplanError(f"invalid installed hash in state: {relative}")
    return state


def load_state(path: Path) -> dict:
    return validate_state(read_json(path))


def apply_file_changes(root: Path, changes: dict[str, bytes | None],
                       expected: dict[str, bytes | None]) -> None:
    """Recheck all snapshots, write atomically per file, roll back caught failures.

    Not a crash-safe multi-file transaction or a filesystem lock. Refuse to roll
    back over an intervening external edit; report any incomplete restoration.
    """
    validate_target_paths(expected)
    if not changes.keys() <= expected.keys():
        raise TheMasterplanError("changed targets must have preflight snapshots")

    def current(relative):
        path = safe_join(root, relative)
        if path.exists() and not path.is_file():
            raise TheMasterplanError(f"target is not a regular file: {relative}")
        if not path.is_file():
            return None, None
        mode = stat.S_IMODE(path.stat().st_mode) if os.name != "nt" else None
        return path.read_bytes(), mode

    modes = {}
    for relative, before in expected.items():
        content, mode = current(relative)
        if content != before:
            raise TheMasterplanError(f"target changed before write: {relative}")
        modes[relative] = mode
    intended_modes = {relative: (None if content is None or os.name == "nt"
                                 else modes[relative] if modes[relative] is not None else 0o600)
                      for relative, content in changes.items()}
    completed = []
    try:
        for relative, content in changes.items():
            if current(relative) != (expected[relative], modes[relative]):
                raise TheMasterplanError(f"target changed before write: {relative}")
            target = safe_join(root, relative)
            completed.append(relative)
            if content is None:
                target.unlink()
            else:
                write_bytes_atomic(target, content, mode=intended_modes[relative])
    except BaseException as exc:
        failed = []
        for relative in reversed(completed):
            try:
                actual = current(relative)
                if actual == (expected[relative], modes[relative]):
                    continue
                if actual != (changes[relative], intended_modes[relative]):
                    failed.append(relative)
                    continue
                target = safe_join(root, relative)
                before = expected[relative]
                if before is None:
                    target.unlink()
                else:
                    write_bytes_atomic(target, before, mode=modes[relative])
            except (OSError, TheMasterplanError):
                failed.append(relative)
        if failed:
            raise TheMasterplanError(
                f"apply failed; rollback incomplete, inspect: {', '.join(failed)}") from exc
        if isinstance(exc, (OSError, TheMasterplanError)):
            raise TheMasterplanError(f"apply failed; completed writes restored: {exc}") from exc
        raise


def write_json_atomic(path: Path, data: dict) -> None:
    """Atomically write a JSON file via a temp file + rename."""
    write_bytes_atomic(path, (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def write_bytes_atomic(path: Path, content: bytes, *, mode: int | None = None) -> None:
    """Atomic replacement preserving existing POSIX mode; new files remain 0600.

    Explicit mode permits restoring a deleted file. Owner, ACL and extended
    attributes are not preserved; this is permission-bit protection, not an
    identity-preserving transaction.
    """
    if mode is None and os.name != "nt" and path.exists():
        mode = stat.S_IMODE(path.stat().st_mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
            fh.flush()
            if mode is not None and os.name != "nt":
                os.fchmod(fh.fileno(), mode)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
