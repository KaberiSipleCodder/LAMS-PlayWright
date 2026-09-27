"""
COMMERCIAL/FINANCIAL DETAILS (wizard Step 3) - NEGATIVE test cases.

TC22 - text where the Basic Cost Sale amount belongs must be rejected;
       the app's numeric sanitiser empties the box, so the server answers
       with "The Basic Cost Sale field is required."
TC23 - the same for the Tariff due to this land:
       "The Tariff due to this land field is required."

Both tests then prove nothing was written: no final banner, the url stays
on .../edit-step3 and a reload shows the stored value exactly as before
(the other 15 Step 3 fields were filled with valid data, so a partial
persist would be visible here).

Evidence (probe_output/):
  * neg_edit_step3_cost_abc.json   -> ["The Basic Cost Sale field is
        required."], no alert, url still .../edit-step3.
  * neg_edit_step3_tariff_abc.json -> ["The Tariff due to this land field
        is required."], same shape.
  * tc_attrs_step3.json -> Step 3 has NO HTML5 required attributes, so
        these messages can only come from the server.

Run just these:   pytest tests/commercial_financial -m negative
"""

import re

import pytest

from test_data import WIND_PROJECT_DATA
from tests.wizard_steps import advance_to

pytestmark = [pytest.mark.negative, pytest.mark.commercial_financial]

#: The final confirmation that must NOT appear after a rejected save.
BANNER_FINAL = re.compile(r"Land Bank (created|updated) successfully", re.I)

BASIC_COST_REQUIRED = "The Basic Cost Sale field is required."
TARIFF_REQUIRED = "The Tariff due to this land field is required."


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def has_message(messages, expected: str) -> bool:
    """True when the whole discovered sentence is on screen (case/space
    tolerant, like tests/test_negative.py)."""
    wanted = _normalize(expected)
    return any(wanted in _normalize(message) for message in messages)


def _assert_step3_rejects(lams, overrides: dict, expected: str) -> None:
    """
    Fills Step 3 with valid data plus ``overrides``, submits, and proves
    the server refused the value: the exact message is on screen, the
    final banner is not, the wizard stays on Step 3, and a reload shows
    the stored value unchanged.
    """
    page = lams.page
    add = advance_to(lams, 3)
    stored_before = add.field_value(add.CF_BASIC_COST_SALE)

    add.fill_commercial_financial(dict(WIND_PROJECT_DATA, **overrides))
    add.click_step3_save()

    messages = add.wait_for_validation_errors(timeout=10000)
    assert has_message(messages, expected), (
        f"Step 3 did not reject the value with {expected!r}: {messages}"
    )
    assert not add.banner_appears(BANNER_FINAL), (
        f"The final save succeeded despite {expected!r}"
    )
    assert "edit-step3" in page.url, (
        f"The rejected submit left Step 3 (url={page.url})"
    )

    # .../edit-step3 reloads onto the Step 3 pane, so wait for the
    # control itself (attached) instead of for Step 1 to be visible.
    page.reload()
    page.locator(f'[name="{add.CF_BASIC_COST_SALE}"]').wait_for(
        state="attached", timeout=15000
    )
    stored_after = add.field_value(add.CF_BASIC_COST_SALE)
    assert stored_after == stored_before, (
        "The rejected final save changed the stored Basic Cost Sale: "
        f"{stored_before!r} -> {stored_after!r}"
    )
    print(f"\n[TC] {expected!r} rejected; stored {stored_before!r} intact")


@pytest.mark.tc_id("TC22")
def test_TC22_non_numeric_basic_cost_sale_is_rejected(lams_list):
    """``basic_cost_sale = "abc"`` must be refused with the server's own
    "The Basic Cost Sale field is required." message (see module doc)."""
    _assert_step3_rejects(
        lams_list, {"basic_cost_sale": "abc"}, BASIC_COST_REQUIRED
    )


@pytest.mark.tc_id("TC23")
def test_TC23_non_numeric_tariff_is_rejected(lams_list):
    """``tariff_due_to_this_land = "abc"`` must be refused with the
    server's own "The Tariff due to this land field is required."."""
    _assert_step3_rejects(
        lams_list, {"tariff_due_to_this_land": "abc"}, TARIFF_REQUIRED
    )
