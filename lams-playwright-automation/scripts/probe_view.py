"""
Discovery probe for the list row action **View** (/land-banks/<uuid>).

Answers, from the live app, the questions the View tests need:
  * what the View menu item's href looks like (vs Edit's .../edit)
  * what the view page renders (heading, tabs, buttons, controls)
  * whether its fields are READ-ONLY (readonly / disabled) and whether any
    submit-capable control exists at all (that is the read-only guarantee)
  * what an UNKNOWN uuid returns (status + landing page)
  * what an UNAUTHENTICATED visit to that URL does (must not show data)
  * that viewing changes nothing on the list (entry count before/after)

Usage (project root, venv active):
    python scripts/probe_view.py
"""

import json
import os
import re
import sys

# The 404 / guard pages contain characters the Windows console codepage
# (cp1252) cannot encode; without this a print() in _summarize() kills the
# probe halfway through.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - very old interpreters
    pass

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright  # noqa: E402

from config import BASE_URL, INDUSTRY, LOGIN_EMAIL, LOGIN_PASSWORD, OTP  # noqa: E402
from pages.dashboard_page import DashboardPage  # noqa: E402
from pages.industry_selection_page import IndustrySelectionPage  # noqa: E402
from pages.login_page import LoginPage  # noqa: E402
from pages.otp_page import OtpPage  # noqa: E402
from test_data import WIND_PROJECT_DATA  # noqa: E402

_OUT_DIR = os.path.join(_ROOT, "probe_output")
LIST_URL = BASE_URL.split("/auth/")[0] + "/land-banks"

# A uuid-shaped id that provably belongs to no record.
UNKNOWN_UUID = "00000000-0000-0000-0000-000000000000"

# Everything the read-only question depends on: controls with their
# readonly/disabled flags, plus any control that could submit the page.
VIEW_JS = """
() => {
    const visible = e => {
        const r = e.getBoundingClientRect();
        const s = window.getComputedStyle(e);
        return r.width > 0 && r.height > 0
            && s.visibility !== 'hidden' && s.display !== 'none';
    };
    const arr = sel => Array.from(document.querySelectorAll(sel));
    const controls = arr('input, select, textarea').map(el => ({
        tag: el.tagName.toLowerCase(),
        type: el.type || '',
        name: el.name || '',
        id: el.id || '',
        value: (el.value || '').toString(),
        readonly: !!el.readOnly,
        disabled: !!el.disabled,
        visible: visible(el),
    }));
    const buttons = arr('button, a.btn, input[type=submit]').map(b => ({
        tag: b.tagName.toLowerCase(),
        type: b.type || '',
        attrType: b.getAttribute('type') || '',
        text: (b.innerText || b.value || '').trim(),
        href: b.getAttribute('href') || '',
        visible: visible(b),
    }));
    // The view page renders its data as .detail-item blocks holding a
    // .detail-label and a .detail-value - capture them as label/value
    // pairs, which is exactly what the assertions read.
    const details = arr('.detail-item').map(item => ({
        label: (item.querySelector('.detail-label') || {}).textContent || '',
        value: ((item.querySelector('.detail-value') || {}).textContent || '')
            .trim(),
    })).filter(d => d.label || d.value);
    return {
        url: location.href,
        title: document.title,
        headings: arr('h1,h2,h3,h4,h5,h6').filter(visible).map(h => h.textContent.trim()),
        details,
        controls,
        buttons,
        forms: arr('form').map(f => ({
            action: f.getAttribute('action') || '',
            method: (f.getAttribute('method') || 'get').toLowerCase(),
        })),
        submitControls: arr(
            'form button[type=submit], form input[type=submit], button[type=submit]'
        ).length,
        tabs: arr('.nav-link, .nav-item, li.active, [class*=step]').filter(visible)
            .map(t => t.innerText.replace(/\\s+/g, ' ').trim()).filter(t => t),
        tables: arr('table').map(t => t.innerText.replace(/\\s+/g, ' ').trim().slice(0, 400)),
        bodyText: (document.body.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 4000),
    };
}
"""

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
        .map(tr => ({
            text: tr.innerText.replace(/\\s+/g, ' ').trim().slice(0, 160),
            hrefs: Array.from(tr.querySelectorAll('a')).map(
                a => (a.getAttribute('href') || '')),
        }));
    const info = Array.from(document.querySelectorAll(
        '[class*="info"], [class*="entries"], [class*="length"]'
    )).filter(visible)
      .map(e => e.innerText.replace(/\\s+/g, ' ').trim())
      .filter(t => /showing|entries|of\\s*\\d+/i.test(t));
    return {url: location.href, rows, info};
}
"""
def capture(page, label, js):
    state = page.evaluate(js)
    base = os.path.join(_OUT_DIR, f"view_{label}")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    with open(base + ".html", "w", encoding="utf-8") as f:
        f.write(page.content())
    page.screenshot(path=base + ".png", full_page=True)
    _summarize(label, state)
    return state


def _summarize(label, state):
    print(f"[{label}] url={state.get('url', '(n/a)')} "
          f"title={state.get('title', '(n/a)')!r}")
    if "headings" in state:
        print("    headings:", state["headings"][:6])
        print("    buttons:", [(b["text"], b["attrType"]) for b in state["buttons"]
                               if b["text"]][:12])
        print("    visible buttons:", [(b["text"], b["attrType"])
                                      for b in state["buttons"]
                                      if b["text"] and b["visible"]])
        print("    forms:", state["forms"], "submitControls:", state["submitControls"])
        print(f"    details={len(state.get('details', []))}",
              [f"{d['label']}={d['value']}" for d in state.get("details", [])[:8]])
        editable = [c for c in state["controls"]
                    if not c["readonly"] and not c["disabled"] and c["visible"]]
        ro = [c for c in state["controls"] if c["readonly"] or c["disabled"]]
        print(f"    controls={len(state['controls'])} readonly/disabled={len(ro)} "
              f"editable+visible={len(editable)}")
        for c in state["controls"][:12]:
            print(f"      {c['tag']}/{c['type']} name={c['name']!r} "
                  f"value={c['value'][:40]!r} readonly={c['readonly']} "
                  f"disabled={c['disabled']} visible={c['visible']}")
        print("    tables:", state["tables"][:1])
        print("    bodyText:", state["bodyText"][:600])
        return
    if "rows" in state:
        print(f"    rows={len(state['rows'])} info={state['info']}")
        for r in state["rows"][:3]:
            print("    row:", r["text"][:120])
            print("      hrefs:", [h for h in r["hrefs"]][:8])
        return
    print("    bodyText:", state.get("bodyText", "")[:600])


def _open_menu_item(page, name, href_must_match):
    """
    Clicks a row action (``name``) for the known proposal and returns the
    href it should have navigated to.

    Same two real-DOM quirks as probe_edit.open_edit(): the table is
    AJAX-loaded, and the row-action items live in a Bootstrap dropdown
    that the theme re-parents once opened - so the href is read BEFORE
    the menu is clicked.
    """
    wanted = WIND_PROJECT_DATA["proposal_name"]
    page.wait_for_function(
        """(wanted) => {
            const rows = Array.from(document.querySelectorAll('table tbody tr'));
            if (!rows.length) return false;
            const text = rows.map(r => r.innerText).join('\\n');
            if (/loading/i.test(text) && rows.length <= 1) return false;
            return rows.some(r => r.innerText.includes(wanted));
        }""",
        arg=wanted,
        timeout=20000,
    )
    row = page.locator("table tbody tr", has_text=wanted).first
    row.wait_for(state="visible", timeout=8000)

    item = row.locator("a.dropdown-item", has_text=name)
    hrefs = [item.nth(i).get_attribute("href") for i in range(item.count())]
    href = next((h for h in hrefs if h and re.search(href_must_match, h)), None)
    print(f"[menu] {name} hrefs in row: {hrefs} -> using {href!r}")

    if not href:
        return None

    try:
        row.locator("button.dropdown-toggle").first.click(timeout=3000)
        page.wait_for_timeout(600)
        page.locator(
            f'a.dropdown-item[href="{href}"]:visible'
        ).first.click(timeout=4000)
    except Exception as exc:
        print(f"[menu] UI click failed ({exc}); goto href")
        page.goto(href)
    page.wait_for_timeout(1500)
    return href




def run():
    os.makedirs(_OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # --- login -> OTP -> industry -> dashboard -> proposals list ---
        LoginPage(page).open(BASE_URL).login(LOGIN_EMAIL, LOGIN_PASSWORD)
        OtpPage(page).enter_otp(OTP)
        ind = IndustrySelectionPage(page)
        ind.select_industry(INDUSTRY)
        ind.confirm_proceed()
        DashboardPage(page).go_to_land_identification()
        page.wait_for_timeout(3000)
        before = capture(page, "list_before", LIST_JS)

        # --- View via the row action menu ---
        href = _open_menu_item(page, "View", r"/land-banks/[^/]+/?$")
        print(f"[view] url after clicking View: {page.url}")
        page.wait_for_timeout(1500)
        view_state = capture(page, "detail", VIEW_JS)

        # --- can anything on the read-only page be edited/submitted? ---
        editable = [c for c in view_state["controls"]
                    if not c["readonly"] and not c["disabled"] and c["visible"]]
        print(f"[view] editable+visible controls: {len(editable)} "
              f"| submitControls: {view_state['submitControls']}")

        # try to type into the first editable control (if any) to see what
        # the app does with the change
        if editable:
            first = editable[0]
            target = page.locator(
                f"input[name='{first['name']}'], select[name='{first['name']}'], "
                f"textarea[name='{first['name']}']"
            ).first
            try:
                target.fill("PROBE-EDIT-ATTEMPT")
            except Exception as exc:
                print(f"[view] fill attempt failed: {exc}")
            page.wait_for_timeout(800)
            capture(page, "after_edit_attempt", VIEW_JS)
        else:
            print("[view] every visible control is readonly/disabled")

        # click any submit-ish button if one exists at all
        submit_like = page.locator(
            "button[type=submit], form button, "
            "button:has-text('Save'), button:has-text('Update'), "
            "button:has-text('Create')"
        )
        if submit_like.count():
            try:
                submit_like.first.click(timeout=3000)
                page.wait_for_timeout(2500)
                capture(page, "after_submit_attempt", VIEW_JS)
            except Exception as exc:
                print(f"[view] submit attempt failed: {exc}")
        else:
            print("[view] no submit-capable button on the page at all")

        # --- negative: an UNKNOWN uuid ---
        unknown_url = LIST_URL + "/" + UNKNOWN_UUID
        resp = page.goto(unknown_url)
        page.wait_for_timeout(2000)
        print(f"[view] unknown uuid -> status={getattr(resp, 'status', None)} "
              f"landed on {page.url}")
        capture(page, "unknown_uuid", VIEW_JS)

        # --- negative: an invalid (non-uuid) id ---
        bad_url = LIST_URL + "/not-a-uuid"
        resp = page.goto(bad_url)
        page.wait_for_timeout(2000)
        print(f"[view] non-uuid id -> status={getattr(resp, 'status', None)} "
              f"landed on {page.url}")
        capture(page, "invalid_id", VIEW_JS)

        # --- negative: the same URL with NO session at all ---
        if href:
            guest = browser.new_context()
            guest_page = guest.new_page()
            resp = guest_page.goto(href)
            guest_page.wait_for_timeout(2500)
            print(f"[view] unauthenticated -> status={getattr(resp, 'status', None)} "
                  f"landed on {guest_page.url}")
            state = guest_page.evaluate(VIEW_JS)
            base = os.path.join(_OUT_DIR, "view_unauthenticated")
            with open(base + ".json", "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            with open(base + ".html", "w", encoding="utf-8") as f:
                f.write(guest_page.content())
            guest_page.screenshot(path=base + ".png", full_page=True)
            print("    headings:", state["headings"][:5])
            print("    bodyText:", state["bodyText"][:300])
            print("    shows proposal name:",
                  WIND_PROJECT_DATA["proposal_name"] in state["bodyText"])
            guest.close()

        # --- negative: a WRITE attempt against the read-only URL ---
        # A plain POST (no _method spoof, no CSRF token) must be refused by
        # the server, and the record's values must be untouched afterwards.
        # Deliberately NOT method-spoofing, and deliberately NOT using
        # DELETE / PUT / PATCH: those URIs have real handlers in this app
        # (the row menu has Delete, the wizard saves with PUT/PATCH), so a
        # request that got past CSRF could destroy or rewrite the very
        # record this suite depends on. POST has no route on
        # /land-banks/<uuid> at all.
        if href:
            details_before = {d["label"]: d["value"] for d in view_state["details"]}
            # NOTE: page.request (the context's APIRequestContext) refuses
            # this environment's certificate chain ("self-signed certificate
            # in certificate chain") - the same request needs its own
            # context created with ignore_https_errors, carrying the
            # session cookies so it is a *signed-in* write attempt.
            api = p.request.new_context(
                ignore_https_errors=True,
                storage_state={
                    "cookies": page.context.cookies(),
                    "origins": [],
                },
            )
            try:
                resp = api.post(
                    href,
                    form={
                        "tlb_proposal_name": "PROBE-TAMPER",
                        "tlb_state_id": "1",
                    },
                )
                body = resp.text()[:200].replace("\n", " ")
                print(f"[view] POST -> status={resp.status} body={body!r}")
            finally:
                api.dispose()
            page.goto(href)
            page.wait_for_timeout(2000)
            after_state = capture(page, "after_write_attempt", VIEW_JS)
            details_after = {d["label"]: d["value"] for d in after_state["details"]}
            changed = {k: (details_before.get(k), details_after.get(k))
                       for k in details_before
                       if details_before.get(k) != details_after.get(k)}
            print(f"[view] values changed by the write attempt: {changed or 'NONE'}")

        # --- back to the list: viewing must have changed nothing ---
        page.goto(LIST_URL)
        page.wait_for_timeout(2500)
        after = capture(page, "list_after", LIST_JS)
        print(f"[view] entries before={before['info']} after={after['info']}")

        browser.close()
    print(f"\nDumped to {_OUT_DIR}")


if __name__ == "__main__":
    run()
