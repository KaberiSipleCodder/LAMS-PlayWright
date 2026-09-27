"""
Shared pytest fixtures for the LAMS suite.

``lams`` is a MODULE-scoped, already signed-in browser session
(login -> OTP -> "Renewable" -> Proceed -> Land Proposals list) that the
negative tests share: they all start from the same authenticated place,
and repeating the 5-step login for each of them would dominate the run
time.

The two positive end-to-end tests deliberately keep logging in inside
their own bodies - proving the real from-scratch journey still works is
their whole point, so they must not be handed a shortcut.
"""

import pytest

from config import BASE_URL, INDUSTRY, LOGIN_EMAIL, LOGIN_PASSWORD, OTP
from pages.add_land_proposal_page import AddLandProposalPage
from pages.dashboard_page import DashboardPage
from pages.industry_selection_page import IndustrySelectionPage
from pages.land_proposals_page import LandProposalsPage
from pages.login_page import LoginPage
from pages.otp_page import OtpPage
from pages.view_land_proposal_page import ViewLandProposalPage
from utils import reporting as lams_reporting

# BASE_URL points at /auth/login, so the list route is derived from it.
LIST_URL = BASE_URL.split("/auth/")[0] + "/land-banks"


class LamsSession:
    """
    A signed-in Playwright page parked on the Land Proposals list, plus
    the navigation moves the negative tests share.

    Every helper re-enters the flow from the list, so a test that left the
    wizard half-filled (or on a rejected save) can never affect the next
    one.
    """

    def __init__(self, page):
        self.page = page
        self.proposals = LandProposalsPage(page)

    def back_to_list(self, timeout: int = 20000):
        """(Re)loads /land-banks - the clean starting point of every test."""
        self.page.goto(LIST_URL)
        assert self.proposals.is_loaded(), "Land Proposals List did not load"
        return self

    def open_create(self) -> AddLandProposalPage:
        """Land Proposals list -> "Add New Land Proposal" (create wizard)."""
        self.proposals.click_add_new_land_proposal()
        return AddLandProposalPage(self.page)

    def open_existing_record(self, proposal_name: str) -> AddLandProposalPage:
        """Land Proposals list -> first row named ``proposal_name`` -> Edit."""
        self.proposals.click_edit_existing(proposal_name)
        return AddLandProposalPage(self.page)

    def open_view_record(self, proposal_name: str) -> ViewLandProposalPage:
        """
        Land Proposals list -> first row named ``proposal_name`` -> View.

        Returns the READ-ONLY page object; ``page.url`` is then the
        record's own ``.../land-banks/<uuid>`` (the same URL the row's
        View item links to).
        """
        self.proposals.click_view_existing(proposal_name)
        return ViewLandProposalPage(self.page)


@pytest.fixture(scope="module")
def lams(browser, browser_context_args):
    """
    Signs in ONCE per test module and yields a ``LamsSession``.

    Module-scoped (not session-scoped) on purpose: the browser context is
    closed as soon as the module finishes, so a broken negative test can
    never leak its state into another module. ``browser_context_args`` is
    session-scoped in pytest-playwright, so replaying it here keeps this
    context identical to the one the ``page`` fixture builds (same
    viewport/video settings honoured from the CLI).
    """
    context = browser.new_context(**browser_context_args)
    page = context.new_page()

    # Same journey the positive tests walk, without the per-test login.
    LoginPage(page).open(BASE_URL).login(LOGIN_EMAIL, LOGIN_PASSWORD)
    OtpPage(page).enter_otp(OTP)

    industry_page = IndustrySelectionPage(page)
    industry_page.select_industry(INDUSTRY)
    industry_page.confirm_proceed()

    dashboard_page = DashboardPage(page)
    assert dashboard_page.is_loaded(), "Dashboard did not load after clicking Proceed"
    dashboard_page.go_to_land_identification()

    session = LamsSession(page)
    assert session.proposals.is_loaded(), "Land Proposals List page did not load"

    yield session
    context.close()


@pytest.fixture
def lams_list(lams):
    """
    The shared session, guaranteed to start on the Land Proposals list.

    Requested by every negative test that is not about login/OTP.
    """
    lams.back_to_list()
    return lams


# =====================================================================
# TEST EXECUTION REPORTING
#
# Everything below is execution plumbing only - it does not change what any
# test does. The logic lives in utils/reporting.py; the hooks here just
# translate pytest callbacks into calls there:
#
#   pytest_sessionstart     -> reset the result registry + start the clock
#   pytest_runtest_setup    -> register a test case the moment it starts
#   pytest_runtest_makereport -> outcome, failure details, screenshot
#   pytest_runtest_logreport  -> the live "TC03 - FAILED ..." console line
#   pytest_terminal_summary -> the Total/Passed/Failed/Skipped/Time block
#   pytest_sessionfinish    -> reports/failures/*.json|.txt + summary.txt
#
# Test case ids come from the test name ("test_TC03_..." -> TC03) and the
# module/page comes from the folder (tests/land_bank/... -> land_bank), so a
# new module folder needs no extra wiring here.
# =====================================================================


def pytest_configure(config):
    """Hands the Config to the reporting layer (for the live TC lines)."""
    lams_reporting.set_config(config)


def pytest_sessionstart(session):
    lams_reporting.session_start()


def pytest_runtest_setup(item):
    lams_reporting.on_test_start(item)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """
    hookwrapper so we run AFTER pytest decided the outcome but BEFORE fixture
    teardown - that is the only window in which the failed page is still open
    and can be screenshotted.
    """
    outcome = yield
    report = outcome.get_result()
    lams_reporting.on_report(item, report, call)


def pytest_runtest_logreport(report):
    """Prints one line per test case: ``TC03   FAILED   test_TC03_...``."""
    lams_reporting.write_live_line(report)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """The end-of-run block: totals, every test case, and the failure rerun hint."""
    terminalreporter.write_line("")
    terminalreporter.write_line(lams_reporting.summary_text())


def pytest_sessionfinish(session, exitstatus):
    """
    Writes reports/failures/<module>.json|.txt, failures_all.json,
    failed_tests.txt and summary.txt.

    Runs on failures too (that is the point). A reporting problem must never
    turn a green suite red, so it is caught and printed instead of raised.
    """
    try:
        lams_reporting.write_reports()
    except Exception as exc:  # pragma: no cover - reporting must not break a run
        print(f"\n[reporting] could not write the reports: {exc!r}")


def pytest_html_results_summary(prefix, summary, postfix, session):
    """
    Adds the LAMS test-case table (id / result / module / error / screenshot
    path) to the top of the pytest-html report.

    ``pytest_html_*`` is pytest-html's own hook, and pytest-html is a hard
    requirement of this project (``pytest.ini`` always passes
    ``--html=reports/report.html``), so the hook can be defined unconditionally.
    """
    prefix.extend([lams_reporting.html_summary()])
