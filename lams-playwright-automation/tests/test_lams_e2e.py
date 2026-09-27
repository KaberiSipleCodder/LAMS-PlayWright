import re

import pytest

from config import BASE_URL, LOGIN_EMAIL, LOGIN_PASSWORD, OTP, INDUSTRY
from pages.login_page import LoginPage
from pages.otp_page import OtpPage
from pages.industry_selection_page import IndustrySelectionPage
from pages.dashboard_page import DashboardPage
from pages.land_proposals_page import LandProposalsPage
from pages.add_land_proposal_page import AddLandProposalPage
from pages.view_land_proposal_page import ViewLandProposalPage
from test_data import WIND_PROJECT_DATA


@pytest.mark.smoke
@pytest.mark.e2e
def test_add_new_land_proposal(page):
    """
    Full flow, step by step:
      1. Login (admin@lams.com / 123456, no captcha)
      2. Enter OTP (123456)
      3. Select "Renewable" industry
      4. Confirm "Proceed" on the modal
      5. Go to Land Identification / Proposal
      6. Click "Add New Land Proposal"
      7. Fill every Step 1 section and submit ("Create Land Bank")
      8. Fill Step 2 "Technical Team" and submit ("Save")
      9. Fill Step 3 "Commercial/Financial Details" and submit ("Save")
    """
    # 1. Login
    login_page = LoginPage(page).open(BASE_URL)
    login_page.login(LOGIN_EMAIL, LOGIN_PASSWORD)

    # 2. OTP
    otp_page = OtpPage(page)
    otp_page.enter_otp(OTP)

    # 3 & 4. Select Renewable, then Proceed
    industry_page = IndustrySelectionPage(page)
    industry_page.select_industry(INDUSTRY)
    industry_page.confirm_proceed()

    dashboard_page = DashboardPage(page)
    assert dashboard_page.is_loaded(), "Dashboard did not load after clicking Proceed"

    # 5. Land Identification / Proposal
    dashboard_page.go_to_land_identification()
    land_proposals_page = LandProposalsPage(page)
    assert land_proposals_page.is_loaded(), "Land Proposals List page did not load"

    # 6. Add New Land Proposal
    land_proposals_page.click_add_new_land_proposal()
    add_land_proposal_page = AddLandProposalPage(page)

    # 7. Fill all Step 1 sections and submit
    add_land_proposal_page.fill_all_sections(WIND_PROJECT_DATA)
    add_land_proposal_page.click_create_land_bank()

    # 8. Step 1 must confirm the save AND show no on-screen validation
    #    errors. Without this the suite reported green even when the form was
    #    rejected for a missing required field (Document Variant / file upload).
    message = add_land_proposal_page.assert_saved()
    print(f"\n[save confirmed] {message}")

    # 9. Step 2 - Technical Team. The wizard activates it automatically
    #    after the Step 1 save ("Proceed to Step 2").
    add_land_proposal_page.fill_technical_team(WIND_PROJECT_DATA)
    add_land_proposal_page.click_step2_save()

    # 10. Step 2 needs the same two-part check: confirmation banner + no
    #     visible validation errors.
    step2_message = add_land_proposal_page.assert_step2_saved()
    print(f"[step 2 save confirmed] {step2_message}")

    # 11. Step 3 - Commercial/Financial Details (final step of the wizard).
    add_land_proposal_page.fill_commercial_financial(WIND_PROJECT_DATA)
    add_land_proposal_page.click_step3_save()

    # 12. Banner + no-validation-errors, same two-part check as before.
    step3_message = add_land_proposal_page.assert_step3_saved()
    print(f"[step 3 save confirmed] {step3_message}")

    # 13. The final save must land back on the Land Proposals List page
    #     (confirmed: Step 3 redirects to /land-banks).
    assert land_proposals_page.is_loaded(), (
        "Did not return to the Land Proposals List after the Step 3 save"
    )


@pytest.mark.smoke
@pytest.mark.e2e
def test_edit_existing_land_proposal(page):
    """
    EDIT flow against EXISTING data - creates NO new land record.

    Deliberate differences from test_add_new_land_proposal:
      * Never clicks "Add New Land Proposal". Instead opens the first
        existing row (same proposal name) through its action menu ->
        Edit (.../land-banks/<uuid>/edit).
      * Never refills Step 1 - the page arrives fully prefilled with the
        record's stored values; the test only submits them
        ("Update Land Bank"). Steps 2/3 are topped up ONLY if the chosen
        record predates those fields (empty step), otherwise they are
        saved as-is too.
      * Proves "no new record" by comparing the list's total-entry count
        before and after the whole edit.

    Steps:
      1-4. Login -> OTP -> Renewable -> Proceed (same as create test)
      5.   Land Identification / Proposal list; capture total entries
      6.   Open existing row via action menu -> Edit
      7.   Assert Step 1 is prefilled with the record's existing data
      8.   Submit Step 1 ("Update Land Bank") + two-part assertion
      9.   Submit Step 2 ("Save") + two-part assertion
      10.  Submit Step 3 ("Save") + two-part assertion
      11.  Back on the list; total entries must be UNCHANGED
    """
    # 1. Login
    login_page = LoginPage(page).open(BASE_URL)
    login_page.login(LOGIN_EMAIL, LOGIN_PASSWORD)

    # 2. OTP
    otp_page = OtpPage(page)
    otp_page.enter_otp(OTP)

    # 3 & 4. Select Renewable, then Proceed
    industry_page = IndustrySelectionPage(page)
    industry_page.select_industry(INDUSTRY)
    industry_page.confirm_proceed()

    dashboard_page = DashboardPage(page)
    assert dashboard_page.is_loaded(), "Dashboard did not load after clicking Proceed"

    # 5. Land Identification / Proposal list + baseline record count
    dashboard_page.go_to_land_identification()
    land_proposals_page = LandProposalsPage(page)
    assert land_proposals_page.is_loaded(), "Land Proposals List page did not load"
    total_before = land_proposals_page.total_entries()
    print(f"\n[entries before] {total_before}")

    # 6. Open the EXISTING record - never touches "Add New Land Proposal"
    land_proposals_page.click_edit_existing(WIND_PROJECT_DATA["proposal_name"])
    add_land_proposal_page = AddLandProposalPage(page)

    # 7. The record's stored data must arrive prefilled (this is what
    #    "test with existing data" means: we submit stored values, not
    #    freshly typed ones).
    prefilled_name = add_land_proposal_page.field_value(
        add_land_proposal_page.PROPOSAL_NAME
    )
    assert prefilled_name == WIND_PROJECT_DATA["proposal_name"], (
        "Edit page did not load the existing record: expected proposal "
        f"name {WIND_PROJECT_DATA['proposal_name']!r}, got {prefilled_name!r}"
    )
    print(f"[existing record] proposal name prefilled: {prefilled_name!r}")

    # 8. Step 1 - submit AS-IS (no refill); edit mode says "updated".
    add_land_proposal_page.click_step1_submit()
    step1_message = add_land_proposal_page.assert_saved()
    print(f"[edit step 1] {step1_message}")

    # 9. Step 2 - top up only if this record predates Step 2 data
    #    (records left by older probe runs can have an empty step).
    if add_land_proposal_page.field_is_empty(
        add_land_proposal_page.TT_PLANT_SIZE
    ):
        print("[edit step 2] record has no stored Step 2 data - topping up")
        add_land_proposal_page.fill_technical_team(WIND_PROJECT_DATA)
    else:
        print("[edit step 2] using stored Step 2 data as-is")
    add_land_proposal_page.click_step2_save()
    step2_message = add_land_proposal_page.assert_step2_saved()
    print(f"[edit step 2] {step2_message}")

    # 10. Step 3 - same top-up-only-if-empty policy.
    if add_land_proposal_page.field_is_empty(
        add_land_proposal_page.CF_BASIC_COST_SALE
    ):
        print("[edit step 3] record has no stored Step 3 data - topping up")
        add_land_proposal_page.fill_commercial_financial(WIND_PROJECT_DATA)
    else:
        print("[edit step 3] using stored Step 3 data as-is")
    add_land_proposal_page.click_step3_save()
    step3_message = add_land_proposal_page.assert_step3_saved()
    print(f"[edit step 3] {step3_message}")

    # 11. Back on the list - and the total count must be UNCHANGED.
    #     This is the core "do not create a new land record" guarantee.
    assert land_proposals_page.is_loaded(), (
        "Did not return to the Land Proposals List after the Step 3 save"
    )
    total_after = land_proposals_page.total_entries()
    print(f"[entries after] {total_after}")
    assert total_after == total_before, (
        "A new land record was created by the EDIT flow! "
        f"Entries before={total_before}, after={total_after}"
    )
@pytest.mark.smoke
@pytest.mark.e2e
def test_view_existing_land_proposal(page):
    """
    READ-ONLY "View" flow - the third row action of the Land Proposals
    list (View / Edit / Convert to Project / Send Approval).

    Deliberate difference from the two flows above: it must prove NOTHING
    is written. It never opens the wizard and never submits a form; it
    asserts both that the record's stored values are what is displayed
    and that the page offers no way to change them.

    Steps:
      1-5. Login -> OTP -> Renewable -> Proceed -> Land Proposals list
           (same journey as the create/edit flows); capture total entries.
      6.   Row action menu -> View. The href the item targets is
           remembered.
      7.   The URL must be that same .../land-banks/<uuid> - NOT /edit.
           (The View page does not render the proposal name, so the uuid
           is what proves the correct record opened.)
      8.   Heading "View Land Proposal" plus the three sections: Land Bank
           Details (Step 1 data), Engineering Team Details (Step 2) and
           BD Team Details (Step 3).
      9.   The record's stored values are on screen. Numbers are compared
           as numbers - the page pads them ("50.0000000000").
      10.  READ-ONLY: zero input/select/textarea elements, zero
           type="submit" controls, no visible write action at all.
      11.  "Back to List" -> the Land Proposals list with an UNCHANGED
           total-entry count (viewing writes nothing).
    """
    # 1. Login
    login_page = LoginPage(page).open(BASE_URL)
    login_page.login(LOGIN_EMAIL, LOGIN_PASSWORD)

    # 2. OTP
    OtpPage(page).enter_otp(OTP)

    # 3 & 4. Select Renewable, then Proceed
    industry_page = IndustrySelectionPage(page)
    industry_page.select_industry(INDUSTRY)
    industry_page.confirm_proceed()

    dashboard_page = DashboardPage(page)
    assert dashboard_page.is_loaded(), "Dashboard did not load after clicking Proceed"

    # 5. Land Identification / Proposal list + baseline record count
    dashboard_page.go_to_land_identification()
    land_proposals_page = LandProposalsPage(page)
    assert land_proposals_page.is_loaded(), "Land Proposals List page did not load"
    total_before = land_proposals_page.total_entries()
    print(f"\n[view] entries before: {total_before}")

    # 6. Row action menu -> View (never "Add New Land Proposal")
    view_href = land_proposals_page.click_view_existing(
        WIND_PROJECT_DATA["proposal_name"]
    )
    print(f"[view] menu item href: {view_href}")

    # 7. The right record, in READ-ONLY form
    view_page = ViewLandProposalPage(page)
    assert view_page.is_loaded(), (
        'The View page did not load (no "View Land Proposal" heading)'
    )
    assert not re.search(r"/edit", page.url), (
        f"View landed on an EDIT url: {page.url}"
    )
    assert page.url.rstrip("/") == view_href.rstrip("/"), (
        "View opened a different record than its menu item links to: "
        f"{page.url} != {view_href}"
    )
    print(f"[view] url: {page.url}")

    # 8. The three sections of stored data
    for section in ViewLandProposalPage.SECTIONS:
        assert view_page.has_section(section), (
            f"The View page is missing the {section!r} section"
        )

    # 9. Stored values (the record was created with WIND_PROJECT_DATA)
    data = WIND_PROJECT_DATA
    assert view_page.detail(ViewLandProposalPage.STATE) == data["state"]
    assert view_page.detail(ViewLandProposalPage.LAND_TYPE) == data["land_type"]
    assert view_page.detail(ViewLandProposalPage.COMPANY) == data["company"]
    assert view_page.detail(ViewLandProposalPage.PROJECT_TYPE) == data["project_type"]
    assert view_page.detail(ViewLandProposalPage.SITE_VISIT_DATE) == \
        data["site_visit_date"]
    assert view_page.detail_number(ViewLandProposalPage.PLANT_SIZE) == \
        pytest.approx(float(data["plant_size_mw"]))
    assert view_page.detail_number(ViewLandProposalPage.DC_FEASIBLE) == \
        pytest.approx(float(data["dc_feasible"]))
    assert view_page.detail_number(ViewLandProposalPage.BASIC_COST_SALE) == \
        pytest.approx(float(data["basic_cost_sale"]))
    assert view_page.detail_number(ViewLandProposalPage.LEASE_TENURE) == \
        pytest.approx(float(data["lease_tenure_years"]))
    assert view_page.detail_number(
        ViewLandProposalPage.TARIFF_DUE_TO_THIS_LAND
    ) == pytest.approx(float(data["tariff_due_to_this_land"]))
    print("[view] stored values shown: state "
          f"{view_page.detail(ViewLandProposalPage.STATE)!r}, plant size "
          f"{view_page.detail(ViewLandProposalPage.PLANT_SIZE)!r}, basic cost "
          f"{view_page.detail(ViewLandProposalPage.BASIC_COST_SALE)!r}")

    # 10. READ-ONLY - the whole point of the page
    assert view_page.form_control_count() == 0, (
        "The View page exposes form controls - it is not read-only: "
        f"{view_page.form_control_count()} input/select/textarea element(s)"
    )
    assert view_page.submit_control_count() == 0, (
        "The View page declares a submit control"
    )
    assert not view_page.has_write_action(), (
        f"The View page offers a write action: {view_page.visible_action_texts()}"
    )
    assert "Back to List" in view_page.visible_action_texts(), (
        "The View page has no way back to the list"
    )

    # 11. Back to the list - nothing was created or changed.
    view_page.back_to_list()
    assert land_proposals_page.is_loaded(), (
        'The "Back to List" link did not return to the Land Proposals List'
    )
    total_after = land_proposals_page.total_entries()
    print(f"[view] entries after: {total_after}")
    assert total_after == total_before, (
        "Viewing a record changed the Land Proposals list! "
        f"Entries before={total_before}, after={total_after}"
    )

