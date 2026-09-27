"""
Failure screenshots.

Rule the whole suite follows: **only a failed test gets a screenshot.**
Passing tests produce nothing, so ``screenshots/`` stays a list of things
that actually need looking at.

Storage layout (module/page-wise, as requested)::

    screenshots/
    ├── land_bank/              TC03_invalid_land_area_FAILED.png
    ├── technical_team/         TC12_future_site_visit_date_FAILED.png
    ├── commercial_financial/   TC16_invalid_money_values_FAILED.png
    └── general/                negative_view_requires_a_session_FAILED.png

The file name always carries the **test case id AND the test name**, plus the
``_FAILED`` marker.
"""

import os

from utils import paths


def build_screenshot_path(tc_id: str, test_name: str, module: str) -> str:
    """Absolute path a failed test's screenshot will be written to."""
    folder = paths.ensure_dir(os.path.join(paths.SCREENSHOTS_DIR, module))
    stem = paths.screenshot_stem(tc_id, test_name)
    return os.path.join(folder, f"{stem}_FAILED.png")


def find_page(item):
    """
    The Playwright ``Page`` to screenshot for ``item``, or ``None``.

    Three shapes exist in this suite, so all three are handled:

    * tests that request the ``page`` fixture directly (pytest-playwright);
    * tests using the shared session ``lams`` / ``lams_list`` fixture - a
      ``LamsSession`` wrapping its own ``page``;
    * anything else - no page, no screenshot (never an error).

    ``item.funcargs`` only holds the fixtures the test already requested, which
    is exactly what we want: a test that never used a browser cannot leak one
    into a screenshot.
    """
    funcargs = getattr(item, "funcargs", {}) or {}
    for fixture_name in ("page", "lams_list", "lams"):
        obj = funcargs.get(fixture_name)
        if obj is None:
            continue
        page = getattr(obj, "page", obj)  # LamsSession -> its .page
        if hasattr(page, "screenshot"):
            return page
    return None


def capture(item, module: str, tc_id: str) -> tuple:
    """
    Screenshots the page for a FAILED ``item``.

    Returns ``(absolute_path, note)`` where exactly one of the two is set:
    ``note`` explains why no screenshot exists (no browser, page already
    closed, ...) so the failure report never silently loses that information.

    The hook that calls this runs while the browser is still open (pytest
    reports the ``call`` phase *before* fixture teardown closes the page), but
    the ``except`` is still needed: a crash inside the page can make even
    ``screenshot()`` fail, and a reporting problem must never hide the real
    test failure.
    """
    page = find_page(item)
    if page is None:
        return "", "no browser page was used by this test"

    path = build_screenshot_path(tc_id, paths.test_name(item), module)
    try:
        page.screenshot(path=path, full_page=True)
    except Exception as exc:  # pragma: no cover - environment dependent
        return "", f"screenshot failed: {type(exc).__name__}: {exc}"
    return path, ""
