"""Verify release publishing decisions without contacting GitHub."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("publish_release", ROOT / ".github/scripts/publish_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        manifest = self.root / "custom_components/freshpoint/manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"version": "0.3.1"}))
        notes = self.root / "release_notes/0.3.1.md"
        notes.parent.mkdir()
        notes.write_text("Release notes for HACS")
        self.calls = []
        self.responses = {}
        self.env = patch.dict(os.environ, {"GITHUB_REF": "refs/heads/main", "GITHUB_SHA": "a" * 40})
        self.env.start()
        self.addCleanup(self.env.stop)

    def api(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "POST":
            return {"html_url": "https://github.com/example/repo/releases/tag/v0.3.1"}
        return self.responses.get(path)

    def test_first_release_creates_tag_at_validated_commit(self):
        release.publish(self.root, self.api)
        payload = self.calls[-1][2]
        self.assertEqual(payload["tag_name"], "v0.3.1")
        self.assertEqual(payload["target_commitish"], "a" * 40)
        self.assertEqual(payload["body"], "Release notes for HACS")
        self.assertFalse(payload["draft"])
        self.assertFalse(payload["prerelease"])

    def test_existing_release_skips_without_changes(self):
        self.responses["releases/tags/v0.3.1"] = {"draft": False, "prerelease": False}
        release.publish(self.root, self.api)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0], "GET")

    def test_conflicting_tag_fails_without_mutation(self):
        self.responses["git/ref/tags/v0.3.1"] = {"object": {"type": "commit", "sha": "b" * 40}}
        with self.assertRaisesRegex(ValueError, "different commit"):
            release.publish(self.root, self.api)
        self.assertTrue(all(method == "GET" for method, _, _ in self.calls))

    def test_annotated_tag_at_same_commit_can_be_released(self):
        self.responses["git/ref/tags/v0.3.1"] = {"object": {"type": "tag", "sha": "b" * 40}}
        self.responses["git/tags/" + "b" * 40] = {"object": {"type": "commit", "sha": "a" * 40}}
        release.publish(self.root, self.api)
        self.assertEqual(self.calls[-1][0], "POST")

    def test_missing_or_empty_notes_block_release(self):
        notes = self.root / "release_notes/0.3.1.md"
        notes.unlink()
        with self.assertRaises(FileNotFoundError):
            release.publish(self.root, self.api)
        notes.write_text(" \n")
        with self.assertRaisesRegex(ValueError, "empty"):
            release.publish(self.root, self.api)
        self.assertTrue(all(method == "GET" for method, _, _ in self.calls))

    def test_non_main_and_invalid_versions_fail(self):
        with patch.dict(os.environ, {"GITHUB_REF": "refs/heads/feature"}):
            with self.assertRaisesRegex(ValueError, "main"):
                release.publish(self.root, self.api)
        manifest = self.root / "custom_components/freshpoint/manifest.json"
        for version in ("../notes", "0.3.1beta", "01.2.3"):
            manifest.write_text(json.dumps({"version": version}))
            with self.assertRaises(ValueError):
                release.publish(self.root, self.api)
        self.assertEqual(self.calls, [])

    def test_workflow_gates_release_on_validation(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
        self.assertEqual(workflow["on"]["push"]["branches"], ["main"])
        self.assertEqual(workflow["jobs"]["release"]["needs"], "validate")
        self.assertEqual(workflow["jobs"]["validate"]["uses"], "./.github/workflows/validate.yml")
        validation = yaml.safe_load((ROOT / ".github/workflows/validate.yml").read_text())
        self.assertIn("workflow_call", validation["on"])
        checkout = workflow["jobs"]["release"]["steps"][0]
        self.assertEqual(checkout["with"]["ref"], "${{ github.sha }}")
        self.assertFalse(checkout["with"]["persist-credentials"])
