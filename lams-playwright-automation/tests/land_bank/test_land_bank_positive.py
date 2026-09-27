"""
LAND BANK DETAILS (wizard Step 1) - POSITIVE test cases.

TC15 - the stored Land Bank Details are accepted by the edit wizard: the
       form confirms the update, hands over to Step 2 (Technical Team) and
       no record is created.

Evidence (probe_output/, nothing here is guessed):
  * tc_probe_summary.json -> "edit_step1_banner":
        "Step 1 updated. Proceed to Step 2."
  * tc_step1check2.log    -> a Step 1 re-submit keeps Steps 2/3 and the list
        entry count (52 entries before and after).
  * tc_attrs_step1.json   -> tlb_proposal_name is the only HTML5-required
        control on Step 1; everything else is validated by the server.

Run just this module:   pytest tests/land_bank -m land_bank
"""

import re

import pytest

from test_data import WIND_PROJECT_DATA

pytestmark = [pytest.mark.positive, pytest.mark.land_bank]

#: Edit mode answers "Step 1 updated. Proceed to Step 2." (create mode
#: says "saved") - the prefix-locked shape keeps a Step 2/3 banner out.
BANNER_STEP1 = re.compile(r"Step 1[^.]*(saved|updated)", re.I)


@pytest.mark.tc_id("TC15")
def test_TC15_valid_land_bank_details_are_accepted(lams_list):
    """
    Submitting the stored Step 1 values must be confirmed by the form with
    its own Step 1 banner, advance the wizard to the Technical Team step,
    and leave the record count untouched (an edit submit creates nothing).
    """
    lams = lams_list
    entries_before = lams.proposals.total_entries()

    # The edit page must arrive with the stored record prefilled.
    add = lams.open_existing_record(WIND_PROJECT_DATA["proposal_name"])
    prefilled = add.field_value(add.PROPOSAL_NAME)
    assert prefilled == WIND_PROJECT_DATA["proposal_name"], (
        "The edit page did not load the stored record: expected "
        f"{WIND_PROJECT_DATA['proposal_name']!r}, got {prefilled!r}"
    )

    # Step 1 submitted AS-IS (stored values, nothing retyped).
    add.click_step1_submit()
    banner = add.assert_saved()
    assert BANNER_STEP1.search(banner), (
        f"Step 1 was not confirmed with its own banner: {banner!r}"
    )

    # The wizard must hand over to Step 2 (Technical Team).
    add.wait_for_step2(timeout=20000)
    assert add.page.url.endswith("/edit-step2") or "edit-step2" in add.page.url, (
        f"The wizard did not move on to Step 2 (url={add.page.url})"
    )

    # An edit-mode Step 1 submit must never create a record.
    lams.back_to_list()
    entries_after = lams.proposals.total_entries()
    assert entries_after == entries_before, (
        "A Step 1 edit submit created a new record: "
        f"{entries_before} -> {entries_after}"
    )
    print(f"\n[TC15] {banner!r}; entries {entries_before} -> {entries_after}")
