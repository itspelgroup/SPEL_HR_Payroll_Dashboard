from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

from app import create_app
from dashboard.attendance import PAKISTAN
from dashboard.config import ROOT, load_settings
from dashboard.machines import Machine, MachinePunch, MachineSnapshot, SqlMachines, recent_punch


class MachineHistoryTests(unittest.TestCase):
    def test_ten_minute_indicator_uses_punch_time_and_rejects_future_dates(self):
        now = datetime(2026, 10, 31, 12, tzinfo=PAKISTAN)
        for seconds, expected in ((0, True), (599, True), (600, False), (-1, False)):
            self.assertEqual(recent_punch(now - timedelta(seconds=seconds), now), expected)
        self.assertFalse(recent_punch(None, now))

    @patch('pyodbc.connect')
    def test_punch_history_attaches_to_its_machine_and_employee_unit(self, connect):
        now = datetime.now(PAKISTAN)
        cursor = connect.return_value.cursor.return_value
        cursor.fetchone.return_value = ('SPEL_ATTENDENCE', 2)
        cursor.fetchall.side_effect = [
            [('A', 'Machine A', 'Pandoki', None, True, now, now),
             ('B', 'Machine B', 'Karachi', None, True, None, None)],
            [('A', 10, '001', now, now, 'Person A', 'EMP-UNIT', 'Room A')]]
        settings = load_settings(ROOT / 'config.example.ini')
        settings.set('database', 'authentication', 'windows')
        snapshot = SqlMachines(settings)(now.date())
        self.assertEqual(snapshot.machines[0].punches[0].employee_unit, 'EMP-UNIT')
        self.assertEqual(snapshot.machines[1].punches, ())
        calls = cursor.execute.call_args_list
        self.assertIn('TOP (?)', calls[-1].args[0])
        self.assertEqual(calls[-1].args[1], 15)
        self.assertIn('ORDER BY CHECKTIME DESC, ID DESC', calls[-1].args[0])

    def test_tile_omits_employee_unit_and_popup_displays_history(self):
        now = datetime.now(PAKISTAN)
        machine = Machine('A', 'Machine A', 'Pandoki', 'LEGACY-MACHINE-UNIT', True, now, now,
                          punches=(MachinePunch(1, '001', now, now, 'Person A', 'EMP-UNIT', 'Room A'),))
        client = create_app(ROOT / 'config.example.ini', machine_provider=lambda day:
                            MachineSnapshot((machine,), now, day)).test_client()
        html = client.get('/').text
        self.assertNotIn('LEGACY-MACHINE-UNIT', html)
        self.assertIn('Last 15 employee punches', html)
        self.assertIn('EMP-UNIT', html)
        self.assertIn('Person A', html)
        self.assertIn('fresh-punch', html)
        self.assertIn('machine-wall.css', html)
        self.assertIn('id="wall-clock"', html)
        self.assertNotIn('Employee unit', html.split('<dialog', 1)[0])


if __name__ == '__main__':
    unittest.main()
