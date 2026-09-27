"""
Discovery probe for EDITING an EXISTING land proposal (NO new record).

Walks: Land Proposals list -> open an existing row's edit view -> re-save
Steps 1-3 with the known-good WIND_PROJECT_DATA (fields arrive prefilled)
-> back to the list. Dumps every stage so edit-mode button labels,
success wording, and the list's total-entry indicator (proof that no new
record was created) can be confirmed before writing the real test.

Usage (project root, venv active):
    python scripts/probe_edit.py
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
from probe_step2 import AFTER_SAVE_JS, DUMP_JS  # noqa: E402

_OUT_DIR = os.path.join(_ROOT, "probe_output")

LIST_JS = """
() => {
    const visible = e => {
        const r = e.getBoundingClientRect();
        const s = window.getComputedStyle(e);
        return r.width > 0 && r.height > 0
            && s.visibility !== 'hidden' && s.display !== 'none';
    };
    const rows = Array.from(document.querySelectorAll('table tbody tr'))
        .filter(visible)
        .map(tr => tr.innerText.replace(/\\s+/g, ' ').trim());
    const actions = Array.from(
        document.querySelectorAll('table tbody a, table tbody button')
    ).map(el => ({
        text: (el.innerText || '').trim(),
        title: el.getAttribute('title') || '',
        href: el.getAttribute('href') || '',
        cls: typeof el.className === 'string' ? el.className : '',
    }));
    const info = Array.from(document.querySelectorAll(
        '[class*="info"], [class*="entries"], [class*="length"]'
    )).filter(visible)
      .map(e => e.innerText.replace(/\\s+/g, ' ').trim())
      .filter(t => /showing|entries|of\\s*\\d+/i.test(t));
    const buttons = Array.from(document.querySelectorAll('button, a.btn'))
        .filter(visible)
        .map(b => ({text: (b.innerText || '').trim(), cls: b.className}));
    return {rows, actions, info, buttons, url: location.href};
}
"""


def capture(page, label, js):
    state = page.evaluate(js)
    base = os.path.join(_OUT_DIR, f"edit_{label}")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    with open(base + ".html", "w", encoding="utf-8") as f:
        f.write(page.content())
    page.screenshot(path=base + ".png", full_page=True)
    _summarize(label, state)
    return state


def _summarize(label, state):
    if "rows" in state:
        print(f"[{label}] url={state.get('url', '')} rows={len(state['rows'])} "
              f"info={state['info']}")
        for r in state["rows"][:6]:
            print("    row:", r[:140])
        return
    if "controls" in state:  # DUMP_JS shape (no url/alerts keys)
        print(f"[{label}] controls={len(state['controls'])} "
              f"buttons={[b['text'] for b in state['buttons']]} "
              f"headings={state['headings']}")
        return
    print(f"[{label}] url={state.get('url', '(n/a)')}")
    print("    alerts:", [a["text"] for a in state.get("alerts", [])])
    print("    buttons:", [b["text"] for b in state.get("buttons", [])])
    print("    active:", [t["text"] for t in state.get("activeStep", [])])
    bad = [i["text"] for i in state.get("invalid", [])
           if i["text"] not in ("*", "")
           and not re.search(r"saved|success|created|complete", i["text"], re.I)]
    print("    invalid:", bad)


def _on_wizard(page) -> bool:
    """True on BOTH the create ("Add New...") and edit ("Edit New...")
    wizard pages - they share the h4.approval-process heading suffix."""
    try:
        page.locator(
            "h4.approval-process", has_text="New Land Proposal Details"
        ).wait_for(state="visible", timeout=2500)
        return True
    except Exception:
        return False


def open_edit(page) -> str:
    """
    Opens the FIRST row for the known proposal name via its action menu.

    Row actions (View / Edit / Convert to Project / Send Approval) live
    inside a Bootstrap dropdown: the items exist in the DOM but stay
    hidden until the row's dropdown-toggle button is clicked. Edit hrefs
    look like .../land-banks/<uuid>/edit.
    """
    name = WIND_PROJECT_DATA["proposal_name"]
    # The list is AJAX-loaded: tbody first shows a "Loading..." placeholder
    # row, so wait until the real row (or at least a finished table) exists.
    try:
        page.wait_for_function(
            """(wanted) => {
                const rows = Array.from(document.querySelectorAll('table tbody tr'));
                if (!rows.length) return false;
                const text = rows.map(r => r.innerText).join('\\n');
                if (/loading/i.test(text) && rows.length <= 1) return false;
                return rows.some(r => r.innerText.includes(wanted));
            }""",
            arg=name,
            timeout=20000,
        )
    except Exception as exc:
        print(f"[edit] row wait failed: {exc}")

    row = page.locator("table tbody tr", has_text=name).first
    try:
        row.wait_for(state="visible", timeout=8000)
    except Exception:
        row = page.locator("table tbody tr").first
        row.wait_for(state="visible", timeout=8000)

    try:
        # Read the Edit href BEFORE opening the menu: the theme re-parents
        # the .dropdown-menu (portal-style) once opened, so row-scoped
        # locators stop matching it afterwards.
        href = row.locator(
            'a.dropdown-item[href*="/edit"]'
        ).first.get_attribute("href")

        # 1) open this row's action dropdown (UI-realistic path)
        row.locator("button.dropdown-toggle").first.click()
        page.wait_for_timeout(600)

        # 2) exactly one Edit anchor is visible now (the open menu's) - the
        #    other 24 rows' copies are hidden.
        try:
            edit_item = page.locator(
                'a.dropdown-item[href*="/edit"]:visible'
            ).first
            with page.expect_navigation(timeout=5000):
                edit_item.click()
        except Exception as nav_exc:
            print(f"[edit] visible-menu click failed ({nav_exc}); goto href")
            page.goto(href)
        page.wait_for_timeout(1500)
        if _on_wizard(page):
            return "row dropdown -> Edit"
    except Exception as exc:
        print(f"[edit] dropdown edit failed: {exc}")
    return ""


def run():
    os.makedirs(_OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # login -> OTP -> industry -> dashboard -> proposals list
        LoginPage(page).open(BASE_URL).login(LOGIN_EMAIL, LOGIN_PASSWORD)
        OtpPage(page).enter_otp(OTP)
        ind = IndustrySelectionPage(page)
        ind.select_industry(INDUSTRY)
        ind.confirm_proceed()
        DashboardPage(page).go_to_land_identification()
        # Wait for the AJAX table to finish its first render before the
        # "before" snapshot - otherwise we just capture "Loading...".
        try:
            page.wait_for_function(
                """() => {
                    const rows = Array.from(
                        document.querySelectorAll('table tbody tr'));
                    if (!rows.length) return false;
                    const text = rows.map(r => r.innerText).join('\\n');
                    return !/^loading/i.test(text.trim());
                }""",
                timeout=20000,
            )
        except Exception as exc:
            print(f"[list] table wait failed: {exc}")
        page.wait_for_timeout(1000)
        before = capture(page, "list_before", LIST_JS)

        # open an EXISTING record - never clicks "Add New Land Proposal"
        sel = open_edit(page)
        print(f"[edit] opened with selector: {sel!r}")
        if not _on_wizard(page):
            capture(page, "not_wizard", DUMP_JS)
            browser.close()
            print(f"\nNever reached the wizard - see edit_not_wizard.* in {_OUT_DIR}")
            return

        add = AddLandProposalPage(page)
        s1 = capture(page, "edit_step1", DUMP_JS)
        print("    prefill:", {c["name"]: c["value"] for c in s1["controls"]})

        def stage(label, fn, wait_ms, cap_label, cap_js):
            try:
                fn()
            except Exception as exc:
                print(f"[{label}] error: {exc}")
            page.wait_for_timeout(wait_ms)
            capture(page, cap_label, cap_js)

        def visible_names():
            return {c["name"] for c in page.evaluate(DUMP_JS)["controls"]}

        def try_advance(to_step_label, step_text):
            # If the next step's fields are not on screen yet, try the two
            # plausible advance mechanisms: the wizard stepper text, then
            # the 'Next' button.
            if to_step_label in visible_names():
                return
            for how in ("stepper", "next-button"):
                try:
                    if how == "stepper":
                        page.get_by_text(step_text, exact=False).first.click(
                            timeout=3000
                        )
                    else:
                        page.get_by_role(
                            "button", name="Next"
                        ).first.click(timeout=3000)
                except Exception as exc:
                    print(f"[advance {how}] {exc}")
                page.wait_for_timeout(1500)
                capture(page, f"advance_{how}", DUMP_JS)
                if to_step_label in visible_names():
                    return

        # SAVE ONLY - do not refill: the whole point is exercising the
        # record's EXISTING data.
        stage("save1", add.click_step1_submit, 3500, "after_step1", AFTER_SAVE_JS)

        try_advance("tlbet_plant_size", "Technical Team")
        stage("save2", add.click_step2_save, 3500, "after_step2", AFTER_SAVE_JS)

        try_advance("tlbbt_land_basic_cost_sale", "Commercial/Financial Details")
        stage("save3", add.click_step3_save, 4500, "after_step3", AFTER_SAVE_JS)

        try:
            page.wait_for_url(re.compile(r".*/land-banks(/|\?|$)"), timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(2500)
        capture(page, "list_after", LIST_JS)

        browser.close()
    print(f"\nDumped to {_OUT_DIR}")


if __name__ == "__main__":
    run()
