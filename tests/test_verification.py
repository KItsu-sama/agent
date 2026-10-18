import sys
import tempfile
import unittest
from pathlib import Path

from agent.tools.verification import verify_workspace


class IndependentVerificationTests(unittest.TestCase):
    def test_uses_process_exit_code_not_successful_sounding_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = verify_workspace(
                Path(temporary),
                commands=((sys.executable, "-c", "print('PASS'); raise SystemExit(7)"),),
            )

        self.assertFalse(result.passed)
        self.assertEqual(result.checks[0].returncode, 7)
        self.assertIn("PASS", result.checks[0].output)

    def test_reports_pass_when_command_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = verify_workspace(
                Path(temporary),
                commands=((sys.executable, "-c", "print('checks completed')"),),
            )

        self.assertTrue(result.passed)
        self.assertEqual(result.checks[0].returncode, 0)

    def test_unsupported_workspace_does_not_count_as_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = verify_workspace(Path(temporary), commands=())

        self.assertFalse(result.passed)
        self.assertEqual(result.checks, ())
        self.assertIn("not a passing result", result.note)


if __name__ == "__main__":
    unittest.main()
