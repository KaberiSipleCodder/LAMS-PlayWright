"""
COMMERCIAL/FINANCIAL DETAILS (wizard Step 3) - POSITIVE test case.

TC21 - valid Commercial/Financial Details complete the record: the final
       save is confirmed ("Land Bank updated successfully"), the app
       returns to the Land Proposals list and the entry count is
       unchanged (an edit save updates, it never creates).

Evidence:
  * pages/add_land_proposal_page.py -> edit mode answers "Land Bank
        updated successfully" after navigating to /land-banks (captured by
        scripts/probe_edit.py -> probe_output/edit_after_step3.json and
        probe_output/neg_edit_step3_*.png).
  * README.md / TEST_CASES.md -> Step 3 is the final step: it redirects to
        the list, there is no "Step 3 saved" banner.

Run just this module:   pytest tests/commercial_financial -m commercial_financial
"""

import re

import pytest

from test_data import WIND_PROJECT_DATA
from tests.wizard_steps import advance_to

pytestmark = [pytest.mark.positive, pytest.mark.commercial_financial]

#: The final confirmation (create: "created", edit: "updated").
BANNER_FINAL = re.compile(r"Land Bank (created|updated) successfully", re.I)


@pytest.mark.tc_id("TC21")
def test_TC21_valid_commercial_financial_details_complete_the_record(lams_list):
    """
    Saving Step 3 with valid data must confirm the final save, land the
    user back on the Land Proposals list and leave the record count
    unchanged - the whole point of editing an existing record.
    """
    lams = lams_list
    entries_before = lams.proposals.total_entries()

    add = advance_to(lams, 3)
    if add.field_is_empty(add.CF_BASIC_COST_SALE):
        add.fill_commercial_financial(WIND_PROJECT_DATA)

    add.click_step3_save()
    message = add.assert_step3_saved()
    assert BANNER_FINAL.search(message) or "Redirected" in message, (
        f"The final save was not confirmed: {message!r}"
    )
    assert not add.visible_validation_errors(), (
        f"Step 3 saved with validation errors on screen: "
        f"{add.visible_validation_errors()}"
    )

    assert lams.proposals.is_loaded(), (
        "The final save did not return to the Land Proposals list"
    )
    entries_after = lams.proposals.total_entries()
    assert entries_after == entries_before, (
        "A Step 3 edit save created a new record: "
        f"{entries_before} -> {entries_after}"
    )
    print(f"\n[TC21] {message!r}; entries {entries_before} -> {entries_after}")
