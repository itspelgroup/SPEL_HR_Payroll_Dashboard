import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from app import create_app
from dashboard.config import ROOT


class AttendanceDashboardTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(ROOT / 'config.example.ini').test_client()

    def test_sample_overview_and_assets(self):
        response = self.client.get('/attendance')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Sample data', response.data)
        self.assertIn(b'No database connected', response.data)
        with self.client.get('/static/dashboard.css') as asset:
            self.assertEqual(asset.status_code, 200)

    def test_filters_change_counts_without_losing_zero_punch_groups(self):
        html = self.client.get('/attendance', query_string={'unit': json.dumps('UNIT3'),
                                                  'location': json.dumps('pandoki')}).text
        self.assertIn('<strong>3</strong>', html)
        self.assertIn('<strong>2</strong>', html)
        self.assertNotIn('data-title="UNIT6"', html)
        html = self.client.get('/attendance', query_string={'unit': json.dumps('UNIT8')}).text
        self.assertIn('<strong>0</strong>', html)
        self.assertIn('data-title="UNIT8"', html)

    def test_location_clears_unit_outside_selected_scope(self):
        location = json.dumps('pandoki')
        expected = self.client.get('/attendance', query_string={'location': location}).text
        actual = self.client.get('/attendance', query_string={
            'location': location, 'unit': json.dumps('UNIT8')}).text
        self.assertEqual(actual, expected)

    def test_empty_and_escaped_filter(self):
        html = self.client.get('/attendance?unit=%3Cscript%3E').text
        self.assertIn('No registered employees match', html)
        self.assertNotIn('<script>', html)

    def test_live_only_deployment_rejects_demo_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.ini'
            config.write_text(
                '[application]\ndata_mode = demo\n'
                '[database]\nenabled = false\n'
                '[deployment]\nlive_only = true\n',
                encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'requires live data mode'):
                create_app(config)

    def test_live_deployment_does_not_import_demo_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.ini'
            config.write_text(
                '[application]\ndata_mode = live\n'
                '[database]\nenabled = true\n'
                '[cache]\nenabled = true\n'
                '[deployment]\nlive_only = true\n'
                '[security]\nenabled = true\n'
                'user_file = ' + str(root / 'users.ini') + '\n'
                'account_directory = ' + str(root / 'instance') + '\n',
                encoding='utf-8')
            with patch.dict('sys.modules', {'dashboard.demo': None}):
                client = create_app(config).test_client()
                response = client.get('/')
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.location, '/setup')


if __name__ == '__main__':
    unittest.main()
