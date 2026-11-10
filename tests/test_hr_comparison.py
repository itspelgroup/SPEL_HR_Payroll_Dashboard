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
from dashboard.hr_comparison import (PeriodGroup, PeriodSnapshot, SqlHrPeriods,
                                     change, comparison_model, fiscal_start, fiscal_label, period_series, sum_groups)


def group(month=date(2026,1,1), net='100', overtime='20', **changes):
    values=dict(month=month,unit='U1',department='HR',worker='SPEL',direct='1',records=10,
                net=Decimal(net),overtime=Decimal(overtime),first_record=month,last_record=month)
    return PeriodGroup(**(values|changes))


class ComparisonCalculationTests(unittest.TestCase):
    def test_total_definition_signed_adjustments_and_ot_share(self):
        summary=sum_groups([group(),group(net='50',overtime='-5')])
        self.assertEqual(summary['net'],Decimal(150))
        self.assertEqual(summary['overtime'],Decimal(15))
        self.assertEqual(summary['total'],Decimal(165))
        self.assertEqual(summary['ot_share'],Decimal(15)/165*100)
        self.assertIsNone(sum_groups([])['ot_share'])

    def test_months_include_missing_period_and_mark_partial_selection(self):
        rows=period_series([group()],date(2026,1,1),date(2026,3,7),'monthly')
        self.assertEqual([r['key'] for r in rows],['2026-01','2026-02','2026-03'])
        self.assertTrue(rows[0]['has_data'])
        self.assertFalse(rows[1]['has_data'])
        self.assertFalse(rows[0]['partial'])
        self.assertTrue(rows[2]['partial'])
        self.assertIsNone(rows[1]['delta']['hours'])
        self.assertEqual(rows[0]['total'],Decimal(120))

    def test_year_grouping_and_monthly_rollup_reconcile(self):
        groups=[group(date(2024,2,1)),group(date(2024,3,1)),group(date(2025,1,1),'200','30')]
        rows=period_series(groups,date(2024,1,1),date(2025,12,31),'yearly',fiscal=False)
        self.assertEqual(rows[0]['total'],Decimal(240))
        self.assertEqual(rows[1]['total'],Decimal(230))
        self.assertEqual(rows[1]['delta']['hours'],Decimal(-10))
        self.assertEqual(sum(r['total'] for r in rows),sum_groups(groups)['total'])

    def test_percentage_change_zero_negative_and_missing_baselines(self):
        self.assertEqual(change(Decimal(120),Decimal(100))['percent'],Decimal(20))
        self.assertIsNone(change(Decimal(10),Decimal(0))['percent'])
        self.assertEqual(change(Decimal(-5),Decimal(-10))['percent'],Decimal(50))
        self.assertIsNone(change(None,Decimal(10))['hours'])

    def test_fiscal_year_boundaries_and_january_rollup(self):
        self.assertEqual(fiscal_start(date(2024,6,30)),date(2023,7,1))
        self.assertEqual(fiscal_start(date(2024,7,1)),date(2024,7,1))
        self.assertEqual(fiscal_label(date(2025,1,1)),'FY 2024/25')
        groups=[group(date(2024,6,1)),group(date(2024,7,1)),group(date(2025,1,1)),group(date(2025,6,1))]
        series=period_series(groups,date(2023,7,1),date(2025,6,30),'yearly')
        self.assertEqual([row['key'] for row in series],['FY2023-24','FY2024-25'])
        self.assertEqual(series[0]['total'],Decimal(120))
        self.assertEqual(series[1]['total'],Decimal(360))
        self.assertEqual(series[1]['end'],'2025-06-30')

    def test_twelve_fiscal_months_current_partial_and_upcoming(self):
        series=period_series([],date(2024,7,1),date(2025,6,30),'monthly',as_of=date(2024,11,7))
        self.assertEqual(len(series),12)
        self.assertEqual(series[0]['key'],'2024-07')
        self.assertEqual(series[-1]['key'],'2025-06')
        self.assertTrue(series[4]['partial'])
        self.assertFalse(series[4]['upcoming'])
        self.assertTrue(series[5]['upcoming'])
        self.assertEqual(series[6]['fiscal_year'],'FY 2024/25')

    def test_leap_day_and_custom_fiscal_partial_period(self):
        series=period_series([group(date(2024,2,1))],date(2024,2,1),date(2024,2,29),'monthly')
        self.assertFalse(series[0]['partial'])
        annual=period_series([group(date(2024,2,1))],date(2024,2,1),date(2024,6,30),'yearly')
        self.assertTrue(annual[0]['partial'])
        self.assertEqual(annual[0]['label'],'FY 2023/24')


class ComparisonProviderTests(unittest.TestCase):
    @patch('dashboard.hr_comparison.build_connection_string',return_value='mock-only')
    @patch('pyodbc.connect')
    def test_monthly_aggregates_preserve_union_and_parameterize_range(self,connect,_):
        cursor=connect.return_value.cursor.return_value
        cursor.fetchone.return_value=(1,2)
        cursor.fetchmany.return_value=[(date(2026,1,1),'U1','HR','SPEL',1,1500,
                                       Decimal('12000'),Decimal('2000'),datetime(2026,1,1),datetime(2026,1,31))]
        snapshot=SqlHrPeriods(load_settings(ROOT/'config.example.ini'))((date(2023,1,1),date(2026,11,7)))
        self.assertEqual(len(snapshot.groups),1)
        self.assertEqual(snapshot.groups[0].records,1500)
        sql=cursor.execute.call_args_list[1]
        self.assertIn('UNION ALL',sql.args[0])
        self.assertIn('GROUP BY',sql.args[0])
        self.assertNotIn('EmpName',sql.args[0])
        self.assertEqual(sql.args[1:],(50001,datetime(2023,1,1),datetime(2026,11,8),
                                       datetime(2023,1,1),datetime(2026,11,8)))
        self.assertTrue(connect.call_args.kwargs['readonly'])
        connect.return_value.close.assert_called_once()

    @patch('dashboard.hr_comparison.build_connection_string',return_value='mock-only')
    @patch('pyodbc.connect')
    def test_aggregate_cap_fails_without_partial_totals(self,connect,_):
        settings=load_settings(ROOT/'config.example.ini');settings.set('hr_hours','max_period_groups','1')
        cursor=connect.return_value.cursor.return_value;cursor.fetchone.return_value=(1,2)
        cursor.fetchmany.return_value=[(),()]
        with self.assertRaises(AttendanceUnavailable):
            SqlHrPeriods(settings)((date(2026,1,1),date(2026,12,31)))


class ComparisonRouteTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app(ROOT/'config.example.ini');self.app.testing=True
        self.today=datetime.now(PAKISTAN).date();self.current=fiscal_start(self.today)
        self.previous=date(self.current.year-1,7,1)
        self.groups=(group(self.previous),group(self.current,'200','40'),
                     group(date(self.current.year,6,1),'50','5',unit='U2'),
                     group(date(self.current.year-12,7,1),'1500','50'))
        self.loader=Mock(side_effect=lambda window:PeriodSnapshot(tuple(row for row in self.groups
            if window[0]<=row.month<=window[1]),datetime.now(PAKISTAN),window))
        self.app.extensions['hr_period_cache'].loader=self.loader
        self.client=self.app.test_client()

    def data(self,response,identity='period-series'):
        return json.loads(response.text.split('id="'+identity+'">',1)[1].split('</script>',1)[0])

    def test_monthly_pairs_current_and_previous_fiscal_year(self):
        response=self.client.get('/hr-hours?analysis=monthly')
        self.assertEqual(response.status_code,200)
        rows=self.data(response)
        self.assertEqual(len(rows),24)
        previous=[row for row in rows if row['month_index']==0 and row['role']=='previous'][0]
        current=[row for row in rows if row['month_index']==0 and row['role']=='current'][0]
        self.assertEqual(previous['total'],'120')
        self.assertEqual(current['total'],'240')
        self.assertEqual(current['fiscal_year'],fiscal_label(self.current))
        self.assertIn('Same months, two fiscal years',response.text)
        self.loader.assert_called_once_with((self.previous,self.today))

    def test_yearly_includes_history_older_than_ten_years_and_current_ytd(self):
        response=self.client.get('/hr-hours?analysis=yearly')
        rows=self.data(response)
        self.assertEqual(len(rows),13)
        self.assertEqual(rows[0]['start'],date(self.current.year-12,7,1).isoformat())
        self.assertEqual(rows[-1]['fiscal_year'],fiscal_label(self.current))
        self.assertEqual(rows[-1]['end'],self.today.isoformat())
        self.assertEqual(rows[-1]['partial'],self.today<date(self.current.year+1,6,30))
        self.assertEqual(rows[-1]['total'],'240')
        self.assertIn('All available fiscal years',response.text)
        self.loader.assert_called_once_with((date(1753,1,1),self.today))

    def test_filters_reuse_the_snapshot_and_source_parameter_is_ignored(self):
        self.client.get('/hr-hours?analysis=monthly')
        response=self.client.get('/hr-hours',query_string={'analysis':'monthly','unit':json.dumps('U2'),'source':json.dumps('HR_MIS')})
        groups=self.data(response,'period-groups')
        self.assertEqual(len(groups),1)
        self.assertEqual(groups[0]['total'],'55')
        self.assertNotIn('name="source"',response.text)
        self.loader.assert_called_once()

    def test_main_screen_has_only_two_views_and_no_advanced_controls(self):
        response=self.client.get('/hr-hours')
        for removed in ('name="fy_start"','name="fy_end"','name="start"','id="chart-orientation"','id="compare-baseline"'):
            self.assertNotIn(removed,response.text)
        self.assertIn('View exact hours',response.text)
        self.assertIn('Year to date through',response.text)
        self.assertIn('id="chart-expand"',response.text)
        self.assertEqual(len(self.data(response)),24)
        response=self.client.get('/hr-hours?analysis=daily')
        self.assertEqual(response.status_code,200)
        self.assertIn('id="hr-hours-data"',response.text)

    def test_old_range_bookmarks_do_not_change_fixed_comparison(self):
        response=self.client.get('/hr-hours',query_string={'analysis':'monthly','fy_start':'1900','fy_end':'2990','start':'bad','end':'bad'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(self.data(response)),24)
        self.loader.assert_called_once_with((self.previous,self.today))

    def test_missing_data_are_not_invented_zero_values_and_failure_is_safe(self):
        response=self.client.get('/hr-hours',query_string={'analysis':'monthly','unit':json.dumps('absent')})
        self.assertTrue(all(row['total'] is None for row in self.data(response)))
        self.app.extensions['hr_period_cache'].entries.clear();self.loader.side_effect=RuntimeError('password-secret')
        response=self.client.get('/hr-hours?analysis=yearly')
        self.assertEqual(response.status_code,503)
        self.assertNotIn('password-secret',response.text)

    def test_monthly_and_yearly_ytd_totals_match_and_keep_separate_caches(self):
        monthly=self.data(self.client.get('/hr-hours?analysis=monthly'))
        yearly=self.data(self.client.get('/hr-hours?analysis=yearly'))
        current_months=[row for row in monthly if row['role']=='current' and row['has_data']]
        self.assertEqual(sum(Decimal(row['total']) for row in current_months),Decimal(yearly[-1]['total']))
        self.assertEqual(self.loader.call_count,2)

    def test_unknown_comparison_view_is_rejected(self):
        self.assertEqual(self.client.get('/hr-hours/comparison?analysis=unknown').status_code,400)
        self.loader.assert_not_called()


class SimpleComparisonModelTests(unittest.TestCase):
    def test_matching_january_months_cross_calendar_year(self):
        today=date(2026,11,7)
        rows=[group(date(2026,1,1),'80','20'),group(date(2026,7,1),'100','30')]
        model=comparison_model(rows,today,'monthly')
        self.assertEqual(len(model['pairs']),12)
        january=model['pairs'][6]
        self.assertEqual(january['label'],'Jan')
        self.assertEqual(january['previous']['total'],Decimal(100))
        self.assertEqual(january['current']['start'],'2027-01-01')
        self.assertTrue(january['current']['upcoming'])
        self.assertFalse(january['current']['has_data'])
        july=model['pairs'][0]
        self.assertEqual(july['current']['total'],Decimal(130))
        self.assertEqual(model['current_summary']['total'],Decimal(130))

    def test_year_history_includes_gaps_without_losing_current_year(self):
        model=comparison_model([group(date(2010,7,1)),group(date(2026,7,1))],date(2026,11,7),'yearly')
        self.assertEqual(len(model['series']),17)
        self.assertTrue(model['series'][-1]['partial'])
        self.assertFalse(model['series'][1]['has_data'])
        self.assertEqual(model['series'][-1]['end'],'2026-11-07')
