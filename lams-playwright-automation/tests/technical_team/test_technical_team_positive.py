"""
TECHNICAL TEAM (wizard Step 2) - POSITIVE test cases.

TC18 - valid Technical Team data is saved: the form confirms the step,
       the wizard opens Step 3 (stepper "3 BD Team Details", url
       .../edit-step3) and no record is created.

Evidence (probe_output/):
  * tc_probe_summary.json -> "edit_step2_banner":
        "Step 2 saved. Proceed to Step 3."
        (edit mode also answers "Step 2 updated. Proceed to Step 3." -
        see neg_edit_step2_ease_99.json, so the banner check accepts both)
  * probe_output/tc_values.log -> after the save pane "tab3" is active and
        Step 3's 19 controls are rendered (tc_attrs_step3.json).
  * tc_attrs_step2.json -> Step 2's fields carry HTML5 required
        attributes, so the record is topped up only when it predates
        Step 2 data.

Run just this module:   pytest tests/technical_team -m technical_team
"""

import re

import pytest

from test_data import WIND_PROJECT_DATA
from tests.wizard_steps import advance_to, save_step2

pytestmark = [pytest.mark.positive, pytest.mark.technical_team]

BANNER_STEP2 = re.compile(r"Step 2[^.]*(saved|updated)", re.I)


@pytest.mark.tc_id("TC18")
def test_TC18_valid_technical_team_details_are_saved(lams_list):
    """
    Saving the Technical Team step must be confirmed by the form, open
    Step 3 (Commercial/Financial Details) and leave the record count
    untouched - an edit-mode save updates, it never creates.
    """
    lams = lams_list
    entries_before = lams.proposals.total_entries()

    add = advance_to(lams, 2)
    if add.field_is_empty(add.TT_PLANT_SIZE):
        add.fill_technical_team(WIND_PROJECT_DATA)

    banner = save_step2(add)
    assert BANNER_STEP2.search(banner), (
        f"Step 2 was not confirmed with its own banner: {banner!r}"
    )
    assert not add.visible_validation_errors(), (
        f"Step 2 saved with validation errors on screen: "
        f"{add.visible_validation_errors()}"
    )

    # The wizard must hand over to Step 3 (BD Team / Commercial-Financial).
    add.wait_for_step3(timeout=20000)
    assert "edit-step3" in add.page.url, (
        f"The wizard did not move on to Step 3 (url={add.page.url})"
    )

    lams.back_to_list()
    entries_after = lams.proposals.total_entries()
    assert entries_after == entries_before, (
        "A Step 2 edit save created a new record: "
        f"{entries_before} -> {entries_after}"
    )
    print(f"\n[TC18] {banner!r}; entries {entries_before} -> {entries_after}")
