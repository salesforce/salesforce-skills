#!/usr/bin/env python3
"""Validate a generated salesforce-for-sales candidate without checking it out.

The validator reads commits and blobs directly from Git. The target workflow supplies
only a branch name and the immutable SHA reported by ``workflow_run``; repository,
path, version, and size invariants stay behind this module's small interface.
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


BASE_BRANCH = "main"
BRANCH_PREFIX = "automation/salesforce-for-sales-v"
MANAGED_PATH = "salesforce-for-sales"
PLUGIN_PATH = f"{MANAGED_PATH}/.claude-plugin/plugin.json"
VERSION_PATH = f"{MANAGED_PATH}/version.json"
MAX_FILES = 500
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 25 * 1024 * 1024
SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>"
    r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*"
    r"))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ValidationError(Exception):
    """A release candidate violated a target repository invariant."""


@dataclass(frozen=True)
class SemVer:
    raw: str
    core: tuple
    prerelease: tuple


def _require(condition, message):
    if not condition:
        raise ValidationError(message)


def _git(repository, *args):
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise ValidationError(f"git {' '.join(args)} failed: {detail.strip()}") from exc


def _git_bytes(repository, *args):
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *args],
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", b"")
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace")
        raise ValidationError(
            f"git {' '.join(args)} failed: {(detail or str(exc)).strip()}"
        ) from exc


def _resolve_commit(repository, ref, label):
    _require(not ref.startswith("-"), f"invalid {label} ref: {ref!r}")
    commit = _git(repository, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    _require(
        SHA_RE.fullmatch(commit) is not None,
        f"{label} did not resolve to a full commit SHA: {commit!r}",
    )
    return commit


def parse_semver(value, label):
    _require(isinstance(value, str) and value, f"{label} must be a non-empty string")
    match = SEMVER_RE.fullmatch(value)
    _require(match is not None, f"{label} is not strict SemVer: {value!r}")
    prerelease = (
        tuple(match.group("prerelease").split("."))
        if match.group("prerelease")
        else ()
    )
    return SemVer(
        raw=value,
        core=tuple(int(match.group(part)) for part in ("major", "minor", "patch")),
        prerelease=prerelease,
    )


def compare_semver(left, right):
    """Return negative/zero/positive using SemVer precedence rules."""
    if left.core != right.core:
        return -1 if left.core < right.core else 1
    if not left.prerelease or not right.prerelease:
        if left.prerelease == right.prerelease:
            return 0
        return -1 if left.prerelease else 1

    for left_id, right_id in zip(left.prerelease, right.prerelease):
        if left_id == right_id:
            continue
        left_numeric = left_id.isdigit()
        right_numeric = right_id.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left_id) < int(right_id) else 1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return -1 if left_id < right_id else 1
    if len(left.prerelease) == len(right.prerelease):
        return 0
    return -1 if len(left.prerelease) < len(right.prerelease) else 1


def _load_git_json(repository, commit, path, label):
    raw = _git_bytes(repository, "show", f"{commit}:{path}")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot parse {label} at {path}: {exc}") from exc
    _require(isinstance(value, dict), f"{label} must be a JSON object: {path}")
    return value


def _release_metadata(repository, commit, label):
    plugin = _load_git_json(repository, commit, PLUGIN_PATH, f"{label} plugin manifest")
    version_file = _load_git_json(
        repository, commit, VERSION_PATH, f"{label} version metadata"
    )
    _require(
        plugin.get("name") == MANAGED_PATH,
        f"{label} plugin name must be {MANAGED_PATH!r}, got {plugin.get('name')!r}",
    )
    plugin_version = plugin.get("version")
    metadata_version = version_file.get("version")
    _require(
        plugin_version == metadata_version,
        f"{label} plugin.json and version.json versions differ: "
        f"{plugin_version!r} != {metadata_version!r}",
    )
    parsed = parse_semver(plugin_version, f"{label} version")
    return plugin_version, parsed


def _changed_paths(repository, parent, head):
    raw = _git_bytes(
        repository,
        "diff-tree",
        "--no-commit-id",
        "--no-renames",
        "--name-only",
        "-r",
        "-z",
        parent,
        head,
    )
    paths = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        try:
            path = item.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError("candidate contains a non-UTF-8 path") from exc
        _require(
            path.startswith(f"{MANAGED_PATH}/"),
            f"candidate changes path outside {MANAGED_PATH}/: {path}",
        )
        _require(
            all(ord(character) >= 32 and ord(character) != 127 for character in path),
            f"candidate path contains a control character: {path!r}",
        )
        paths.append(path)
    return paths


def _managed_tree(repository, head):
    raw = _git_bytes(repository, "ls-tree", "-r", "-z", head, "--", MANAGED_PATH)
    files = []
    total_bytes = 0
    for item in raw.split(b"\0"):
        if not item:
            continue
        try:
            metadata, raw_path = item.split(b"\t", 1)
            mode, object_type, object_id = metadata.decode("ascii").split()
            path = raw_path.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValidationError("candidate contains an invalid Git tree entry") from exc
        _require(
            path.startswith(f"{MANAGED_PATH}/"), f"unexpected managed-tree path: {path}"
        )
        _require(
            all(ord(character) >= 32 and ord(character) != 127 for character in path),
            f"candidate path contains a control character: {path!r}",
        )
        _require(
            mode == "100644" and object_type == "blob",
            f"candidate files must be non-executable regular files; "
            f"found mode={mode} type={object_type} at {path}",
        )
        size = int(_git(repository, "cat-file", "-s", object_id).strip())
        _require(
            size <= MAX_FILE_BYTES,
            f"candidate file exceeds {MAX_FILE_BYTES} bytes: {path} ({size})",
        )
        total_bytes += size
        files.append(path)

    _require(files, f"candidate tree {MANAGED_PATH}/ is empty")
    _require(
        len(files) <= MAX_FILES,
        f"candidate has {len(files)} files; maximum is {MAX_FILES}",
    )
    _require(
        total_bytes <= MAX_TOTAL_BYTES,
        f"candidate contains {total_bytes} bytes; maximum is {MAX_TOTAL_BYTES}",
    )
    _require(PLUGIN_PATH in files, f"candidate is missing {PLUGIN_PATH}")
    _require(VERSION_PATH in files, f"candidate is missing {VERSION_PATH}")
    return files, total_bytes


def validate_release(repository, branch, expected_head):
    repository = Path(repository).resolve()
    _require(repository.is_dir(), f"repository does not exist: {repository}")
    _require(
        branch.startswith(BRANCH_PREFIX),
        f"candidate branch must start with {BRANCH_PREFIX!r}: {branch!r}",
    )
    branch_version = branch[len(BRANCH_PREFIX) :]
    parse_semver(branch_version, "candidate branch version")
    _require(
        SHA_RE.fullmatch(expected_head) is not None,
        f"expected head is not a full commit SHA: {expected_head!r}",
    )

    base_ref = f"refs/remotes/origin/{BASE_BRANCH}"
    candidate_ref = f"refs/remotes/origin/{branch}"
    base = _resolve_commit(repository, base_ref, "base")
    head = _resolve_commit(repository, candidate_ref, "candidate")
    _require(
        head == expected_head,
        f"candidate ref moved: expected {expected_head}, found {head}",
    )

    ancestry = _git(repository, "rev-list", "--parents", "-n", "1", head).split()
    _require(
        len(ancestry) == 2,
        "candidate must contain exactly one non-merge commit on top of main",
    )
    parent = ancestry[1]
    _require(
        parent == base,
        f"candidate parent {parent} is not current {BASE_BRANCH} {base}; rerun release",
    )

    _changed_paths(repository, parent, head)
    files, total_bytes = _managed_tree(repository, head)
    candidate_version, candidate_semver = _release_metadata(repository, head, "candidate")
    _require(
        candidate_version == branch_version,
        f"candidate version {candidate_version!r} does not match branch "
        f"version {branch_version!r}",
    )

    base_version, base_semver = _release_metadata(repository, base, "base")
    base_tree = _git(repository, "rev-parse", f"{base}:{MANAGED_PATH}").strip()
    candidate_tree = _git(repository, "rev-parse", f"{head}:{MANAGED_PATH}").strip()
    has_changes = base_tree != candidate_tree
    precedence = compare_semver(candidate_semver, base_semver)
    _require(
        precedence >= 0,
        f"candidate version {candidate_version} is older than base version {base_version}",
    )
    if precedence == 0:
        _require(
            candidate_version == base_version,
            f"candidate version {candidate_version} does not advance base version "
            f"{base_version}",
        )
        _require(
            not has_changes,
            f"version {candidate_version} is already on {BASE_BRANCH} with different content",
        )
    else:
        _require(
            has_changes,
            f"version advanced to {candidate_version} without changing the managed tree",
        )

    return {
        "version": candidate_version,
        "branch": branch,
        "file_count": str(len(files)),
        "total_bytes": str(total_bytes),
        "has_changes": "true" if has_changes else "false",
        "base_sha": base,
        "head_sha": head,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate a salesforce-for-sales automation branch from trusted main."
    )
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)

    try:
        outputs = validate_release(args.repository, args.branch, args.expected_head)
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as output_file:
                for key in (
                    "version",
                    "branch",
                    "file_count",
                    "total_bytes",
                    "has_changes",
                    "base_sha",
                    "head_sha",
                ):
                    output_file.write(f"{key}={outputs[key]}\n")
    except (OSError, ValidationError) as exc:
        sys.stderr.write(f"release candidate rejected: {exc}\n")
        return 1

    print(
        f"Validated {outputs['branch']} at {outputs['head_sha']} "
        f"({outputs['file_count']} files, changes={outputs['has_changes']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
