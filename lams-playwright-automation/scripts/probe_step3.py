"""
Discovery probe for STEP 3 ("Commercial/Financial Details") of Add New
Land Proposal.

Runs the real flow through the Step 1 and Step 2 saves, then dumps every
visible control of the active Step 3 panel (label, name/id, type, options)
plus raw HTML.

With --save it additionally exercises the Step 3 page-object methods
(fill + Save) and captures whatever the app shows afterwards (success
banner / validation errors / redirect), so wording and validation rules
can be confirmed before running the real pytest suite.

Usage (from project root, venv active):
    python scripts/probe_step3.py           # dump the Step 3 panel only
    python scripts/probe_step3.py --save    # also fill + Save + capture
"""

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
# scripts/ itself, so probe_step2's shared dump JS can be imported.
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
# Shared dump scripts from the Step 2 probe (import runs no side effects).
from probe_step2 import AFTER_SAVE_JS, DUMP_JS  # noqa: E402

_OUT_DIR = os.path.join(_ROOT, "probe_output")
_DO_SAVE = "--save" in sys.argv


def run():
    os.makedirs(_OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # login -> OTP -> industry -> dashboard -> proposals -> create
        LoginPage(page).open(BASE_URL).login(LOGIN_EMAIL, LOGIN_PASSWORD)
        OtpPage(page).enter_otp(OTP)
        ind = IndustrySelectionPage(page)
        ind.select_industry(INDUSTRY)
        ind.confirm_proceed()
        DashboardPage(page).go_to_land_identification()
        LandProposalsPage(page).click_add_new_land_proposal()

        add = AddLandProposalPage(page)
        add.fill_all_sections(WIND_PROJECT_DATA)
        add.click_create_land_bank()
        print(f"[step1] {add.wait_for_save_success(timeout=20000)}")

        add.fill_technical_team(WIND_PROJECT_DATA)
        add.click_step2_save()
        print(f"[step2] {add.wait_for_step2_save_success(timeout=20000)}")

        page.wait_for_timeout(2000)
        page.screenshot(path=os.path.join(_OUT_DIR, "step3_panel.png"), full_page=True)

        data = page.evaluate(DUMP_JS)
        with open(os.path.join(_OUT_DIR, "step3_dump.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        with open(os.path.join(_OUT_DIR, "step3_page.html"), "w", encoding="utf-8") as f:
            f.write(page.content())

        print(f"\n[controls] {len(data['controls'])}")
        print(f"[buttons] {[b['text'] for b in data['buttons']]}")
        for c in data["controls"]:
            print(
                f"  - {c['tag']:6} name={c['name']!r} id={c['id']!r} "
                f"type={c['type']!r} label={c['label']!r} "
                f"req={c['required']} ro={c['readonly']} "
                f"opts={[o['text'] for o in (c.get('options') or [])]}"
            )

        if not _DO_SAVE:
            browser.close()
            print(f"\nDumped to {_OUT_DIR}")
            return

        # --save: exercise the real page-object Step 3 methods.
        if not hasattr(add, "fill_commercial_financial"):
            print("\n[--save] Step 3 page-object methods not implemented yet - "
                  "run the dump first, implement them, then re-run with --save.")
            browser.close()
            return

        add.fill_commercial_financial(WIND_PROJECT_DATA)
        try:
            add.click_step3_save()
            print("\n[step3] Save clicked")
        except Exception as exc:
            print(f"\n[step3] Save click failed: {exc}")

        after = {}
        for delay in (2000, 3000, 5000):
            page.wait_for_timeout(delay)
            after = page.evaluate(AFTER_SAVE_JS)
            print(f"\n[after save +{delay}ms]")
            print(json.dumps(after, indent=2, ensure_ascii=False))

        page.screenshot(path=os.path.join(_OUT_DIR, "after_step3_save.png"), full_page=True)
        with open(os.path.join(_OUT_DIR, "after_step3_save.json"), "w", encoding="utf-8") as f:
            json.dump(after, f, indent=2, ensure_ascii=False)
        with open(os.path.join(_OUT_DIR, "after_step3_save.html"), "w", encoding="utf-8") as f:
            f.write(page.content())

        browser.close()
    print(f"\nDumped to {_OUT_DIR}")


if __name__ == "__main__":
    run()
