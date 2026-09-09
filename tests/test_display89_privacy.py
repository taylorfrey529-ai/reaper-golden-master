import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'recovery/workspace/reaper-display88-tcp-candidate.py'
spec = importlib.util.spec_from_file_location('candidate', SOURCE)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class PrivacyTests(unittest.TestCase):
    def test_cookie_stays_in_stdin(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'Xauthority'
            with patch.object(candidate.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as call:
                secret = candidate.make_xauthority(target, 89)
            self.assertNotIn(secret, repr(call.call_args.args))
            self.assertIn(secret, call.call_args.kwargs['input'])
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_error_is_redacted_and_temp_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(candidate.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, 'SECRET', 'SECRET')):
                with self.assertRaises(RuntimeError) as error:
                    candidate.make_xauthority(Path(directory) / 'Xauthority', 89)
            self.assertNotIn('SECRET', str(error.exception))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_existing_authority_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'Xauthority'
            target.write_text('existing')
            with self.assertRaises(RuntimeError):
                candidate.make_xauthority(target, 89)
            self.assertEqual(target.read_text(), 'existing')

    def test_symlink_target_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'Xauthority'
            target.symlink_to(Path(directory) / 'absent')
            with self.assertRaises(RuntimeError):
                candidate.make_xauthority(target, 89)
            self.assertFalse((Path(directory) / 'absent').exists())

    def test_public_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o755)
            with self.assertRaises(RuntimeError):
                candidate.make_xauthority(Path(directory) / 'Xauthority', 89)

    def test_canonical_display_and_acquisition_are_blocked(self):
        with self.assertRaises(RuntimeError):
            candidate.selftest(88)
        with self.assertRaises(RuntimeError):
            candidate.acquire_tcp_candidate(Path('/absent'), 88, Path('/absent'))

    def test_unverified_and_broad_listeners_are_refused(self):
        for records in [[], [{'family': 'IPv4', 'address_hex': '00000000', 'inode': '1'}],
                        [{'family': 'IPv6', 'address_hex': '0' * 32, 'inode': '1'}]]:
            with self.subTest(records=records), self.assertRaises(RuntimeError):
                candidate.verify_listener(records, os.getpid())


if __name__ == '__main__':
    unittest.main()
