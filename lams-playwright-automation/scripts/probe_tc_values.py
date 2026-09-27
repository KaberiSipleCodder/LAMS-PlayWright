"""
Targeted diagnostic for two open questions left by ``probe_tc_matrix.py``:

1. Does Step 2's own oninput sanitiser neutralise a negative number
   (Plant Size "-5") the way Step 1 neutralises "-5" TL distance?
   (FILLED ONLY, never submitted -> no state change at all.)
2. After a valid Step 2 save the app answers "Step 2 saved. Proceed to
   Step 3." yet ``wait_for_step3()`` timed out - which pane/tab is
   actually active, and what has to be clicked for Step 3 to show?
   When Step 3 does show, its controls are dumped to
   ``probe_output/tc_attrs_step3.json`` (read-only; Step 3 is NEVER
   submitted by this script).

Usage:  python scripts/probe_tc_values.py
"""

import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright  # noqa: E402

from config import BASE_URL, INDUSTRY, LOGIN_EMAIL, LOGIN_PASSWORD, OTP  # noqa: E402
from pages.add_land_proposal_page import AddLandProposalPage  # noqa: E402
from pages.dashboard_page import DashboardPage  # noqa: E402
from pages.industry_selection_page import IndustrySelectionPage  # noqa: E402
from pages.land_proposals_page import LandProposalsPage  # noqa: E402
from pages.login_page import LoginPage  # noqa: E402
from pages.otp_page import OtpPage  # noqa: E402
from test_data import WIND_PROJECT_DATA  # noqa: E402
from probe_tc_matrix import (  # noqa: E402
    EXISTING_NAME,
    FIELDS_JS,
    write_evidence,
)

_OUT_DIR = os.path.join(_ROOT, "probe_output")

#: What the wizard looks like right now - tabs, panes, Step 3's first field.
DIAGNOSE_JS = """
() => {
    const field = document.querySelector('[name="tlbbt_land_basic_cost_sale"]');
    const paneOf = field ? field.closest('.tab-pane') : null;
    const rect = field ? field.getBoundingClientRect() : null;
    return {
        url: location.href,
        navs: [...document.querySelectorAll('a.nav-link, a[href^="#tab"]')]
            .map(a => ({
                text: (a.innerText || '').trim().replace(/\\s+/g, ' '),
                href: a.getAttribute('href'),
                cls: a.className,
            })),
        panes: [...document.querySelectorAll('.tab-pane')]
            .map(p => ({id: p.id, cls: p.className})),
        cf_field: field ? {
            exists: true,
            visible: !!(rect && rect.width > 0 && rect.height > 0),
            pane_id: paneOf ? paneOf.id : null,
        } : {exists: false},
        errors: [...document.querySelectorAll('.invalid-feedback, .text-danger')]
            .map(e => (e.innerText || '').trim()).filter(Boolean),
        alerts: [...document.querySelectorAll('.alert')]
            .map(a => (a.innerText || '').trim()).filter(Boolean),
    };
}
"""



def main() -> int:
    os.makedirs(_OUT_DIR, exist_ok=True)
    sys.stdout.reconfigure(line_buffering=True)
    result = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        LoginPage(page).open(BASE_URL).login(LOGIN_EMAIL, LOGIN_PASSWORD)
        OtpPage(page).enter_otp(OTP)
        industry = IndustrySelectionPage(page)
        industry.select_industry(INDUSTRY)
        industry.confirm_proceed()
        DashboardPage(page).go_to_land_identification()

        proposals = LandProposalsPage(page)
        assert proposals.is_loaded(), "Land Proposals List did not load"
        proposals.click_edit_existing(EXISTING_NAME)

        add = AddLandProposalPage(page)

        # --- Step 1 (stored values as-is) -> Step 2 -------------------
        add.click_step1_submit()
        result["step1_banner"] = add.assert_saved()
        add.wait_for_step2()

        # (1) negative Plant Size, FILLED ONLY - never submitted.
        add._fill(add.TT_PLANT_SIZE, "-5")
        page.wait_for_timeout(400)
        result["plant_size_after_typing_negative"] = add.field_value(add.TT_PLANT_SIZE)

        # (2) valid Step 2 data, then save (the top-up the suite does).
        add.fill_technical_team(WIND_PROJECT_DATA)
        result["plant_size_before_save"] = add.field_value(add.TT_PLANT_SIZE)
        add.click_step2_save()
        try:
            result["step2_banner"] = add.wait_for_step2_save_success(timeout=20000)
        except Exception as exc:  # noqa: BLE001 - probe: capture why, keep going
            result["step2_banner"] = None
            result["step2_banner_error"] = str(exc).splitlines()[0][:200]
            result["step2_native"] = add.native_validation_errors()
            result["step2_server_errors"] = add.visible_validation_errors()
            write_evidence("step2_save_failed", result, page)
            print(f"[step 2] NO BANNER: {result['step2_banner_error']}", flush=True)
            print(f"[step 2] native (browser): {result['step2_native']}", flush=True)
            print(f"[step 2] server: {result['step2_server_errors']}", flush=True)
        page.wait_for_timeout(2500)

        # (2a) What does the wizard look like straight after the save?
        result["after_save"] = page.evaluate(DIAGNOSE_JS)

        # (2b) Try the ways Step 3 could be revealed, cheapest first.
        attempts = []
        if not result["after_save"]["cf_field"]["visible"]:
            steps = (
                ("stepper 'edit-step3'", lambda: page.locator('a[href$="edit-step3"]').first.click(timeout=3000)),
                (
                    "stepper 'BD Team Details'",
                    lambda: page.locator("a.nav-link", has_text="BD Team").first.click(timeout=3000),
                ),
                (
                    "text 'Commercial/Financial Details'",
                    lambda: page.get_by_text("Commercial/Financial Details", exact=False)
                    .first.click(timeout=3000),
                ),
            )
            for how, click in steps:
                try:
                    click()
                    page.wait_for_timeout(2500)
                    state = page.evaluate(DIAGNOSE_JS)
                    attempts.append({"how": how, "cf_visible": state["cf_field"]["visible"]})
                    if state["cf_field"]["visible"]:
                        result["after_click"] = state
                        break
                except Exception as exc:  # noqa: BLE001 - probe: record and move on
                    attempts.append({"how": how, "error": str(exc).splitlines()[0][:200]})
        result["reveal_attempts"] = attempts

        # (3) Step 3 attributes (read-only; Step 3 is never submitted).
        state = page.evaluate(DIAGNOSE_JS)
        result["final_state"] = state
        if state["cf_field"]["visible"]:
            result["step3_fields"] = page.evaluate(FIELDS_JS)
            write_evidence("attrs_step3", {"fields": result["step3_fields"]}, page)
            print(f"[step 3] {len(result['step3_fields'])} control(s) dumped")
        else:
            print("[step 3] NOT reachable - see reveal_attempts / final_state")

        print(f"\n[step 2] plant size typed '-5' -> {result['plant_size_after_typing_negative']!r}")
        print(f"[step 2] banner: {result['step2_banner']!r}")
        print(f"[step 2] alerts after save: {state['alerts']}")
        print(f"[step 2] errors: {state['errors']}")
        for nav in state["navs"]:
            print(f"  nav {nav['href']!r:<12} cls={nav['cls']!r:<40} {nav['text']!r}")
        for pane in state["panes"]:
            print(f"  pane {pane['id']!r:<12} {pane['cls']!r}")

        write_evidence("step3_diag", result, page)

        # (4) Single-field Step 1 rejection: clear the land latitude degree
        # and submit. Rejected => nothing is persisted (state unchanged).
        # Accepted  => the stored value is restored right away.
        page.locator("a.nav-link", has_text="Land Bank Details").first.click()
        page.locator('[name="tlb_proposal_name"]').wait_for(state="visible", timeout=15000)
        before = add.field_value(add.LAND_LAT_DEGREE)
        add.clear_field(add.LAND_LAT_DEGREE)
        result["lat_degree_cleared"] = add.field_value(add.LAND_LAT_DEGREE)
        add.click_step1_submit()
        result["lat_reject_errors"] = add.wait_for_validation_errors(timeout=12000)
        result["lat_reject_banner"] = add.banner_appears(
            re.compile(r"Step 1[^.]*(saved|updated)", re.I), timeout=4000
        )
        result["lat_reject_url"] = page.url
        page.reload()
        page.locator('[name="tlb_proposal_name"]').wait_for(state="visible", timeout=15000)
        result["lat_degree_after_reload"] = add.field_value(add.LAND_LAT_DEGREE)
        result["lat_degree_before"] = before

        if not result["lat_reject_errors"]:
            # Accepted (unexpected): put the stored value back.
            add.clear_field(add.LAND_LAT_DEGREE)
            add._fill(add.LAND_LAT_DEGREE, before)
            add.click_step1_submit()
            add.wait_for_save_success(timeout=15000)
            result["lat_restore"] = "submitted back"

        print(f"\n[step1 lat] cleared -> {result['lat_degree_cleared']!r}")
        print(f"[step1 lat] errors: {result['lat_reject_errors']}")
        print(f"[step1 lat] success banner: {result['lat_reject_banner']}")
        print(f"[step1 lat] url: {result['lat_reject_url']}")
        print(f"[step1 lat] stored before={before!r} "
              f"after reload={result['lat_degree_after_reload']!r}")

        write_evidence("step1_lat_cleared", result, page)
        print(f"\nEvidence written to {_OUT_DIR}")
        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
