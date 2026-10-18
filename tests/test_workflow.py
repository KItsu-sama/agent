import unittest

from agent.tools.tests import checks_passed, edit_succeeded


class WorkflowMarkerTests(unittest.TestCase):
    def test_accepts_explicit_success_markers(self) -> None:
        self.assertTrue(edit_succeeded("Done.\nEDIT_STATUS: COMPLETE"))
        self.assertTrue(checks_passed("All checks passed.\nCHECKS_STATUS: PASS"))

    def test_rejects_failure_missing_and_embedded_markers(self) -> None:
        self.assertFalse(edit_succeeded("EDIT_STATUS: FAIL"))
        self.assertFalse(edit_succeeded("The status is EDIT_STATUS: COMPLETE"))
        self.assertFalse(checks_passed("CHECKS_STATUS: FAIL"))
        self.assertFalse(checks_passed("Tests passed, probably."))


if __name__ == "__main__":
    unittest.main()
