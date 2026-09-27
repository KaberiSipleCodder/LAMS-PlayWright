"""
NEGATIVE / REJECTION TESTS - each step must refuse bad input instead of
silently doing the wrong thing.

Every expected message below was CAPTURED from the live UAT app by
``scripts/probe_negative.py`` (raw evidence in ``probe_output/neg_*.json``
+ ``.png``); none of it is guessed. ``TEST_CASES.md`` maps each assertion
back to its capture file. If the app's wording ever changes, re-run that
probe and update the constants in this module only.

Coverage
--------
* Login  - a wrong password must never reach the OTP screen
* OTP    - a blank and an incorrect code must both be rejected
* Create - empty Step 1, missing Document Variant, missing document file
* Edit   - cleared Proposal Name, empty Step 2 (BLOCKED BY THE BROWSER,
           not the server - see that test's docstring), non-integer Shape
           Index, empty Step 3, non-numeric money fields
* Safety - no rejected submit may create a record (entry count compared
           before/after)

Run just these:   pytest -m negative
Skip just these:  pytest -m "not negative"
"""

import re

import pytest

from config import BASE_URL, LOGIN_EMAIL, LOGIN_PASSWORD, OTP
from pages.login_page import LoginPage
from pages.otp_page import OtpPage
from pages.view_land_proposal_page import ViewLandProposalPage
from test_data import WIND_PROJECT_DATA

pytestmark = pytest.mark.negative


# ---------------------------------------------------------------------
# Discovered expectations (probe_output/neg_*.json)
# ---------------------------------------------------------------------
WRONG_PASSWORD = "WrongPass123!"

# A code that is provably NOT the configured one, so this test keeps
# failing for the right reason even if config.OTP changes later.
WRONG_OTP = "".join("9" if digit != "9" else "8" for digit in OTP)

# "Invalid credntials given" - the app's own typo. Matching only
# "Invalid cred" keeps the test passing if that typo is ever fixed.
LOGIN_ERROR = re.compile(r"Invalid cred", re.I)
LOGIN_URL = re.compile(r"/auth/login")
OTP_PAGE_URL = re.compile(r"/auth/validate-otp")
OTP_BLANK_ERROR = "Please enter OTP"
OTP_WRONG_ERROR = "The OTP is incorrect."

STEP1_REQUIRED = (
    "Please enter proposal name",
    "Please select company",
    "Please select project type",
    "Please select state",
    "Please enter latitude degree",
    "Please enter TL distance",
    "Please select document type",
    "Please upload document",
)
VARIANT_REQUIRED = "Please select document variant"
FILE_REQUIRED = "Please upload document"
NAME_REQUIRED = "Please enter proposal name"
SHAPE_INTEGER = "Shape Index must be integer"
STEP3_REQUIRED = (
    "The Basic Cost Sale field is required.",
    "The Commercial Negotiation field is required.",
    "The Tariff due to this land field is required.",
)
TARIFF_REQUIRED = "The Tariff due to this land field is required."
COST_REQUIRED = "The Basic Cost Sale field is required."

# URL shapes used to prove a rejected submit did NOT advance the wizard.
CREATE_WIZARD = re.compile(r"/land-banks/create/?(\d+|$)")
EDIT_STEP1 = re.compile(r"/land-banks/[^/]+/edit/?(\?|$)")
EDIT_STEP2 = re.compile(r"/land-banks/[^/]+/edit-step2")
EDIT_STEP3 = re.compile(r"/land-banks/[^/]+/edit-step3")

# ---------------------------------------------------------------------
# List row action -> View (read-only), captured by scripts/probe_view.py
# ---------------------------------------------------------------------
# The list route again, but for the row's View action the destination is
# the record id and NOTHING else (Edit appends "/edit"):
#   probe_output/view_list_before.json -> View hrefs end at "/<uuid>".
LIST_URL = BASE_URL.split("/auth/")[0] + "/land-banks"
VIEW_URL = re.compile(r".*/land-banks/[^/]+/?$")

# A uuid-shaped id that provably belongs to no record.
# probe_output/view_unknown_uuid.json: HTTP 404, headings
# ['404', 'Page Not Found'], body "404 Page Not Found ... We couldn't find
# the page you are looking for. Back to home", URL unchanged.
UNKNOWN_UUID = "00000000-0000-0000-0000-000000000000"
NOT_FOUND_HEADING = "404"
NOT_FOUND_TEXT = "Page Not Found"
NOT_FOUND_DETAIL = "We couldn't find the page you are looking for."
VIEW_SECTION = "Land Bank Details"

# probe_output/view_unauthenticated.json: HTTP 200 (the login form), URL
# https://.../auth/login, body "Please sign in to your account ...".
LOGIN_URL_RE = re.compile(r"/auth/login")
LOGIN_PAGE_TEXT = "Please sign in"

# Sent by the write attempt against the read-only URL. Never method-
# spoofed: a spoofed PUT could reach a real update handler and change the
# record this suite depends on.
TAMPER_NAME = "PROBE-TAMPER"



# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def has_message(messages, expected: str) -> bool:
    """
    True when ``expected`` (a whole discovered sentence) is on screen.

    Deliberately tolerant about whitespace/casing - the app sometimes
    wraps a message in extra markup - while still requiring the full
    sentence, so a different error can never satisfy it.
    """
    wanted = _normalize(expected)
    return any(wanted in _normalize(m) for m in messages)


def missing_messages(messages, expected) -> list:
    """The subset of ``expected`` that is NOT on screen (empty = all found)."""
    return [text for text in expected if not has_message(messages, text)]


def expect_message(page, pattern, timeout: int = 10000) -> str:
    """Waits for a validation message to become visible, returns its text."""
    element = page.get_by_text(pattern).first
    element.wait_for(state="visible", timeout=timeout)
    return element.inner_text().strip()


def assert_still_on(page, pattern, what: str) -> None:
    assert pattern.search(page.url), f"{what} left the expected page (url={page.url})"


def open_record_and_advance(lams, step: int):
    """
    Opens the existing record and walks the wizard to ``step`` (1-3).

    Steps 1/2 are submitted with the record's STORED data (topped up only
    if that record predates the step), exactly like the positive edit
    test - so the only thing that can fail afterwards is the negative
    behaviour under test. Rejected submits never persist, which is what
    makes this safe to repeat for every edit test.
    """
    add = lams.open_existing_record(WIND_PROJECT_DATA["proposal_name"])
    if step >= 2:
        add.click_step1_submit()
        add.assert_saved()
    if step >= 3:
        if add.field_is_empty(add.TT_PLANT_SIZE):
            add.fill_technical_team(WIND_PROJECT_DATA)
        add.click_step2_save()
        add.assert_step2_saved()
    return add


# =====================================================================
# Login / OTP
# =====================================================================
def test_negative_login_wrong_password_is_rejected(page):
    """
    A wrong password must show the app's error and stay on /auth/login -
    it must never hand the user an OTP screen.

    Discovered: "Invalid credntials given" (neg_login_wrong_password.png),
    url unchanged at /auth/login.
    """
    login = LoginPage(page).open(BASE_URL)
    login.email_input.fill(LOGIN_EMAIL)
    login.password_input.fill(WRONG_PASSWORD)
    login.sign_in_button.click()

    message = expect_message(page, LOGIN_ERROR)
    assert_still_on(page, LOGIN_URL, "The rejected login")
    assert not OTP_PAGE_URL.search(page.url), (
        f"A wrong password reached the OTP screen! url={page.url}"
    )
    print(f"\n[negative] login rejected with: {message!r}")


def test_negative_otp_blank_is_rejected(page):
    """
    Submitting the OTP form without typing a digit must be rejected with
    "Please enter OTP" and keep the user on the OTP screen.

    Discovered: neg_otp_blank.json. OtpPage.enter_otp() is unusable here
    (it asserts a 6-digit code and waits for the post-success redirect),
    so this test clicks the real button directly.
    """
    LoginPage(page).open(BASE_URL).login(LOGIN_EMAIL, LOGIN_PASSWORD)
    OtpPage(page).verify_button.click()

    message = expect_message(page, re.compile(re.escape(OTP_BLANK_ERROR)))
    assert_still_on(page, OTP_PAGE_URL, "The blank OTP submit")
    print(f"\n[negative] blank OTP rejected with: {message!r}")


def test_negative_otp_incorrect_is_rejected(page):
    """
    A complete but wrong 6-digit code must be rejected with
    "The OTP is incorrect." and keep the user on the OTP screen.

    Discovered: neg_otp_wrong.json.
    """
    LoginPage(page).open(BASE_URL).login(LOGIN_EMAIL, LOGIN_PASSWORD)
    otp_page = OtpPage(page)
    otp_page.fill_otp(WRONG_OTP)
    otp_page.submit()

    message = expect_message(page, re.compile(r"The OTP is incorrect", re.I))
    assert_still_on(page, OTP_PAGE_URL, "The incorrect OTP submit")
    print(f"\n[negative] OTP {WRONG_OTP} rejected with: {message!r}")


# =====================================================================
# Create wizard - Step 1
# =====================================================================
def test_negative_create_empty_step1_is_rejected(lams_list):
    """
    Submitting Step 1 with nothing filled in must be rejected field by
    field and must NOT create the land bank: no success banner and the
    wizard stays open.

    Discovered: neg_create_empty_submit.json - 48 on-screen messages
    including every entry asserted below, url still /land-banks/create/1.
    """
    page = lams_list.page
    add = lams_list.open_create()
    add.click_create_land_bank()

    messages = add.wait_for_validation_errors(timeout=10000)
    assert messages, "The empty Step 1 submit was not rejected at all"
    missing = missing_messages(messages, STEP1_REQUIRED)
    assert not missing, (
        f"Step 1 did not complain about {missing}. On screen: {messages}"
    )
    assert not add.banner_appears(BANNER_STEP1), (
        "Step 1 reported success even though the form was empty"
    )
    assert_still_on(page, CREATE_WIZARD, "The rejected Step 1 submit")
    print(f"\n[negative] empty Step 1 rejected with {len(messages)} messages, "
          f"e.g. {messages[0]!r}")


def test_negative_create_missing_document_variant_and_file(lams_list):
    """
    Two document-row rejections on an otherwise valid Step 1:
      1. no Variant and no file -> "Please select document variant"
         AND "Please upload document"
      2. Variant chosen, file still missing -> the variant message is gone
         and only "Please upload document" remains
    Neither attempt may save (the wizard must stay open).

    Discovered: neg_create_no_variant.json (1), neg_create_no_file.json (2).
    """
    page = lams_list.page
    add = lams_list.open_create()

    # 1) everything valid EXCEPT the document row
    add.fill_all_sections(
        dict(WIND_PROJECT_DATA, document_variant=None, document_file_path=None)
    )
    add.click_create_land_bank()
    messages = add.wait_for_validation_errors(timeout=10000)
    assert has_message(messages, VARIANT_REQUIRED), (
        f"The missing-variant submit was not rejected for the variant: {messages}"
    )
    assert has_message(messages, FILE_REQUIRED), (
        f"The missing-variant submit was not rejected for the file: {messages}"
    )
    assert_still_on(page, CREATE_WIZARD, "The submit without a variant")

    # 2) supply the Variant only - the file is still missing
    add.fill_document_section(dict(WIND_PROJECT_DATA, document_file_path=None))
    add.click_create_land_bank()
    messages = add.wait_for_validation_errors(timeout=10000)
    assert has_message(messages, FILE_REQUIRED), (
        f"Choosing the variant hid the file error too - not rejected: {messages}"
    )
    assert not has_message(messages, VARIANT_REQUIRED), (
        f"The variant error survived choosing the variant: {messages}"
    )
    assert not add.banner_appears(BANNER_STEP1), (
        "Step 1 reported success without a document file"
    )
    assert_still_on(page, CREATE_WIZARD, "The submit without a document file")
    print(f"\n[negative] document-row rejections confirmed: "
          f"{VARIANT_REQUIRED!r} then {FILE_REQUIRED!r}")


# =====================================================================
# Edit wizard (existing record) - Step 1
# =====================================================================
def test_negative_edit_cleared_proposal_name_is_rejected(lams_list):
    """
    Clearing the prefilled, required Proposal Name must reject the Step 1
    update with "Please enter proposal name" and persist NOTHING - after
    a reload the stored name is still the original one.

    Discovered: neg_edit_step1_no_name.json - the only message on screen
    is "Please enter proposal name", url still .../land-banks/<uuid>/edit
    (no "Step 1 updated" banner).
    """
    page = lams_list.page
    add = open_record_and_advance(lams_list, 1)
    add.clear_field(add.PROPOSAL_NAME)
    assert add.field_is_empty(add.PROPOSAL_NAME), "The name field was not cleared"

    add.click_step1_submit()
    messages = add.wait_for_validation_errors(timeout=10000)
    assert has_message(messages, NAME_REQUIRED), (
        f"Cleared name was not rejected with {NAME_REQUIRED!r}: {messages}"
    )
    assert not add.banner_appears(BANNER_STEP1), (
        "Step 1 was accepted even though the required name was empty"
    )
    assert_still_on(page, EDIT_STEP1, "The rejected Step 1 update")

    # Nothing was persisted - the reload shows the stored name again.
    page.reload()
    stored = add.field_value(add.PROPOSAL_NAME)
    assert stored == WIND_PROJECT_DATA["proposal_name"], (
        f"The rejected update changed the stored name: {stored!r}"
    )
    print(f"\n[negative] cleared name rejected; stored value intact: {stored!r}")


# =====================================================================
# Edit wizard - Step 2 (Technical Team)
# =====================================================================
def test_negative_edit_empty_step2_is_blocked_by_the_browser(lams_list):
    """
    Clearing every Step 2 field and clicking Save must be BLOCKED BY THE
    BROWSER, not answered by the server.

    Discovered: neg_edit_step2_empty.json holds NO app-level error at all
    (invalid: [] - only the stale "Step 1 updated. Proceed to Step 2."
    banner) yet the url stays on /edit-step2, so the submit never reached
    the server. The captured DOM still shows required="" on
    tlbet_shape_index and on the required selects, and the screenshot
    shows Chrome's own "Please fill in this field." bubble. The decisive
    assertion is therefore validationMessage(), not on-screen text.

    (The earlier suspicion that the server refilled the fields was a
    measurement artefact: clear_field() changes the DOM *property* while
    getAttribute('value') / the saved HTML keep the original attribute.)
    """
    page = lams_list.page
    add = open_record_and_advance(lams_list, 2)
    add.clear_step2_fields()
    assert add.field_is_empty(add.TT_SHAPE_INDEX), "Step 2 was not cleared"
    assert add.field_is_empty(add.TT_SITE_VISIT_DATE), "Step 2 was not cleared"

    blocked = add.native_validation_errors()
    assert blocked, (
        "The browser considers the empty Step 2 form valid - nothing would "
        "stop the submit from reaching the server"
    )

    add.click_step2_save()
    page.wait_for_timeout(1500)

    assert add.native_validation_blocked(), (
        "After clicking Save the browser no longer flags the empty form"
    )
    assert not add.banner_appears(BANNER_STEP2), (
        "Step 2 accepted an entirely empty form"
    )
    assert_still_on(page, EDIT_STEP2, "The browser-blocked Step 2 save")
    print(f"\n[negative] empty Step 2 blocked by the browser on "
          f"{len(blocked)} control(s), e.g. {blocked[0]}")


def test_negative_edit_non_integer_shape_index_is_rejected(lams_list):
    """
    Shape Index = 0.5 must be rejected server-side with
    "Shape Index must be integer" and the wizard must stay on Step 2.

    Discovered: neg_edit_step2_bad_shape.json - the field's own oninput
    sanitiser strips the dot, and the server still refuses the resulting
    value, so the whole Step 2 save fails. After a reload the stored value
    must be intact (the bad value was never persisted).
    """
    page = lams_list.page
    add = open_record_and_advance(lams_list, 2)
    add.fill_technical_team(dict(WIND_PROJECT_DATA, shape_index="0.5"))
    add.click_step2_save()

    messages = add.wait_for_validation_errors(timeout=10000)
    assert has_message(messages, SHAPE_INTEGER), (
        f"Decimal Shape Index was not rejected with {SHAPE_INTEGER!r}: {messages}"
    )
    assert not add.banner_appears(BANNER_STEP2), (
        "Step 2 was accepted with a non-integer Shape Index"
    )
    assert_still_on(page, EDIT_STEP2, "The rejected Step 2 save")

    page.reload()
    stored = add.field_value(add.TT_SHAPE_INDEX)
    assert stored and stored != "0.5", (
        f"The rejected Shape Index was persisted on the record: {stored!r}"
    )
    print(f"\n[negative] shape index 0.5 rejected; stored value intact: {stored!r}")


# =====================================================================
# Edit wizard - Step 3 (Commercial/Financial Details)
# =====================================================================
def test_negative_edit_empty_step3_is_rejected(lams_list):
    """
    Clearing every Step 3 field must be rejected with one
    "The <Field> field is required." message per field - server-side,
    Laravel-style validation (Step 3 has no browser-level required
    attributes, unlike Step 2) - and the final save must not happen.

    Discovered: neg_edit_step3_empty.json - 17 such messages, url still
    .../edit-step3, no "Land Bank updated successfully" alert.
    """
    page = lams_list.page
    add = open_record_and_advance(lams_list, 3)
    add.clear_step3_fields()
    assert add.field_is_empty(add.CF_BASIC_COST_SALE), "Step 3 was not cleared"

    add.click_step3_save()
    messages = add.wait_for_validation_errors(timeout=10000)
    missing = missing_messages(messages, STEP3_REQUIRED)
    assert not missing, (
        f"Step 3 did not complain about {missing}. On screen: {messages}"
    )
    assert not add.banner_appears(BANNER_FINAL), (
        "The final save was accepted even though Step 3 was empty"
    )
    assert_still_on(page, EDIT_STEP3, "The rejected final save")

    page.reload()
    stored = add.field_value(add.CF_BASIC_COST_SALE)
    assert stored, "The rejected final save wiped the stored Step 3 data"
    print(f"\n[negative] empty Step 3 rejected with {len(messages)} messages; "
          f"stored Basic Cost Sale intact: {stored!r}")


def test_negative_edit_non_numeric_money_values_are_rejected(lams_list):
    """
    Text where an amount belongs must be rejected on Step 3 - the app's
    numeric sanitiser empties the box, so the server answers with the
    plain "field is required." message for that one field.

    Discovered:
      * tariff_due_to_this_land = "abc" -> "The Tariff due to this land
        field is required."  (neg_edit_step3_tariff_abc.json)
      * basic_cost_sale = "abc"         -> "The Basic Cost Sale field is
        required."          (neg_edit_step3_cost_abc.json)

    The test then restores the valid data and completes the wizard, so
    the record is left exactly as it was found (and the count safety net
    in the last test still holds).
    """
    page = lams_list.page
    add = open_record_and_advance(lams_list, 3)

    add.fill_commercial_financial(
        dict(WIND_PROJECT_DATA, tariff_due_to_this_land="abc")
    )
    add.click_step3_save()
    messages = add.wait_for_validation_errors(timeout=10000)
    assert has_message(messages, TARIFF_REQUIRED), (
        f"Non-numeric tariff was not rejected with {TARIFF_REQUIRED!r}: {messages}"
    )
    assert_still_on(page, EDIT_STEP3, "The rejected non-numeric tariff")

    add.fill_commercial_financial(dict(WIND_PROJECT_DATA, basic_cost_sale="abc"))
    add.click_step3_save()
    messages = add.wait_for_validation_errors(timeout=10000)
    assert has_message(messages, COST_REQUIRED), (
        f"Non-numeric basic cost was not rejected with {COST_REQUIRED!r}: {messages}"
    )
    assert_still_on(page, EDIT_STEP3, "The rejected non-numeric basic cost")

    # Restore the valid data and finish: the record keeps its own values.
    add.fill_commercial_financial(WIND_PROJECT_DATA)
    add.click_step3_save()
    step3_message = add.assert_step3_saved()
    assert lams_list.proposals.is_loaded(), (
        "Did not return to the Land Proposals List after restoring Step 3"
    )
    print(f"\n[negative] non-numeric amounts rejected; data restored: "
          f"{step3_message!r}")


# =====================================================================
# Safety net
# =====================================================================
def test_negative_rejected_submits_create_no_records(lams_list):
    """
    The guarantee behind everything above: a rejected Create attempt and a
    rejected Edit attempt must leave the Land Proposals list's total-entry
    count EXACTLY as it was.

    Discovered: scripts/probe_negative.py ran all ten rejection scenarios
    and finished with "entries final 48 (baseline 48) -> NO RECORDS
    CREATED". Mirrors the positive edit test's no-new-record guarantee for
    the failure paths instead of the success path.
    """
    before = lams_list.proposals.total_entries()
    print(f"\n[negative] entries before the rejected submits: {before}")

    # (a) create mode - empty Step 1 submit
    add = lams_list.open_create()
    add.click_create_land_bank()
    assert add.wait_for_validation_errors(timeout=10000), (
        "The empty Step 1 create was not rejected"
    )

    # (b) edit mode - empty Step 3 submit. Back to the list first: the
    #     create wizard has no record rows for the edit helper to find.
    lams_list.back_to_list()
    add = open_record_and_advance(lams_list, 3)
    add.clear_step3_fields()
    add.click_step3_save()
    assert add.wait_for_validation_errors(timeout=10000), (
        "The empty Step 3 edit was not rejected"
    )

    lams_list.back_to_list()
    after = lams_list.proposals.total_entries()
    assert after == before, (
        "A rejected submit created a land record! "
        f"Entries before={before}, after={after}"
    )
    print(f"[negative] entries after the rejected submits: {after} (unchanged)")
# =====================================================================
# List row action: View (read-only)
# =====================================================================
def test_negative_view_unknown_proposal_returns_404(lams_list):
    """
    A uuid-shaped id that belongs to no record must NOT render a proposal:
    the app answers 404 and the page carries none of the View page's
    content - no "View Land Proposal" heading and not a single
    label/value block, so nothing can be read out of the system.

    Discovered: probe_output/view_unknown_uuid.json/.png - HTTP 404,
    headings ['404', 'Page Not Found'], body "404 Page Not Found ...
    We couldn't find the page you are looking for. Back to home", and the
    URL is left on the same (missing) id: no redirect to the list and no
    fallback to some other record.
    """
    page = lams_list.page
    missing_url = f"{LIST_URL}/{UNKNOWN_UUID}"
    response = page.goto(missing_url)
    page.wait_for_timeout(1500)
    status = getattr(response, "status", None)

    assert status == 404, (
        f"An unknown proposal id answered {status}, not 404 (url={page.url})"
    )
    assert_still_on(page, re.compile(re.escape(UNKNOWN_UUID)),
                    "The unknown-proposal page")
    assert not ViewLandProposalPage(page).is_loaded(timeout=3000), (
        "The read-only View page rendered for an id that does not exist"
    )

    body = page.inner_text("body")
    assert NOT_FOUND_TEXT in body and NOT_FOUND_DETAIL in body, (
        f"The 404 page did not show the expected wording: {body[:200]!r}"
    )
    assert not page.locator(".detail-item").count(), (
        "The 404 page leaked land-record field values"
    )
    print(f"\n[negative] unknown proposal id -> {status}, no record rendered")


def test_negative_view_page_cannot_change_data(lams_list, playwright):
    """
    The View page must be unusable for changing anything:

      * it contains ZERO form controls (no input / select / textarea),
      * it declares no ``type="submit"`` control and shows no visible
        write action (the only visible action is "Back to List"),
      * a direct write attempt on the same URL is refused by the server
        and every stored value is identical afterwards.

    Discovered: probe_output/view_detail.json - controls=0,
    submitControls=0, visible buttons ['Back to List'] (the layout's
    hidden modal "Delete" button has no type attribute at all).
    The write attempt deliberately does NOT method-spoof: POST to
    ``/land-banks/<uuid>`` is refused with HTTP 405 (Laravel's "Method Not
    Allowed" page - probe log "[view] POST -> status=405 ... <title>Laravel")
    whereas a spoofed PUT could reach a real update handler and modify the
    record. Afterwards every label/value pair on the page is byte-for-byte
    identical ("values changed by the write attempt: NONE").

    The attempt runs through its own request context because this
    environment's certificate chain is rejected by the API request stack
    ("self-signed certificate in certificate chain", found by the probe).
    """
    page = lams_list.page
    view = lams_list.open_view_record(WIND_PROJECT_DATA["proposal_name"])
    assert view.is_loaded(), "The read-only View page did not load"
    url = page.url

    controls = view.form_control_count()
    assert controls == 0, (
        f"The read-only page exposes {controls} form control(s) - it could "
        "be edited"
    )
    assert view.submit_control_count() == 0, (
        "The read-only page declares a submit control"
    )
    assert not view.has_write_action(), (
        "The read-only page offers a write action: "
        f"{view.visible_action_texts()}"
    )
    assert "Back to List" in view.visible_action_texts(), (
        f"No way back to the list from the View page: "
        f"{view.visible_action_texts()}"
    )

    before = view.all_details()
    assert before, "The View page rendered no label/value blocks"

    # The write attempt needs its own request context: this environment's
    # certificate chain is not trusted by the API request stack ("self-signed
    # certificate in certificate chain" - see scripts/probe_view.py), so it
    # takes ignore_https_errors PLUS the session cookies; without the cookies
    # the request would simply be an unauthenticated one and prove nothing.
    api = playwright.request.new_context(
        ignore_https_errors=True,
        storage_state={"cookies": page.context.cookies(), "origins": []},
    )
    try:
        response = api.post(
            url,
            form={"tlb_proposal_name": TAMPER_NAME, "tlb_state_id": "1"},
        )
        status = response.status
    finally:
        api.dispose()
    print(f"\n[negative] POST {url} -> {status}")

    page.goto(url)
    page.wait_for_timeout(1500)
    assert view.is_loaded(), "The View page did not survive the write attempt"
    after = view.all_details()

    assert TAMPER_NAME not in str(after), (
        f"The write attempt reached the record: {after.get('State')!r}"
    )
    assert after == before, (
        "The write attempt changed the stored record. "
        f"Changed: {[k for k in before if before[k] != after.get(k)]}"
    )
    assert status >= 400, (
        f"POST to the read-only URL was accepted (status {status})"
    )
    print("[negative] read-only page: no controls, no submit, write refused")


def test_negative_view_requires_a_session(browser, lams_list):
    """
    A real record's View URL requested WITHOUT a session must never
    disclose the record: the app sends the visitor to the login page and
    the page contains no land-record field values.

    Discovered: probe_output/view_unauthenticated.json - a brand-new
    browser context (no cookies) opening
    ``.../land-banks/<uuid>`` lands on ``/auth/login`` (HTTP 200 for the
    login form), body "Please sign in to your account ..." and
    ``shows proposal name: False``.

    The guest context is separate from the shared signed-in session on
    purpose - and it is always closed in ``finally`` so it can never leak
    into the other tests.
    """
    page = lams_list.page
    view = lams_list.open_view_record(WIND_PROJECT_DATA["proposal_name"])
    assert view.is_loaded(), "The read-only View page did not load"
    view_url = page.url

    # Hand the shared session back its clean starting page before opening
    # a second browser context.
    lams_list.back_to_list()

    guest_context = browser.new_context()
    try:
        guest = guest_context.new_page()
        guest.goto(view_url)
        guest.wait_for_timeout(1500)

        assert not ViewLandProposalPage(guest).is_loaded(timeout=3000), (
            "An unauthenticated visitor was served the record's View page"
        )
        assert LOGIN_URL_RE.search(guest.url), (
            f"Unauthenticated access was not sent to the login page: "
            f"{guest.url}"
        )
        body = guest.inner_text("body")
        assert LOGIN_PAGE_TEXT in body, (
            f"The login page did not load: {body[:200]!r}"
        )
        assert not guest.locator(".detail-item").count(), (
            "The login page leaked land-record field values"
        )
        print(f"\n[negative] guest visit to {view_url} -> {guest.url} "
              "(no record data)")
    finally:
        guest_context.close()


# Success wording that must never appear after a rejected submit.
BANNER_STEP1 = re.compile(r"Step 1[^.]*(saved|updated)", re.I)
BANNER_STEP2 = re.compile(r"Step 2[^.]*(saved|updated)", re.I)
BANNER_FINAL = re.compile(r"Land Bank (created|updated) successfully", re.I)
