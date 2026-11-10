from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from app import create_app
from dashboard.attendance import AttendanceUnavailable, PAKISTAN
from dashboard.config import ROOT, load_settings
from dashboard.hr_hours import (HoursRecord, HoursSnapshot, RangeCache, SqlHrHours,
                                annotate, breakdown, hours, summarize)


def record(identity='001', net='8', overtime='2', **changes):
    values = dict(source='HR_MIS_C', unit='U1', worker='SPEL', employee_id=identity,
                  name='Example Person', department='Production', doc_date=datetime(2026, 11, 1),
                  time_in='08:00', time_out='17:00', direct=1,
                  net=hours(net), overtime=hours(overtime), created_at=None)
    return HoursRecord(**(values | changes))


class HrHoursAnalysisTests(unittest.TestCase):
    def test_union_rows_retained_and_employees_counted_once(self):
        rows = annotate([record(), record(source='HR_MIS'), record('002', '4', '-1'),
                         record('', '0', '1')])
        summary = summarize(rows)
        self.assertEqual(summary['records'], 4)
        self.assertEqual(summary['employees'], 2)
        self.assertEqual(summary['net'], Decimal(20))
        self.assertEqual(summary['overtime'], Decimal(4))
        self.assertEqual(summary['total'], Decimal(24))
        self.assertEqual(summary['ot_share'], Decimal(4)/24*100)
        self.assertEqual(summary['ot_rate'], Decimal(20))
        self.assertEqual(summary['overtime_employees'], 1)
        self.assertEqual(summary['review'], 4)
        self.assertTrue(any('Repeated' in reason for reason in rows[0].flags))

    def test_invalid_zero_and_signed_hours_are_not_hidden(self):
        self.assertIsNone(hours(float('nan')))
        self.assertIsNone(hours(None))
        rows = annotate([record(net='-1', overtime='0'), record('002', '0', '0')])
        self.assertEqual(summarize(rows)['net'], Decimal(-1))
        self.assertIsNone(summarize(rows)['ot_rate'])
        self.assertEqual(summarize([])['employees'], 0)
        self.assertEqual(breakdown(rows, 'unit')[0]['records'], 2)

    def test_range_cache_shares_filters_but_isolates_date_windows(self):
        loader = Mock(side_effect=lambda key: HoursSnapshot((), datetime.now(PAKISTAN), key))
        cache = RangeCache(loader, 300, 2)
        a, b, c = [(date(2026, 11, day), date(2026, 11, day)) for day in (1, 2, 3)]
        cache.get(a); cache.get(a); cache.get(b); cache.get(c)
        self.assertEqual(loader.call_count, 3)
        self.assertEqual(len(cache.entries), 2)
        self.assertNotIn(a, cache.entries)


class HrHoursProviderTests(unittest.TestCase):
    @patch('dashboard.hr_hours.build_connection_string', return_value='mock-only')
    @patch('pyodbc.connect')
    def test_readonly_union_parameters_and_cleanup(self, connect, _):
        settings = load_settings(ROOT / 'config.example.ini')
        cursor = connect.return_value.cursor.return_value
        cursor.fetchone.return_value = (1, 2)
        cursor.fetchmany.return_value = [('HR_MIS_C', 'U1', 'SPEL', '001', 'Payroll Name',
            'HR', datetime(2026, 11, 1), '08:00', '17:00', 1, 8.5, -1.5, None)]
        window = (date(2026, 11, 1), date(2026, 11, 7))
        snapshot = SqlHrHours(settings)(window)
        self.assertEqual(snapshot.records[0].name, 'Payroll Name')
        self.assertEqual(snapshot.records[0].overtime, Decimal('-1.5'))
        calls = cursor.execute.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertIn('UNION ALL', calls[1].args[0])
        self.assertNotIn('SELECT *', calls[1].args[0])
        self.assertEqual(calls[1].args[1:], (50001, datetime(2026, 11, 1), datetime(2026, 11, 8),
                                             datetime(2026, 11, 1), datetime(2026, 11, 8)))
        self.assertTrue(connect.call_args.kwargs['readonly'])
        self.assertTrue(connect.call_args.kwargs['autocommit'])
        self.assertEqual(connect.return_value.timeout, 15)
        connect.return_value.close.assert_called_once()
        cursor.close.assert_called_once()

    @patch('dashboard.hr_hours.build_connection_string', return_value='mock-only')
    @patch('pyodbc.connect')
    def test_row_cap_rejects_partial_totals_and_no_access_stops_query(self, connect, _):
        settings = load_settings(ROOT / 'config.example.ini')
        settings.set('hr_hours', 'max_rows', '1')
        cursor = connect.return_value.cursor.return_value
        cursor.fetchone.return_value = (1, 2)
        cursor.fetchmany.return_value = [(), ()]
        with self.assertRaises(AttendanceUnavailable):
            SqlHrHours(settings)((date(2026, 11, 1), date(2026, 11, 1)))
        cursor.reset_mock()
        cursor.fetchone.return_value = (0, 2)
        with self.assertRaises(AttendanceUnavailable):
            SqlHrHours(settings)((date(2026, 11, 1), date(2026, 11, 1)))
        self.assertEqual(cursor.execute.call_count, 1)


class HrHoursRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(ROOT / 'config.example.ini')
        self.loader = Mock(side_effect=lambda window: HoursSnapshot(annotate([
            record(), record('002', unit='U2', worker='HRSG', department='Quality'),
            record('003', unit='', name='<script>unsafe</script>')]), datetime.now(PAKISTAN), window))
        self.app.extensions['hr_hours_cache'].loader = self.loader
        self.client = self.app.test_client()
        self.query = {'start': '2026-11-01', 'end': '2026-11-07'}

    def details(self, response):
        return json.loads(response.text.split('id="hr-hours-data">', 1)[1].split('</script>', 1)[0])

    def test_filters_share_one_snapshot_and_hours_tab_is_available(self):
        response = self.client.get('/hr-hours', query_string=self.query)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.details(response)), 3)
        self.assertIn('HR Hours</a>', response.text)
        self.assertIn('no-store', response.headers['Cache-Control'])
        response = self.client.get('/hr-hours', query_string=self.query | {'unit': json.dumps('U2')})
        self.assertEqual([r['id'] for r in self.details(response)], ['002'])
        response = self.client.get('/hr-hours', query_string=self.query | {'worker': json.dumps('SPEL')})
        self.assertEqual(len(self.details(response)), 2)
        response = self.client.get('/hr-hours', query_string=self.query | {'unit': json.dumps('')})
        self.assertEqual([r['id'] for r in self.details(response)], ['003'])
        self.assertNotIn('<script>unsafe</script>', response.text)
        self.loader.assert_called_once()

    def test_bad_dates_rejected_before_loading(self):
        for query in ({'start': 'bad'}, {'start': '2026-11-07', 'end': '2026-11-01'},
                      {'start': '2026-01-01', 'end': '2026-11-01'},
                      {'start': '0001-01-01', 'end': '0001-01-01'}):
            self.assertEqual(self.client.get('/hr-hours', query_string=query).status_code, 400)
        self.loader.assert_not_called()

    def test_failure_does_not_leak_connection_details(self):
        self.loader.side_effect = RuntimeError('password-secret')
        response = self.client.get('/hr-hours', query_string=self.query)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('password-secret', response.text)
        self.assertNotIn('id="hr-hours-data"', response.text)

    def test_date_window_changes_load_an_independent_snapshot(self):
        self.client.get('/hr-hours', query_string=self.query)
        self.client.get('/hr-hours', query_string=self.query | {'end': '2026-11-06'})
        self.assertEqual(self.loader.call_count, 2)

    def test_scoped_user_cannot_access_unmapped_hr_location_scope(self):
        with self.app.test_request_context('/hr-hours'):
            from flask import g
            g.dashboard_user = {'is_admin': False, 'location': 'Pandoki'}
            with self.assertRaises(Exception) as context:
                self.app.view_functions['hr_hours']()
            self.assertEqual(context.exception.code, 403)
        self.loader.assert_not_called()

    def test_invalid_hr_setting_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.ini'
            path.write_text('[hr_hours]\nrefresh_seconds=0\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                create_app(path)
