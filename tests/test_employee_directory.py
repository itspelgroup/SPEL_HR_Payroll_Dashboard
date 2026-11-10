from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from app import create_app
from dashboard.attendance import PAKISTAN
from dashboard.config import ROOT, load_settings
from dashboard.employee_directory import DirectoryEmployee, DirectorySnapshot, SqlEmployeeDirectory


class EmployeeDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app(ROOT/'config.example.ini')
        people=(DirectoryEmployee('001','First Person','First PName','U1','HR','Pandoki'),
                DirectoryEmployee('002','Second Person',None,'U1','IT','Pandoki'),
                DirectoryEmployee('003','Other Site Person',None,'U8','IT','Karachi'),
                DirectoryEmployee('004','Unassigned Person',None,None,None,None))
        self.loader=Mock(side_effect=lambda day:DirectorySnapshot(people,datetime.now(PAKISTAN),day))
        self.app.extensions['employee_directory_cache'].loader=self.loader
        self.client=self.app.test_client()

    def details(self,html):
        return json.loads(html.split('id="directory-data">',1)[1].split('</script>',1)[0])

    def test_location_scopes_data_and_popup_filters_do_not_reduce_main_totals(self):
        response=self.client.get('/employee-directory',query_string={'location':'"pandoki"'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(self.details(response.text)),2)
        self.assertNotIn('Other Site Person',response.text)
        html=self.client.get('/employee-directory',query_string={'location':'"pandoki"','unit':'U1','department':'HR'}).text
        self.assertEqual([row['id'] for row in self.details(html)],['001','002'])
        self.assertIn('First PName',html)
        self.loader.assert_called_once()
        banner=html.split('<header',1)[1].split('</header>',1)[0]
        self.assertEqual(banner.count('<select'),1)
        self.assertIn('Attendance Alerts',banner)
        self.assertIn('>Employees</a>',banner)

    def test_unassigned_employee_remains_visible_and_invalid_unit_resets(self):
        html=self.client.get('/employee-directory',query_string={'unit':'unknown'}).text
        data=self.details(html)
        self.assertEqual(len(data),4)
        self.assertEqual(next(row for row in data if row['id']=='004')['unit'],'Not assigned')
        html=self.client.get('/employee-directory',query_string={'location':'""'}).text
        self.assertEqual([row['id'] for row in self.details(html)],['004'])

    def test_failure_shows_no_fake_headcount_or_connection_details(self):
        self.app.extensions['employee_directory_cache'].loader=Mock(side_effect=RuntimeError('private-password'))
        response=self.client.get('/employee-directory')
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private-password',response.text)
        self.assertNotIn('id="directory-data"',response.text)

    @patch('pyodbc.connect')
    def test_sql_reads_active_roster_only_without_punch_or_device_queries(self,connect):
        settings=load_settings(ROOT/'config.example.ini')
        settings.set('database','authentication','windows')
        cursor=connect.return_value.cursor.return_value
        cursor.fetchone.return_value=('SPEL_ATTENDENCE',2)
        cursor.fetchall.return_value=[('001','Actual Person','U1','HR','Pandoki')]
        snapshot=SqlEmployeeDirectory(settings)(datetime.now(PAKISTAN).date())
        self.assertEqual(snapshot.employees[0].name,'Actual Person')
        calls=cursor.execute.call_args_list
        self.assertEqual(len(calls),2)
        self.assertIn('WHERE Active = 1',calls[1].args[0])
        self.assertNotIn('JOIN',calls[1].args[0].upper())
        self.assertTrue(connect.call_args.kwargs['readonly'])
        connect.return_value.close.assert_called_once()

    def test_invalid_directory_refresh_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.ini'
            path.write_text('[employee_directory]\nrefresh_seconds=0\n',encoding='utf-8')
            with self.assertRaises(ValueError):create_app(path)


if __name__=='__main__':unittest.main()
