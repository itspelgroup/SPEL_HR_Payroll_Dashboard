import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime
from unittest.mock import Mock
from werkzeug.security import generate_password_hash

from app import create_app
from dashboard.attendance import PAKISTAN
from dashboard.machines import Machine, MachineSnapshot, MachinePunch
from dashboard.users import connect_users


class MachineAccessTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        self.path = root / 'test.ini'
        self.path.write_text('[security]\nenabled=true\naccount_directory=' + str(root / 'accounts'), encoding='utf-8')
        with connect_users(root / 'accounts') as connection:
            for name, location, admin in [('admin', None, 1), ('pandoki', 'Pandoki', 0)]:
                connection.execute('INSERT INTO users VALUES (?, ?, ?, ?)',
                                   (name, generate_password_hash('test-password-123'), location, admin))
        now = datetime.now(PAKISTAN)
        self.loader = Mock(side_effect=lambda day: MachineSnapshot((
            Machine('PAN', 'Pandoki machine', 'Pandoki', 'U1', True, now, now,
                    '001', now, 'Pandoki Person', 'Pandoki room',
                    (MachinePunch(1, '001', now, now, 'Pandoki Person', 'EMPLOYEE-UNIT', 'Pandoki room'),)),
            Machine('KHI', 'Karachi machine', 'Karachi', 'U8', True, now, now,
                    '999', now, 'Karachi Secret Person', 'Karachi room',
                    (MachinePunch(2, '999', now, now, 'Karachi Secret Person', 'EMPLOYEE-UNIT', 'Karachi room'),)),
        ), now, day))
        self.client = create_app(self.path, machine_provider=self.loader).test_client()

    def sign_in(self, username):
        self.client.get('/login')
        with self.client.session_transaction() as state:
            csrf = state['csrf']
        return self.client.post('/login', data=dict(username=username,
                                password='test-password-123', csrf=csrf))

    def test_anonymous_requests_cannot_load_machine_data(self):
        self.assertEqual(self.client.get('/').status_code, 302)
        self.loader.assert_not_called()

    def test_location_account_cannot_override_scope_or_read_other_employee_details(self):
        self.assertEqual(self.sign_in('pandoki').status_code, 302)
        response = self.client.get('/', query_string={'location': json.dumps('karachi')})
        self.assertIn('Pandoki Person', response.text)
        self.assertNotIn('Karachi Secret Person', response.text)
        self.assertNotIn('Karachi machine', response.text)
        self.assertEqual(self.client.get('/attendance').status_code, 403)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_admin_can_view_every_location(self):
        self.sign_in('admin')
        html = self.client.get('/').text
        self.assertIn('Pandoki Person', html)
        self.assertIn('Karachi Secret Person', html)

    def test_login_rejects_missing_csrf(self):
        self.assertEqual(self.client.post('/login', data=dict(username='admin',
                         password='test-password-123')).status_code, 400)


if __name__ == '__main__':
    unittest.main()
