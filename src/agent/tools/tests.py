"""Interpret explicit implementation and check status markers."""

import re


def _marker_matches(report: str, marker: str, value: str) -> bool:
    pattern = rf"(?m)^{re.escape(marker)}:\s*{re.escape(value)}\s*$"
    return re.search(pattern, report, re.IGNORECASE) is not None


def edit_succeeded(report: str) -> bool:
    return _marker_matches(report, "EDIT_STATUS", "COMPLETE")


def checks_passed(report: str) -> bool:
    return _marker_matches(report, "CHECKS_STATUS", "PASS")

