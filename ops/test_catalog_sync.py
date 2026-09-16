"""Changing context settings must invalidate pinned metadata without editing user thresholds."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import manage


class CatalogSyncTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.core, self.codex = root / 'bridge', root / 'codex'
        (self.core / 'local-ops').mkdir(parents=True)
        self.codex.mkdir()
        self.bridge = self.core / 'config.json'
        self.bridge.write_text(json.dumps({'mode': 'full', 'proAvailable': True,
                                          'experimentalBiggerContext': False}))
        self.config = self.codex / 'config.toml'
        self.original = 'model="gpt-6-astra"\nmodel_context_window=1000000\nmodel_auto_compact_token_limit=900000\n'
        self.config.write_text(self.original)
        (self.codex / 'auth.json').write_text('{"tokens":{"access_token":"fake-local-test"}}')
        self.catalog = self.core / 'local-ops/web-models.json'
        self.catalog.write_text('{"models":[]}')
        for p in (patch.object(manage, 'CORE', self.core), patch.object(manage, 'CODEX', self.codex)):
            p.start()
            self.addCleanup(p.stop)
        self.save_state()

    def save_state(self):
        manage.atomic_private_json(self.core / 'local-ops/catalog-state.json', {
            'inputs': manage.catalog_inputs(), 'sha256': hashlib.sha256(self.catalog.read_bytes()).hexdigest()})

    def toggle(self):
        c = json.loads(self.bridge.read_text())
        c['experimentalBiggerContext'] = True
        self.bridge.write_text(json.dumps(c))

    def test_toggle_invalidates_and_unchanged_does_not_fetch(self):
        self.assertTrue(manage.catalog_is_current())
        with patch.object(manage, 'refresh_catalog') as refresh:
            manage.sync_catalog()
            refresh.assert_not_called()
            self.toggle()
            self.assertFalse(manage.catalog_is_current())
            manage.sync_catalog()
            refresh.assert_called_once()
        self.assertEqual(self.config.read_text(), self.original)

    def test_native_context_change_invalidates_but_model_pick_does_not(self):
        self.config.write_text(self.original.replace('gpt-6-astra', 'chatgpt-web/pro'))
        self.assertTrue(manage.catalog_is_current())
        self.config.write_text(self.original.replace('1000000', '1050000'))
        self.assertFalse(manage.catalog_is_current())

    def test_failed_refresh_keeps_previous_snapshot(self):
        before = self.catalog.read_bytes()
        self.toggle()
        with patch.object(manage, 'refresh_catalog', side_effect=OSError('offline')), patch.object(manage.time, 'sleep'):
            with self.assertRaises(OSError):
                manage.sync_catalog()
        self.assertEqual(self.catalog.read_bytes(), before)
        self.assertFalse(manage.catalog_is_current())

    def test_refresh_publishes_metadata_and_preserves_native_settings(self):
        self.toggle()
        catalogue = {'models': [{'slug': 'chatgpt-web/pro', 'apply_patch_tool_type': 'freeform',
                                'auto_compact_token_limit': 285000}]}
        response = Mock()
        response.__enter__ = Mock(return_value=io.StringIO(json.dumps(catalogue)))
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        with patch.object(manage, 'health', return_value={'service': 'codex-chatgpt-web', 'mode': 'full'}), \
                patch.object(manage.subprocess, 'check_output', return_value='codex-cli 0.154.0'), \
                patch.object(manage.urllib.request, 'build_opener', return_value=opener), \
                contextlib.redirect_stdout(io.StringIO()):
            manage.refresh_catalog()
        self.assertEqual(json.loads(self.catalog.read_text()), catalogue)
        self.assertTrue(manage.catalog_is_current())
        self.assertEqual(self.config.read_text(), self.original)

    def test_snapshot_tamper_invalidates(self):
        self.catalog.write_text('{"models":[],"changed":true}')
        self.assertFalse(manage.catalog_is_current())


if __name__ == '__main__':
    unittest.main()
