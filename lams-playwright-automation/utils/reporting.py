"""
The result registry behind the reporting hooks in ``tests/conftest.py``.

Why a separate module instead of putting it all in ``conftest.py``: the hooks
have to be tiny, because a bug in a reporting hook can hide the test failure it
was supposed to describe. Here the logic is readable and testable, and the hooks
are three lines each.

What one run produces:

* a live console line per test case - ``TC03  FAILED  test_TC03_...``;
* a failure screenshot, only for failures (``utils/screenshots.py``);
* a per-module failure detail record (``utils/failure_records.py``);
* the end-of-run Total/Passed/Failed/Skipped block (``utils/summary.py``) on
  the console, in ``reports/summary.txt`` and inside the pytest-html report.
"""

import base64
import os
import time

from utils import failure_records, paths, screenshots, summary

#: node id -> result row, plus the order the tests ran in.
_RESULTS = {}
_ORDER = []

#: Set by ``session_start``; the execution time shown in the summary.
_SESSION_START = None

#: The pytest ``Config`` (set in ``pytest_configure``) - the terminal reporter
#: is reached through it to print the live "TC03 - FAILED" lines.
_CONFIG = None


def _first_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


# ---------------------------------------------------------------------
# Session / per-test bookkeeping
# ---------------------------------------------------------------------
def set_config(config) -> None:
    """
    Remembers the pytest Config.

    Needed because ``pytest_runtest_logreport`` only receives the report, and a
    ``TestReport`` carries no Config - so the terminal reporter has to be
    looked up from here to print the live TC lines.
    """
    global _CONFIG
    _CONFIG = config


def _terminal_writer():
    if _CONFIG is None:
        return None
    return _CONFIG.pluginmanager.getplugin("terminalreporter")


def session_start() -> None:
    """Fresh state for every run (also when a script calls pytest twice)."""
    global _SESSION_START
    _RESULTS.clear()
    del _ORDER[:]
    _SESSION_START = time.time()


def elapsed_seconds() -> float:
    if _SESSION_START is None:
        return 0.0
    return time.time() - _SESSION_START


def _new_row(item) -> dict:
    row = {
        "node_id": item.nodeid,
        "tc_id": paths.testcase_id(item),
        "name": paths.test_name(item),
        "module": paths.test_module(item),
        "outcome": None,
        "duration": 0.0,
        "failure_head": "",
        "screenshot": "",
        "record": None,
        "announced": False,
    }
    _RESULTS[item.nodeid] = row
    _ORDER.append(item.nodeid)
    return row


def on_test_start(item) -> None:
    """Registers the test the moment pytest starts setting it up."""
    if item.nodeid not in _RESULTS:
        _new_row(item)


def results() -> list:
    """Every result row, in run order."""
    return [_RESULTS[node_id] for node_id in _ORDER if node_id in _RESULTS]


def _page_url(item) -> str:
    """The url the page was on when the test failed - often the whole story."""
    page = screenshots.find_page(item)
    if page is None:
        return ""
    try:
        return page.url
    except Exception:  # pragma: no cover - page already closed/crashed
        return ""


# ---------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------
def _attach_html_extras(report, record) -> None:
    """
    Puts the screenshot + failure details into the pytest-html report.

    pytest-html 4 expects an image's **base64 content**, not a file path: given
    a path it emits an ``<img src="C:\\...">`` link, which a shared report cannot
    open (and the self-contained report warns about). Encoding it here is what
    makes the screenshot visible inside ``reports/report.html``.

    Guarded import: the reporting layer must never be the reason a run breaks,
    so if pytest-html is missing the rest of the framework still works.
    """
    try:
        from pytest_html import extras as html_extras
    except ImportError:  # pragma: no cover - pytest-html is in requirements.txt
        return

    extras = list(getattr(report, "extras", []) or [])
    encoded = _base64_image(record.get("screenshot_path"))
    if encoded:
        extras.append(html_extras.image(encoded, name="Failure screenshot"))
    extras.append(
        html_extras.text(
            "TC id  : {}\nModule : {}\nError  : {}".format(
                record["test_case_id"],
                record["module"],
                record["error_message_head"] or "(no message)",
            ),
            name="Failure details",
        )
    )
    report.extras = extras


def _base64_image(path: str) -> str:
    """``path`` as base64 text, or ``""`` when the file is missing/unreadable."""
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as handle:
            return base64.b64encode(handle.read()).decode("utf-8")
    except OSError:  # pragma: no cover - locked file, permissions, ...
        return ""


def _record_failure(row, item, report, call) -> None:
    """Screenshot + failure record for the FIRST failure of a test case."""
    if row["outcome"] == "failed":
        return
    row["outcome"] = "failed"
    row["duration"] = report.duration or row["duration"]

    shot_path, note = screenshots.capture(item, row["module"], row["tc_id"])
    record = failure_records.build_record(
        tc_id=row["tc_id"],
        test_name=row["name"],
        module=row["module"],
        nodeid=row["node_id"],
        phase=call.when,
        excinfo=call.excinfo,
        longrepr=str(report.longrepr) if report.longrepr else "",
        screenshot=shot_path,
        screenshot_note=note,
        page_url=_page_url(item),
        duration=report.duration,
    )
    # The absolute path is kept out of the JSON (so the reports stay portable)
    # but pytest-html needs it to embed the image.
    record["screenshot_path"] = shot_path

    row["record"] = record
    row["screenshot"] = record["screenshot"]
    row["failure_head"] = record["assertion_head"] or _first_line(
        record["error_message_head"]
    )

    _attach_html_extras(report, record)


def on_report(item, report, call) -> None:
    """
    The single entry point used by ``pytest_runtest_makereport``.

    Outcome rules:
      * ``setup`` failure -> the test never ran; still a failure (a fixture or
        browser problem), and the fixture may already have opened a page we can
        screenshot;
      * ``call``          -> the real result;
      * ``teardown``      -> an error here belongs to the test case as well.
    """
    # NOTE: not ``_RESULTS.setdefault(item.nodeid, _new_row(item))`` - the
    # default argument is evaluated EAGERLY, so that would build a fresh row
    # (outcome None) on every single report and wipe the result.
    row = _RESULTS.get(item.nodeid)
    if row is None:
        row = _new_row(item)

    if call.when == "setup":
        if report.failed:
            _record_failure(row, item, report, call)
        elif report.skipped:
            row["outcome"] = "skipped"
        return

    if call.when == "call":
        row["duration"] = report.duration or row["duration"]
        if report.failed:
            _record_failure(row, item, report, call)
        elif report.skipped:
            row["outcome"] = "skipped"
        else:
            row["outcome"] = "passed"
        return

    if report.failed:  # teardown
        _record_failure(row, item, report, call)


# ---------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------
def live_line(report) -> str:
    """
    ``"TC03   FAILED   test_TC03_invalid_land_area   (18.4s)"``.

    Returns ``""`` when this report is not the one that decides the test's
    outcome, so a test case is announced exactly once.
    """
    row = _RESULTS.get(report.nodeid)
    if row is None or row["announced"]:
        return ""

    decides = (
        report.when == "call"
        or (report.when == "setup" and (report.failed or report.skipped))
        or (report.when == "teardown" and report.failed)
    )
    if not decides:
        return ""

    row["announced"] = True
    outcome = row["outcome"] or ("failed" if report.failed else "skipped")
    duration = row["duration"] or report.duration or 0.0
    return (
        f"{row['tc_id'] or '-':<7}{outcome.upper():<9}{row['name']}"
        f"   ({summary.format_duration(duration)})"
    )


def write_live_line(report) -> str:
    """
    Prints the one-line result for a test case as soon as it is decided.

    Returns the text that was printed (``""`` when this report was not the
    deciding one) so the caller can fall back to ``print`` without a terminal.
    """
    line = live_line(report)
    if not line:
        return ""

    terminal = _terminal_writer()
    if terminal is not None:
        terminal.write_line("  " + line)
    else:  # pragma: no cover - only without the terminal plugin
        print("  " + line)
    return line


# ---------------------------------------------------------------------
# Writing everything at the end of the run
# ---------------------------------------------------------------------
def summary_text() -> str:
    """The console / ``reports/summary.txt`` block."""
    return summary.build_summary(results(), elapsed_seconds())


def html_summary() -> str:
    """The same block as HTML, for the pytest-html report."""
    return summary.build_html_summary(results(), elapsed_seconds())


def write_reports() -> dict:
    """
    Writes the failure reports and ``reports/summary.txt``; returns the paths.

    Called from ``pytest_sessionfinish``, so it runs even when the suite fails
    - which is exactly when these files matter.
    """
    records = [row["record"] for row in results() if row.get("record")]
    written = failure_records.write_all(records)

    summary_file = os.path.join(paths.ensure_dir(paths.REPORTS_DIR), "summary.txt")
    with open(summary_file, "w", encoding="utf-8") as handle:
        handle.write(summary_text() + "\n")

    written["summary"] = summary_file
    return written


