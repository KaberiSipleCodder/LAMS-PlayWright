"""
LAND BANK DETAILS (wizard Step 1) - NEGATIVE test cases.

TC16 - a cleared required co-ordinate is refused by the SERVER with
       "Please enter latitude degree"; the wizard stays on Step 1, shows no
       success banner and the stored value survives a reload.
TC17 - a negative TL distance can never even be typed: the field's own
       oninput sanitiser rewrites "-5" into "5" before anything is sent.

Evidence (probe_output/):
  * tc_step1_lat_cleared.json -> errors ["Please enter latitude degree"],
        success banner False, url still .../edit, latitude degree "22"
        before and after the reload (scripts/probe_tc_values.py).
  * neg_create_empty_submit.json -> the server's Step 1 message list,
        including "Please enter latitude degree".
  * tc_attempt_tl_distance_negative.json -> typing "-5" leaves the value
        "5" (native_validation_before_submit: [], then the submit is
        accepted as a positive distance).

Run just these:   pytest tests/land_bank -m negative
"""

import re

import pytest

from test_data import WIND_PROJECT_DATA

pytestmark = [pytest.mark.negative, pytest.mark.land_bank]

BANNER_STEP1 = re.compile(r"Step 1[^.]*(saved|updated)", re.I)
LAT_DEGREE_REQUIRED = "Please enter latitude degree"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def has_message(messages, expected: str) -> bool:
    """True when the whole discovered sentence is on screen (case/space
    tolerant, like tests/test_negative.py)."""
    wanted = _normalize(expected)
    return any(wanted in _normalize(message) for message in messages)


def _open_step1(lams):
    add = lams.open_existing_record(WIND_PROJECT_DATA["proposal_name"])
    add.page.locator(f'[name="{add.PROPOSAL_NAME}"]').wait_for(
        state="visible", timeout=15000
    )
    return add


@pytest.mark.tc_id("TC16")
def test_TC16_cleared_latitude_degree_is_rejected(lams_list):
    """
    Clearing the land Latitude Degree and submitting Step 1 must be
    refused server-side with "Please enter latitude degree" - no success
    banner, still on the Step 1 edit page, and the stored value is intact
    after a reload (a rejected submit never persists).
    """
    lams = lams_list
    page = lams.page
    add = _open_step1(lams)

    stored = add.field_value(add.LAND_LAT_DEGREE)
    assert stored, "The record has no stored land Latitude Degree to restore"

    add.clear_field(add.LAND_LAT_DEGREE)
    assert add.field_is_empty(add.LAND_LAT_DEGREE), (
        "The Latitude Degree could not be cleared"
    )

    add.click_step1_submit()
    messages = add.wait_for_validation_errors(timeout=12000)
    assert has_message(messages, LAT_DEGREE_REQUIRED), (
        f"Cleared Latitude Degree was not rejected with "
        f"{LAT_DEGREE_REQUIRED!r}: {messages}"
    )
    assert not add.banner_appears(BANNER_STEP1, timeout=4000), (
        "Step 1 reported success even though the co-ordinate was missing"
    )
    assert "/edit" in page.url and "edit-step" not in page.url, (
        f"The rejected submit left Step 1 (url={page.url})"
    )

    page.reload()
    add.page.locator(f'[name="{add.PROPOSAL_NAME}"]').wait_for(
        state="visible", timeout=15000
    )
    assert add.field_value(add.LAND_LAT_DEGREE) == stored, (
        "The rejected submit changed the stored Latitude Degree: "
        f"{stored!r} -> {add.field_value(add.LAND_LAT_DEGREE)!r}"
    )
    print(f"\n[TC16] {LAT_DEGREE_REQUIRED!r}; stored {stored!r} intact")


@pytest.mark.tc_id("TC17")
def test_TC17_negative_tl_distance_cannot_be_typed(lams_list):
    """
    A distance cannot be negative, and the form never even lets one be
    entered: filling "-5" leaves the value "5" (Step 1's oninput
    sanitiser), so a negative distance can never reach the server.
    Nothing is submitted - the reload proves the stored value is untouched.
    """
    lams = lams_list
    page = lams.page
    add = _open_step1(lams)

    stored = add.field_value(add.TL_DISTANCE)
    distance = page.locator(f'[name="{add.TL_DISTANCE}"]')

    distance.fill("-5")
    page.wait_for_timeout(300)
    typed = add.field_value(add.TL_DISTANCE)
    assert typed == "5", (
        f"-5 TL distance was accepted as-is: the field holds {typed!r}"
    )
    assert not typed.startswith("-"), (
        f"A negative distance is still in the field: {typed!r}"
    )

    page.reload()
    add.page.locator(f'[name="{add.PROPOSAL_NAME}"]').wait_for(
        state="visible", timeout=15000
    )
    assert add.field_value(add.TL_DISTANCE) == stored, (
        "The un-submitted form changed the stored TL distance: "
        f"{stored!r} -> {add.field_value(add.TL_DISTANCE)!r}"
    )
    print(f"\n[TC17] '-5' was sanitised to {typed!r}; stored {stored!r} intact")
