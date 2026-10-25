import contextlib
import io
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

import rr_entry as entry
import runrunit_api as api


class ConfigurationTests(unittest.TestCase):
    def test_parse_whitelist_quotes_and_no_execution(self):
        text = '''RUNRUNIT_APP_KEY="literal-key"
RUNRUNIT_USER_TOKEN='literal-token'
export RUNRUNIT_USER_ID=example
UNRELATED=ignore
RUNRUNIT_UPLOAD_URL=$(never-execute)
'''
        values = entry.parse_config(text)
        self.assertEqual(values['RUNRUNIT_USER_ID'], 'example')
        self.assertEqual(values['RUNRUNIT_UPLOAD_URL'], '$(never-execute)')
        self.assertNotIn('UNRELATED', values)

    def test_load_preserves_environment_and_supports_explicit_path(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'env'; p.write_text('RUNRUNIT_APP_KEY=file-key\nRUNRUNIT_USER_ID=example\n')
            with patch.dict(os.environ, {'RUNRUNIT_ENV_FILE': str(p), 'RUNRUNIT_APP_KEY': 'environment-key'}, clear=True):
                entry.load_config()
                self.assertEqual(os.environ['RUNRUNIT_APP_KEY'], 'environment-key')
                self.assertEqual(os.environ['RUNRUNIT_USER_ID'], 'example')

    def test_windows_config_directory(self):
        native_path = type(Path())
        expected = native_path('/example/appdata') / 'runrunit-cli' / 'env'
        with patch.object(entry.os, 'name', 'nt'), patch.dict(os.environ, {'APPDATA': '/example/appdata'}, clear=True), patch.object(entry, 'Path', native_path):
            self.assertEqual(entry.default_config_path(), expected)

    def test_help_never_requires_credentials_or_api(self):
        with patch.object(api, 'call') as call, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as result: entry.configure(['--help'])
            self.assertEqual(result.exception.code, 0)
            call.assert_not_called()

    def test_wizard_validates_then_saves_without_echoing_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'config' / 'env'
            out = io.StringIO()
            with patch.object(entry, 'config_path', return_value=path), patch.object(entry.sys.stdin, 'isatty', return_value=True), patch.object(entry.getpass, 'getpass', side_effect=['mock-key-unique', 'mock-token-unique']), patch.object(api, 'call', return_value={'status': 200, 'body': [{'id': 'example-user'}]}), contextlib.redirect_stdout(out):
                entry.configure([])
            values = entry.parse_config(path.read_text())
            self.assertEqual(values['RUNRUNIT_USER_ID'], 'example-user')
            self.assertEqual(values['RUNRUNIT_USER_TOKEN'], 'mock-token-unique')
            self.assertNotIn('mock-token-unique', out.getvalue())
            self.assertNotIn('mock-key-unique', out.getvalue())
            if os.name != 'nt': self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_failed_validation_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'env'; path.write_text('preserved')
            with patch.object(entry, 'config_path', return_value=path), patch.object(entry.sys.stdin, 'isatty', return_value=True), patch('builtins.input', return_value='s'), patch.object(entry.getpass, 'getpass', side_effect=['key', 'token']), patch.object(api, 'call', side_effect=SystemExit(1)), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit): entry.configure([])
            self.assertEqual(path.read_text(), 'preserved')

    def test_declined_overwrite_does_not_request_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'env'; path.write_text('preserved')
            with patch.object(entry, 'config_path', return_value=path), patch.object(entry.sys.stdin, 'isatty', return_value=True), patch('builtins.input', return_value='n'), patch.object(entry.getpass, 'getpass') as prompt, contextlib.redirect_stdout(io.StringIO()):
                entry.configure([]); prompt.assert_not_called()
            self.assertEqual(path.read_text(), 'preserved')


if __name__ == '__main__': unittest.main()
