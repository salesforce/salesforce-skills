#!/usr/bin/env python3
"""Tests for the trusted salesforce-for-sales release-candidate validator."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR_PATH = (
    REPO_ROOT / ".github" / "scripts" / "validate_salesforce_for_sales_release.py"
)
SPEC = importlib.util.spec_from_file_location("release_validator", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class ReleaseValidatorTests(unittest.TestCase):
    BASE_VERSION = "1.0.0-beta.1.2"

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="salesforce-release-validator-")
        self.addCleanup(shutil.rmtree, self._tmp, True)
        self.repo = Path(self._tmp) / "repository"
        self._git("init", "--quiet", "--initial-branch=main", str(self.repo), cwd=None)
        self._git("config", "user.name", "Release Test")
        self._git("config", "user.email", "release-test@example.com")
        self._write_release(self.BASE_VERSION, "base\n")
        self._commit("Base release")
        self.base_sha = self._head()
        self._remote_ref("main", self.base_sha)

    def _git(self, *args, cwd=True):
        command = ["git"]
        if cwd:
            command.extend(["-C", str(self.repo)])
        command.extend(args)
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def _write_release(self, version, content):
        root = self.repo / "salesforce-for-sales"
        plugin = root / ".claude-plugin" / "plugin.json"
        plugin.parent.mkdir(parents=True, exist_ok=True)
        plugin.write_text(
            json.dumps({"name": "salesforce-for-sales", "version": version}),
            encoding="utf-8",
        )
        (root / "version.json").write_text(
            json.dumps({"version": version}), encoding="utf-8"
        )
        (root / "README.md").write_text(content, encoding="utf-8")

    def _commit(self, message, allow_empty=False):
        self._git("add", "--all")
        command = ["commit", "--quiet"]
        if allow_empty:
            command.append("--allow-empty")
        self._git(*command, "-m", message)

    def _head(self):
        return self._git("rev-parse", "HEAD")

    def _remote_ref(self, branch, sha):
        self._git("update-ref", f"refs/remotes/origin/{branch}", sha)

    def _candidate(self, version, content="candidate\n", mutate=None, allow_empty=False):
        branch = f"automation/salesforce-for-sales-v{version}"
        self._git("switch", "--quiet", "--create", branch, "main")
        if not allow_empty:
            self._write_release(version, content)
        if mutate:
            mutate()
        self._commit("Candidate", allow_empty=allow_empty)
        head = self._head()
        self._remote_ref(branch, head)
        return branch, head

    def test_valid_candidate_is_accepted_and_reports_outputs(self):
        branch, head = self._candidate("1.0.0-beta.2")

        outputs = validator.validate_release(self.repo, branch, head)

        self.assertEqual(outputs["version"], "1.0.0-beta.2")
        self.assertEqual(outputs["file_count"], "3")
        self.assertEqual(outputs["has_changes"], "true")
        self.assertEqual(outputs["base_sha"], self.base_sha)

    def test_same_version_identical_empty_commit_is_a_noop(self):
        branch, head = self._candidate(self.BASE_VERSION, allow_empty=True)

        outputs = validator.validate_release(self.repo, branch, head)

        self.assertEqual(outputs["has_changes"], "false")

    def test_same_version_with_different_content_is_rejected(self):
        branch, head = self._candidate(self.BASE_VERSION, content="changed\n")

        with self.assertRaisesRegex(validator.ValidationError, "different content"):
            validator.validate_release(self.repo, branch, head)

    def test_version_rollback_is_rejected(self):
        branch, head = self._candidate("1.0.0-beta.1.1")

        with self.assertRaisesRegex(validator.ValidationError, "older than base"):
            validator.validate_release(self.repo, branch, head)

    def test_out_of_scope_change_is_rejected(self):
        def mutate():
            (self.repo / "README.md").write_text("out of scope\n", encoding="utf-8")

        branch, head = self._candidate("1.0.0-beta.2", mutate=mutate)

        with self.assertRaisesRegex(
            validator.ValidationError, "outside salesforce-for-sales"
        ):
            validator.validate_release(self.repo, branch, head)

    def test_symlink_is_rejected(self):
        def mutate():
            os.symlink("README.md", self.repo / "salesforce-for-sales" / "linked-readme")

        branch, head = self._candidate("1.0.0-beta.2", mutate=mutate)

        with self.assertRaisesRegex(
            validator.ValidationError, "non-executable regular files"
        ):
            validator.validate_release(self.repo, branch, head)

    def test_executable_file_is_rejected(self):
        def mutate():
            executable = self.repo / "salesforce-for-sales" / "run.sh"
            executable.write_text("#!/bin/sh\n", encoding="utf-8")
            executable.chmod(0o755)

        branch, head = self._candidate("1.0.0-beta.2", mutate=mutate)

        with self.assertRaisesRegex(
            validator.ValidationError, "non-executable regular files"
        ):
            validator.validate_release(self.repo, branch, head)

    def test_branch_version_must_match_metadata(self):
        _, head = self._candidate("1.0.0-beta.2")
        mismatched = "automation/salesforce-for-sales-v1.0.0-beta.3"
        self._remote_ref(mismatched, head)

        with self.assertRaisesRegex(validator.ValidationError, "does not match branch"):
            validator.validate_release(self.repo, mismatched, head)

    def test_stale_head_and_stale_base_are_rejected(self):
        branch, head = self._candidate("1.0.0-beta.2")
        with self.assertRaisesRegex(validator.ValidationError, "candidate ref moved"):
            validator.validate_release(self.repo, branch, "0" * 40)

        self._git("switch", "--quiet", "main")
        (self.repo / "base-advanced.txt").write_text("advanced\n", encoding="utf-8")
        self._commit("Advance main")
        self._remote_ref("main", self._head())
        with self.assertRaisesRegex(validator.ValidationError, "is not current main"):
            validator.validate_release(self.repo, branch, head)


if __name__ == "__main__":
    unittest.main(verbosity=2)
