# LAMS UAT — Test Case Catalogue

Every test in this repository, what it drives, what it asserts, and **where the
expected wording came from**.

Nothing below is guessed. The positive flows were built from live DOM dumps
(`scripts/probe_step2.py`, `probe_step3.py`, `probe_edit.py`) and every rejection
message was captured by `scripts/probe_negative.py` into `probe_output/neg_*.json`
(+ `.png` screenshots and `.html` DOM dumps). The "Evidence" column of each case
names the capture file that proves the expected behaviour.

## How to run

| Command | What runs |
| --- | --- |
| `pytest` | everything (3 reference flows + 14 rejection tests + 9 module-wise cases = 26) |
| `pytest -m smoke` | the three reference business flows |
| `pytest -m negative` | the 20 rejection tests (14 flat + 6 module-wise) |
| `pytest -m positive` | the 3 module-wise positive cases (TC-15, TC-18, TC-21) |
| `pytest -m "not negative"` | positive flows only |
| `pytest tests/land_bank` | the Step 1 module (TC-15 … TC-17) |
| `pytest tests/technical_team` | the Step 2 module (TC-18 … TC-20) |
| `pytest tests/commercial_financial` | the Step 3 module (TC-21 … TC-23) |
| `pytest tests/test_lams_e2e.py::test_edit_existing_land_proposal` | the no-new-record edit flow |
| `pytest tests/test_lams_e2e.py::test_view_existing_land_proposal` | the read-only View flow |
| `pytest -k view` | just the four View cases (1 positive + 3 negative) |
| `pytest -k "login or otp"` | just the three authentication rejections (~55 s) |

Module-wise cases (section 7) live under `tests/<module>/`, are tagged with their
module marker (`land_bank` / `technical_team` / `commercial_financial`) and carry an
explicit `@pytest.mark.tc_id("TCnn")`, which is what puts `TC15 …` in front of every
row of `reports/summary.txt` and names their screenshots
`screenshots/<module>/TCnn_<name>_FAILED.png`.

`pytest.ini` sets `addopts = --browser chromium --headed --slowmo=500`, so the
browser is always visible and slightly slowed down. Measured runtime: **2 min**
for the three positive flows (create 66 s, edit 57 s, view 41 s), and
**5 min 16 s** for the 14 negative tests in one
`pytest -m negative` run (they share a single signed-in browser session — see
`tests/conftest.py`).

Every test is tagged `[chromium]` because of the `--browser chromium` flag.

---

## 1. Positive tests — `tests/test_lams_e2e.py`

### TC-01 · `test_add_new_land_proposal`  · markers: `smoke`, `e2e`

The full create-mode journey. **Creates one new land record per run.**

| # | Action | Expected result |
| --- | --- | --- |
| 1 | Open `BASE_URL` | Login page (`/auth/login`) |
| 2 | Log in as `admin@lams.com` / `123456` | OTP page (`/auth/validate-otp`), no captcha |
| 3 | Enter OTP `123456` | Industry Selection page |
| 4 | Select **Renewable** → **Proceed** | Dashboard loads (`DashboardPage.is_loaded()`) |
| 5 | Dashboard → Land Identification / Proposal | Land Proposals List loads |
| 6 | **Add New Land Proposal** | Wizard Step 1 (`/land-banks/create/1`) |
| 7 | Fill every Step 1 section, **Create Land Bank** | `assert_saved()`: banner **"Land Bank created successfully"** *and* zero visible validation errors |
| 8 | Fill Step 2 (Technical Team), **Save** | `assert_step2_saved()`: banner **"Step 2 saved. Proceed to Step 3."** and no validation errors |
| 9 | Fill Step 3 (Commercial/Financial), **Save** | `assert_step3_saved()`: alert **"Land Bank created successfully"** (or the redirect as fallback) and no validation errors |
| 10 | — | Back on the Land Proposals List; the new row is present |

Data: `test_data.WIND_PROJECT_DATA` ("New Wind Project", a real uploaded document
fixture — the file upload is genuinely exercised).

*Why the two-part check (banner ± errors):* an earlier version of this test went
green while the form was actually rejected for a missing required field, so
`assert_saved()` now demands the confirmation **and** an empty validation-error
set.

### TC-02 · `test_edit_existing_land_proposal`  · markers: `smoke`

Opens the **existing** record (never "Add New Land Proposal"), submits its stored
data through Steps 1–3 and proves **no new record is created**.

| # | Action | Expected result |
| --- | --- | --- |
| 1 | Login → OTP → Renewable → Proceed → Land Proposals List | as TC-01 |
| 2 | Read the info bar (`total_entries()`) | e.g. **"Showing 1 to 25 of 48 entries"** → `total_before = 48` |
| 3 | Row action menu → **Edit** for `New Wind Project` | `/land-banks/<uuid>/edit` |
| 4 | Read the proposal-name field | Prefilled with exactly `New Wind Project` (proves the real record loaded, not a blank form) |
| 5 | Step 1 → **Update Land Bank** | Banner **"Step 1 updated. Proceed to Step 2."** |
| 6 | Step 2 → **Save** (stored data as-is; topped up only if that record predates Step 2) | Banner **"Step 2 updated. Proceed to Step 3."** |
| 7 | Step 3 → **Save** | Alert **"Land Bank updated successfully"**, then redirect to `/land-banks` (the alert is often auto-dismissed, so the redirect is an accepted fallback) |
| 8 | Read the info bar again | `total_after == total_before` — **48 → 48**, i.e. the edit flow created nothing |

Cross-check for the negative suite: `test_negative_rejected_submits_create_no_records`
asserts the same guarantee for the *failure* paths.

### TC-14 `test_view_existing_land_proposal`  markers: `smoke`, `e2e`

The read-only **View** flow - the third row action (View / Edit / Convert to
Project / Send Approval). It never opens the wizard and never submits anything:
it proves the record's stored values are what the page shows **and** that the
page cannot change them.

| # | Action | Expected result |
| --- | --- | --- |
| 1 | Login -> OTP -> Renewable -> Proceed -> Land Proposals List | as TC-01 |
| 2 | Read the info bar (`total_entries()`) | e.g. `Showing 1 to 25 of 50 entries` -> `total_before = 50` |
| 3 | Row action menu -> **View** for `New Wind Project` | `.../land-banks/<uuid>` - the list route plus the record id, **no** `/edit`; `click_view_existing()` returns that href |
| 4 | Compare `page.url` with the menu item's href | equal, and the URL contains no `/edit` |
| 5 | Check the headings | `View Land Proposal` and the sections `Land Bank Details` / `Engineering Team Details` / `BD Team Details` |
| 6 | Read the stored values | `State = Bihar`, `Company = Heritage Builders pvt.ltd`, `Project Type = Wind`, `Site Visit Date = 2026-09-20`, `Plant Size = 50`, `DC Feasible = 40`, `Land Basic Cost Sale = 500000`, `Lease Tenure (Years) = 30`, `Tariff Due to this Land = 4` |
| 7 | Count the controls | `input` / `select` / `textarea` = **0**, `type="submit"` = **0**, no visible write action - the only visible action is **Back to List** |
| 8 | **Back to List** | back on the Land Proposals List with `total_after == total_before` (**50 -> 50**) |

*Why the uuid comparison instead of the name:* the live page renders 56
`.detail-item` label/value pairs and never prints the proposal name, so the record
identity has to come from the URL (`probe_output/view_detail.json`).

Numbers are compared as numbers because the page pads them (`50` arrives as
`"50.0000000000"`), and `ViewLandProposalPage.detail()` matches labels
case-insensitively because the page's CSS uppercases them.

Evidence: `probe_output/view_detail.json|.html|.png`, `view_list_before.json` /
`view_list_after.json`, and the run log:

```
[view] entries before: 50
[view] menu item href: https://uat.lamsapp.com/php8_4/product/advanced/current/land-banks/9094659b-d0c7-4abd-af6c-1df449e829ff
[view] url: https://uat.lamsapp.com/php8_4/product/advanced/current/land-banks/9094659b-d0c7-4abd-af6c-1df449e829ff
[view] stored values shown: state 'Bihar', plant size '50.0000000000', basic cost '500000.00'
[view] entries after: 50
```

---

## 2. Negative / rejection tests — `tests/test_negative.py`

All 14 are marked `negative` (`pytestmark = pytest.mark.negative`), so
`pytest -m negative` selects them and `pytest -m "not negative"` excludes them.

| ID | Test | Bad input | Expected rejection | Evidence |
| --- | --- | --- | --- | --- |
| TC-03 | `test_negative_login_wrong_password_is_rejected` | password `WrongPass123!` | `Invalid credntials given` — stays on `/auth/login`, never reaches OTP | `neg_login_wrong_password.json/.png` |
| TC-04 | `test_negative_otp_blank_is_rejected` | empty OTP | `Please enter OTP` — stays on `/auth/validate-otp` | `neg_otp_blank.json/.png` |
| TC-05 | `test_negative_otp_incorrect_is_rejected` | OTP `999999` | `The OTP is incorrect.` — stays on `/auth/validate-otp` | `neg_otp_wrong.json/.png` |
| TC-06 | `test_negative_create_empty_step1_is_rejected` | nothing filled in Step 1 | all 8 `Please …` messages incl. `Please select document variant` + `Please upload document`; no success banner | `neg_create_empty_submit.json/.png` |
| TC-07 | `test_negative_create_missing_document_variant_and_file` | (a) no Variant + no file, (b) Variant only | (a) `Please select document variant` **and** `Please upload document`; (b) only `Please upload document` | `neg_create_no_variant.json`, `neg_create_no_file.json` |
| TC-08 | `test_negative_edit_cleared_proposal_name_is_rejected` | cleared required Proposal Name | `Please enter proposal name`; nothing persisted (reload shows the old name) | `neg_edit_step1_no_name.json` |
| TC-09 | `test_negative_edit_empty_step2_is_blocked_by_the_browser` | every Step 2 field cleared, then **Save** | **No server response at all** — Chrome blocks the submit (`Please fill in this field.`), wizard stays on `/edit-step2` | `neg_edit_step2_empty.json/.png` |
| TC-10 | `test_negative_edit_non_integer_shape_index_is_rejected` | Shape Index `0.5` | `Shape Index must be integer`; stored value unchanged | `neg_edit_step2_bad_shape.json` |
| TC-11 | `test_negative_edit_empty_step3_is_rejected` | all Step 3 fields cleared | one `The <Field> field is required.` per field; no `Land Bank updated successfully` | `neg_edit_step3_empty.json/.png` |
| TC-12 | `test_negative_edit_non_numeric_money_values_are_rejected` | `tariff_due_to_this_land = abc`, then `basic_cost_sale = abc` | `The Tariff due to this land field is required.` / `The Basic Cost Sale field is required.`; data then restored and the wizard completed | `neg_edit_step3_tariff_abc.json`, `neg_edit_step3_cost_abc.json` |
| TC-13 | `test_negative_rejected_submits_create_no_records` | empty Step 1 create **+** empty Step 3 edit | both rejected **and** list entry count unchanged (48 → 48) | probe console: `[entries final] 48 (baseline 48) -> NO RECORDS CREATED` |

### Authentication (TC-03 … TC-05)

The three cases are intentionally independent of the shared session: each builds
its own `LoginPage` / `OtpPage` and starts from a fresh `page`, exactly like the
positive tests do.

* **TC-03** — the wrong-password path must not advance to OTP. The assertion is
  the combination of the message and `assert_still_on(page, LOGIN_URL, …)`,
  because a message alone would still pass if the app echoed an error *and*
  navigated on.
  ⚠ The app's real wording contains a typo — **"Invalid credntials given"**. The
  constant is `re.compile(r"Invalid cred", re.I)` so the test keeps passing if
  that typo is ever fixed.
* **TC-04 / TC-05** — `OtpPage` was refactored into `fill_otp()` + `submit()`
  so these tests can submit a blank/incorrect code without `enter_otp()`'s
  wait-for-redirect. `WRONG_OTP` is *derived* from `config.OTP`
  (`"9"` for every digit, `"8"` where the real digit is `9`), so it can never
  accidentally equal the valid code, and it stays wrong if the configured OTP
  changes.

Observed run output:

```
[negative] login rejected with: 'Invalid credntials given'
[negative] blank OTP rejected with: 'Please enter OTP'
[negative] OTP 999999 rejected with: 'The OTP is incorrect.'
```

### Create wizard, Step 1 (TC-06, TC-07)

* **TC-06 — empty submit.** Clicking **Create Land Bank** on a completely empty
  Step 1 produces a wall of inline errors and the wizard stays on
  `/land-banks/create/1`. The test asserts all eight discovered sentences
  (`STEP1_REQUIRED`), that no success banner appeared, and the URL — a
  field-by-field rejection is the real requirement, not just "something went
  red". Observed: **58 on-screen messages** (the probe's de-duplicated list held
  48), e.g. `'Please enter proposal name'`.
* **TC-07 — the Document row.** Two-part test on an otherwise valid Step 1:
  1. **No Variant and no file** → both `Please select document variant` and
     `Please upload document`, wizard still open.
  2. **Variant chosen, file still missing** → the Variant error disappears and
     only `Please upload document` remains.

  Step (2) is what makes this a real test: it proves the two conditions are
  validated independently rather than one masking the other. Neither attempt may
  save.

Observed:

```
[negative] empty Step 1 rejected with 58 messages, e.g. 'Please enter proposal name'
[negative] document-row rejections confirmed: 'Please select document variant' then 'Please upload document'
```

### Edit wizard, Step 1 (TC-08)

Clearing the **prefilled, required** Proposal Name and pressing **Update Land
Bank** gives `Please enter proposal name`, no "Step 1 updated…" banner, and the
URL stays on `/land-banks/<uuid>/edit`. The test then **reloads the page** and
asserts the field is back to `New Wind Project` — proof the rejected submit wrote
nothing. (A rejection that still persisted a blank name would be the worst
possible bug here, so it is explicitly covered.)

### Edit wizard, Step 2 (TC-09, TC-10)

* **TC-09 — a browser block, not a server error.** Clearing *every* Step 2 field
  and clicking Save produces **no application-level validation at all**
  (`invalid: []` in the capture — only the stale "Step 1 updated. Proceed to
  Step 2." banner). The URL never changes, so the request never reached the
  server. The decisive assertion is therefore Chrome's own
  `validationMessage()`, not on-screen text:
  - `native_validation_errors()` → **14 controls** flagged, e.g.
    `tlbet_plant_size` → `'Please fill in this field.'`
  - `native_validation_blocked()` after the click → the browser is still holding
    the form back.

  > **Investigation note.** An earlier run looked like the server was *refilling*
  > the cleared fields (a capture showed `value="50"` again). That was a
  > measurement artefact: `clear_field()` changes the input's DOM **property**,
  > while `getAttribute('value')` / saved HTML keep the original **attribute**.
  > The screenshot's `Please fill in this field.` bubble settled it — the fields
  > really were empty and the submit was blocked client-side.

* **TC-10 — non-integer Shape Index.** `0.5` is refused with
  `Shape Index must be integer` and Step 2 does not save, even though the field's
  own `oninput` handler strips the dot before the request is sent (the resulting
  value is still rejected server-side). After a reload the stored value is
  intact (`'1'`), i.e. the bad value was never persisted.

### Edit wizard, Step 3 (TC-11, TC-12)

Step 3 behaves differently from Step 2: it has **no** browser-level `required`
attributes, so an empty submit *does* reach the server and comes back with one
Laravel-style `The <Field> field is required.` per field.

* **TC-11** — clearing everything yields one message per field (observed: **16
  messages**; the probe's list held 17 entries, one of which is a duplicate of a
  field rendered twice). The test requires the three representative sentences in
  `STEP3_REQUIRED`, asserts the final alert **"Land Bank updated successfully"**
  did *not* appear, and after a reload confirms the stored Basic Cost Sale
  (`'500000'`) survived.
* **TC-12 — text instead of an amount.** The numeric sanitiser blanks the box, so
  the server answers with the plain *required* message for that single field:
  `tariff_due_to_this_land = "abc"` → `The Tariff due to this land field is
  required.`; `basic_cost_sale = "abc"` → `The Basic Cost Sale field is
  required.` The test then restores the valid stored data and completes the
  wizard, so **the record is left exactly as it was found** and the count
  guarantee of TC-13 still holds.

Observed:

```
[negative] empty Step 3 rejected with 16 messages; stored Basic Cost Sale intact: '500000'
[negative] non-numeric amounts rejected; data restored: 'Land Bank updated successfully'
```

### Safety net (TC-13)

`test_negative_rejected_submits_create_no_records` re-runs a rejected **create**
(empty Step 1) and a rejected **edit** (empty Step 3), then compares the list's
total-entry count before and after. It failed on the first attempt for an
instructive reason — it jumped straight from the create wizard into the edit
helper, so the AJAX list had no rows to find; the fix was an explicit
`back_to_list()` between the two halves.

Observed:

```
[negative] entries before the rejected submits: 48
[negative] entries after the rejected submits: 48 (unchanged)
```

The absolute number simply reflects the UAT list at the time of the run — it grows
every time TC-01 runs (the create flow adds a row on purpose). The assertion is
**relative** (`after == before`), so it stays valid at 48, 49 or any later count.

---

## 3. Discovered message catalogue

Exact strings the app produces, as captured. These are the constants in
`tests/test_negative.py` — change them *there* if the app's wording changes.

| Where | Exact text |
| --- | --- |
| Login | `Invalid credntials given` *(app typo — matched as `r"Invalid cred"`)* |
| OTP, blank | `Please enter OTP` |
| OTP, wrong | `The OTP is incorrect.` |
| Step 1 | `Please enter proposal name`, `Please select company`, `Please select project type`, `Please select state`, `Please enter latitude degree`, `Please enter TL distance`, `Please select document type`, `Please select document variant`, `Please upload document` |
| Step 2 | `Shape Index must be integer` |
| Step 2 (browser, not app) | `Please fill in this field.` |
| Step 3 | `The <Field> field is required.` — e.g. `The Basic Cost Sale field is required.`, `The Commercial Negotiation field is required.`, `The Tariff due to this land field is required.` |
| Success (create) | `Land Bank created successfully`, `Step 2 saved. Proceed to Step 3.` |
| Success (edit) | `Step N updated. Proceed to Step N+1.`, `Land Bank updated successfully` |

Matching rule: `has_message()` only compares whitespace-normalised,
case-insensitive text and requires the **whole** discovered sentence, so a
different error can never accidentally satisfy an assertion.

## 4. Findings that are documented but not automated

* **No range validation on Ease of Acceptance.** The field is presented as a
  0–10 score, but `99` was **accepted** (not rejected as out of range) during
  probing (`probe_output/neg_edit_step2_ease_99.json/.png`). Because that submit
  modified the record, it is recorded here as a finding rather than asserted in
  the suite — an automated test would have to change the record and then change
  it back.
* **Step 2 relies on the browser.** An entirely empty Step 2 never reaches the
  server (TC-09). If a future build removes the `required` attributes, the app
  has to reject it itself — the current tests would catch that regression
  (`native_validation_errors()` would come back empty, the assertion fails).
* **Numeric fields are sanitised client-side.** *abc* / *0.5* are stripped by
  `oninput` handlers before submission, so the messages the server returns are
  the *required* / *must be integer* ones rather than a "not a number" message.
* **Duplicate proposal names are accepted.** `probe_output/tc_cleanup.log` opens
  with `[cleanup] 21 row(s) named 'New Wind Project' in the list` — every one of
  them came from an accepted create-wizard Step 1 carrying the same name, so a
  "duplicate name must be rejected" case would fail against today's app. The
  behaviour is recorded here rather than asserted; the probe's own duplicate-name
  attempt never ran (after an accepted Step 1 the create wizard sits on Step 2,
  and `probe_tc_matrix.py` timed out filling the hidden Step 1 field — see
  `probe_output/tc_probe.log`).

## 5. Test-session design (`tests/conftest.py`)

The negative tests share one signed-in browser session through a **module-scoped**
fixture — 11 separate logins would take far longer than the assertions themselves:

| Fixture / helper | Purpose |
| --- | --- |
| `lams` (module-scoped) | Logs in once (login → OTP → industry → Proceed → Land Proposals List) and yields a `LamsSession` |
| `lams_list` | The same session, exposed as `LamsSession` with `page` + `proposals` for list-level assertions |
| `LamsSession.back_to_list()` | Re-navigates to the list between tests, so each test starts from a known page |
| `LamsSession.open_create()` | Returns a fresh `AddLandProposalPage` on Step 1 of create mode |
| `LamsSession.open_existing_record(name)` | Returns an `AddLandProposalPage` on the existing record's Step 1 (used by `open_record_and_advance`) |

The two positive tests in `tests/test_lams_e2e.py` deliberately keep their own
inline login: they are the end-to-end reference flows and must prove the login
journey works from scratch every run.

`open_record_and_advance(lams, step)` walks the wizard to Step 1/2/3 using the
record's own stored data, which is what makes every edit-mode negative test
independent: the only thing that can fail once the test starts poking at the form
is the negative behaviour under test.

## 6. Evidence & maintenance

Raw evidence is produced by the probe scripts and kept in `probe_output/`:

| Script | Produces |
| --- | --- |
| `scripts/probe_negative.py` | `neg_*.json` (URL, visible messages, on-screen `invalid: []` list, native validation), `neg_*.png` screenshots, `neg_*.html` DOM dumps — plus the entry-count checkpoints printed to the console (`[entries baseline] 48` … `[entries final] 48 (baseline 48) -> NO RECORDS CREATED`) |
| `scripts/probe_step2.py` / `probe_step3.py` / `probe_edit.py` | The positive-flow DOM dumps the page objects were built from |

To re-capture after an app change:

```bash
python scripts/probe_negative.py     # refreshes probe_output/neg_*
pytest -m negative                   # re-verify the assertions against the new wording
```

> Probe logs written through PowerShell redirection are **UTF-16**; read them with
> `Get-Content probe_output/<file>.log -Encoding Unicode` or you will see
> interleaved NUL characters.

When the app's wording changes, update the constants at the top of
`tests/test_negative.py` (and the catalogue in section 3) — no test body needs to
change, because every assertion is written against a named constant.

---

## 7. Module-wise tests — `tests/land_bank/`, `tests/technical_team/`, `tests/commercial_financial/`

One folder per wizard step, each with a `*_positive.py` and a `*_negative.py` file.
All nine walk the **edit** wizard (never the create wizard), so no test can add a
record, and every expectation was captured by `scripts/probe_tc_matrix.py` /
`scripts/probe_tc_values.py` (raw evidence in `probe_output/tc_*`).

| TC | Module | Test | Kind | Expected result | Evidence |
| --- | --- | --- | --- | --- | --- |
| TC-15 | `land_bank` | `test_TC15_valid_land_bank_details_are_accepted` | positive | `Step 1 updated. Proceed to Step 2.`, wizard opens Step 2, entry count unchanged | `tc_probe_summary.json`, `tc_step1check2.log` |
| TC-16 | `land_bank` | `test_TC16_cleared_latitude_degree_is_rejected` | negative | server: `Please enter latitude degree`; no banner; url stays `.../edit`; stored `22` intact after reload | `tc_step1_lat_cleared.json`, `neg_create_empty_submit.json` |
| TC-17 | `land_bank` | `test_TC17_negative_tl_distance_cannot_be_typed` | negative | typing `-5` leaves `5` — a negative distance can never reach the server | `tc_attempt_tl_distance_negative.json` |
| TC-18 | `technical_team` | `test_TC18_valid_technical_team_details_are_saved` | positive | `Step 2 saved/updated. Proceed to Step 3.`, wizard opens Step 3 (`.../edit-step3`), count unchanged | `tc_probe_summary.json`, `tc_values.log` |
| TC-19 | `technical_team` | `test_TC19_negative_plant_size_is_sanitised_by_the_browser` | negative | typing `-5` leaves `5`; nothing submitted, stored value intact | `tc_step3_diag.json` |
| TC-20 | `technical_team` | `test_TC20_cleared_plant_size_is_blocked_by_the_browser` | negative | the browser blocks the empty required field (`validationMessage`), no banner, no server error, url stays `.../edit-step2` | `tc_attrs_step2.json`, `neg_edit_step2_empty.json` |
| TC-21 | `commercial_financial` | `test_TC21_valid_commercial_financial_details_complete_the_record` | positive | `Land Bank updated successfully` (or the redirect), back on the list, count unchanged | `edit_after_step3.json`, page-object docstring |
| TC-22 | `commercial_financial` | `test_TC22_non_numeric_basic_cost_sale_is_rejected` | negative | `The Basic Cost Sale field is required.`; no final banner; stored value unchanged | `neg_edit_step3_cost_abc.json` |
| TC-23 | `commercial_financial` | `test_TC23_non_numeric_tariff_is_rejected` | negative | `The Tariff due to this land field is required.`; same three guards | `neg_edit_step3_tariff_abc.json` |

Design rules the nine follow:

* **Edit mode only.** An accepted create-wizard Step 1 *creates* a record
  (51 → 52 during probing), so only rejected submits are safe there; the
  module-wise cases never risk that.
* **Rejects must leave no trace.** Every negative case reloads afterwards and
  compares the stored value with the value it started from.
* **One helper.** `tests/wizard_steps.py` holds `advance_to()` / `save_step2()`
  (including the single retry the UAT app's occasionally dropped Step 2 save
  needs) so all four modules walk the wizard identically.
* **Reloads wait for the active pane.** `.../edit-step2` and `.../edit-step3`
  reopen on their own step, so the tests wait for the control to be *attached*
  — waiting for Step 1 to be visible times out (this cost TC-19/TC-20 their
  first run).
