from datetime import datetime, timedelta
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import create_app
from dashboard.attendance import PAKISTAN
from dashboard.config import ROOT, load_settings
from dashboard.employees import EmployeeSnapshot, build_employees, direction_from_name, SqlEmployees
from dashboard.employee_views import normalized_location


class EmployeeOverviewTests(unittest.TestCase):
    def test_direction_uses_complete_machine_name_tokens(self):
        for name, expected in (('TS-IN-01','IN'), ('TS-OUT-02','OUT'),
                               (' ts-in-01 ','IN'), ('KHI_OUT_01','OUT'),
                               ('MAIN-01',None), ('PRINT-01',None),
                               ('IN-OUT-01',None), ('TS-01',None), (None,None)):
            with self.subTest(name=name):
                self.assertEqual(direction_from_name(name),expected)

    def setUp(self):
        self.now = datetime.now(PAKISTAN)
        self.devices = (('PAN-IN', 'Pandoki', 'U1'), ('PAN-OUT', 'Pandoki', 'U1'),
                        ('KHI-IN', 'Karachi', 'U8'))
        self.directions = {'PAN-IN':'IN', 'PAN-OUT':'OUT', 'KHI-IN':'IN'}

    def people(self, events):
        return build_employees([('1','Person One','U1','Production','Room 1')],
                               self.devices, events, self.directions, self.now)

    def test_later_out_removes_inside_state(self):
        person = self.people([('1',self.now-timedelta(hours=3),'PAN-IN'),
                              ('1',self.now-timedelta(hours=1),'PAN-OUT')])[0]
        self.assertIsNone(person.in_time)
        self.assertFalse(person.unresolved)

    @patch('pyodbc.connect')
    def test_live_direction_follows_name_not_device_code(self, connect):
        cursor=connect.return_value.cursor.return_value
        cursor.fetchone.return_value=('SPEL_ATTENDENCE',2)
        stamp=self.now-timedelta(minutes=1)
        cursor.fetchall.side_effect=[
            [('1','Person One','U1','Production','Pandoki')],
            [('CODE-OUT-01','Pandoki','U1','TS-IN-01')],
            [('1',stamp,'CODE-OUT-01')]]
        settings=load_settings(ROOT/'config.example.ini')
        settings.set('database','authentication','windows')
        snapshot=SqlEmployees(settings)(self.now.date())
        self.assertEqual(snapshot.employees[0].in_time,stamp)
        self.assertEqual(snapshot.employees[0].in_location,'Pandoki')
        lower_bound=cursor.execute.call_args_list[-1].args[1]
        expected=(self.now-timedelta(hours=96)).replace(tzinfo=None)
        self.assertLess(abs((lower_bound-expected).total_seconds()),5)
        query_now=cursor.execute.call_args_list[-1].args[2]
        self.assertLess(abs((query_now-self.now.replace(tzinfo=None)).total_seconds()),5)
        query=cursor.execute.call_args_list[-1].args[0]
        self.assertIn('MAX(CHECKTIME) OVER (PARTITION BY USERID)',query)
        self.assertIn('MAX(CASE WHEN Direction = \'IN\' THEN CHECKTIME END)',query)
        self.assertEqual(query.count('FROM dbo.ZK_CHECKINOUT AS p'),1)
        self.assertNotIn('MAX(CHECKTIME) AS LastTime',query)

    def test_conflicting_ties_unknown_direction_and_future_time_are_unresolved(self):
        for events in ([('1',self.now,'PAN-IN'),('1',self.now,'PAN-OUT')],
                       [('1',self.now,'UNKNOWN')],
                       [('1',self.now+timedelta(minutes=1),'PAN-IN')]):
            with self.subTest(events=events):
                person=self.people(events)[0]
                self.assertTrue(person.unresolved)
                self.assertIsNone(person.in_time)

    def test_last_in_machine_location_and_elapsed_over_threshold(self):
        people = self.people([('1',self.now-timedelta(hours=13),'KHI-IN')])
        app = create_app(ROOT / 'config.example.ini')
        app.extensions['employee_overview_cache'].loader = lambda day: EmployeeSnapshot(
            people,self.devices,self.now,day)
        client=app.test_client()
        html=client.get('/employees',query_string={'location':'"karachi"'}).text
        self.assertIn('Person One',html)
        self.assertIn('13h',html)
        self.assertIn('Over 12 Hours',html)
        self.assertIn('"overdue": true',html)
        self.assertNotIn('Registered employees',html)
        html=client.get('/employees',query_string={'location':'"pandoki"'}).text
        data=json.loads(html.split('id="employee-overview-data">',1)[1].split('</script>',1)[0])
        self.assertEqual([person['id'] for person in data],['1'])

    def test_invalid_employee_threshold_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.ini'
            path.write_text('[employee_overview]\nlong_stay_hours=48\nlookback_hours=48\n',encoding='utf-8')
            with self.assertRaises(ValueError):
                create_app(path)

    def test_location_mismatch_uses_employee_unit_mapping_not_physical_location(self):
        person = self.people([('1',self.now-timedelta(hours=2),'PAN-IN')])[0]
        people = (replace(person,id='1',unit='UNIT3',physical_location='  pAnDoKi  '),
                  replace(person,id='2',unit='UNIT8',physical_location='Pandoki'),
                  replace(person,id='3',unit='UNIT3',physical_location=None))
        app=create_app(ROOT/'config.example.ini')
        app.extensions['employee_overview_cache'].loader=lambda day: EmployeeSnapshot(people,self.devices,self.now,day)
        html=app.test_client().get('/employees').text
        data=json.loads(html.split('id="employee-overview-data">',1)[1].split('</script>',1)[0])
        by_id={row['id']:row for row in data}
        self.assertFalse(by_id['1']['mismatch'])
        self.assertTrue(by_id['2']['mismatch'])
        self.assertFalse(by_id['3']['mismatch'])
        self.assertEqual(by_id['3']['physical'],'Not assigned')
        self.assertNotIn('Registered employees',html)

    def test_guest_employees_are_excluded_from_other_location_flag(self):
        events=[('9923',self.now-timedelta(hours=2),'PAN-IN')]
        person=build_employees(
            [('9923','Guest','UNIT8','Operations','Karachi')],
            self.devices,events,self.directions,self.now)[0]
        app=create_app(ROOT/'config.example.ini')
        app.extensions['employee_overview_cache'].loader=lambda day: EmployeeSnapshot(
            (person,),self.devices,self.now,day)
        html=app.test_client().get('/employees').text
        data=json.loads(html.split('id="employee-overview-data">',1)[1].split('</script>',1)[0])
        self.assertTrue(data[0]['guest'])
        self.assertFalse(data[0]['from_other_location'])

    def test_over_12_hours_uses_two_decimal_sql_threshold(self):
        person=build_employees(
            [('1','Person One','U1','Production','Room 1')],
            self.devices,
            [('1',self.now-timedelta(hours=12,seconds=17),'PAN-IN')],
            self.directions,self.now)[0]
        app=create_app(ROOT/'config.example.ini')
        app.extensions['employee_overview_cache'].loader=lambda day: EmployeeSnapshot(
            (person,),self.devices,self.now,day)
        html=app.test_client().get('/employees').text
        self.assertIn('>Over 12 Hours</span><strong>0</strong>',html)

    def test_base_query_alert_flags_and_punch_details(self):
        events = [
            ('1', self.now-timedelta(hours=2), 'PAN-IN',
             self.now-timedelta(hours=2), None),
            ('9923', self.now-timedelta(hours=13), 'PAN-IN',
             self.now-timedelta(hours=13), self.now-timedelta(hours=14)),
        ]
        people = build_employees(
            [('1','Employee One','UNIT8','Operations','Karachi','Karachi Branch'),
             ('9923','Guest','UNIT3','Operations','Pandoki','Pandoki Branch')],
            self.devices, events, self.directions, self.now)
        app=create_app(ROOT/'config.example.ini')
        app.extensions['employee_overview_cache'].loader=lambda day: EmployeeSnapshot(
            people,self.devices,self.now,day)
        html=app.test_client().get('/employees').text
        data=json.loads(html.split('id="employee-overview-data">',1)[1].split('</script>',1)[0])
        by_id={row['id']:row for row in data}
        self.assertTrue(by_id['1']['from_other_location'])
        self.assertEqual(by_id['1']['branch'],'Karachi Branch')
        self.assertEqual(by_id['1']['employee_location'],'Karachi')
        self.assertTrue(by_id['9923']['guest'])
        self.assertTrue(by_id['9923']['working_hours_limit'])
        self.assertEqual(by_id['9923']['last_in_hours'],'13.00')
        self.assertIn('Last OUT · PKT',html)
        self.assertIn('>In Premises',html)
        self.assertIn('>Over 12 Hours',html)
        self.assertIn('>From Other Location',html)
        self.assertIn('>Guest',html)
        self.assertNotIn('Missing IN Punch',html)
        self.assertNotIn('Missing OUT Punch',html)
        self.assertNotIn('Needs Review',html)
        main=html.split('<dialog',1)[0]
        self.assertIn('aria-label="In premises employees by branch, unit and department"',main)
        self.assertIn('<h2>Branch Name',main)
        self.assertIn('<h2>Unit',main)
        self.assertIn('<h2>Department',main)
        self.assertIn('<th scope="row">Karachi Branch</th><td>1</td>',main)
        self.assertNotIn('data-staff-groups="branch"',html)
        self.assertEqual(html.count('data-staff-kind='),4)

    def test_in_premises_excludes_roster_with_no_recent_events(self):
        person=self.people([])[0]
        app=create_app(ROOT/'config.example.ini')
        app.extensions['employee_overview_cache'].loader=lambda day: EmployeeSnapshot(
            (person,),self.devices,self.now,day)
        html=app.test_client().get('/employees').text
        data=json.loads(html.split('id="employee-overview-data">',1)[1].split('</script>',1)[0])
        self.assertEqual(data,[])
        self.assertEqual(html.count('data-staff-kind='),4)

    def test_unknown_direction_is_explained_and_not_counted_inside(self):
        people=self.people([('1',self.now,'UNKNOWN')])
        app=create_app(ROOT/'config.example.ini')
        app.extensions['employee_overview_cache'].loader=lambda day: EmployeeSnapshot(people,self.devices,self.now,day)
        html=app.test_client().get('/employees').text
        data=json.loads(html.split('id="employee-overview-data">',1)[1].split('</script>',1)[0])
        self.assertEqual(data,[])
        self.assertNotIn('Needs Review',html)

    def test_location_aliases_are_explicit_and_case_whitespace_insensitive(self):
        self.assertEqual(normalized_location(' Head   Office '),'head office')
        self.assertEqual(normalized_location(' Head Office ',{'head office':'headoffice'}),'headoffice')

    def test_unit_filters_are_inside_popup_and_do_not_change_main_tile_scope(self):
        person=self.people([('1',self.now-timedelta(hours=2),'PAN-IN')])[0]
        people=(replace(person,id='1',name='First employee',unit='U1'),
                replace(person,id='2',name='Second employee',unit='U2'))
        app=create_app(ROOT/'config.example.ini')
        app.extensions['employee_overview_cache'].loader=lambda day: EmployeeSnapshot(people,self.devices,self.now,day)
        html=app.test_client().get('/employees',query_string={'unit':'U2'}).text
        data=json.loads(html.split('id="employee-overview-data">',1)[1].split('</script>',1)[0])
        self.assertEqual([person['id'] for person in data],['1','2'])
        self.assertIn('data-staff-filter="unit"',html)
        self.assertIn('From Other Location',html)
        self.assertIn('In premises employees by branch, unit and department',html)
        self.assertIn('data-staff-filter="branch"',html)
        self.assertIn('<section class="attendance-breakdowns"',html)
        self.assertIn('First employee',html)
        banner=html.split('<header',1)[1].split('</header>',1)[0]
        self.assertEqual(banner.count('<select'),1)
        self.assertNotIn('name="unit"',banner)
        main_screen=html.split('<dialog',1)[0]
        self.assertNotIn('data-staff-filter',main_screen)
        self.assertNotIn('department-panel',main_screen)

    def test_invalid_unit_resets_to_all_units(self):
        person=self.people([('1',self.now-timedelta(hours=2),'PAN-IN')])[0]
        app=create_app(ROOT/'config.example.ini')
        app.extensions['employee_overview_cache'].loader=lambda day: EmployeeSnapshot((person,),self.devices,self.now,day)
        html=app.test_client().get('/employees',query_string={'unit':'does-not-exist'}).text
        self.assertIn('Person One',html)

    def test_alert_location_filter_only_lists_current_in_prem_locations(self):
        person=self.people([('1',self.now-timedelta(hours=2),'KHI-IN')])[0]
        app=create_app(ROOT/'config.example.ini')
        app.extensions['employee_overview_cache'].loader=lambda day: EmployeeSnapshot(
            (person,),self.devices,self.now,day)
        html=app.test_client().get('/employees').text
        location_select=html.split('<select id="location"',1)[1].split('</select>',1)[0]
        self.assertIn('>Karachi</option>',location_select)
        self.assertNotIn('>Pandoki</option>',location_select)
        self.assertNotIn('>HeadOffice</option>',location_select)

    def test_in_premises_and_tile_counts_follow_selected_in_prem_location(self):
        events=[
            ('1',self.now-timedelta(hours=2),'PAN-IN',
             self.now-timedelta(hours=2),None),
            ('2',self.now-timedelta(hours=3),'KHI-IN',
             self.now-timedelta(hours=3),None),
        ]
        people=build_employees(
            [('1','Pandoki Person','UNIT3','Operations','Pandoki','Pandoki Branch'),
             ('2','Karachi Person','UNIT8','Operations','Karachi','Karachi Branch')],
            self.devices,events,self.directions,self.now)
        app=create_app(ROOT/'config.example.ini')
        app.extensions['employee_overview_cache'].loader=lambda day: EmployeeSnapshot(
            people,self.devices,self.now,day)
        client=app.test_client()
        all_html=client.get('/employees').text
        self.assertIn('<strong>2</strong>',all_html)
        all_data=json.loads(all_html.split('id="employee-overview-data">',1)[1].split('</script>',1)[0])
        self.assertEqual({person['id'] for person in all_data},{'1','2'})
        location_html=client.get('/employees',query_string={'location':'"karachi"'}).text
        self.assertIn('selected>Karachi</option>',location_html)
        self.assertIn('<strong>1</strong>',location_html)
        location_data=json.loads(location_html.split('id="employee-overview-data">',1)[1].split('</script>',1)[0])
        self.assertEqual([person['id'] for person in location_data],['2'])
        self.assertEqual(location_data[0]['branch'],'Karachi Branch')


if __name__ == '__main__':
    unittest.main()
