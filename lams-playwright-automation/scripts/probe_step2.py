"""
Discovery probe for STEP 2 ("Technical Team") of Add New Land Proposal.

Runs the real flow up to and including the Step 1 save, dumps every
visible control of the Step 2 panel, fills + saves Step 2, then dumps
whatever confirmation (or validation errors) the page shows afterwards.

Usage (from project root, venv active):
    python scripts/probe_step2.py
"""

import json
import os
import sys

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

# Everything textual on the page: alerts, toasts, headings, buttons -
# whatever the app shows after the Step 2 Save click.
AFTER_SAVE_JS = """
() => {
    const visible = e => {
        const r = e.getBoundingClientRect();
        const s = window.getComputedStyle(e);
        return r.width > 0 && r.height > 0
            && s.visibility !== 'hidden' && s.display !== 'none';
    };
    const texts = sel => Array.from(document.querySelectorAll(sel))
        .filter(visible)
        .map(e => ({sel: e.tagName + '.' + e.className, text: e.innerText.trim()}))
        .filter(t => t.text);
    return {
        alerts: texts('.alert, .notyf, .toast, [class*=toast], [class*=notyf], [class*=notification]'),
        headings: texts('h1,h2,h3,h4,h5,h6'),
        buttons: texts('button, a.btn, input[type=submit]'),
        activeStep: texts('.active, li.active, .nav-link.active, [class*=active]')
            .filter(t => /Land Bank|Technical|Commercial/i.test(t.text)),
        invalid: texts('.invalid-feedback, .error, .text-danger, [class*=invalid], [class*=error]'),
        url: location.href,
    };
}
"""


DUMP_JS = """
() => {
    const visible = e => {
        const r = e.getBoundingClientRect();
        const s = window.getComputedStyle(e);
        return r.width > 0 && r.height > 0
            && s.visibility !== 'hidden' && s.display !== 'none';
    };
    const labelText = el => {
        if (el.id) {
            const lab = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
            if (lab) return lab.textContent.trim();
        }
        const parent = el.closest('.form-group, .col, .mb-3, div');
        const lab = parent && parent.querySelector('label');
        return lab ? lab.textContent.trim() : '';
    };
    const controls = Array.from(
        document.querySelectorAll('input, select, textarea')
    ).filter(visible).map(el => ({
        tag: el.tagName.toLowerCase(),
        type: el.type || '',
        name: el.name || '',
        id: el.id || '',
        placeholder: el.placeholder || '',
        label: labelText(el),
        required: !!el.required || el.getAttribute('aria-required') === 'true',
        disabled: !!el.disabled,
        readonly: !!el.readOnly,
        classes: el.className || '',
        options: el.tagName === 'SELECT'
            ? Array.from(el.options).map(o => ({text: o.text.trim(), value: o.value}))
            : undefined,
        value: el.tagName === 'SELECT' ? el.value : (el.value || ''),
    }));
    const buttons = Array.from(
        document.querySelectorAll('button, a.btn, input[type=submit]')
    ).filter(visible)
     .map(b => ({text: (b.innerText || b.value || '').trim(), classes: b.className || ''}));
    const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'))
        .filter(visible)
        .map(h => h.textContent.trim());
    const stepper = Array.from(document.querySelectorAll(
        '.wizard-stepper li, .steps li, [class*=step] li, .breadcrumb-item, li.step'
    )).map(s => ({text: s.innerText.trim(), classes: s.className}));
    return {controls, buttons, headings, stepper};
}
"""


def run():
    os.makedirs(_OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # --- login -> OTP -> industry -> dashboard -> proposals -> create ---
        LoginPage(page).open(BASE_URL).login(LOGIN_EMAIL, LOGIN_PASSWORD)
        OtpPage(page).enter_otp(OTP)
        ind = IndustrySelectionPage(page)
        ind.select_industry(INDUSTRY)
        ind.confirm_proceed()
        DashboardPage(page).go_to_land_identification()
        LandProposalsPage(page).click_add_new_land_proposal()

        # --- Step 1 ---
        add = AddLandProposalPage(page)
        add.fill_all_sections(WIND_PROJECT_DATA)
        add.click_create_land_bank()
        try:
            msg = add.wait_for_save_success(timeout=20000)
            print(f"[step1] {msg}")
        except Exception as exc:
            print(f"[step1] no success banner: {exc}")

        page.wait_for_timeout(3000)
        page.screenshot(path=os.path.join(_OUT_DIR, "after_step1.png"), full_page=True)

        # Try clicking the "Technical Team" stepper entry so the Step 2 panel
        # is definitely the active one before dumping.
        for sel in (
            page.get_by_text("Technical Team", exact=False),
            page.locator("li", has_text="Technical Team"),
        ):
            try:
                sel.first.click(timeout=3000)
                page.wait_for_timeout(1000)
                break
            except Exception:
                continue

        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(_OUT_DIR, "step2_panel.png"), full_page=True)

        data = page.evaluate(DUMP_JS)
        with open(os.path.join(_OUT_DIR, "step2_dump.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        with open(os.path.join(_OUT_DIR, "step2_page.html"), "w", encoding="utf-8") as f:
            f.write(page.content())

        print(f"\n[controls] {len(data['controls'])}")
        print(f"[buttons] {[b['text'] for b in data['buttons']]}")
        print(f"[headings] {data['headings']}")
        for c in data["controls"]:
            print(
                f"  - {c['tag']:6} name={c['name']!r} id={c['id']!r} "
                f"label={c['label']!r} req={c['required']} "
                f"opts={len(c.get('options') or [])}"
            )

        # ---- fill + save Step 2 and capture what the app says ----
        add.fill_technical_team(WIND_PROJECT_DATA)
        try:
            add.click_step2_save()
            print("\n[step2] Save clicked")
        except Exception as exc:
            print(f"\n[step2] Save click failed: {exc}")

        for delay in (2000, 3000, 5000):
            page.wait_for_timeout(delay)
            after = page.evaluate(AFTER_SAVE_JS)
            print(f"\n[after save +{delay}ms]")
            print(json.dumps(after, indent=2, ensure_ascii=False))

        page.screenshot(path=os.path.join(_OUT_DIR, "after_step2_save.png"), full_page=True)
        with open(os.path.join(_OUT_DIR, "after_step2_save.json"), "w", encoding="utf-8") as f:
            json.dump(after, f, indent=2, ensure_ascii=False)
        with open(os.path.join(_OUT_DIR, "after_step2_save.html"), "w", encoding="utf-8") as f:
            f.write(page.content())

        browser.close()
    print(f"\nDumped to {_OUT_DIR}")


if __name__ == "__main__":
    run()
