import unittest
from unittest.mock import patch

from dashboard.config import ROOT, build_connection_string, load_settings


class ConfigTests(unittest.TestCase):
    @patch.dict('os.environ', {}, clear=True)
    def test_special_characters_are_quoted(self):
        settings = load_settings(ROOT / 'config.example.ini')
        settings['database']['password'] = 'pass%;word}x'
        self.assertIn('PWD={pass%;word}}x};', build_connection_string(settings))

    @patch.dict('os.environ', {'SPEL_SQL_CONNECTION_STRING': 'custom-odbc-string'}, clear=True)
    def test_raw_environment_override(self):
        self.assertEqual(build_connection_string(load_settings(ROOT / 'config.example.ini')), 'custom-odbc-string')

    @patch.dict('os.environ', {}, clear=True)
    def test_windows_auth_needs_no_password(self):
        settings = load_settings(ROOT / 'config.example.ini')
        settings['database']['authentication'] = 'windows'
        result = build_connection_string(settings)
        self.assertIn('Trusted_Connection=yes', result)
        self.assertNotIn('PWD=', result)
