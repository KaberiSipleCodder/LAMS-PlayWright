"""
Failure detail capture - one record per FAILED test case.

Requirement: for every failure we must know the
* test case id, test name and module/page,
* error message and the assertion text,
* the screenshot path,
* and the relevant Playwright error / trace when one exists.

The records are organised module-wise::

    reports/
    ├── failures/
    │   ├── land_bank.json          machine readable (one object per case)
    │   ├── land_bank.txt           the same thing, meant to be read
    │   ├── commercial_financial.json / .txt
    │   └── ...
    ├── failures_all.json           every module in one file
    ├── failed_tests.txt            node ids only - input for the rerun script
    └── summary.txt                 the end-of-run summary block

Nothing here runs when the suite is green: the files are only touched when at
least one test failed, and ``failed_tests.txt`` is deliberately rewritten
(emptied) on a fully green run so it can never point at stale failures.
"""

import json
import os
import re

from utils import paths

#: Playwright messages include the whole call log ("Call log: - waiting for
#: locator..."), which can run to thousands of characters. The limits below
#: only keep the reports readable - the full text is still in ``traceback``.
MESSAGE_HEAD_CHARS = 600
LONGREPR_CHARS = 6000

_ARTIFACT_SUFFIXES = (".zip", ".webm", ".png", ".txt")


def is_playwright_error(excinfo) -> bool:
    """
    True when the failure came from Playwright itself (timeout, strict-mode
    violation, target closed, ...) rather than from an ``assert``.

    Checked by module, not by class name: ``Error`` is a very common name but
    ``playwright._impl._errors.Error`` uniquely identifies the library.
    """
    if excinfo is None or excinfo.type is None:
        return False
    return (getattr(excinfo.type, "__module__", "") or "").startswith("playwright")


def _first_meaningful_line(text: str) -> str:
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def _sanitize(text: str) -> str:
    """pytest-playwright spells artifact folders with non-word chars as '-'."""
    return re.sub(r"[^\w\-]+", "-", text or "")


def find_playwright_artifacts(test_name: str) -> list:
    """
    Any artifact pytest-playwright saved for this test (``trace.zip``,
    ``video.webm``, ``test-failed-1.png``, ...).

    Only present when the run asked for them - e.g.
    ``python -m pytest --tracing=retain-on-failure``. When they are missing
    this returns ``[]`` and the report says so instead of pretending a trace
    exists.
    """
    if not os.path.isdir(paths.PLAYWRIGHT_ARTIFACTS_DIR):
        return []

    needle = _sanitize(test_name).lower()
    found = []
    for folder, _subfolders, files in os.walk(paths.PLAYWRIGHT_ARTIFACTS_DIR):
        # The folder is named after the test, so match either the folder name
        # or the full relative path (artifact naming differs between versions).
        haystack = _sanitize(os.path.relpath(folder, paths.PLAYWRIGHT_ARTIFACTS_DIR))
        if needle not in _sanitize(os.path.basename(folder)) and needle not in haystack:
            continue
        for file_name in files:
            if file_name.lower().endswith(_ARTIFACT_SUFFIXES):
                found.append(os.path.join(folder, file_name))
    return sorted(found)


def build_record(
    *,
    tc_id: str,
    test_name: str,
    module: str,
    nodeid: str,
    phase: str,
    excinfo,
    longrepr: str,
    screenshot: str,
    screenshot_note: str,
    page_url: str,
    duration: float,
) -> dict:
    """One failure as a plain dict (JSON-friendly, easy to print)."""
    error_message = ""
    assertion = ""
    if excinfo is not None and excinfo.value is not None:
        error_message = str(excinfo.value).strip()
        if isinstance(excinfo.value, AssertionError):
            assertion = error_message

    playwright_error = is_playwright_error(excinfo)

    # The call log is the interesting half of a Playwright timeout, so keep it
    # separately whenever the failure came from Playwright.
    call_log = ""
    if playwright_error:
        match = re.search(r"Call log:(.*)", error_message, re.DOTALL)
        call_log = match.group(1).strip() if match else ""

    return {
        "test_case_id": tc_id or "(no TC id)",
        "test_name": test_name,
        "module": module,
        "node_id": nodeid,
        "failed_in_phase": phase,
        "error_type": excinfo.type.__name__ if excinfo is not None else "",
        "error_message": error_message,
        "error_message_head": error_message[:MESSAGE_HEAD_CHARS],
        "assertion_error": assertion,
        "assertion_head": _first_meaningful_line(assertion),
        "is_playwright_error": playwright_error,
        "playwright_call_log": call_log,
        "traceback": (longrepr or "")[:LONGREPR_CHARS],
        "page_url": page_url,
        "screenshot": paths.relative_to_project(screenshot),
        "screenshot_note": screenshot_note,
        "playwright_artifacts": [
            paths.relative_to_project(p) for p in find_playwright_artifacts(test_name)
        ],
        "duration_seconds": round(duration or 0.0, 2),
    }


# ---------------------------------------------------------------------
# Writing the reports
# ---------------------------------------------------------------------
_HEADER = "=" * 78


def record_as_text(record: dict) -> str:
    """The human-readable block used in ``reports/failures/<module>.txt``."""
    lines = [
        _HEADER,
        f"{record['test_case_id']} - {record['test_name']}   [FAILED]",
        _HEADER,
        f"  Module / page    : {record['module']}",
        f"  Node id          : {record['node_id']}",
        f"  Failed in phase  : {record['failed_in_phase']}",
        f"  Duration         : {record['duration_seconds']}s",
        f"  Page url         : {record['page_url'] or '(not captured)'}",
        f"  Error type       : {record['error_type']}",
        f"  Error message    : {record['error_message_head'] or '(none)'}",
    ]
    if record["assertion_head"]:
        lines.append(f"  Assertion        : {record['assertion_head']}")
    if record["playwright_call_log"]:
        lines.append("  Playwright call log:")
        lines += [f"      {line}" for line in record["playwright_call_log"].splitlines()]
    if record["screenshot"]:
        lines.append(f"  Screenshot       : {record['screenshot']}")
    else:
        lines.append(f"  Screenshot       : (none - {record['screenshot_note']})")
    if record["playwright_artifacts"]:
        lines.append("  Playwright artifacts:")
        lines += [f"      {path}" for path in record["playwright_artifacts"]]
    else:
        lines.append(
            "  Playwright artifacts: none (rerun with --tracing=retain-on-failure "
            "to record a trace)"
        )
    lines.append("  Traceback:")
    lines += [f"      {line}" for line in (record["traceback"] or "").splitlines()]
    lines.append("")
    return "\n".join(lines)


def write_all(records: list) -> dict:
    """
    Writes every failure report and returns the paths that were produced.

    ``records`` is the list of failed-test records for the run, in the order
    pytest ran them.
    """
    paths.ensure_dir(paths.FAILURES_DIR)

    # failed_tests.txt always exists (also when empty) so the rerun script can
    # rely on it and a green run cannot leave yesterday's failures behind.
    failed_tests_path = os.path.join(paths.REPORTS_DIR, "failed_tests.txt")
    with open(failed_tests_path, "w", encoding="utf-8") as handle:
        handle.write("# Node ids of every test that failed in the LAST run.\n")
        handle.write("# Rerun just these:  python scripts/run_failed_tests.py\n")
        if not records:
            handle.write("# (none - the last run had no failures)\n")
        for record in records:
            handle.write(record["node_id"] + "\n")

    all_json_path = os.path.join(paths.REPORTS_DIR, "failures_all.json")
    with open(all_json_path, "w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2, ensure_ascii=False)

    written = {
        "failed_tests": failed_tests_path,
        "all_json": all_json_path,
        "modules": {},
    }

    for module in sorted({record["module"] for record in records}):
        module_records = [r for r in records if r["module"] == module]
        json_path = os.path.join(paths.FAILURES_DIR, f"{module}.json")
        text_path = os.path.join(paths.FAILURES_DIR, f"{module}.txt")

        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(module_records, handle, indent=2, ensure_ascii=False)
        with open(text_path, "w", encoding="utf-8") as handle:
            handle.write(
                f"LAMS failure details - module '{module}' "
                f"({len(module_records)} failed test case(s))\n\n"
            )
            for record in module_records:
                handle.write(record_as_text(record) + "\n")

        written["modules"][module] = {"json": json_path, "txt": text_path}

    return written


