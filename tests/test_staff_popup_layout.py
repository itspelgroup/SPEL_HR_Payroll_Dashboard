import unittest

from app import create_app
from dashboard.config import ROOT


class StaffPopupLayoutTests(unittest.TestCase):
    def setUp(self):
        self.client=create_app(ROOT/'config.example.ini').test_client()

    def test_both_pages_keep_detail_tables_and_filters_inside_dialogs(self):
        for path in ('/employees','/employee-directory'):
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertEqual(response.status_code,200)
                main=response.text.split('<main',1)[1].split('<dialog',1)[0]
                self.assertNotIn('<select',main)
                self.assertNotIn('department-panel',main)
                self.assertNotIn('directory-panel',main)
                self.assertIn('data-staff-kind',main)
                if path == '/employees':
                    self.assertIn('<section class="attendance-breakdowns"',main)
                    self.assertEqual(main.count('<table>'),3)
                else:
                    self.assertNotIn('<table',main)
                popup=response.text.split('<dialog',1)[1]
                fields=('branch','unit','department','employee_location') if path == '/employees' else ('unit','department','physical')
                for field in fields:
                    self.assertIn('data-staff-filter="'+field+'"',popup)
                self.assertNotIn('Designation',popup)
                self.assertIn('data-staff-search',popup)
                self.assertEqual('data-staff-breakdown' in popup,path == '/employee-directory')
                self.assertIn('data-staff-sort',popup)

    def test_every_directory_tile_opens_a_popup(self):
        html=self.client.get('/employee-directory').text
        tiles=html.split('<section class="directory-summary"',1)[1].split('</section>',1)[0]
        self.assertEqual(tiles.count('data-staff-kind="all"'),3)
        self.assertNotIn('<article',tiles)


if __name__=='__main__':unittest.main()
