"""Offline authorization checks; no production SQL or real account credentials."""
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from flask import template_rendered

from app import create_app
from dashboard.account_store import IniUserStore, AccountStoreError, verify_password
from dashboard.attendance import PAKISTAN
from dashboard.employee_directory import DirectoryEmployee, DirectorySnapshot
from dashboard.employees import EmployeeSnapshot, OverviewEmployee
from dashboard.hr_comparison import PeriodGroup, PeriodSnapshot
from dashboard.hr_hours import HoursRecord, HoursSnapshot
from dashboard.machines import Machine, MachineSnapshot, MachinePunch


class UserSettingsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'config.ini'
        self.path.write_text('[security]\nenabled=true\nuser_file=' + str(self.root / 'users.ini')
                             + '\naccount_directory=' + str(self.root / 'instance'), encoding='utf-8')
        self.now = datetime.now(PAKISTAN)
        machines = tuple(Machine(key, key + '-IN', place, 'U', True, self.now, self.now,
                                 key, self.now, place + ' Person', place,
                                 (MachinePunch(1,key,self.now,self.now,place+' Person','U',place),))
                         for key, place in [('PAN','Pandoki'), ('KHI','Karachi'), ('OTHER','Private')])
        self.loader = Mock(return_value=MachineSnapshot(machines, self.now, self.now.date()))
        self.app = create_app(self.path, machine_provider=self.loader)
        self.app.testing = True
        self.store = self.app.extensions['user_store']
        for label in ('Pandoki', 'Karachi', 'Private'):
            self.store.save_location(label, [])
        self.store.save_user('admin', password='admin-test-password', is_admin=True, create=True)
        self.store.save_user('operator', password='operator-test-password', tabs=['machines','alerts','directory','hr_hours'],
                             locations=['Pandoki','Karachi'], create=True)
        self.client = self.app.test_client()

    def test_lan_host_environment_override_is_used(self):
        with patch.dict('os.environ', {'SPEL_HOST': '0.0.0.0'}):
            app = create_app(self.path, machine_provider=self.loader)
        self.assertEqual(app.config['SPEL_HOST'], '0.0.0.0')

    def test_live_data_cannot_bind_to_network_without_authentication(self):
        path = self.root / 'live-network.ini'
        path.write_text(
            '[application]\nhost = 0.0.0.0\ndata_mode = live\n'
            '[database]\nenabled = true\n[cache]\nenabled = true\n'
            '[security]\nenabled = false\n',
            encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Authentication is required'):
            create_app(path)

    def csrf(self, client=None):
        with (client or self.client).session_transaction() as state:
            return state['csrf']

    def login(self, name='operator', password='operator-test-password', client=None):
        client = client or self.client
        client.get('/login')
        return client.post('/login', data={'username':name, 'password':password, 'csrf':self.csrf(client)})

    def context(self, url, **kwargs):
        captured = []
        def receive(sender, template, context, **extra):
            captured.append(context)
        with template_rendered.connected_to(receive, self.app):
            response = self.client.get(url, **kwargs)
        self.assertEqual(response.status_code, 200)
        return captured[-1]

    def test_multi_location_scope_includes_both_and_rejects_forged_filter(self):
        self.login()
        for args in ({}, {'location':json.dumps('private')}):
            response = self.client.get('/', query_string=args)
            self.assertIn('Pandoki Person', response.text)
            self.assertIn('Karachi Person', response.text)
            self.assertNotIn('Private Person', response.text)
            self.assertNotIn('OTHER-IN', response.text)
        response = self.client.get('/', query_string={'location':json.dumps('karachi')})
        self.assertIn('Karachi Person', response.text)
        self.assertNotIn('Pandoki Person', response.text)

    def test_tab_permissions_apply_before_loading_and_navigation(self):
        self.store.save_user('operator', tabs=['directory'], locations=['Pandoki'])
        self.login()
        self.assertEqual(self.client.get('/').location, '/employee-directory')
        for path in ('/employees','/hr-hours','/hr-hours/comparison','/attendance','/settings'):
            self.assertEqual(self.client.get(path).status_code, 403)
        self.loader.assert_not_called()
        html = self.client.get('/employee-directory').text
        self.assertNotIn('>Machines</a>', html)
        self.assertNotIn('>HR Hours</a>', html)
        self.assertNotIn('href="/settings"', html)

    def test_admin_settings_create_user_without_exposing_password(self):
        self.login('admin', 'admin-test-password')
        response = self.client.post('/settings', data={'csrf':self.csrf(), 'action':'create',
            'username':'new-user', 'password':'Plain%Secret#2026', 'enabled':'on',
            'tabs':['machines','directory'], 'locations':['Pandoki','Karachi']})
        self.assertEqual(response.status_code, 302)
        saved = self.store.read()['users']['new-user']
        self.assertEqual(saved['password'], 'Plain%Secret#2026')
        self.assertEqual(saved['locations'], ['Pandoki','Karachi'])
        html = self.client.get('/settings').text
        self.assertIn('new-user', html)
        self.assertNotIn('Plain%Secret#2026', html)
        self.assertNotIn('admin-test-password', html)
        self.assertNotIn('password', dict(self.client.get('/settings').headers).get('Set-Cookie',''))
        other = self.app.test_client()
        self.assertEqual(self.login('new-user','Plain%Secret#2026',other).status_code,302)
        self.assertEqual(other.get('/employees').status_code,403)

    def test_disabled_account_and_permissions_change_revoke_old_sessions(self):
        self.login()
        self.store.save_user('operator', enabled=False, tabs=['machines'], locations=['Pandoki'])
        self.assertEqual(self.client.get('/').location, '/login')
        self.assertNotEqual(self.login().status_code, 302)
        self.store.save_user('operator', tabs=['machines'], locations=['Pandoki'])
        self.login()
        self.store.save_user('operator', tabs=['directory'], locations=['Karachi'])
        self.assertEqual(self.client.get('/').location, '/login')

    def test_manual_password_edit_invalidates_session(self):
        self.login()
        path = self.store.path
        path.write_text(path.read_text(encoding='utf-8').replace('operator-test-password','changed-password'), encoding='utf-8')
        self.assertEqual(self.client.get('/').location, '/login')

    def test_password_change_invalidates_other_sessions(self):
        other = self.app.test_client()
        self.login(); self.login(client=other)
        response = self.client.post('/account', data={'csrf':self.csrf(),
            'current_password':'operator-test-password', 'password':'new-private-password',
            'confirm_password':'new-private-password'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(other.get('/').location,'/login')
        self.assertTrue(verify_password(self.store.read()['users']['operator'],'new-private-password'))

    def test_csrf_and_nonadmin_writes_rejected(self):
        self.login('admin','admin-test-password')
        self.assertEqual(self.client.post('/settings',data={'action':'location','label':'FORGED'}).status_code,400)
        self.assertNotIn('FORGED',self.store.read()['locations'])
        self.assertEqual(self.client.post('/logout',data={'csrf':'wrong'}).status_code,400)
        self.client.post('/logout', data={'csrf':self.csrf()})
        self.login()
        self.assertEqual(self.client.post('/settings',data={'csrf':self.csrf(),'action':'location','label':'FORGED'}).status_code,403)

    def test_last_admin_cannot_be_disabled_or_demoted(self):
        for changes in ({'enabled':False,'is_admin':True}, {'is_admin':False}):
            with self.assertRaises(ValueError):
                self.store.save_user('admin',tabs=['machines'],locations=['Pandoki'],**changes)
        self.assertTrue(self.store.read()['users']['admin']['enabled'])
        self.assertTrue(self.store.read()['users']['admin']['is_admin'])

    def test_location_mapping_must_be_explicit_and_unique(self):
        self.login()
        loader = Mock()
        self.app.extensions['hr_period_cache'].loader = loader
        self.assertEqual(self.client.get('/hr-hours').status_code,403)
        loader.assert_not_called()
        self.store.save_location('Pandoki',['UNIT1'])
        with self.assertRaises(ValueError):
            self.store.save_location('Karachi',[' unit1 '])
        self.assertEqual(self.store.read()['locations']['Karachi'],[])

    def test_manual_duplicate_hr_mapping_fails_closed(self):
        self.store.save_location('Pandoki',['UNIT1'])
        self.store.save_location('Karachi',['UNIT8'])
        self.store.path.write_text(self.store.path.read_text(encoding='utf-8').replace('["UNIT8"]','["unit1"]'),encoding='utf-8')
        self.assertEqual(self.client.get('/login').status_code,503)

    def test_employee_directory_filters_before_options_totals_and_details(self):
        employees = tuple(DirectoryEmployee(str(i),place+' Employee','PName',place+' unit','Dept',place)
                          for i,place in enumerate(('Pandoki','Karachi','Private')))
        self.app.extensions['employee_directory_cache'].loader = Mock(return_value=DirectorySnapshot(employees,self.now,self.now.date()))
        self.login()
        context = self.context('/employee-directory?location='+json.dumps('private'))
        self.assertEqual(context['total'],2)
        self.assertEqual(len(context['details']),2)
        self.assertNotIn('Private',str(context['details'])+str(context['locations']))

    def test_alerts_scope_limits_location_options_and_in_premises_details(self):
        people = [OverviewEmployee(str(i),place+' Staff','U','D',place,(place,),self.now,place)
                  for i,place in enumerate(('Pandoki','Karachi','Private'))]
        people += [OverviewEmployee('unknown','Unknown private event','U','D','Pandoki',('Pandoki',),
                     unresolved=True,last_event_time=self.now),
                   OverviewEmployee('none','Private no events','U','D','Private',('Private',))]
        devices = tuple((str(i),place,'U') for i,place in enumerate(('Pandoki','Karachi','Private')))
        self.app.extensions['employee_overview_cache'].loader = Mock(return_value=EmployeeSnapshot(tuple(people),devices,self.now,self.now.date()))
        self.login()
        context = self.context('/employees')
        self.assertEqual(context['inside'],2)
        self.assertEqual(len(context['details']),2)
        self.assertNotIn('Private',str(context['details'])+str(context['locations']))

    def test_hr_monthly_yearly_and_daily_scope_options_and_popup_records(self):
        self.store.save_location('Pandoki',['ALLOWED1'])
        self.store.save_location('Karachi',['ALLOWED2'])
        month = self.now.date().replace(day=1)
        groups = tuple(PeriodGroup(month,unit,unit+' department','Worker','1',1,Decimal(8),Decimal(2),month,month)
                       for unit in ('ALLOWED1','ALLOWED2','SECRET'))
        self.app.extensions['hr_period_cache'].loader = Mock(side_effect=lambda key:PeriodSnapshot(groups,self.now,key))
        records = tuple(HoursRecord('HR_MIS',unit,'Worker',unit,unit+' Person',unit+' department',self.now,
                        '08:00','18:00',1,Decimal(8),Decimal(2),None) for unit in ('ALLOWED1','ALLOWED2','SECRET'))
        self.app.extensions['hr_hours_cache'].loader = Mock(side_effect=lambda key:HoursSnapshot(records,self.now,key))
        self.login()
        for analysis in ('monthly','yearly'):
            context = self.context('/hr-hours?analysis='+analysis)
            self.assertEqual(context['summary']['total'],Decimal(20))
            self.assertEqual(len(context['groups']),2)
            self.assertNotIn('SECRET',str(context['options'])+str(context['groups']))
        context = self.context('/hr-hours?start='+self.now.date().isoformat())
        self.assertEqual(context['summary']['total'],Decimal(20))
        self.assertEqual(len(context['details']),2)
        self.assertNotIn('SECRET',str(context['details'])+str(context['options']))
        # Shared source cache still must not broaden a later user's serialized data.
        self.store.save_user('operator',tabs=['hr_hours'],locations=['Pandoki'])
        self.login()
        context = self.context('/hr-hours?analysis=monthly')
        self.assertEqual(context['summary']['total'],Decimal(10))
        self.assertNotIn('ALLOWED2',str(context['options'])+str(context['groups']))

    def test_optional_hash_storage(self):
        store = IniUserStore(self.root/'hash-users.ini',password_storage='hash')
        store.initialize()
        store.save_user('admin', password='hash-test-password', is_admin=True, create=True)
        account = store.read()['users']['admin']
        self.assertNotEqual(account['password'],'hash-test-password')
        self.assertTrue(verify_password(account,'hash-test-password'))
        self.assertFalse(verify_password(account,'wrong-password'))

    def test_admin_can_reset_password_and_edit_multiple_permissions(self):
        staff=self.app.test_client();self.login(client=staff)
        self.login('admin','admin-test-password')
        response=self.client.post('/settings',data={'csrf':self.csrf(),'action':'edit',
            'username':'operator','password':'reset-private-password','enabled':'on',
            'tabs':['directory','hr_hours'],'locations':['Karachi']})
        self.assertEqual(response.status_code,302)
        self.assertEqual(staff.get('/').location,'/login')
        self.assertTrue(verify_password(self.store.read()['users']['operator'],'reset-private-password'))
        self.assertEqual(self.login('operator','reset-private-password',staff).location,'/employee-directory')
        self.assertEqual(staff.get('/employees').status_code,403)

    def test_all_location_permission_and_admin_are_unrestricted(self):
        self.store.save_user('operator',all_locations=True,tabs=['machines'])
        self.login()
        self.assertIn('Private Person',self.client.get('/').text)
        self.login('admin','admin-test-password')
        self.assertIn('Private Person',self.client.get('/').text)

    def test_invalid_assignments_and_passwords_are_rejected_without_changes(self):
        for changes in ({'locations':['Not configured']},{'tabs':[]}, {'password':' short '}):
            values={'tabs':['machines'],'locations':['Pandoki']}
            values.update(changes)
            with self.assertRaises(ValueError):
                self.store.save_user('operator',**values)
        self.assertTrue(verify_password(self.store.read()['users']['operator'],'operator-test-password'))

    def test_login_lockout_and_session_cookie_flags(self):
        for _ in range(5):
            self.assertEqual(self.login(password='wrong-password').status_code,200)
        self.assertEqual(self.login().status_code,429)
        response=self.login('admin','admin-test-password')
        cookie=response.headers['Set-Cookie']
        self.assertIn('HttpOnly',cookie)
        self.assertIn('SameSite=Lax',cookie)
        self.assertNotIn('admin-test-password',cookie)
        self.assertEqual(self.client.get('/settings').headers['Cache-Control'],'no-store')

    def test_empty_store_bootstrap_only_local_with_csrf(self):
        other_path = self.root/'bootstrap.ini'
        other_path.write_text('[security]\nenabled=true\nuser_file='+str(self.root/'empty.ini')
                              +'\naccount_directory='+str(self.root/'fresh'),encoding='utf-8')
        app=create_app(other_path);client=app.test_client()
        self.assertEqual(client.get('/').location,'/setup')
        self.assertEqual(client.get('/setup',environ_base={'REMOTE_ADDR':'192.168.1.10'}).status_code,403)
        self.assertEqual(client.post('/setup',data={'username':'first','password':'first-password'}).status_code,400)
        client.get('/setup')
        response=client.post('/setup',data={'csrf':self.csrf(client),'username':'first','password':'first-password'})
        self.assertEqual(response.location,'/login')
        self.assertEqual(client.get('/setup').location,'/login')
        self.assertEqual(len(app.extensions['user_store'].read()['users']),1)


if __name__ == '__main__':
    unittest.main()
