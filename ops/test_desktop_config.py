"""Desktop integration must restore only its own fields and preserve concurrent edits."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import manage


class DesktopConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.codex, self.core = root / 'codex', root / 'bridge'
        self.codex.mkdir()
        (self.core / 'local-ops').mkdir(parents=True)
        (self.core / 'local-ops/web-models.json').write_text('{"models":[]}')
        self.config = self.codex / 'config.toml'
        self.original = ('# Keep this comment\nmodel = "gpt-6-astra" # user choice\n'
                         'model_provider = "custom"\nservice_tier = "fast"\n'
                         'openai_base_url = "http://127.0.0.1:17841/v1"\n'
                         '\n[features]\nmulti_agent = true\n')
        self.config.write_text(self.original)
        self.patches = [patch.object(manage, 'CODEX', self.codex),
                        patch.object(manage, 'CORE', self.core)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def switch(self, enabled):
        with contextlib.redirect_stdout(io.StringIO()):
            manage.desktop_config(enabled)

    def test_roundtrip_preserves_bytes_and_unrelated_concurrent_edit(self):
        self.switch(True)
        self.config.write_text(self.config.read_text().replace('multi_agent = true', 'multi_agent = false'))
        self.switch(False)
        self.assertEqual(self.config.read_text(), self.original.replace('multi_agent = true', 'multi_agent = false'))
        self.switch(False)

    def test_web_picker_selection_restores_previous_native_model(self):
        self.switch(True)
        self.config.write_text(self.config.read_text().replace('chatgpt-web/high', 'chatgpt-web/pro'))
        self.switch(False)
        self.assertEqual(self.config.read_text(), self.original)

    def test_new_native_selection_is_preserved(self):
        self.switch(True)
        self.config.write_text(self.config.read_text().replace('chatgpt-web/high', 'gpt-5.6-sol'))
        self.switch(False)
        self.assertIn('model = "gpt-5.6-sol"', self.config.read_text())

    def test_conflicting_provider_is_not_overwritten(self):
        self.switch(True)
        changed = self.config.read_text().replace('model_provider = "openai"', 'model_provider = "other"')
        self.config.write_text(changed)
        for enabled in (False, True):
            with self.assertRaises(RuntimeError):
                self.switch(enabled)
            self.assertEqual(self.config.read_text(), changed)

    def test_prepared_journal_recovers_without_losing_original(self):
        self.switch(True)
        journal = self.core / 'local-ops/desktop-integration.json'
        state = json.loads(journal.read_text())
        state['phase'] = 'prepared'
        journal.write_text(json.dumps(state))
        self.switch(True)
        self.switch(False)
        self.assertEqual(self.config.read_text(), self.original)


if __name__ == '__main__':
    unittest.main()
