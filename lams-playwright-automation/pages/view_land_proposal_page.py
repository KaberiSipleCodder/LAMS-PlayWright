"""
Page Object for the READ-ONLY "View Land Proposal" screen
(``.../land-banks/<uuid>`` - the list row action menu -> View).

Discovered with ``scripts/probe_view.py``; raw evidence lives in
``probe_output/view_*.json|html|png``. What the live page actually is:

* The URL is the list route plus the record id and NOTHING else - no
  ``/edit``, no query string (Edit is ``<uuid>/edit``, View is ``<uuid>``).
* It renders its data as label/value blocks, not as form fields::

      <div class="detail-item">
          <div class="detail-label">State</div>
          <div class="detail-value">Bihar</div>
      </div>

  56 of those pairs were captured (``view_detail.json``). The CSS
  uppercases ``.detail-label``, so ``innerText`` reads "STATE" while
  ``textContent`` reads "State" - every label lookup below is therefore
  case-insensitive.
* The document contains **zero** ``input`` / ``select`` / ``textarea``
  elements and zero ``type="submit"`` controls: the page cannot be used
  to change anything. That (not the presence of a ``readonly``
  attribute) is what the read-only assertions check.
* Headings: ``h4.approval-process`` "View Land Proposal" plus the three
  section headings "Land Bank Details" (Step 1 data), "Engineering Team
  Details" (Step 2) and "BD Team Details" (Step 3).
* The only VISIBLE action is the "Back to List" link (``.../land-banks``).
  (The layout also carries a hidden modal "Delete" button, which has no
  ``type="submit"`` attribute and is never visible - see
  ``visible_action_texts()``.)
* The proposal NAME is not rendered anywhere on this page, so "the right
  record was opened" is proven by the URL's uuid (returned by
  ``LandProposalsPage.click_view_existing()``) plus the stored values.
"""

import re


class ViewLandProposalPage:

    # Exact .detail-label texts (Title Case in the DOM), captured in
    # probe_output/view_detail.json.
    STATE = "State"
    DISTRICT = "District"
    VILLAGE = "Village"
    LAND_TYPE = "Land Type"
    COMPANY = "Company"
    PROJECT_TYPE = "Project Type"
    APPROVED_STATUS = "Approved Status"
    PLANT_SIZE = "Plant Size"
    SHAPE_INDEX = "Shape Index"
    SITE_VISIT_DATE = "Site Visit Date"
    DC_FEASIBLE = "DC Feasible"
    BASIC_COST_SALE = "Land Basic Cost Sale"
    LEASE_TENURE = "Lease Tenure (Years)"
    LAND_BEING_CONSIDERED_FOR = "Land Being Considered For"
    TARIFF_DUE_TO_THIS_LAND = "Tariff Due to this Land"

    def __init__(self, page):
        self.page = page
        self.heading = page.locator(
            "h4.approval-process", has_text="View Land Proposal"
        )
        self.back_to_list_link = page.get_by_role("link", name="Back to List")

    # -----------------------------------------------------------------
    # Page identity
    # -----------------------------------------------------------------
    def is_loaded(self, timeout: int = 15000) -> bool:
        """
        True when the read-only page is on screen.

        Unlike the other page objects this never waits forever: the
        negative tests call it on 404 / guard pages, where the heading
        must simply never appear.
        """
        try:
            self.heading.wait_for(state="visible", timeout=timeout)
        except Exception:
            return False
        return self.heading.is_visible()

    def has_section(self, name: str, timeout: int = 5000) -> bool:
        """True when a section heading (e.g. "BD Team Details") is visible."""
        heading = self.page.locator("h3.icon-text", has_text=name).first
        try:
            heading.wait_for(state="visible", timeout=timeout)
        except Exception:
            return False
        return True

    # -----------------------------------------------------------------
    # The data it renders
    # -----------------------------------------------------------------
    def detail_item(self, label: str):
        """
        The ``.detail-item`` block whose label is exactly ``label``.

        Matched case-insensitively because the page's CSS uppercases the
        label ("State" -> "STATE" on screen and in ``innerText``).
        """
        return self.page.locator(".detail-item").filter(
            has=self.page.locator(
                ".detail-label",
                has_text=re.compile(rf"^{re.escape(label)}$", re.I),
            )
        ).first

    def detail(self, label: str, timeout: int = 5000) -> str:
        """The value shown for ``label`` ("" when that label is absent)."""
        item = self.detail_item(label)
        try:
            item.wait_for(state="visible", timeout=timeout)
        except Exception:
            return ""
        return item.locator(".detail-value").first.inner_text().strip()

    def detail_number(self, label: str) -> float:
        """
        ``detail()`` as a number - the page pads numeric values
        ("50.0000000000", "500000.00"), so tests compare numbers.
        """
        raw = self.detail(label)
        match = re.search(r"-?\d+(?:\.\d+)?", raw)
        assert match, f"{label!r} is not numeric on the view page: {raw!r}"
        return float(match.group(0))

    def all_details(self) -> dict:
        """
        Every label -> value pair on the page, as displayed.

        Used to compare a full page state before/after a write attempt
        (read via ``textContent`` so the CSS never changes the comparison).
        """
        return self.page.evaluate(
            """() => {
                const out = {};
                document.querySelectorAll('.detail-item').forEach(item => {
                    const label = item.querySelector('.detail-label');
                    const value = item.querySelector('.detail-value');
                    if (label || value) {
                        out[(label ? label.textContent : '').trim()] =
                            (value ? value.textContent : '').trim();
                    }
                });
                return out;
            }"""
        )

    # -----------------------------------------------------------------
    # Read-only guarantees
    # -----------------------------------------------------------------
    def form_control_count(self) -> int:
        """
        How many ``input`` / ``select`` / ``textarea`` elements the page
        holds - visible or not. The live page has NONE, which is a much
        stronger statement than "every field is readonly".
        """
        return self.page.locator("input, select, textarea").count()

    def submit_control_count(self) -> int:
        """
        How many real submit controls the page declares.

        Counts the ``type="submit"`` ATTRIBUTE, not the DOM ``type``
        *property* (which reports "submit" for any plain ``<button>``) -
        the hidden layout modal button would otherwise be counted.
        """
        return self.page.locator(
            'button[type="submit"], input[type="submit"]'
        ).count()

    def visible_action_texts(self) -> list:
        """Text of every visible button / link-styled-as-button on screen."""
        return self.page.evaluate(
            """() => {
                const visible = e => {
                    const r = e.getBoundingClientRect();
                    const s = window.getComputedStyle(e);
                    return r.width > 0 && r.height > 0
                        && s.visibility !== 'hidden' && s.display !== 'none';
                };
                return Array.from(document.querySelectorAll('button, a.btn'))
                    .filter(visible)
                    .map(b => (b.innerText || b.value || '').trim())
                    .filter(t => t);
            }"""
        )

    def has_write_action(self) -> bool:
        """
        True when a visible control could change data (Save / Update /
        Create / Submit / Delete / Approve / Convert). Must stay False:
        the read-only page may only offer "Back to List".
        """
        return self.page.locator(
            "button:visible, a.btn:visible, a:visible"
        ).filter(
            has_text=re.compile(
                r"save|update|create|submit|delete|approve|convert", re.I
            )
        ).count() > 0

    def back_to_list(self):
        """Follows "Back to List" back to the Land Proposals list."""
        self.back_to_list_link.click()
        self.page.wait_for_url(re.compile(r".*/land-banks/?$"))
        return self



    # The three sections of the read-only page, in DOM order.
    SECTIONS = ("Land Bank Details", "Engineering Team Details", "BD Team Details")
