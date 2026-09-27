"""
Page Object for the "Add New Land Proposal Details" screen.

Sections covered:
  - Land Bank Details
  - Land Co-ordinates
  - Sub-Station Co-ordinates
  - Additional Details
  - Document Section
  - Technical Team (wizard Step 2, activated after "Create Land Bank"
    saves Step 1 - see scripts/probe_step2.py for how the DOM was
    discovered)
  - Commercial/Financial Details (wizard Step 3, the FINAL step - on
    success the app redirects to the Land Proposals list with
    "Land Bank created successfully"; see scripts/probe_step3.py)

LOCATOR STRATEGY
The previous version located fields by walking the DOM forward from their
visible label text:
    //label[contains(., 'Latitude Degree')]/following::input[1]
That is ambiguous. The Land Co-ordinates and Sub-Station Co-ordinates
sections both render a label with the exact text "Latitude Degree", so the
XPath resolved to *two* inputs and Playwright raised a strict-mode violation:

    Locator.fill: Error: strict mode violation:
    locator("//label[contains(normalize-space(.), 'Latitude Degree')]
             /following::input[1]") resolved to 2 elements:
      1) <input id="tlb_land_dms_lat_degree" name="tlb_land_dms_lat_degree" ...>
      2) <input id="tlb_substation_dms_lat_degree"
                name="tlb_substation_dms_lat_degree" ...>

The real screen gives every control a stable, unique ``name`` (and usually
``id``) - e.g. ``tlb_land_dms_lat_degree`` for the Land section versus
``tlb_substation_dms_lat_degree`` for the Sub-Station section. We target those
directly, so each locator matches exactly one element and strict mode is happy.

All dropdowns on this screen are Select2 widgets that wrap a real ``<select>``
element (class ``select2-hidden-accessible``). We drive the underlying
``<select>`` directly and dispatch a real ``change`` event so Select2 and the
app's own dependent-field handlers react exactly as they would for a user.
"""

import re
import time


class AddLandProposalPage:

    # -----------------------------------------------------------------
    # Unique field identifiers taken from the real DOM (name attributes)
    # -----------------------------------------------------------------

    # Land Bank Details
    PROPOSAL_NAME = "tlb_proposal_name"
    COMPANY = "tlb_company_id"
    PROJECT_TYPE = "tlb_project_type"
    LAND_TYPE = "tlb_land_type_id"
    STATE = "tlb_state_id"
    DISTRICT = "tlb_district_id"
    TALUKA = "tlb_taluka_id"
    VILLAGE = "tlb_village_id"

    # Land Co-ordinates
    LAND_LAT_DEGREE = "tlb_land_dms_lat_degree"
    LAND_LAT_MINUTES = "tlb_land_dms_lat_minutes"
    LAND_LAT_SECONDS = "tlb_land_dms_lat_seconds"
    LAND_LAT_DIRECTION = "tlb_land_dms_lat_direction_id"
    LAND_LONG_DEGREE = "tlb_land_dms_long_degree"
    LAND_LONG_MINUTES = "tlb_land_dms_long_minutes"
    LAND_LONG_SECONDS = "tlb_land_dms_long_seconds"
    LAND_LONG_DIRECTION = "tlb_land_dms_long_direction_id"
    SUBSTATION = "tlb_substation_id"
    CTU_STU = "tlb_ctu_stu"

    # Sub-Station Co-ordinates
    SS_LAT_DEGREE = "tlb_substation_dms_lat_degree"
    SS_LAT_MINUTES = "tlb_substation_dms_lat_minutes"
    SS_LAT_SECONDS = "tlb_substation_dms_lat_seconds"
    SS_LAT_DIRECTION = "tlb_substation_dms_lat_direction_id"
    SS_LONG_DEGREE = "tlb_substation_long_degree"
    SS_LONG_MINUTES = "tlb_substation_long_minutes"
    SS_LONG_SECONDS = "tlb_substation_long_seconds"
    SS_LONG_DIRECTION = "tlb_substation_long_direction_id"

    # Additional Details
    TL_DISTANCE = "tlb_tl_distance"
    SS_EVACUATION_CAPACITY = "tlb_ss_evacuation_capacity"
    VOLTAGE_LEVEL = "tlb_voltage_level"
    SS_READINESS = "tlb_ss_readiness"
    LAND_QUANTUM_LEASE = "tlb_land_quantum_offered_lease"
    LAND_QUANTUM_PURCHASE = "tlb_land_quantum_offered_purchase"
    CONNECTIVITY_STATUS = "tlb_connectivity_status"
    QUANTUM_OF_CONNECTIVITY = "tlb_quantum_of_connectivity"
    REMARKS = "tcom_remarks"

    # Document Section - rows are indexed; row 0 uses either a bracketed
    # array name ("document_type[0]") or an underscored id ("document_type_0")
    # depending on the build, so each selector below matches both forms.
    DOCUMENT_TYPE_SEL = 'select[name="document_type[0]"], select#document_type_0'
    DOCUMENT_VARIANT_SEL = 'select[name="document_variant[0]"], select#document_variant_0'
    PHYSICAL_FILE_LOCATION_SEL = (
        '[name="physical_document_location[0]"], #physical_document_location_0'
    )
    DOCUMENT_TITLE_SEL = '[name="document_label[0]"], #document_label_0'

    # -----------------------------------------------------------------
    # Step 2: Technical Team - unique name/id per control (all tlbet_*),
    # confirmed against the live DOM via scripts/probe_step2.py. Step 2
    # activates automatically once Step 1 reports "Proceed to Step 2".
    # -----------------------------------------------------------------
    TT_PLANT_SIZE = "tlbet_plant_size"
    TT_LAND_QUANTUM_USABLE = "tlbet_land_quantum_usable"
    TT_SHAPE_INDEX = "tlbet_shape_index"
    TT_FIT_FOR_TRACKER = "tlbet_fit_for_tracker"
    TT_SITE_VISIT_STATUS = "tlbet_site_visit_status"
    TT_SITE_VISIT_DATE = "tlbet_site_visit_date"
    TT_EASE_OF_ACQUISITION = "tlbet_ease_of_acquisition"
    TT_GHI = "tlbet_ghi"
    TT_ALBEDO = "tlbet_albedo"
    TT_DC_FEASIBLE = "tlbet_dc_feasible"
    TT_ENERGY_YIELD = "tlbet_energy_yield"
    TT_PLF_OF_PLANT = "tlbet_plf_of_plant"
    TT_ENVIRONMENT_STUDY_STATUS = "tlbet_environment_study_status"
    TT_GO_NO_GO_ENVIRONMENT = "tlbet_go_no_go_from_environment_team"
    TT_GO_NO_GO_ENGINEERING = "tlbet_go_no_go_from_engineering_team"

    # -----------------------------------------------------------------
    # Step 3: Commercial/Financial Details - unique name/id per control
    # (all tlbbt_*), confirmed against the live DOM via
    # scripts/probe_step3.py. Step 3 activates automatically once Step 2
    # reports "Proceed to Step 3".
    # -----------------------------------------------------------------
    CF_BASIC_COST_SALE = "tlbbt_land_basic_cost_sale"
    CF_BASIC_COST_LEASE = "tlbbt_land_basic_cost_lease"
    CF_STAMP_DUTY_SALE = "tlbbt_stamp_duty_and_reg_charges_sale"
    CF_STAMP_DUTY_LEASE = "tlbbt_stamp_duty_and_reg_charges_lease"
    CF_OTHER_STAT_CHARGES = "tlbbt_other_stat_charges"
    CF_SERVICE_FEE_SALE = "tlbbt_service_fee_sale"
    CF_SERVICE_FEE_LEASE = "tlbbt_service_fee_lease"
    CF_LEASE_TENURE_YEARS = "tlbbt_lease_tenure_years"
    CF_LEASE_ESCALATION_RATE = "tlbbt_lease_escalation_rate"
    CF_LEASE_ESCALATION_FREQUENCY = "tlbbt_lease_escalation_frequency_years"
    CF_TOTAL_LAND_COST = "tlbbt_total_land_cost"
    CF_SERVICE_FEE = "tlbbt_service_fee"
    CF_COMMERCIAL_NEGOTIATION = "tlbbt_commercial_negotiation"
    CF_LAND_COST_FOR_BD = "tlbbt_land_cost_to_be_considered_for_bd"
    CF_LAND_BEING_CONSIDERED_FOR = "tlbbt_land_being_considered_for"
    CF_TARIFF_DUE_TO_THIS_LAND = "tlbbt_tariff_due_to_this_land"

    def __init__(self, page):
        self.page = page
        self.heading = page.locator(
            # Matches both the CREATE heading ("Add New Land Proposal
            # Details") and the EDIT heading ("Edit New Land Proposal
            # Details") - the edit mode of an existing record reuses this
            # same page object.
            "h4.approval-process", has_text="New Land Proposal Details"
        )
        self.create_land_bank_button = page.get_by_role(
            "button", name="Create Land Bank"
        )
        self.heading.wait_for(state="visible")

    # -----------------------------------------------------------------
    # Generic helpers - every one resolves to a single element
    # -----------------------------------------------------------------
    def _field(self, name: str):
        """A single text input / textarea addressed by its unique name."""
        return self.page.locator(f'[name="{name}"]')

    def _fill(self, name: str, value):
        if value is None:
            return
        self._field(name).fill(str(value))

    def _select(self, name: str, value, name_is_selector: bool = False):
        """
        Choose ``value`` in the Select2-backed dropdown whose underlying
        ``<select>`` is identified by ``name`` (a field name by default, or a
        ready-made CSS selector when ``name_is_selector`` is True).

        Strategy (robust against AJAX-populated, hidden Select2 selects):
          1. Wait for the *specific* option text to actually exist in the
             native <select>. Dependent dropdowns (District, Taluka, Village,
             Document Type, ...) are filled by AJAX *after* the parent is
             chosen, so waiting on an option *count* is not enough - the
             placeholder alone satisfies it and we would race the AJAX.
          2. Set the native <select>'s value and dispatch a real 'change'
             event. Select2 mirrors the change into its UI and the app's own
             jQuery handlers (including dependent-field logic) fire exactly as
             they would for a real user selection.
        If step 1 times out, we fail with the list of options that *were*
        available so a data mismatch is obvious instead of a bare timeout.
        """
        if value is None:
            return

        target = str(value).strip()
        selector = name if name_is_selector else f'select[name="{name}"]'

        # 1) Wait until THIS exact option (whitespace/case-insensitive) exists.
        try:
            self.page.wait_for_function(
                """([selector, wanted]) => {
                    const s = document.querySelector(selector);
                    if (!s) return false;
                    const norm = t => (t || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                    return Array.from(s.options).some(o => norm(o.text) === norm(wanted));
                }""",
                arg=[selector, target],
                timeout=15000,
            )
        except Exception as exc:
            available = self.page.evaluate(
                """(selector) => {
                    const s = document.querySelector(selector);
                    return s ? Array.from(s.options).map(o => o.text) : [];
                }""",
                selector,
            )
            raise AssertionError(
                f"Option {target!r} not found in dropdown {selector!r}. "
                f"Available options: {available}"
            ) from exc

        # 2) Drive the real <select>; Select2 syncs from the 'change' event.
        self.page.evaluate(
            """([selector, wanted]) => {
                const s = document.querySelector(selector);
                const norm = t => (t || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                const opt = Array.from(s.options).find(o => norm(o.text) === norm(wanted));
                s.value = opt.value;
                s.dispatchEvent(new Event('change', { bubbles: true }));
            }""",
            [selector, target],
        )

    # -----------------------------------------------------------------
    # Section 1: Land Bank Details
    # -----------------------------------------------------------------
    def fill_land_bank_details(self, data: dict):
        self._fill(self.PROPOSAL_NAME, data.get("proposal_name"))
        self._select(self.COMPANY, data.get("company"))
        self._select(self.PROJECT_TYPE, data.get("project_type"))
        self._select(self.LAND_TYPE, data.get("land_type"))

        self._select(self.STATE, data.get("state"))
        # District/Taluka/Village are chained AJAX dropdowns; _select() waits
        # for the specific option text, so no separate count-wait is needed.
        self._select(self.DISTRICT, data.get("district"))
        self._select(self.TALUKA, data.get("taluka"))
        self._select(self.VILLAGE, data.get("village"))
        return self

    # -----------------------------------------------------------------
    # Section 2: Land Co-ordinates
    # -----------------------------------------------------------------
    def fill_land_coordinates(self, data: dict):
        self._fill(self.LAND_LAT_DEGREE, data.get("latitude_degree"))
        self._fill(self.LAND_LAT_MINUTES, data.get("latitude_minutes"))
        self._fill(self.LAND_LAT_SECONDS, data.get("latitude_seconds"))
        self._select(self.LAND_LAT_DIRECTION, data.get("latitude_direction"))
        # Decimal Latitude is auto-calculated by the page - not set here.
        self._fill(self.LAND_LONG_DEGREE, data.get("longitude_degree"))
        self._fill(self.LAND_LONG_MINUTES, data.get("longitude_minutes"))
        self._fill(self.LAND_LONG_SECONDS, data.get("longitude_seconds"))
        self._select(self.LAND_LONG_DIRECTION, data.get("longitude_direction"))
        # Decimal Longitude is auto-calculated by the page - not set here.
        self._select(self.SUBSTATION, data.get("substation"))
        self._select(self.CTU_STU, data.get("ctu_stu"))
        return self

    # -----------------------------------------------------------------
    # Section 3: Sub-Station Co-ordinates
    # -----------------------------------------------------------------
    def fill_sub_station_coordinates(self, data: dict):
        self._fill(self.SS_LAT_DEGREE, data.get("sub_station_latitude_degree"))
        self._fill(self.SS_LAT_MINUTES, data.get("sub_station_latitude_minutes"))
        self._fill(self.SS_LAT_SECONDS, data.get("sub_station_latitude_seconds"))
        self._select(self.SS_LAT_DIRECTION, data.get("sub_station_latitude_direction"))
        self._fill(self.SS_LONG_DEGREE, data.get("sub_station_longitude_degree"))
        self._fill(self.SS_LONG_MINUTES, data.get("sub_station_longitude_minutes"))
        self._fill(self.SS_LONG_SECONDS, data.get("sub_station_longitude_seconds"))
        self._select(self.SS_LONG_DIRECTION, data.get("sub_station_longitude_direction"))
        # Decimal Latitude / Longitude here are also auto-calculated.
        return self

    # -----------------------------------------------------------------
    # Section 4: Additional Details
    # -----------------------------------------------------------------
    def fill_additional_details(self, data: dict):
        self._fill(self.TL_DISTANCE, data.get("tl_distance_km"))
        self._fill(self.SS_EVACUATION_CAPACITY, data.get("ss_evacuation_capacity_mw"))
        self._fill(self.VOLTAGE_LEVEL, data.get("voltage_level_kv"))
        self._select(self.SS_READINESS, data.get("ss_readiness"))
        self._fill(self.LAND_QUANTUM_LEASE, data.get("land_quantum_offered_lease"))
        self._fill(self.LAND_QUANTUM_PURCHASE, data.get("land_quantum_offered_purchase"))
        # Land Quantum Offered (Total) is auto-calculated (Lease + Purchase).
        self._select(self.CONNECTIVITY_STATUS, data.get("connectivity_status"))
        self._fill(self.QUANTUM_OF_CONNECTIVITY, data.get("quantum_of_connectivity"))
        self._fill(self.REMARKS, data.get("remarks"))
        return self

    # -----------------------------------------------------------------
    # Section 5: Document Section
    # -----------------------------------------------------------------
    def fill_document_section(self, data: dict):
        # Document Type options load on State change; _select() waits for the
        # specific option text so we don't need a separate count-wait.
        self._select(
            self.DOCUMENT_TYPE_SEL, data.get("document_type"), name_is_selector=True
        )
        self._select(
            self.DOCUMENT_VARIANT_SEL,
            data.get("document_variant"),
            name_is_selector=True,
        )

        physical_location = data.get("physical_file_location")
        if physical_location is not None:
            self.page.locator(self.PHYSICAL_FILE_LOCATION_SEL).first.fill(
                physical_location
            )

        title = data.get("document_title")
        if title is not None:
            self.page.locator(self.DOCUMENT_TITLE_SEL).first.fill(title)

        file_path = data.get("document_file_path")
        if file_path:
            # Dropzone renders a hidden <input type="file"> per row.
            self.page.locator(
                "input.dz-hidden-input, input[type='file']"
            ).first.set_input_files(file_path)
        return self

    # -----------------------------------------------------------------
    # Convenience: fill every section in order
    # -----------------------------------------------------------------
    def fill_all_sections(self, data: dict):
        self.fill_land_bank_details(data)
        self.fill_land_coordinates(data)
        self.fill_sub_station_coordinates(data)
        self.fill_additional_details(data)
        self.fill_document_section(data)
        return self

    def click_create_land_bank(self):
        self.create_land_bank_button.click()
        return self

    def click_step1_submit(self):
        """
        Clicks Step 1's submit button while EDITING an existing record.

        The accessible name differs between modes - "Create Land Bank"
        when creating (use click_create_land_bank for that), an
        Update/Save variant when editing (confirmed by
        scripts/probe_edit.py) - so target the ACTIVE tab pane's primary
        button instead of a fixed label.
        """
        pane = self.page.locator(
            "div.tab-pane.show.active, div.tab-pane.active"
        ).first
        primary = pane.locator("button.btn-primary")
        if primary.count() == 0:
            primary = pane.get_by_role(
                "button", name=re.compile(r"create|update|save", re.I)
            )
        primary.first.click()
        return self

    # -----------------------------------------------------------------
    # Post-submit verification
    # -----------------------------------------------------------------
    def visible_validation_errors(self):
        """
        Validation messages that are actually on screen.

        Two filters matter here:
          * Visibility - the page keeps stale spans around after a successful
            save (e.g. a hidden "Please upload document" left over from an
            earlier failed attempt), so only on-screen text counts.
          * Success exclusion - the confirmation itself renders inside an
            ``.alert``, so "Step 1 saved..." must never be mistaken for a
            validation error.
        """
        return self.page.evaluate(
            """() => {
                const sel = ['.invalid-feedback', '.error', '.text-danger',
                             '.invalid-feedback.show', '.select2-error',
                             '.notyf-error', '.toast-error',
                             '[class*="invalid"]', '[class*="error"]'].join(',');
                const visible = e => {
                    const r = e.getBoundingClientRect();
                    const s = window.getComputedStyle(e);
                    return r.width > 0 && r.height > 0
                        && s.visibility !== 'hidden' && s.display !== 'none';
                };
                const successRe = /saved|success|proceed to step|done|complete/i;
                return Array.from(document.querySelectorAll(sel))
                    .filter(e => visible(e))
                    .map(e => e.textContent.trim())
                    .filter(t => t && t !== '*' && t.length < 300)
                    .filter(t => !successRe.test(t));
            }"""
        )

    def field_value(self, name: str) -> str:
        """Current value of any named control (input or select)."""
        loc = self._field(name)
        loc.wait_for(state="attached", timeout=5000)
        return loc.input_value()

    def field_is_empty(self, name: str) -> bool:
        """
        True when the named control holds no value. The edit-existing
        flow uses this to decide whether a step needs its data topped
        up: records created before a step existed open with that step
        empty, complete records arrive fully prefilled.
        """
        return not self.field_value(name).strip()

    def clear_field(self, name: str):
        """Empties a named input or select (negative tests)."""
        loc = self._field(name)
        loc.wait_for(state="attached", timeout=5000)
        tag = loc.evaluate("el => el.tagName")
        if tag == "SELECT":
            loc.evaluate(
                "el => { el.value = '';"
                " el.dispatchEvent(new Event('change', { bubbles: true })); }"
            )
        else:
            loc.fill("")
        return self

    # Step 2 / Step 3 field sets - used by the negative tests to wipe a
    # whole step before submitting (all-empty required-field case).
    STEP2_FIELDS = (
        TT_PLANT_SIZE, TT_LAND_QUANTUM_USABLE, TT_SHAPE_INDEX,
        TT_FIT_FOR_TRACKER, TT_SITE_VISIT_STATUS, TT_SITE_VISIT_DATE,
        TT_EASE_OF_ACQUISITION, TT_GHI, TT_ALBEDO, TT_DC_FEASIBLE,
        TT_ENERGY_YIELD, TT_PLF_OF_PLANT, TT_ENVIRONMENT_STUDY_STATUS,
        TT_GO_NO_GO_ENVIRONMENT, TT_GO_NO_GO_ENGINEERING,
    )
    STEP3_FIELDS = (
        CF_BASIC_COST_SALE, CF_BASIC_COST_LEASE, CF_STAMP_DUTY_SALE,
        CF_STAMP_DUTY_LEASE, CF_OTHER_STAT_CHARGES, CF_SERVICE_FEE_SALE,
        CF_SERVICE_FEE_LEASE, CF_LEASE_TENURE_YEARS,
        CF_LEASE_ESCALATION_RATE, CF_LEASE_ESCALATION_FREQUENCY,
        CF_TOTAL_LAND_COST, CF_SERVICE_FEE, CF_COMMERCIAL_NEGOTIATION,
        CF_LAND_COST_FOR_BD, CF_LAND_BEING_CONSIDERED_FOR,
        CF_TARIFF_DUE_TO_THIS_LAND,
    )

    def clear_step2_fields(self):
        for name in self.STEP2_FIELDS:
            self.clear_field(name)
        return self

    def clear_step3_fields(self):
        for name in self.STEP3_FIELDS:
            self.clear_field(name)
        return self

    def wait_for_validation_errors(self, timeout: int = 10000) -> list:
        """
        Polls visible_validation_errors() until at least one real error
        is on screen (or ``timeout`` elapses, returning [] then).
        Used by negative tests to prove a submit was REJECTED.
        """
        deadline = time.time() + timeout / 1000
        errors = []
        while time.time() < deadline:
            errors = self.visible_validation_errors()
            if errors:
                return errors
            self.page.wait_for_timeout(250)
        return errors

    def banner_appears(self, pattern, timeout: int = 4000) -> bool:
        """
        True when a success banner matching ``pattern`` (str or regex)
        shows within ``timeout``. Negative tests assert this is False -
        the prefix-locked patterns (Step 1/2/3) ensure one step's banner
        can never be mistaken for another's.
        """
        banner = self.page.get_by_text(pattern).first
        try:
            banner.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    # -----------------------------------------------------------------
    # Browser (HTML5) validation - what stops a submit BEFORE the server
    # -----------------------------------------------------------------
    def native_validation_errors(self) -> list:
        """
        Every control in the ACTIVE wizard pane that the BROWSER itself
        considers invalid, with the message the browser would show.

        Why this exists: the Step 2 (Technical Team) form carries HTML5
        ``required`` attributes on its inputs/selects, so submitting it
        empty never reaches the server - Chrome cancels the submit and
        shows its own bubble ("Please fill in this field." /
        "Please select an item in the list."). Consequence found by
        ``scripts/probe_negative.py``: the rejected Step 2 response
        contains NO app-level validation message at all
        (``invalid: []``), unlike Steps 1/3 which answer with server-side
        text. Asserting on ``validationMessage`` is therefore the only
        way to prove Step 2's empty submit was really rejected.

        Note the trap this helper avoids: ``clear_field()`` mutates the
        DOM *property*, which ``getAttribute('value')`` / the serialised
        HTML never reflects - reading the attribute makes a cleared
        field look "still filled".
        """
        return self.page.evaluate(
            """() => {
                const pane = document.querySelector(
                    'div.tab-pane.show.active, div.tab-pane.active') || document;
                return Array.from(pane.querySelectorAll('input, select, textarea'))
                    .filter(el => el.willValidate && !el.checkValidity())
                    .map(el => ({
                        name: el.name || el.id,
                        message: el.validationMessage,
                    }));
            }"""
        )

    def native_validation_blocked(self) -> bool:
        """True when the browser would refuse to submit the active pane."""
        return bool(self.native_validation_errors())

    def wait_for_save_success(self, timeout: int = 15000):
        """
        Waits for the Step 1 confirmation banner and returns its text.

        CREATE mode says "Step 1 saved. Proceed to Step 2."; EDIT mode
        says "Step 1 updated. Proceed to Step 2." - accept both, but
        require the "Step 1" prefix so a Step 2/3 banner can never
        satisfy this wait.
        """
        banner = self.page.get_by_text(
            re.compile(r"Step 1[^.]*(saved|updated)", re.I)
        ).or_(
            self.page.get_by_text("saved successfully", exact=False)
        ).first
        banner.wait_for(state="visible", timeout=timeout)
        return banner.inner_text().strip()

    def assert_saved(self):
        """
        The real end-to-end check: the form must confirm the save AND show no
        on-screen validation errors. Without this the suite reported green even
        when the page rejected the submit (missing required Document Variant /
        uploaded file).
        """
        message = self.wait_for_save_success()
        errors = self.visible_validation_errors()
        assert not errors, (
            "Step 1 was rejected after submitting it (create: 'Create "
            f"Land Bank', edit: 'Update Land Bank'). "
            f"Visible validation errors: {errors}"
        )
        return message

    # =================================================================
    # STEP 2: Technical Team
    # =================================================================
    def wait_for_step2(self, timeout: int = 15000):
        """
        Waits until the Step 2 "Technical Team" panel is active.

        After a successful Step 1 save the page itself announces
        "Step 1 saved. Proceed to Step 2." and switches the wizard, so
        normally the first field is simply already visible. If that ever
        regresses, fall back to clicking the stepper entry.
        """
        first_field = self._field(self.TT_PLANT_SIZE)
        try:
            first_field.wait_for(state="visible", timeout=timeout)
        except Exception:
            self.page.get_by_text("Technical Team", exact=False).first.click()
            first_field.wait_for(state="visible", timeout=timeout)
        return self

    def fill_technical_team(self, data: dict):
        """
        Fills every Step 2 field.

        Dropdowns are Select2-wrapped <select>s; ``_select()`` drives the
        native element and dispatches 'change', exactly like Step 1.
        Site Visit Date is an ``<input type="date">``: Playwright fills it
        in ISO yyyy-mm-dd form even though the visible mask is dd-mm-yyyy.
        """
        self.wait_for_step2()
        self._fill(self.TT_PLANT_SIZE, data.get("plant_size_mw"))
        self._fill(self.TT_LAND_QUANTUM_USABLE, data.get("land_quantum_usable_acres"))
        self._fill(self.TT_SHAPE_INDEX, data.get("shape_index"))
        self._select(self.TT_FIT_FOR_TRACKER, data.get("fit_for_tracker"))
        self._select(self.TT_SITE_VISIT_STATUS, data.get("site_visit_status"))
        self._fill(self.TT_SITE_VISIT_DATE, data.get("site_visit_date"))
        self._fill(self.TT_EASE_OF_ACQUISITION, data.get("ease_of_acquisition"))
        self._fill(self.TT_GHI, data.get("ghi"))
        self._fill(self.TT_ALBEDO, data.get("albedo"))
        self._fill(self.TT_DC_FEASIBLE, data.get("dc_feasible"))
        self._fill(self.TT_ENERGY_YIELD, data.get("energy_yield"))
        self._fill(self.TT_PLF_OF_PLANT, data.get("plf_of_plant"))
        self._select(
            self.TT_ENVIRONMENT_STUDY_STATUS,
            data.get("environment_study_status"),
        )
        self._select(
            self.TT_GO_NO_GO_ENVIRONMENT,
            data.get("go_no_go_environment_team"),
        )
        self._select(
            self.TT_GO_NO_GO_ENGINEERING,
            data.get("go_no_go_engineering_team"),
        )
        return self

    def click_step2_save(self):
        # Step 2's submit is a plain "Save" (Step 1 used
        # "Create Land Bank"). Exact match so we can't hit some other
        # button containing the word "Save".
        self.page.get_by_role("button", name="Save", exact=True).click()
        return self

    def wait_for_step2_save_success(self, timeout: int = 15000):
        """
        Waits for the Step 2 confirmation banner and returns its text.

        CREATE mode says "Step 2 saved. Proceed to Step 3."; EDIT mode
        says "Step 2 updated. Proceed to Step 3." - accept both, but
        require the "Step 2" prefix so the Step 1 banner
        ("Step 1 saved/updated. Proceed to Step 2.") can never satisfy
        the wait - that would let the suite pass before the Step 2
        response arrived.
        """
        banner = self.page.get_by_text(
            re.compile(r"Step 2[^.]*(saved|updated)", re.I)
        ).or_(
            self.page.get_by_text("saved successfully", exact=False)
        ).first
        banner.wait_for(state="visible", timeout=timeout)
        return banner.inner_text().strip()

    def assert_step2_saved(self):
        """Step 2 must confirm the save AND show no validation errors."""
        message = self.wait_for_step2_save_success()
        errors = self.visible_validation_errors()
        assert not errors, (
            "Step 2 was rejected after clicking 'Save'. "
            f"Visible validation errors: {errors}"
        )
        return message

    # =================================================================
    # STEP 3: Commercial/Financial Details
    # =================================================================
    def wait_for_step3(self, timeout: int = 15000):
        """
        Waits until the Step 3 "Commercial/Financial Details" panel is
        active. After a successful Step 2 save the page announces
        "Step 2 saved. Proceed to Step 3." and switches the wizard by
        itself; clicking the stepper is only a fallback.
        """
        first_field = self._field(self.CF_BASIC_COST_SALE)
        try:
            first_field.wait_for(state="visible", timeout=timeout)
        except Exception:
            # The stepper's own label is "3 BD Team Details" (only the
            # panel is called "Commercial/Financial Details"), so clicking
            # that text never worked and the wait below timed out - seen
            # in probe_output/tc_attrs.log. Target the stepper's href
            # first, keep the text click as the last resort.
            try:
                stepper = self.page.locator('a[href$="edit-step3"], a[href*="step3"]')
                stepper.first.wait_for(state="visible", timeout=3000)
                stepper.first.click()
            except Exception:
                self.page.get_by_text(
                    "Commercial/Financial Details", exact=False
                ).first.click()
            first_field.wait_for(state="visible", timeout=timeout)
        return self

    def fill_commercial_financial(self, data: dict):
        """
        Fills every Step 3 field.

        15 text inputs + one Select2 dropdown (Commercial Negotiation),
        driven exactly like Steps 1/2: native <select> + 'change' event.
        """
        self.wait_for_step3()
        self._fill(self.CF_BASIC_COST_SALE, data.get("basic_cost_sale"))
        self._fill(self.CF_BASIC_COST_LEASE, data.get("basic_cost_lease"))
        self._fill(self.CF_STAMP_DUTY_SALE, data.get("stamp_duty_reg_charges_sale"))
        self._fill(self.CF_STAMP_DUTY_LEASE, data.get("stamp_duty_reg_charges_lease"))
        self._fill(self.CF_OTHER_STAT_CHARGES, data.get("other_statutory_charges"))
        self._fill(self.CF_SERVICE_FEE_SALE, data.get("service_fee_sale"))
        self._fill(self.CF_SERVICE_FEE_LEASE, data.get("service_fee_lease"))
        self._fill(self.CF_LEASE_TENURE_YEARS, data.get("lease_tenure_years"))
        self._fill(self.CF_LEASE_ESCALATION_RATE, data.get("lease_escalation_rate"))
        self._fill(
            self.CF_LEASE_ESCALATION_FREQUENCY,
            data.get("lease_escalation_frequency_years"),
        )
        self._fill(self.CF_TOTAL_LAND_COST, data.get("total_land_cost_for_bd"))
        self._fill(self.CF_SERVICE_FEE, data.get("service_fee"))
        self._select(
            self.CF_COMMERCIAL_NEGOTIATION,
            data.get("commercial_negotiation"),
        )
        self._fill(self.CF_LAND_COST_FOR_BD, data.get("land_cost_for_bd"))
        self._fill(
            self.CF_LAND_BEING_CONSIDERED_FOR,
            data.get("land_being_considered_for"),
        )
        self._fill(self.CF_TARIFF_DUE_TO_THIS_LAND, data.get("tariff_due_to_this_land"))
        return self

    def click_step3_save(self):
        # Every wizard step renders its own "Save" button inside its tab
        # pane, so scope to the ACTIVE pane instead of an exact-name role
        # locator (which could resolve to two buttons in strict mode).
        self.page.locator(
            "div.tab-pane.show.active button, div.tab-pane.active button"
        ).first.click()
        return self

    def wait_for_step3_save_success(self, timeout: int = 15000):
        """
        Waits for the final-submit confirmation and returns its text.

        CREATE mode shows "Land Bank created successfully"; EDIT mode
        shows "Land Bank updated successfully" (both confirmed by the
        probes: scripts/probe_step3.py --save and scripts/probe_edit.py)
        after navigating to the Land Proposals list (/land-banks).
        Primary match accepts both wordings; the Step 3 / generic
        variants are kept defensively so the Step 1/Step 2 banners can
        never satisfy the wait. If the alert ever auto-dismisses before
        we see it, the redirect to the list page alone proves the save.
        """
        banner = self.page.get_by_text(
            re.compile(r"Land Bank (created|updated) successfully", re.I)
        ).or_(
            self.page.get_by_text(re.compile(r"Step 3[^.]*(saved|updated)", re.I))
        ).or_(
            self.page.get_by_text("saved successfully", exact=False)
        ).first
        try:
            banner.wait_for(state="visible", timeout=timeout)
            message = banner.inner_text().strip()
        except Exception:
            # No banner (e.g. auto-dismissed): the redirect alone proves
            # the save - we left the create wizard for the list page.
            self.page.wait_for_url(
                re.compile(r".*/land-banks(/|\?|$)"), timeout=5000
            )
            return f"Redirected to {self.page.url} (no banner visible)"
        return message

    def assert_step3_saved(self):
        """Step 3 must confirm the save AND show no validation errors."""
        message = self.wait_for_step3_save_success()
        errors = self.visible_validation_errors()
        assert not errors, (
            "Step 3 was rejected after clicking 'Save'. "
            f"Visible validation errors: {errors}"
        )
        return message
