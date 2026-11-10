from datetime import datetime
import re
import unittest

from dashboard.attendance import PAKISTAN, QUERY_DIR
from dashboard.employees import build_employees


class EmployeeNameSourceTests(unittest.TestCase):
    def test_runtime_employee_queries_never_select_biometric_name(self):
        for filename in ('employee_snapshot.sql','employee_roster.sql','active_employee_directory.sql','machine_recent_punches.sql'):
            with self.subTest(filename=filename):
                sql=(QUERY_DIR/filename).read_text(encoding='utf-8')
                sql=re.sub(r'--[^\n]*','',sql)
                self.assertRegex(sql,r'\bPName\b')
                self.assertNotRegex(sql,r'\b(?:e\.)?Name\b')

    def test_alerts_show_pname_and_leave_missing_pname_unavailable(self):
        now=datetime.now(PAKISTAN)
        roster=[('001','Payroll Person','U1','HR','Pandoki'),
                ('002',None,'U1','HR','Pandoki')]
        people=build_employees(roster,[],[],{},now)
        self.assertEqual(people[0].name,'Payroll Person')
        self.assertEqual(people[1].name,'Name unavailable')


if __name__=='__main__':unittest.main()
