from datetime import datetime
import unittest

from app import create_app
from dashboard.attendance import PAKISTAN
from dashboard.config import ROOT
from dashboard.machines import Machine, MachineSnapshot


class MachineGroupTests(unittest.TestCase):
    def test_entry_exit_and_unknown_names_have_separate_sections(self):
        now=datetime.now(PAKISTAN)
        machines=tuple(Machine(code,name,'Pandoki',None,True,now,now)
                       for code,name in [('A','TS-IN-01'),('B','TS-OUT-01'),('C','UNKNOWN-01')])
        client=create_app(ROOT/'config.example.ini',machine_provider=lambda day:
                          MachineSnapshot(machines,now,day)).test_client()
        html=client.get('/').text
        self.assertIn('machine-section direction-in',html)
        self.assertIn('machine-section direction-out',html)
        self.assertIn('machine-section direction-unknown',html)
        self.assertIn('Entry machines',html)
        self.assertIn('Exit machines',html)
        self.assertEqual(html.count('class="wall-tile '),3)
        self.assertEqual(html.count('<select'),1)


if __name__ == '__main__':
    unittest.main()
