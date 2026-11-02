import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from app import create_app
from dashboard.attendance import PAKISTAN
from dashboard.config import ROOT
from dashboard.machines import Machine, MachineSnapshot, machine_status, SqlMachines


class MachineTests(unittest.TestCase):
    def test_status_boundaries_and_unknown_receipts(self):
        now = datetime(2026, 10, 31, 12, tzinfo=PAKISTAN)
        for minutes, expected in ((0, 'Recent'), (60, 'Delayed'), (61, 'Delayed'),
                                  (1440, 'Delayed'), (1441, 'No recent punches'),
                                  (-1, 'Check timestamp')):
            machine = Machine('A', 'A', 'Pandoki', 'U1', True, now - timedelta(minutes=minutes),
                              now - timedelta(minutes=minutes))
            self.assertEqual(machine_status(machine, now, 60, 1440), expected)
        self.assertEqual(machine_status(Machine('A', 'A', None, None, True, None, None),
                                        now, 60, 1440), 'No punches received')
        self.assertEqual(machine_status(Machine('A', 'A', None, None, False, now, now),
                                        now, 60, 1440), 'Disabled')

    def test_location_totals_include_disabled_and_never_used_machines(self):
        now = datetime.now(PAKISTAN)
        loader = Mock(side_effect=lambda day: MachineSnapshot((
            Machine('A', 'First machine', 'Pandoki', 'U1', True, now, now),
            Machine('B', 'Second machine', 'PANDOKI', 'U2', False, None, None),
            Machine('C', 'Third machine', 'Karachi', 'U8', True, None, None),
        ), now, day))
        client = create_app(ROOT / 'config.example.ini', machine_provider=loader).test_client()
        self.assertIn('Machines', client.get('/').text)
        html = client.get('/', query_string={'location': json.dumps('pandoki')}).text
        self.assertIn('First machine', html)
        self.assertIn('Second machine', html)
        self.assertNotIn('Third machine', html)
        self.assertEqual(html.count('class="wall-tile '), 2)
        self.assertNotIn('<table', html.split('<dialog', 1)[0])
        self.assertIn('data-dialog="machine-A"', html)
        self.assertNotIn('Machine overview totals', html)
        self.assertIn('data-refresh-seconds="60"', html)
        self.assertIn('selected', html.split('<select', 1)[1].split('</select>', 1)[0])
        self.assertIn('machines.js', html)
        loader.assert_called_once()

    @patch('pyodbc.connect')
    def test_machine_page_startup_never_connects(self, connect):
        create_app(ROOT / 'config.example.ini')
        connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
