"""
TECHNICAL TEAM (wizard Step 2) - NEGATIVE test cases.

TC19 - a negative Plant Size can never be typed on Step 2 either: the
       field's oninput sanitiser rewrites "-5" into "5" (same guard as
       Step 1's TL distance), and nothing is submitted.
TC20 - a cleared required Plant Size is blocked by the BROWSER, not the
       server: the field carries HTML5 required, so Chrome refuses the
       submit, no banner appears, the url stays on .../edit-step2 and the
       stored value survives a reload.

Evidence (probe_output/):
  * tc_step3_diag.json -> plant size typed "-5" holds "5"
  * tc_attrs_step2.json -> tlbet_plant_size has required=true (Step 2's
        numeric fields carry no min/max, so negatives would otherwise
        reach the server).
  * neg_edit_step2_empty.json -> an empty Step 2 submit produces NO
        app-level error at all (invalid: []) and the url stays on
        /edit-step2: the request never left the browser.

Run just these:   pytest tests/technical_team -m negative
"""

import re

import pytest

from test_data import WIND_PROJECT_DATA
from tests.wizard_steps import advance_to

pytestmark = [pytest.mark.negative, pytest.mark.technical_team]

BANNER_STEP2 = re.compile(r"Step 2[^.]*(saved|updated)", re.I)


@pytest.mark.tc_id("TC19")
def test_TC19_negative_plant_size_is_sanitised_by_the_browser(lams_list):
    """
    Plant Size "50 MW" cannot be negative: filling "-5" must leave the
    value "5", so a negative size can never reach the server. The form is
    not submitted - a reload proves the stored value is untouched.
    """
    lams = lams_list
    page = lams.page
    add = advance_to(lams, 2)

    stored = add.field_value(add.TT_PLANT_SIZE)
    assert stored, "The record has no stored Plant Size to compare against"

    page.locator(f'[name="{add.TT_PLANT_SIZE}"]').fill("-5")
    page.wait_for_timeout(300)
    typed = add.field_value(add.TT_PLANT_SIZE)
    assert typed == "5", (
        f"-5 Plant Size was accepted as-is: the field holds {typed!r}"
    )
    assert not typed.startswith("-"), (
        f"A negative plant size is still in the field: {typed!r}"
    )

    # The url is .../edit-step2, so the reload reopens the STEP 2 pane:
    # wait for the control to be back in the DOM (it is hidden in the
    # Step 1 pane), not for Step 1 to be visible.
    page.reload()
    page.locator(f'[name="{add.TT_PLANT_SIZE}"]').wait_for(
        state="attached", timeout=15000
    )
    assert add.field_value(add.TT_PLANT_SIZE) == stored, (
        "The un-submitted form changed the stored Plant Size: "
        f"{stored!r} -> {add.field_value(add.TT_PLANT_SIZE)!r}"
    )
    print(f"\n[TC19] '-5' was sanitised to {typed!r}; stored {stored!r} intact")


@pytest.mark.tc_id("TC20")
def test_TC20_cleared_plant_size_is_blocked_by_the_browser(lams_list):
    """
    Plant Size is HTML5-required, so clearing it and clicking Save must be
    stopped by the BROWSER: the control reports a validationMessage, the
    request never reaches the server (no banner, no server error), the url
    stays on .../edit-step2 and the stored value is still there on reload.
    """
    lams = lams_list
    page = lams.page
    add = advance_to(lams, 2)

    stored = add.field_value(add.TT_PLANT_SIZE)
    add.clear_field(add.TT_PLANT_SIZE)
    assert add.field_is_empty(add.TT_PLANT_SIZE), (
        "The Plant Size could not be cleared"
    )

    blocked = add.native_validation_errors()
    assert blocked, (
        "The browser considers the empty Plant Size valid - nothing would "
        "stop the submit from reaching the server"
    )
    flagged = [entry["name"] for entry in blocked]
    assert add.TT_PLANT_SIZE in flagged, (
        f"{add.TT_PLANT_SIZE} is not the control the browser flagged: {flagged}"
    )

    add.click_step2_save()
    page.wait_for_timeout(1500)
    assert add.native_validation_blocked(), (
        "After clicking Save the browser no longer flags the empty field"
    )
    assert not add.banner_appears(BANNER_STEP2), (
        "Step 2 accepted a submit with an empty required Plant Size"
    )
    assert "edit-step2" in page.url, (
        f"The browser-blocked submit left the wizard (url={page.url})"
    )
    assert not add.wait_for_validation_errors(timeout=1500), (
        "The browser-blocked submit still reached the server: "
        f"{add.visible_validation_errors()}"
    )

    # .../edit-step2 reloads onto the Step 2 pane, so wait for the
    # control itself (attached) instead of for Step 1 to be visible.
    page.reload()
    page.locator(f'[name="{add.TT_PLANT_SIZE}"]').wait_for(
        state="attached", timeout=15000
    )
    assert add.field_value(add.TT_PLANT_SIZE) == stored, (
        "The blocked submit changed the stored Plant Size: "
        f"{stored!r} -> {add.field_value(add.TT_PLANT_SIZE)!r}"
    )
    print(f"\n[TC20] empty Plant Size blocked by the browser on "
          f"{len(blocked)} control(s); stored {stored!r} intact")
