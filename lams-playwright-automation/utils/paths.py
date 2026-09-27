"""
Filesystem paths and "who is this test?" helpers for the reporting layer.

Everything the suite produces (screenshots, reports, failure logs) is placed
relative to the PROJECT ROOT - the folder that holds ``pytest.ini`` - so the
paths are identical no matter which directory pytest was started from.

The two identity helpers are the reason a report line can read
``TC03 - FAILED`` and a screenshot can be stored under ``screenshots/land_bank/``:

* ``testcase_id(item)`` reads the ``TC<number>`` out of the test name
  (``test_TC03_invalid_land_area`` -> ``TC03``). A test can also state its id
  explicitly with ``@pytest.mark.tc_id("TC03")``, which wins over the name.
* ``test_module(item)`` maps the test's FOLDER to the module/page bucket
  (``tests/land_bank/... -> land_bank``). Tests that are not module-wise
  (the older flat files in ``tests/``) fall back to ``general``.
"""

import os
import re

# ---------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------
# utils/paths.py -> utils/ -> project root (the folder with pytest.ini)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, "screenshots")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")
FAILURES_DIR = os.path.join(REPORTS_DIR, "failures")

#: pytest-playwright's own artifact folder (traces/videos/screenshots when
#: ``--tracing`` / ``--video`` / ``--screenshot`` are switched on).
PLAYWRIGHT_ARTIFACTS_DIR = os.path.join(PROJECT_ROOT, "test-results")

#: Folders under ``tests/`` that count as a module/page. The FIRST match in
#: the test's path wins, so nesting (``tests/land_bank/step1/...``) still
#: reports the module as ``land_bank``.
MODULES = ("land_bank", "technical_team", "commercial_financial")

#: Bucket used for tests that are not inside a module folder.
DEFAULT_MODULE = "general"

# Matches "TC03", "tc 3", "TC_3" - the number is re-padded to 2 digits.
_TC_ID_RE = re.compile(r"tc[\s_-]*0*(\d+)", re.IGNORECASE)

# Characters Windows refuses in a file name. "/" and "\" are separators, so
# they would be a path-injection if left alone.
_ILLEGAL_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def ensure_dir(path: str) -> str:
    """Creates ``path`` (and its parents) if needed and returns it."""
    os.makedirs(path, exist_ok=True)
    return path


def _path_of(item) -> str:
    """The test file a pytest Item belongs to, as a normalised string."""
    # ``item.path`` exists on pytest >= 7 (this project pins 8.3.3);
    # ``item.fspath`` is the legacy fallback.
    raw = getattr(item, "path", None) or getattr(item, "fspath", "")
    return str(raw).replace("\\", "/").lower()


def test_name(item) -> str:
    """
    The test name WITHOUT pytest's parametrization suffix.

    pytest-playwright parametrizes every test with the browser, so ``item.name``
    is ``test_TC03_invalid_land_area[chromium]``. ``originalname`` drops the
    ``[chromium]`` - which is what a report row and a screenshot file name
    should carry.
    """
    return str(getattr(item, "originalname", None) or item.name)


def testcase_id(item) -> str:
    """
    The test case id for ``item``, e.g. ``"TC03"``; ``""`` when it has none.

    Order of preference:
      1. an explicit ``@pytest.mark.tc_id("TC03")`` marker, so a test can be
         renamed without losing its id;
      2. the ``TC<number>`` inside the test name.
    """
    marker = item.get_closest_marker("tc_id")
    if marker is not None and marker.args:
        raw = str(marker.args[0])
        match = _TC_ID_RE.search(raw)
        if match:
            return "TC" + match.group(1).zfill(2)
        return _ILLEGAL_CHARS_RE.sub("-", raw).strip().upper()

    match = _TC_ID_RE.search(test_name(item))
    if match:
        return "TC" + match.group(1).zfill(2)
    return ""


def test_module(item) -> str:
    """The module/page bucket for ``item`` (``land_bank``, ``general``, ...)."""
    parts = _path_of(item).split("/")
    for module in MODULES:
        if module in parts:
            return module
    return DEFAULT_MODULE


def safe_name(text: str) -> str:
    """
    Turns a test name into a file-name-safe stem (no ``/``, ``:``, spaces).

    ``test_TC03_invalid_land_area`` -> ``TC03_invalid_land_area`` (the leading
    ``test_`` is dropped by ``screenshot_stem``, not here, because a failure
    detail line may still want the original name).
    """
    return _ILLEGAL_CHARS_RE.sub("-", text).strip() or "test"


def screenshot_stem(tc_id: str, test_name: str) -> str:
    """
    The file-name stem for a failure screenshot.

    ``("TC03", "test_TC03_invalid_land_area")`` -> ``"TC03_invalid_land_area"``

    The leading ``test_`` and the ``TC03_`` that follows it are removed so the
    id is not repeated, exactly like the required example
    ``TC03_invalid_land_area_FAILED.png``. Tests without a TC id keep their
    whole name (``negative_view_requires_a_session``) so a screenshot is never
    anonymous.
    """
    name = re.sub(r"^test_", "", test_name)
    if tc_id:
        name = re.sub(rf"^{re.escape(tc_id)}_?", "", name, flags=re.IGNORECASE)
    stem = f"{tc_id}_{name}" if tc_id else name
    return safe_name(stem) or "test"


def relative_to_project(path: str) -> str:
    """``path`` as a root-relative string with forward slashes, for reports."""
    if not path:
        return ""
    try:
        rel = os.path.relpath(path, PROJECT_ROOT)
    except ValueError:  # different drive (rare on Windows) - keep it absolute
        rel = path
    return rel.replace("\\", "/")
