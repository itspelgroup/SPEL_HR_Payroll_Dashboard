import unittest
import json

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


if __name__ == '__main__':
    unittest.main()
