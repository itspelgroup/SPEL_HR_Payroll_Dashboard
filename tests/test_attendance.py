import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from app import create_app
from dashboard.attendance import (AttendanceUnavailable, Group, PAKISTAN,
                                  SharedAttendanceCache, Snapshot, SqlAttendance,
                                  Employee, display_name, make_snapshot)
from dashboard.config import ROOT, load_settings


def sample(day):
    employees = [Employee(str(i), 'Test person', 'UNIT3', None, i < 3, True,
                          ('Pandoki',)) for i in range(5)]
    employees += [Employee(str(i), 'Test person', None, None, False, True) for i in range(5, 7)]
    employees.append(Employee('unmapped', 'Name unavailable', None, None, True, False))
    return make_snapshot(employees, day)


class CacheTests(unittest.TestCase):
    def test_concurrent_requests_share_one_load(self):
        loader = Mock(side_effect=sample)
        cache = SharedAttendanceCache(loader, 60)
        day = date(2026, 10, 29)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: cache.get(day), range(20)))
        loader.assert_called_once_with(day)
        self.assertEqual(len(results), 20)

    def test_failed_refresh_retains_same_day_and_backs_off(self):
        clock = Mock(return_value=0)
        loader = Mock(side_effect=[sample(date(2026, 10, 29)), RuntimeError('secret')])
        cache = SharedAttendanceCache(loader, 60, clock)
        day = date(2026, 10, 29)
        cache.get(day)
        clock.return_value = 61
        snapshot, stale = cache.get(day)
        self.assertTrue(stale)
        self.assertEqual(snapshot.day, day)
        cache.get(day)
        self.assertEqual(loader.call_count, 2)

    def test_rollover_never_displays_previous_day(self):
        loader = Mock(side_effect=[sample(date(2026, 10, 29)), RuntimeError('secret')])
        cache = SharedAttendanceCache(loader, 60)
        cache.get(date(2026, 10, 29))
        with self.assertRaises(AttendanceUnavailable):
            cache.get(date(2026, 10, 30))


class EmployeeNameTests(unittest.TestCase):
    def test_name_falls_back_for_blank_numeric_and_placeholder_values(self):
        for name in (None, '', '  ', '001', '123456', 'User001', 'Employee 001', 'NULL'):
            self.assertEqual(display_name('001', name, 'Payroll Person'), 'Payroll Person')
        self.assertEqual(display_name('001', 'Valid Person', 'Payroll Person'), 'Valid Person')
        self.assertEqual(display_name('001', 'علی', None), 'علی')
        self.assertEqual(display_name('001', None, None), 'Name unavailable')


class SqlProviderTests(unittest.TestCase):
    @patch('dashboard.attendance.build_connection_string', return_value='mock-only')
    @patch('pyodbc.connect')
    def test_only_fixed_selects_and_date_parameters(self, connect, _):
        connection = connect.return_value
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = ('SPEL_ATTENDENCE', 2)
        cursor.fetchall.side_effect = [[
            ('001', 'User001', 'Proper Person', 'UNIT3', None, '001', 'Pandoki'),
            ('001', 'User001', 'Proper Person', 'UNIT3', None, '001', 'PANDOKI'),
            ('002', 'Other Person', None, 'UNIT3', None, None, 'Pandoki'),
            (None, None, None, None, None, '099', None)],
            [('Pandoki', 'UNIT3'), ('Empty Location', 'UNIT9')]]
        provider = SqlAttendance(load_settings(ROOT / 'config.example.ini'))
        snapshot = provider(date(2026, 10, 29))
        self.assertEqual(snapshot.unmapped, 1)
        self.assertEqual(snapshot.groups[0].registered, 2)
        self.assertEqual(snapshot.groups[0].punched, 1)
        self.assertEqual(snapshot.employees[0].name, 'Proper Person')
        self.assertEqual(snapshot.employees[0].locations, ('Pandoki',))
        self.assertTrue(connect.call_args.kwargs['readonly'])
        self.assertTrue(connect.call_args.kwargs['autocommit'])
        self.assertEqual(connection.timeout, 15)
        calls = cursor.execute.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertIn(('Empty Location', 'UNIT9'), snapshot.device_units)
        self.assertEqual(calls[1].args[1:], (datetime(2026, 10, 29), datetime(2026, 10, 30)))
        connection.close.assert_called_once()
        cursor.close.assert_called_once()

    @patch('dashboard.attendance.build_connection_string', return_value='mock-only')
    @patch('pyodbc.connect')
    def test_unexpected_database_stops_before_attendance_query(self, connect, _):
        cursor = connect.return_value.cursor.return_value
        cursor.fetchone.return_value = ('MISC', 2)
        with self.assertRaises(AttendanceUnavailable):
            SqlAttendance(load_settings(ROOT / 'config.example.ini'))(date(2026, 10, 29))
        self.assertEqual(cursor.execute.call_count, 1)


class LivePageTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'test.ini'
        self.path.write_text('[application]\ndata_mode=live\n[database]\nenabled=true\n'
                             '[cache]\nenabled=true\n[security]\nenabled=false\n', encoding='utf-8')

    def test_live_filters_use_one_snapshot_and_null_groups_remain_visible(self):
        loader = Mock(side_effect=sample)
        client = create_app(self.path, provider=loader).test_client()
        html = client.get('/attendance').text
        self.assertIn('SQL attendance data', html)
        self.assertIn('Not assigned', html)
        self.assertNotIn('Sample data', html)
        html = client.get('/attendance', query_string={'unit': json.dumps(None)}).text
        self.assertIn('<strong>2</strong>', html)
        self.assertIn('<strong>0</strong>', html)
        self.assertEqual(loader.call_count, 1)

    def test_failure_does_not_leak_details_or_show_fake_zero_counts(self):
        client = create_app(self.path, provider=Mock(side_effect=RuntimeError('PWD=secret'))).test_client()
        response = client.get('/attendance')
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'Attendance data is unavailable', response.data)
        self.assertNotIn(b'secret', response.data)
        self.assertNotIn(b'Filtered attendance counts', response.data)

    def test_location_contains_multiple_units_without_double_counting(self):
        def loader(day):
            return make_snapshot([
                Employee('001', 'First Person', 'UNIT1', None, True, True, ('Pandoki',)),
                Employee('002', 'Second Person', 'UNIT2', None, False, True, ('Pandoki', 'Karachi')),
                Employee('003', 'Third Person', 'UNIT8', None, True, True, ('Karachi',)),
            ], day)
        client = create_app(self.path, provider=loader).test_client()
        html = client.get('/attendance', query_string={'location': json.dumps('pandoki')}).text
        self.assertIn('data-title="UNIT1"', html)
        self.assertIn('data-title="UNIT2"', html)
        self.assertNotIn('data-title="UNIT8"', html)
        self.assertIn('<strong>2</strong>', html)
        self.assertIn('First Person', html)
        self.assertNotIn('Third Person', html)
        self.assertIn('ATTENDANCE OVERVIEW', html)
        self.assertNotIn('name="department"', html)
        self.assertIn('<strong>3</strong>', client.get('/attendance').text)

    def test_device_locations_and_units_include_empty_roster_groups(self):
        loader = Mock(side_effect=lambda day: make_snapshot([
            Employee('001', 'First Person', 'UNIT1', None, True, True, ('Pandoki',)),
        ], day, (('Pandoki', 'UNIT1'), ('Karachi', 'UNIT8'), ('Karachi', 'UNIT9'))))
        client = create_app(self.path, provider=loader).test_client()
        html = client.get('/attendance').text
        self.assertIn('>Karachi</option>', html)
        html = client.get('/attendance', query_string={'location': json.dumps('karachi')}).text
        unit_select = html.split('<select id="unit"', 1)[1].split('</select>', 1)[0]
        self.assertIn('>UNIT8</option>', unit_select)
        self.assertIn('>UNIT9</option>', unit_select)
        self.assertNotIn('>UNIT1</option>', unit_select)
        self.assertIn('No registered employees match', html)
        self.assertEqual(loader.call_count, 1)

    @patch('pyodbc.connect')
    def test_app_startup_does_not_connect(self, connect):
        create_app(self.path)
        connect.assert_not_called()
