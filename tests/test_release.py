"""Check the release workflow and its small preparation step without networking."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).parents[1]


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load((ROOT / '.github/workflows/release.yml').read_text())
        self.steps = self.workflow['jobs']['release']['steps']
        self.prepare = next(step for step in self.steps if step.get('id') == 'prepare')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        manifest = self.root / 'custom_components/freshpoint/manifest.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'version': '0.3.1'}))
        notes = self.root / 'release_notes/0.3.1.md'
        notes.parent.mkdir()
        notes.write_text('Release notes for HACS')
        binaries = self.root / 'bin'
        binaries.mkdir()
        (binaries / 'gh').write_text('''#!/bin/sh
case "$TEST_RELEASE" in
  existing) printf '{"draft":false,"prerelease":false}';;
  draft) printf '{"draft":true,"prerelease":false}';;
  forbidden) echo '(HTTP 403)' >&2; exit 1;;
  *) echo '(HTTP 404)' >&2; exit 1;;
esac
''')
        (binaries / 'git').write_text('''#!/bin/sh
case "$1" in
  ls-remote) test -z "$TEST_TAG_SHA" || echo "$TEST_TAG_SHA refs/tags/v0.3.1"; exit 0;;
  fetch) exit 0;;
  rev-parse) echo "$TEST_TAG_SHA";;
  *) exit 1;;
esac
''')
        for binary in binaries.iterdir():
            binary.chmod(0o755)
        self.env = {
            **os.environ,
            'PATH': str(binaries) + os.pathsep + os.environ['PATH'],
            'GITHUB_REPOSITORY': 'example/repo',
            'GITHUB_SHA': 'a' * 40,
            'GITHUB_OUTPUT': str(self.root / 'output'),
            'RUNNER_TEMP': str(self.root),
            'TEST_RELEASE': 'missing',
            'TEST_TAG_SHA': '',
        }

    def run_prepare(self, **overrides):
        return subprocess.run(
            ['bash', '-e', '-o', 'pipefail', '-c', self.prepare['run']],
            cwd=self.root, env={**self.env, **overrides}, capture_output=True, text=True,
        )

    def output(self):
        path = self.root / 'output'
        return path.read_text() if path.exists() else ''

    def test_new_release_passes_version_and_notes_to_action(self):
        result = self.run_prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output(), 'tag=v0.3.1\nnotes=release_notes/0.3.1.md\npublish=true\n')

    def test_existing_release_is_not_updated(self):
        result = self.run_prepare(TEST_RELEASE='existing')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output(), 'publish=false\n')

    def test_api_failure_does_not_mean_missing_release(self):
        self.assertNotEqual(self.run_prepare(TEST_RELEASE='forbidden').returncode, 0)
        self.assertNotIn('publish=true', self.output())

    def test_draft_is_not_silently_published(self):
        self.assertNotEqual(self.run_prepare(TEST_RELEASE='draft').returncode, 0)
        self.assertNotIn('publish=true', self.output())

    def test_conflicting_tag_is_rejected(self):
        self.assertNotEqual(self.run_prepare(TEST_TAG_SHA='b' * 40).returncode, 0)
        self.assertNotIn('publish=true', self.output())

    def test_existing_tag_at_validated_commit_is_accepted(self):
        result = self.run_prepare(TEST_TAG_SHA='a' * 40)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('publish=true', self.output())

    def test_missing_or_empty_notes_fail(self):
        notes = self.root / 'release_notes/0.3.1.md'
        notes.unlink()
        self.assertNotEqual(self.run_prepare().returncode, 0)
        notes.write_text(' \n')
        self.assertNotEqual(self.run_prepare().returncode, 0)
        self.assertNotIn('publish=true', self.output())

    def test_invalid_version_fails_before_api_calls(self):
        manifest = self.root / 'custom_components/freshpoint/manifest.json'
        for value in ('../notes', '0.3.1beta', '01.2.3'):
            manifest.write_text(json.dumps({'version': value}))
            self.assertNotEqual(self.run_prepare().returncode, 0)
        self.assertNotIn('publish=true', self.output())

    def test_publication_is_gated_and_uses_prebuilt_action(self):
        job = self.workflow['jobs']['release']
        self.assertEqual(job['needs'], 'validate')
        self.assertEqual(job['if'], "github.ref == 'refs/heads/main'")
        self.assertEqual(job['runs-on'], 'ubuntu-latest')
        publish = self.steps[-1]
        self.assertEqual(publish['uses'], 'softprops/action-gh-release@v3')
        self.assertEqual(publish['if'], "steps.prepare.outputs.publish == 'true'")
        self.assertEqual(publish['with']['target_commitish'], '${{ github.sha }}')
        self.assertEqual(publish['with']['body_path'], '${{ steps.prepare.outputs.notes }}')
        validation = yaml.safe_load((ROOT / '.github/workflows/validate.yml').read_text())
        self.assertIn('workflow_call', validation['on'])
        self.assertEqual(validation['jobs']['validate']['runs-on'], 'ubuntu-latest')
        uses = [step.get('uses') for step in validation['jobs']['validate']['steps']]
        self.assertIn('actions/checkout@v7', uses)
        self.assertIn('actions/setup-python@v7', uses)
