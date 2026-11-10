from pathlib import Path
import tempfile
import unittest

from app import create_app


class MachineSettingsTests(unittest.TestCase):
    def test_server_thread_count_is_configurable_and_bounded(self):
        app = self.app_with('[server]\nthreads=12\n')
        self.assertEqual(app.config['SPEL_THREADS'], 12)
        with self.assertRaises(ValueError):
            self.app_with('[server]\nthreads=0\n')

    def app_with(self, text):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / 'test.ini'
        path.write_text(text, encoding='utf-8')
        return create_app(path)

    def test_local_settings_control_refresh_history_and_activity_labels(self):
        app = self.app_with('[dashboard]\nauto_refresh_seconds=30\n'
                            '[punch_history]\nlimit=10\n'
                            '[machine_activity]\nrecent_minutes=5\ndelayed_minutes=120\n')
        html = app.test_client().get('/').text
        self.assertIn('data-refresh-seconds="30"', html)
        self.assertIn('Last 10 employee punches', html)
        self.assertIn('less than 5 minutes old', html)
        self.assertEqual(app.extensions['machine_cache'].ttl, 30)

    def test_invalid_refresh_and_history_settings_are_rejected(self):
        for text in ('[dashboard]\nauto_refresh_seconds=0\n',
                     '[punch_history]\nlimit=0\n',
                     '[wall_display]\nreference_tile_width=0\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.app_with(text)


if __name__ == '__main__':
    unittest.main()
