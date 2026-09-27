"""
The end-of-run summary ("Total / Passed / Failed / Skipped / Execution Time")
and the matching block for the HTML report.

It is written for one purpose: after ``python -m pytest`` you should be able to
read the bottom of the console and know exactly which test case ids failed
without scrolling back through the whole run.
"""

from utils import paths

_LINE = "=" * 78
_THIN = "-" * 78


def format_duration(seconds: float) -> str:
    """``3725.4`` -> ``"1h 02m 05s"``; short runs stay in seconds."""
    seconds = max(float(seconds or 0.0), 0.0)
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, rest = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {rest:02d}s"
    return f"{minutes}m {rest:02d}s"


def counts(results: list) -> dict:
    """``{"total":.., "passed":.., "failed":.., "skipped":..}`` for the run."""
    total = len(results)
    passed = sum(1 for r in results if r["outcome"] == "passed")
    failed = sum(1 for r in results if r["outcome"] == "failed")
    skipped = sum(1 for r in results if r["outcome"] == "skipped")
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "other": total - passed - failed - skipped,
    }


def outcome_of(row: dict) -> str:
    """
    The row's outcome, never ``None``.

    A defensive default: if a future pytest ever reports a test in a way this
    framework does not expect, the summary must still print something instead of
    crashing while describing it.
    """
    return row.get("outcome") or "unknown"


def _label(row: dict) -> str:
    return f"{row['tc_id'] or '-':<7}{outcome_of(row).upper():<9}{row['name']}"


def build_summary(results: list, duration_seconds: float) -> str:
    """
    The console block + ``reports/summary.txt``.

    Every test case gets its own line ("TC03 - FAILED") so the requirement
    "I should be able to see every test case result clearly" is satisfied by
    the summary alone, even at the end of a long run.
    """
    stats = counts(results)
    lines = [
        _LINE,
        " LAMS TEST EXECUTION SUMMARY",
        _LINE,
        f" Total Tests    : {stats['total']}",
        f" Passed         : {stats['passed']}",
        f" Failed         : {stats['failed']}",
        f" Skipped        : {stats['skipped']}",
        f" Execution Time : {format_duration(duration_seconds)}",
        _THIN,
        f" {'TC ID':<7}{'RESULT':<9}TEST CASE",
        _THIN,
    ]
    lines += [_label(row) for row in results] or [" (no tests ran)"]

    failures = [row for row in results if row["outcome"] == "failed"]
    if failures:
        lines += [_THIN, " FAILED TEST CASES (rerun only these below)", _THIN]
        for row in failures:
            lines.append(f" {row['tc_id'] or '-':<7}{row['name']}  [{row['module']}]")
            lines.append(f"         {row['node_id']}")
            if row.get("failure_head"):
                lines.append(f"         {row['failure_head']}")
            if row.get("screenshot"):
                lines.append(f"         screenshot: {row['screenshot']}")
        lines += [
            _THIN,
            " Rerun only the failed tests:",
            "     python -m pytest --lf                 (pytest's own cache)",
            "     python scripts/run_failed_tests.py    (uses reports/failed_tests.txt)",
        ]
    else:
        lines += [_THIN, " No failures - no screenshots were taken."]

    lines += [
        _THIN,
        f" HTML report   : {paths.relative_to_project(paths.REPORTS_DIR)}/report.html",
    ]
    if failures:
        lines.append(
            f" Failure log   : reports/failures/<module>.json|.txt  "
            f"({', '.join(sorted({row['module'] for row in failures}))})"
        )
        lines.append(f" Screenshots   : screenshots/<module>/<TCxx>_<name>_FAILED.png")
    lines.append(_LINE)
    return "\n".join(lines)


def build_html_summary(results: list, duration_seconds: float) -> str:
    """
    The same block as HTML, injected into the pytest-html report.

    pytest-html's own summary table already lists passed/failed/skipped, but it
    has no idea what a "TC03" is, so this adds the test-case view on top:
    id + name + module + duration, with the failed rows marked and their
    screenshot/error shown.
    """
    stats = counts(results)
    rows = []
    for row in results:
        outcome = outcome_of(row)
        colour = {"passed": "#2e7d32", "failed": "#c62828"}.get(outcome, "#616161")
        detail = ""
        if outcome == "failed":
            if row.get("failure_head"):
                detail += f"<div style='color:#c62828'>{_escape(row['failure_head'])}</div>"
            if row.get("screenshot"):
                detail += (
                    "<div>Screenshot: <code>"
                    f"{_escape(row['screenshot'])}</code></div>"
                )
        rows.append(
            "<tr>"
            f"<td><b>{_escape(row['tc_id'] or '-')}</b></td>"
            f"<td style='color:{colour}'><b>{outcome.upper()}</b></td>"
            f"<td>{_escape(row['module'])}</td>"
            f"<td>{_escape(row['name'])}{detail}</td>"
            f"<td>{format_duration(row.get('duration', 0))}</td>"
            "</tr>"
        )

    return (
        "<h2>LAMS test-case summary</h2>"
        "<p>"
        f"<b>Total tests:</b> {stats['total']} &nbsp;|&nbsp; "
        f"<b>Passed:</b> {stats['passed']} &nbsp;|&nbsp; "
        f"<b>Failed:</b> {stats['failed']} &nbsp;|&nbsp; "
        f"<b>Skipped:</b> {stats['skipped']} &nbsp;|&nbsp; "
        f"<b>Execution time:</b> {format_duration(duration_seconds)}"
        "</p>"
        "<table style='width:100%;border-collapse:collapse'>"
        "<thead><tr style='text-align:left'>"
        "<th>TC ID</th><th>Result</th><th>Module / page</th>"
        "<th>Test case</th><th>Duration</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
