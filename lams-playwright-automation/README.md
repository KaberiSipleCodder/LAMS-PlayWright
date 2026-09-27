# LAMS Playwright Automation (Python + pytest)

Automates the LAMS UAT flow in two modes:

- **Create** (`test_add_new_land_proposal`): Login → OTP → Select "Renewable" →
  Proceed → Land Identification/Proposal → Add New Land Proposal → fill
  Step 1 (Land Bank Details) → Create Land Bank → fill Step 2 (Technical
  Team) → Save → fill Step 3 (Commercial/Financial Details) → Save →
  back to Land Proposals List ("Land Bank created successfully").
  *Creates one new record per run.*

- **Edit existing** (`test_edit_existing_land_proposal`): same login, then
  opens the FIRST existing row via its action menu → Edit, submits the
  record's **stored data** through Steps 1–3 without refilling, and
  asserts the list's total-entry count is **unchanged** — i.e. it never
  creates a new land record. Run it alone with:

  ```bash
  pytest tests/test_lams_e2e.py::test_edit_existing_land_proposal
  ```

- **View (read-only)** (`test_view_existing_land_proposal`): opens the FIRST
  existing row via its action menu → View (`.../land-banks/<uuid>`, **no**
  `/edit`), asserts the record's stored values are what the page displays,
  that the page has **no form control, no submit control and no write
  action** whatsoever, and that the list's total-entry count is unchanged
  (viewing writes nothing). Run it alone with:

  ```bash
  pytest tests/test_lams_e2e.py::test_view_existing_land_proposal
  ```

- **Negative / rejection tests** (`tests/test_negative.py`, 14 cases): wrong
  password, blank + incorrect OTP, empty Step 1, missing document Variant/file,
  cleared Proposal Name, empty Step 2, non-integer Shape Index, empty Step 3,
  non-numeric money fields, the three **View** cases (unknown id answers 404, the
  read-only page refusing a write, unauthorised access), plus a "no rejected
  submit creates a record" safety
  net. Every expected message was captured from the live app — see
  **[`TEST_CASES.md`](TEST_CASES.md)** for the full catalogue (positive + negative
  behaviour, exact wording, and the `probe_output/` evidence behind each one).

- **Module-wise tests** (`tests/land_bank/`, `tests/technical_team/`,
  `tests/commercial_financial/`, 9 cases, TC-15 … TC-23): one folder per wizard
  step, each with a positive and a negative file — e.g. valid Step 1 details are
  accepted and hand over to Step 2, a cleared co-ordinate is refused with
  `Please enter latitude degree`, `-5` can never be typed into a distance/size
  field, an empty required Step 2 field is blocked by the browser, and non-numeric
  Step 3 amounts come back as `The Basic Cost Sale field is required.` Every case
  is tagged with its module marker and an explicit `@pytest.mark.tc_id("TCnn")`,
  which is what puts `TC15 …` in front of each row of `reports/summary.txt`.

Built with the Page Object Model (POM): each screen has its own file under
`pages/`, and the tests only describe the business flow, not locator details.

## Project structure

```
lams-playwright-automation/
├── config.py                      # base URL, credentials, OTP, industry
├── test_data.py                   # sample "New Wind Project" form data
├── test_data/
│   └── sample_document.pdf        # the file the upload field actually sends
├── pytest.ini                     # markers + browser flags
├── requirements.txt
├── TEST_CASES.md                  # catalogue of every test + its evidence
├── pages/
│   ├── login_page.py
│   ├── otp_page.py                # fill_otp() + submit() (negative tests reuse these)
│   ├── industry_selection_page.py
│   ├── dashboard_page.py
│   ├── land_proposals_page.py      # list + row actions (View / Edit)
│   ├── add_land_proposal_page.py   # Steps 1 + 2 + 3 of the wizard
│   └── view_land_proposal_page.py  # read-only View page (.detail-item blocks)
├── scripts/
│   ├── probe_step2.py              # DOM discovery probe (dev tool)
│   ├── probe_step3.py              # Step 3 probe (--save dry-run)
│   ├── probe_edit.py               # Edit-existing-record probe
│   ├── probe_view.py               # View (read-only) probe + write attempt
│   └── probe_negative.py           # captures every rejection message (probe_output/)
└── tests/
    ├── conftest.py                 # shared module-scoped sign-in for negative tests
    ├── wizard_steps.py             # advance_to()/save_step2() used by the modules
    ├── test_lams_e2e.py            # the three reference flows (create / edit / view)
    ├── test_negative.py            # the 14 flat rejection tests
    ├── land_bank/                  # Step 1 module: TC-15 (positive), TC-16/17
    ├── technical_team/             # Step 2 module: TC-18 (positive), TC-19/20
    └── commercial_financial/        # Step 3 module: TC-21 (positive), TC-22/23
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium     # downloads the browser binary
```

## Run

`pytest.ini` sets `addopts = --browser chromium --headed --slowmo=500`, so the
browser is visible by default (`--headed` is passed through to the playwright
fixture).

```bash
# Everything - 26 tests: 3 reference flows + 14 flat + 9 module-wise cases
pytest

# Only the positive business flows
pytest -m "not negative"        # or: pytest -m smoke

# Only the negative / rejection tests (shares one signed-in session)
pytest -m negative

# A single case while debugging
pytest -k "login or otp" -v -s

# Faster / invisible run (clear the ini browser flags - headless is the
# playwright default)
pytest -o addopts="--browser chromium"
```

Use `-s` to see the `[negative] …` lines each test prints: they quote the exact
message the app returned, which makes a failure easy to read.

## Notes / known caveats

- **Captcha**: not handled at all — this UAT account has it disabled.
  If your environment shows a real captcha, this suite will need a
  solving/bypass strategy added to `LoginPage` before login will work.
- **OTP**: hardcoded to `123456` in `config.py`, assuming a fixed test OTP
  rather than a real emailed one. For a real emailed OTP you'd need to pull
  it from a test-mailbox API (Mailinator/Mailosaur/Gmail API) instead.
- **Dropdown locators**: every control is addressed by its `name` attribute and
  `AddLandProposalPage._select()` drives the native `<select>` behind each
  Select2 widget. It first waits for the *specific option text* to appear
  (dependent dropdowns — District, Taluka, Village, Document Type — are
  AJAX-populated *after* their parent is chosen, so waiting on an option count
  would race the AJAX) and then sets the value and dispatches a real `change`
  event, so Select2's UI and the app's own jQuery handlers update exactly as
  they would for a human. If the option never appears the failure message lists
  the options that *were* available, so a data mismatch is obvious instead of a
  bare timeout.
- **Document upload**: `document_file_path` in `test_data.py` points at the
  bundled `test_data/sample_document.pdf`, so the upload field is genuinely
  exercised by the default run. Point it at another absolute path to upload a
  different file.
- **Step 2 (Technical Team)**: locators are the real `tlbet_*` `name`
  attributes, captured from the live UAT DOM with
  `python scripts/probe_step2.py` (dumps JSON + HTML + screenshots into
  `probe_output/`). Re-run that probe if the app's Step 2 changes.
  - Success banner is exactly **"Step 2 saved. Proceed to Step 3."**
    (rendered in `.alert-success` after the page navigates to
    `/land-banks/create/3`); `wait_for_step2_save_success()` matches
    `Step 2[^.]*saved` so the Step 1 banner can never satisfy it.
  - `shape_index` must be an **integer** — the server rejects decimals
    with "Shape Index must be integer" and the whole Step 2 save fails.
  - `site_visit_date` is an `<input type="date">`; pass ISO `yyyy-mm-dd`
    even though the UI displays `dd-mm-yyyy`.
- **Step 3 (Commercial/Financial Details)**: locators are the real
  `tlbbt_*` `name` attributes, captured with
  `python scripts/probe_step3.py` (add `--save` for a fill+save dry-run
  that captures the app's response). Notes:
  - It is the **final** step: success redirects to `/land-banks` and
    shows the alert **"Land Bank created successfully"** — there is no
    "Step 3 saved" banner. `wait_for_step3_save_success()` matches that
    alert, with the redirect as a fallback if the alert is dismissed.
  - Every wizard step renders its own `Save` button, so
    `click_step3_save()` scopes the click to the active
    `div.tab-pane.active` instead of matching all `Save` buttons.
- **Edit existing record (no new record)**: locators/flow discovered by
  `python scripts/probe_edit.py`. Notes:
  - Edit URL is `.../land-banks/<uuid>/edit` (row action menu → Edit).
    The list is AJAX-loaded ("Loading..." placeholder row) and the row
    action menu never became visible under automation, so
    `click_edit_existing()` reads the hidden Edit `href` first, tries the
    UI click briefly, then falls back to navigating to that same href.
  - Edit mode uses the same wizard with different wording: heading
    "Edit New Land Proposal Details", button **Update Land Bank** for
    Step 1, banners **"Step N updated. Proceed to Step N+1."**, and the
    final alert **"Land Bank updated successfully"** (create mode:
    "saved"/"created"). The success waits accept both.
  - The no-new-record guarantee is the total-entry info bar
    ("Showing 1 to 25 of 48 entries"): `total_entries()` before vs
    after must be equal.
  - Steps arrive **prefilled** with stored values; the edit test submits
    them as-is and only tops up a step if that record predates it (empty
    field).
- **View (read-only) page**: discovered by `python scripts/probe_view.py`
  (JSON/HTML/screenshots in `probe_output/view_*`, console log
  `probe_output/probe_view_run.log`). Notes:
  - The row's **View** action links to `.../land-banks/<uuid>` - the list
    route plus the record id, with no `/edit` suffix (Edit links to
    `.../land-banks/<uuid>/edit`). `click_view_existing()` returns that href,
    which is how a test proves the right record opened: the page does **not**
    render the proposal name anywhere.
  - The data arrives as `.detail-item` blocks (`.detail-label` +
    `.detail-value`) - 56 label/value pairs on the sampled record. The CSS
    uppercases the labels, so `ViewLandProposalPage.detail("State")` matches
    case-insensitively and numeric values are compared as numbers
    (`"50.0000000000"` -> 50).
  - Read-only means, concretely: **0** `input`/`select`/`textarea` elements,
    **0** `type="submit"` controls and no visible write action at all - the
    only visible action is "Back to List". A signed-in `POST` to the same URL
    is refused with **405 Method Not Allowed** and every stored value is
    unchanged afterwards.
  - That write attempt cannot use `page.request`: this environment's
    certificate chain is rejected by Playwright's API request stack
    ("self-signed certificate in certificate chain"), so the test builds its
    own request context with `ignore_https_errors=True` plus the session
    cookies.
  - A uuid that matches no record answers **404** ("Page Not Found", URL left
    alone, no field values rendered); a malformed id such as
    `/land-banks/not-a-uuid` answers **500** with a Laravel SQL exception
    trace - see the findings section of `TEST_CASES.md`.
- **Negative tests share one session**: `tests/conftest.py` signs in **once**
  (module-scoped `lams` / `lams_list` fixtures) and exposes `back_to_list()`,
  `open_create()` and `open_existing_record()` — otherwise the 11 rejection tests
  would pay for 11 full logins. The two positive tests deliberately keep their
  own inline login so they stay true from-scratch end-to-end flows.
- **Rejection messages are captured, not invented**: `visible_validation_errors()`
  returns only messages actually on screen, `wait_for_validation_errors()` polls
  for them, and `native_validation_errors()` reports what the *browser* refuses to
  submit (Chrome's `validationMessage()`) — that last one is how the empty-Step-2
  case is asserted, since it never reaches the server at all. Every exact string
  lives in the constants at the top of `tests/test_negative.py`.
- **Re-probing after an app change**: `python scripts/probe_negative.py`
  re-captures all rejection evidence into `probe_output/neg_*.json|png|html`.
  Its console log is **UTF-16** when redirected in PowerShell — read it with
  `Get-Content <file>.log -Encoding Unicode`.

