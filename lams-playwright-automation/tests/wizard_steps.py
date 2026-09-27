"""
Shared "walk the edit wizard" helpers for the module-wise tests.

The same two-step journey (Step 1 submit -> Step 2 save -> Step 3) is
needed by the Technical Team and Commercial/Financial modules, so it lives
in one place instead of being copied into every test file.

Imported as ``from tests.wizard_steps import ...`` - the project root is
on sys.path through pytest.ini's ``pythonpath = .``.
"""

from test_data import WIND_PROJECT_DATA


def save_step2(add):
    """
    Clicks Step 2's Save and returns the confirmation banner.

    One retry: the UAT app occasionally drops the first Save (observed by
    scripts/probe_tc_values.py - no banner after 20 s, then a plain
    re-click saved fine), so a single lost request must not fail a test.
    """
    add.click_step2_save()
    try:
        return add.assert_step2_saved()
    except Exception as exc:  # noqa: BLE001 - retry, then fail for real
        print(f"[step 2] no banner after the first Save ({exc}); retrying")
        add.click_step2_save()
        return add.assert_step2_saved()


def advance_to(lams, step: int):
    """
    Opens the existing record and walks the wizard to ``step`` (2 or 3).

    Steps are submitted with the record's STORED data, topped up only when
    that record predates the step - exactly what the positive tests do, so
    the only thing that can fail afterwards is the behaviour under test.
    """
    add = lams.open_existing_record(WIND_PROJECT_DATA["proposal_name"])
    if step >= 2:
        add.click_step1_submit()
        add.assert_saved()
        add.wait_for_step2(timeout=20000)
    if step >= 3:
        if add.field_is_empty(add.TT_PLANT_SIZE):
            add.fill_technical_team(WIND_PROJECT_DATA)
        save_step2(add)
        add.wait_for_step3(timeout=20000)
    return add
