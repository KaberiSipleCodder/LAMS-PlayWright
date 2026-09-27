"""
Discovery probe for NEGATIVE (rejection) behaviour across every step we
have automated: Login -> OTP -> Step 1 (create) -> Steps 1/2/3 (edit).

Captures the real validation messages + URLs for:
  * blank login / wrong password
  * blank OTP / wrong OTP
  * Step 1 empty submit, missing document variant, variant without file
  * Edit Step 1 cleared proposal name
  * Edit Step 2 all-empty + non-integer Shape Index + out-of-range Ease
  * Edit Step 3 all-empty + non-numeric tariff / basic cost

Also counts list entries at every checkpoint to prove which actions do
(NOT) create records.

Usage (project root, venv active):
    python scripts/probe_negative.py
"""

import json
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
from probe_step2 import AFTER_SAVE_JS  # noqa: E402
from probe_edit import _summarize  # noqa: E402

_OUT_DIR = os.path.join(_ROOT, "probe_output")
LIST_URL = BASE_URL.split("/auth/")[0] + "/land-banks"


def capture(page, label, js=AFTER_SAVE_JS):
    state = page.evaluate(js)
    base = os.path.join(_OUT_DIR, f"neg_{label}")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    with open(base + ".html", "w", encoding="utf-8") as f:
        f.write(page.content())
    page.screenshot(path=base + ".png", full_page=True)
    _summarize(label, state)
    return state


def bad(state):
    """Filtered validation messages from an AFTER_SAVE_JS state."""
    return [
        i["text"] for i in state.get("invalid", [])
        if i["text"] not in ("*", "")
        and not re.search(r"saved|success|created|complete", i["text"], re.I)
    ]


def where(url) -> str:
    if "edit-step3" in url:
        return "step3"
    if "edit-step2" in url:
        return "step2"
    if url.rstrip("/").endswith("/edit"):
        return "step1-edit"
    if url.rstrip("/").endswith("/land-banks"):
        return "list"
    if "/create" in url:
        return "create"
    return "other"


def click_sign_in(page, password):
    LoginPage(page).open(BASE_URL)
    page.locator("input[type='text']").first.fill(LOGIN_EMAIL)
    page.locator("input[type='password']").fill(password)
    page.get_by_role("button", name="Sign In").click()


def verify_otp(page, code):
    boxes = page.locator("input.auth-input.numeral-mask[maxlength='1']")
    for i in range(6):
        boxes.nth(i).fill(code[i])
        boxes.nth(i).dispatch_event("keyup")
    page.get_by_role("button", name="Verify my account").click()


def run():
    os.makedirs(_OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # ---------- auth negatives ----------
        click_sign_in(page, "WrongPass123!")
        page.wait_for_timeout(2500)
        capture(page, "login_wrong_password")
        print("[login] url after wrong password:", page.url)

        # correct credentials on the still-open login page
        page.locator("input[type='text']").first.fill(LOGIN_EMAIL)
        page.locator("input[type='password']").fill(LOGIN_PASSWORD)
        page.get_by_role("button", name="Sign In").click()
        page.wait_for_url("**/validate-otp*", timeout=15000)

        page.get_by_role("button", name="Verify my account").click()
        page.wait_for_timeout(2000)
        capture(page, "otp_blank")
        print("[otp] url after BLANK verify:", page.url)

        verify_otp(page, "999999")
        page.wait_for_timeout(2500)
        capture(page, "otp_wrong")
        print("[otp] url after WRONG otp:", page.url)

        OtpPage(page).enter_otp(OTP)
        ind = IndustrySelectionPage(page)
        ind.select_industry(INDUSTRY)
        ind.confirm_proceed()
        DashboardPage(page).go_to_land_identification()
        lp = LandProposalsPage(page)
        assert lp.is_loaded()
        e0 = lp.total_entries()
        print(f"[entries baseline] {e0}")

        # ---------- create-mode negatives ----------
        with page.expect_navigation(
            url=re.compile(r".*/land-banks/create/")
        ):
            lp.add_new_button.click()
        add = AddLandProposalPage(page)
        print("[create] url:", page.url, "->", where(page.url))

        # 1) completely empty submit
        add.click_create_land_bank()
        page.wait_for_timeout(3000)
        s = capture(page, "create_empty_submit")
        print("[create empty] errors:", bad(s), "| at:", where(page.url))

        # 2) all valid but NO document variant (file also absent)
        no_var = dict(WIND_PROJECT_DATA)
        no_var["document_variant"] = None
        no_var["document_file_path"] = None
        add.fill_all_sections(no_var)
        add.click_create_land_bank()
        page.wait_for_timeout(3000)
        s = capture(page, "create_no_variant")
        print("[create no-variant] errors:", bad(s), "| at:", where(page.url))

        # 3) variant set but still NO file upload
        add._select(
            AddLandProposalPage.DOCUMENT_VARIANT_SEL,
            WIND_PROJECT_DATA["document_variant"],
            name_is_selector=True,
        )
        add.click_create_land_bank()
        page.wait_for_timeout(3000)
        s = capture(page, "create_no_file")
        print("[create no-file] errors:", bad(s), "| at:", where(page.url))

        # abandon - never passed validation, so no save; count entries
        page.goto(LIST_URL)
        lp.is_loaded()
        e1 = lp.total_entries()
        print(f"[entries after abandoned create attempts] {e1} (was {e0})")

        # ---------- edit-mode negatives ----------
        lp.click_edit_existing(WIND_PROJECT_DATA["proposal_name"])
        add = AddLandProposalPage(page)
        print("[edit] at:", where(page.url))

        # 4) cleared proposal name -> step 1 must reject
        add.clear_field(add.PROPOSAL_NAME)
        add.click_step1_submit()
        page.wait_for_timeout(3000)
        s = capture(page, "edit_step1_no_name")
        print("[edit no-name] errors:", bad(s), "| at:", where(page.url))

        # restore name and advance
        add.fill_land_bank_details(WIND_PROJECT_DATA)
        add.click_step1_submit()
        page.wait_for_timeout(3000)
        print("[edit step1 retry] at:", where(page.url))

        # 5) step 2 fully cleared -> reject
        add.clear_step2_fields()
        add.click_step2_save()
        page.wait_for_timeout(3000)
        s = capture(page, "edit_step2_empty")
        print("[edit s2 empty] errors:", bad(s), "| at:", where(page.url))

        # 6) step 2 valid except non-integer Shape Index
        bad_shape = dict(WIND_PROJECT_DATA)
        bad_shape["shape_index"] = "0.5"
        add.fill_technical_team(bad_shape)
        add.click_step2_save()
        page.wait_for_timeout(3000)
        s = capture(page, "edit_step2_bad_shape")
        print("[edit s2 shape=0.5] errors:", bad(s), "| at:", where(page.url))

        # 7) step 2 valid except out-of-range Ease (0-10) = 99
        bad_ease = dict(WIND_PROJECT_DATA)
        bad_ease["ease_of_acquisition"] = "99"
        add.fill_technical_team(bad_ease)
        add.click_step2_save()
        page.wait_for_timeout(3000)
        s = capture(page, "edit_step2_ease_99")
        print("[edit s2 ease=99] errors:", bad(s), "| at:", where(page.url))

        # restore step 2 and advance
        add.fill_technical_team(WIND_PROJECT_DATA)
        add.click_step2_save()
        page.wait_for_timeout(3000)
        print("[edit step2 retry] at:", where(page.url))

        # 8-10) step 3 negatives
        if where(page.url) == "step3":
            add.clear_step3_fields()
            add.click_step3_save()
            page.wait_for_timeout(3500)
            s = capture(page, "edit_step3_empty")
            print("[edit s3 empty] errors:", bad(s), "| at:", where(page.url))

            bad_tariff = dict(WIND_PROJECT_DATA)
            bad_tariff["tariff_due_to_this_land"] = "abc"
            add.fill_commercial_financial(bad_tariff)
            add.click_step3_save()
            page.wait_for_timeout(3500)
            s = capture(page, "edit_step3_tariff_abc")
            print("[edit s3 tariff=abc] errors:", bad(s),
                  "| at:", where(page.url))

            bad_cost = dict(WIND_PROJECT_DATA)
            bad_cost["basic_cost_sale"] = "abc"
            add.fill_commercial_financial(bad_cost)
            add.click_step3_save()
            page.wait_for_timeout(3500)
            s = capture(page, "edit_step3_cost_abc")
            print("[edit s3 cost=abc] errors:", bad(s),
                  "| at:", where(page.url))

            # restore and finish cleanly (record left as it was)
            add.fill_commercial_financial(WIND_PROJECT_DATA)
            add.click_step3_save()
            page.wait_for_timeout(4000)
            print("[edit step3 retry] at:", where(page.url))
        else:
            print("[edit] DID NOT reach step3 - s3 negatives skipped:",
                  where(page.url))

        try:
            page.wait_for_url(re.compile(r".*/land-banks(/|\?|$)"), timeout=8000)
        except Exception:
            pass
        page.goto(LIST_URL)
        lp.is_loaded()
        e2 = lp.total_entries()
        print(f"[entries final] {e2} (baseline {e0}) -> "
              + ("NO RECORDS CREATED" if e2 == e0 else "RECORD COUNT CHANGED!"))

        browser.close()
    print(f"\nDumped to {_OUT_DIR}")


if __name__ == "__main__":
    run()
