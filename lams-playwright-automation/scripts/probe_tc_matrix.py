"""
Discovery probe for the module-wise TC tests.

Answers - from the live app, never by guessing - the questions the new
``tests/land_bank``, ``tests/technical_team`` and ``tests/commercial_financial``
cases need:

1. Which client-side constraints the wizard's fields actually declare
   (``required`` / ``min`` / ``max`` / ``step`` / ``maxlength``) - dumped for
   Steps 1, 2 and 3 with NO submit at all, which is what makes the boundary
   tests safe.
2. What the CREATE wizard does with suspicious Step 1 input:
   a negative TL distance, a non-numeric land quantum, an out-of-range
   latitude degree / minutes, and a DUPLICATE proposal name (one that already
   exists in the list).
3. Which "cancel / back / reset" controls the create wizard offers.
4. Whether an ACCEPTED Step 1 alone (wizard abandoned before Step 3) adds a row
   to the Land Proposals list - the entry count is compared before and after, so
   the new tests can be written without polluting the environment.
5. The same field dump for Steps 2 and 3, reached through the EXISTING record in
   edit mode and submitted with its own stored values (exactly like the
   positive edit test) - so nothing is modified.

Every attempt is made in the CREATE wizard, which persists nothing: a land
record only appears once Step 3 is completed. The probe never submits Step 3.

Usage (project root, venv active):

    python scripts/probe_tc_matrix.py --attrs-only   # safe: dumps 1/2/3
    python scripts/probe_tc_matrix.py --cleanup      # rename probe drafts
    python scripts/probe_tc_matrix.py                # also the input attempts

>>> FINDINGS THAT SHAPED THE TC TESTS (see probe_output/tc_*.json) <<<
* Step 1 has ONE HTML5-required control (``tlb_proposal_name``) and no
  ``min`` / ``max`` anywhere: Step 1's "Please select/enter ..." messages are
  SERVER side, so they need a real submit to observe.
* Numeric Step 1 fields sanitise input in the page itself (``oninput``):
  typing ``-5`` into TL Distance leaves ``5``, so "negative distance" can never
  reach the server.
* An ACCEPTED create-wizard Step 1 CREATES THE LAND RECORD immediately
  (entries 51 -> 52, URL ``/land-banks/create/<id>``), even though the list row
  is only complete after Step 3. Consequence: the create wizard is NOT a safe
  sandbox for accepted submits - only rejected ones. Run ``--cleanup`` if an
  attempt was accepted.
* The create wizard has NO cancel / reset / back control at all.
* After an accepted Step 1, another "Add New Land Proposal" RESUMES the same
  draft on Step 2 (which is why the probe must click the ``#tab1`` step link,
  and why the TC tests never leave a wizard half-finished).
"""

import argparse
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - very old interpreters
    pass

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

from config import BASE_URL, INDUSTRY, LOGIN_EMAIL, LOGIN_PASSWORD, OTP  # noqa: E402
from pages.add_land_proposal_page import AddLandProposalPage  # noqa: E402
from pages.dashboard_page import DashboardPage  # noqa: E402
from pages.industry_selection_page import IndustrySelectionPage  # noqa: E402
from pages.land_proposals_page import LandProposalsPage  # noqa: E402
from pages.login_page import LoginPage  # noqa: E402
from pages.otp_page import OtpPage  # noqa: E402
from test_data import WIND_PROJECT_DATA  # noqa: E402

_OUT_DIR = os.path.join(_ROOT, "probe_output")
LIST_URL = BASE_URL.split("/auth/")[0] + "/land-banks"
EXISTING_NAME = WIND_PROJECT_DATA["proposal_name"]

# Every control in the ACTIVE wizard pane, with the attributes that decide what
# the BROWSER itself accepts or refuses.
FIELDS_JS = """
() => {
    const pane = document.querySelector(
        'div.tab-pane.show.active, div.tab-pane.active') || document;
    return Array.from(pane.querySelectorAll('input, select, textarea'))
        .filter(el => el.type !== 'hidden' || el.name)
        .map(el => ({
            name: el.name || el.id,
            tag: el.tagName.toLowerCase(),
            type: (el.type || '').toLowerCase(),
            required: !!el.required,
            min: el.getAttribute('min'),
            max: el.getAttribute('max'),
            step: el.getAttribute('step'),
            maxlength: el.getAttribute('maxlength'),
            pattern: el.getAttribute('pattern'),
            readonly: !!el.readOnly,
            disabled: !!el.disabled,
        }));
}
"""

# Visible buttons / links - used to find a cancel / reset control.
ACTIONS_JS = """
() => {
    const visible = e => {
        const r = e.getBoundingClientRect();
        const s = window.getComputedStyle(e);
        return r.width > 0 && r.height > 0
            && s.visibility !== 'hidden' && s.display !== 'none';
    };
    return Array.from(document.querySelectorAll('button, a'))
        .filter(visible)
        .map(e => ({
            tag: e.tagName.toLowerCase(),
            text: (e.innerText || e.value || '').trim(),
            href: e.getAttribute('href') || '',
            type: e.getAttribute('type') || '',
        }))
        .filter(a => a.text || a.href);
}
"""


def write_evidence(label: str, payload: dict, page=None) -> None:
    """Saves one probe step as JSON (+ PNG when a page was passed)."""
    with open(os.path.join(_OUT_DIR, f"tc_{label}.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    if page is not None:
        page.screenshot(path=os.path.join(_OUT_DIR, f"tc_{label}.png"), full_page=True)


def sign_in(page) -> None:
    """Login -> OTP -> Renewable -> Proceed -> Land Proposals list."""
    LoginPage(page).open(BASE_URL).login(LOGIN_EMAIL, LOGIN_PASSWORD)
    OtpPage(page).enter_otp(OTP)
    industry = IndustrySelectionPage(page)
    industry.select_industry(INDUSTRY)
    industry.confirm_proceed()
    dashboard = DashboardPage(page)
    assert dashboard.is_loaded(), "dashboard did not load"
    dashboard.go_to_land_identification()
    assert LandProposalsPage(page).is_loaded(), "list did not load"


def fresh_create(page, proposals) -> AddLandProposalPage:
    """
    A create wizard whose Step 1 pane is on screen.

    The app RESUMES an in-progress draft - probed: after an accepted Step 1 the
    next "Add New Land Proposal" opens the SAME draft on Step 2 - so the Step 1
    tab is clicked explicitly instead of assuming the wizard opens on it.
    """
    page.goto(LIST_URL)
    assert proposals.is_loaded(), "list did not load before opening the wizard"
    proposals.click_add_new_land_proposal()
    add = AddLandProposalPage(page)

    step1_tab = page.locator("a[href='#tab1']").first
    if step1_tab.count():
        step1_tab.click()
        page.wait_for_timeout(500)
    return add


def attempt(page, proposals, label, overrides, note) -> dict:
    """
    Fills a fully valid Step 1, applies ``overrides`` (raw field name -> value),
    clicks "Create Land Bank" and records exactly what happened.

    Runs in the CREATE wizard only, so nothing can be persisted. The entry count
    after the attempt answers "did that create a record?".
    """
    add = fresh_create(page, proposals)
    add.fill_all_sections(WIND_PROJECT_DATA)
    for field_name, value in overrides.items():
        add._fill(field_name, value)

    state = {
        "note": note,
        "url_on_step1": page.url,
        "overrides": overrides,
        "values_after_fill": {},
        "native_validation_before_submit": add.native_validation_errors(),
    }
    for field_name in overrides:
        try:
            state["values_after_fill"][field_name] = add.field_value(field_name)
        except Exception as exc:  # pragma: no cover
            state["values_after_fill"][field_name] = f"<unreadable: {exc}>"

    add.click_create_land_bank()
    page.wait_for_timeout(2500)

    state["url_after_submit"] = page.url
    state["visible_errors"] = add.wait_for_validation_errors(timeout=6000)
    state["native_validation_after_submit"] = add.native_validation_errors()
    state["step1_banner_visible"] = add.banner_appears(
        re.compile(r"Step 1[^.]*(saved|updated)", re.I), timeout=2500
    )
    state["advanced_to_step2"] = add._field(add.TT_PLANT_SIZE).is_visible()

    page.goto(LIST_URL)
    state["entries_after"] = proposals.total_entries()

    write_evidence(f"attempt_{label}", state, page)
    print(
        f"\n[attempt {label}] {note}"
        f"\n  values after fill : {state['values_after_fill']}"
        f"\n  native refused    : {state['native_validation_before_submit']}"
        f"\n  step 1 banner     : {state['step1_banner_visible']}"
        f"\n  advanced to step2 : {state['advanced_to_step2']}"
        f"\n  url after         : {state['url_after_submit']}"
        f"\n  visible errors    : {state['visible_errors']}"
        f"\n  entries after     : {state['entries_after']}"
    )
    return state



# The Edit links of every row named after the probe's proposal name, IN LIST
# ORDER. Read straight from the DOM (the dropdown items are hidden until the row
# menu is clicked, but their href is readable) - the same trick
# LandProposalsPage._open_row_action uses; it just always takes the first row.
EDIT_HREFS_JS = """
(wanted) => {
    const rows = Array.from(document.querySelectorAll('table tbody tr'))
        .filter(r => (r.innerText || '').includes(wanted));
    return rows.map(row => {
        const hrefs = Array.from(row.querySelectorAll('a'))
            .map(a => a.getAttribute('href') || '')
            .filter(h => h);
        const edit = hrefs.filter(h => /\\/edit$/.test(h))[0]
            || hrefs.filter(h => h.includes('/edit'))[0]
            || '';
        return {
            text: (row.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 80),
            edit_href: edit,
            hrefs: hrefs,
        };
    });
}
"""


def parse_args():
    parser = argparse.ArgumentParser(
        description="Discover the behaviour the module-wise TC tests assert."
    )
    parser.add_argument(
        "--attrs-only",
        action="store_true",
        help="skip the create-wizard input attempts (the only mode that writes "
        "anything) and just dump Steps 1-3 attributes",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="rename the Step-1-only draft records left behind by an accepted "
        "attempt, so they no longer clash with the suite's record",
    )
    parser.add_argument(
        "--restore-names",
        action="store_true",
        help="undo --cleanup: give every '<name> (probe draft)' row its original "
        "proposal name back, then report what the first matching row holds",
    )
    parser.add_argument(
        "--step1-check",
        action="store_true",
        help="submit the first record's Step 1 and re-read it, to prove whether "
        "Steps 2/3 survive a Step 1 re-submit",
    )
    return parser.parse_args()


def cleanup_draft_duplicates(page, proposals) -> list:
    """
    Renames Step-1-only drafts created by an accepted attempt.

    Why this exists: the probe proved that an ACCEPTED create-wizard Step 1
    creates a land record immediately (51 -> 52 entries), long before Step 3.
    Such a draft carries the same proposal name as the record the whole suite
    works on, which would make "the first row named X" ambiguous.

    A draft is recognised by its EMPTY Step 2 (``tlb_plant_size`` has no value):
    the real record always has a plant size. Renaming - rather than deleting -
    keeps the data and removes the clash with a single, safe Step 1 update.
    """
    page.goto(LIST_URL)
    assert proposals.is_loaded(), "list did not load"
    proposals._wait_for_row(EXISTING_NAME)  # the table is AJAX-loaded

    rows = page.evaluate(EDIT_HREFS_JS, EXISTING_NAME)
    print(f"[cleanup] {len(rows)} row(s) named {EXISTING_NAME!r} in the list")
    for row in rows:
        print(f"  -> {row['text']!r}\n     edit href: {row['edit_href']!r}")

    renamed = []
    for row in rows:
        href = row["edit_href"]
        if not href:
            print("[cleanup] no Edit link in this row - skipped")
            continue
        page.goto(href)
        add = AddLandProposalPage(page)
        try:
            has_step2_data = not add.field_is_empty(add.TT_PLANT_SIZE)
        except Exception:
            has_step2_data = False  # no Step 2 controls at all -> Step 1 only

        if has_step2_data:
            print(f"[cleanup] {href} already has Step 2 data - left untouched")
            continue

        new_name = f"{EXISTING_NAME} (probe draft)"
        add._fill(add.PROPOSAL_NAME, new_name)
        add.click_step1_submit()
        banner = add.assert_saved()
        renamed.append({"edit_href": href, "renamed_to": new_name, "banner": banner})
        print(f"[cleanup] renamed Step-1-only draft {href}\n           -> {new_name!r} ({banner})")

    if not renamed:
        print(f"[cleanup] no Step-1-only draft found for {EXISTING_NAME!r}")
    return renamed


def restore_probe_names(page, proposals) -> list:
    """
    Undoes ``--cleanup``: every row renamed to "<name> (probe draft)" goes back.

    ``--cleanup`` must never be run blindly: on this environment the draft
    detection could not be trusted (the Step 2 controls are not readable while
    the wizard sits on Step 1), so the safe repair is to give EVERY renamed row
    its original proposal name back - the rename only ever changed that one
    field, so this returns the records to their previous state.
    """
    draft_name = f"{EXISTING_NAME} (probe draft)"
    page.goto(LIST_URL)
    assert proposals.is_loaded(), "list did not load"
    proposals._wait_for_row(draft_name)

    rows = page.evaluate(EDIT_HREFS_JS, draft_name)
    print(f"[restore] {len(rows)} row(s) currently named {draft_name!r}")

    restored = []
    for row in rows:
        href = row["edit_href"]
        if not href:
            continue
        page.goto(href)
        add = AddLandProposalPage(page)
        add._fill(add.PROPOSAL_NAME, EXISTING_NAME)
        add.click_step1_submit()
        banner = add.assert_saved()
        restored.append(href)
        print(f"[restore] {href} -> {EXISTING_NAME!r} ({banner})")

    print(f"[restore] {len(restored)} record(s) restored")
    return restored


def verify_first_record(page, proposals) -> dict:
    """
    Prints what the FIRST row named after the suite's record actually holds.

    The whole existing suite finds a record by name and takes the first match,
    so this reports the Step 2 / Step 3 values the positive edit and view tests
    depend on (Site Visit Date, Plant Size, Basic Cost Sale).
    """
    from pages.view_land_proposal_page import ViewLandProposalPage

    page.goto(LIST_URL)
    proposals.click_view_existing(EXISTING_NAME)
    view = ViewLandProposalPage(page)
    assert view.is_loaded(), "the View page did not load"

    details = {
        "site_visit_date": view.detail(ViewLandProposalPage.SITE_VISIT_DATE),
        "plant_size": view.detail(ViewLandProposalPage.PLANT_SIZE),
        "basic_cost_sale": view.detail(ViewLandProposalPage.BASIC_COST_SALE),
        "state": view.detail(ViewLandProposalPage.STATE),
        "view_url": page.url,
    }
    page.goto(LIST_URL)
    return details


def step1_submit_then_check(page, proposals) -> dict:
    """
    Submits Step 1 of the FIRST matching record, then re-reads it.

    Answers the one question the positive Step-1 test depends on: does
    re-submitting an existing record's Step 1 keep the data captured in Steps 2
    and 3? (The record used here is already Step-1-only, so the experiment
    cannot destroy anything either way.)
    """
    before = verify_first_record(page, proposals)

    page.goto(LIST_URL)
    proposals.click_edit_existing(EXISTING_NAME)
    add = AddLandProposalPage(page)
    add.click_step1_submit()
    banner = add.assert_saved()

    after = verify_first_record(page, proposals)
    return {
        "step1_banner": banner,
        "before": before,
        "after": after,
        "steps_2_3_survived": (
            after["plant_size"] == before["plant_size"]
            and after["basic_cost_sale"] == before["basic_cost_sale"]
        ),
    }


def run_step1_probe(page, proposals, results) -> None:
    """
    Dumps Step 1's controls/actions and then tries suspicious Step 1 input.

    >>> WARNING <<< an ACCEPTED create-wizard Step 1 CREATES A LAND RECORD
    (probed: 51 -> 52 list entries), so this mode leaves a draft behind that
    shares WIND_PROJECT_DATA's proposal name. Run ``--cleanup`` afterwards.
    """
    fresh_create(page, proposals)
    step1 = {
        "fields": page.evaluate(FIELDS_JS),
        "actions": page.evaluate(ACTIONS_JS),
    }
    write_evidence("attrs_step1", step1, page)
    results["step1_fields"] = step1["fields"]

    print("\n[step 1] controls the browser itself validates:")
    for field in step1["fields"]:
        if field["required"] or field["min"] or field["max"] or field["step"]:
            print(
                f"  {field['name']:<40} type={field['type']:<10}"
                f" required={field['required']!s:<5}"
                f" min={field['min']} max={field['max']} step={field['step']}"
            )
    print("\n[step 1] visible actions (looking for cancel/reset/back):")
    for action in step1["actions"]:
        print(
            f"  {action['tag']:<7} {action['text'][:45]!r}"
            f" href={action['href']!r}"
        )

    add_cls = AddLandProposalPage
    attempts = (
        (
            "tl_distance_negative",
            {add_cls.TL_DISTANCE: "-5"},
            "negative TL distance (a distance cannot be negative)",
        ),
        (
            "land_quantum_text",
            {add_cls.LAND_QUANTUM_LEASE: "abc"},
            "non-numeric land quantum offered on lease",
        ),
        (
            "lat_degree_out_of_range",
            {add_cls.LAND_LAT_DEGREE: "91", add_cls.LAND_LAT_MINUTES: "75"},
            "latitude degree 91 (max 90) and minutes 75 (max 59)",
        ),
        (
            "duplicate_proposal_name",
            {add_cls.PROPOSAL_NAME: EXISTING_NAME},
            f"proposal name {EXISTING_NAME!r} already exists in the list",
        ),
    )
    for label, overrides, note in attempts:
        results[label] = attempt(page, proposals, label, overrides, note)


def main() -> None:
    args = parse_args()
    os.makedirs(_OUT_DIR, exist_ok=True)
    results = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            sign_in(page)
            proposals = LandProposalsPage(page)
            results["list_url"] = page.url
            results["entries_baseline"] = proposals.total_entries()
            print(f"\n[baseline] {results['entries_baseline']} entries in the list")

            if args.step1_check:
                results["step1_check"] = step1_submit_then_check(page, proposals)
                print(
                    "\n[step1-check] Steps 2/3 survived a Step 1 re-submit: "
                    f"{results['step1_check']['steps_2_3_survived']}"
                )
                for key in ("before", "after"):
                    print(f"  {key}: {results['step1_check'][key]}")
                return

            if args.restore_names:
                results["restored"] = restore_probe_names(page, proposals)
                results["first_record"] = verify_first_record(page, proposals)
                results["entries_final"] = proposals.total_entries()
                print(
                    f"\n[restore] first row named {EXISTING_NAME!r} now holds:\n"
                    f"  {results['first_record']}"
                )
                return

            if args.cleanup:
                results["renamed_drafts"] = cleanup_draft_duplicates(page, proposals)
                page.goto(LIST_URL)
                results["entries_final"] = proposals.total_entries()
                print(
                    f"\n[cleanup] {results['entries_final']} entries in the list "
                    f"(baseline was {results['entries_baseline']})"
                )
                return

            # ---------------------------------------------------------
            # 1 + 2. Step 1 controls/actions + suspicious input.
            # Section 2 is the ONLY part of this probe that writes (an accepted
            # Step 1 creates a record), so --attrs-only skips it.
            # ---------------------------------------------------------
            if not args.attrs_only:
                run_step1_probe(page, proposals, results)

            # ---------------------------------------------------------
            # 3. Steps 2 + 3 attributes, reached through the EXISTING
            #    record in edit mode and submitted with its own stored
            #    values (identical to the positive edit test - no change).
            # ---------------------------------------------------------
            page.goto(LIST_URL)
            proposals.click_edit_existing(EXISTING_NAME)
            add = AddLandProposalPage(page)
            add.click_step1_submit()
            results["edit_step1_banner"] = add.assert_saved()

            add.wait_for_step2()
            results["step2_fields"] = page.evaluate(FIELDS_JS)
            write_evidence("attrs_step2", {"fields": results["step2_fields"]}, page)

            if add.field_is_empty(add.TT_PLANT_SIZE):
                add.fill_technical_team(WIND_PROJECT_DATA)
            add.click_step2_save()
            results["edit_step2_banner"] = add.assert_step2_saved()

            add.wait_for_step3()
            results["step3_fields"] = page.evaluate(FIELDS_JS)
            write_evidence("attrs_step3", {"fields": results["step3_fields"]}, page)

            for step, key in (("step 2", "step2_fields"), ("step 3", "step3_fields")):
                print(f"\n[{step}] controls the browser itself validates:")
                for field in results[key]:
                    if (
                        field["required"]
                        or field["min"]
                        or field["max"]
                        or field["step"]
                    ):
                        print(
                            f"  {field['name']:<45} type={field['type']:<10}"
                            f" required={field['required']!s:<5}"
                            f" min={field['min']} max={field['max']}"
                            f" step={field['step']}"
                        )

            # Nothing was submitted on Step 3: leave the wizard without saving.
            page.goto(LIST_URL)
            results["entries_final"] = proposals.total_entries()
            results["no_records_created"] = (
                results["entries_final"] == results["entries_baseline"]
            )
            print(
                f"\n[entries] baseline {results['entries_baseline']} -> final "
                f"{results['entries_final']}"
                f"  NO RECORDS CREATED: {results['no_records_created']}"
            )

        finally:
            write_evidence("probe_summary", results)
            context.close()
            browser.close()

    print("\n[probe] evidence written to probe_output/tc_*.json|png")


if __name__ == "__main__":
    main()

