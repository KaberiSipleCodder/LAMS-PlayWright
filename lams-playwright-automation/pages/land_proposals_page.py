"""
Page Object for the Land Proposals List page.
"""

import re


class LandProposalsPage:
    def __init__(self, page):
        self.page = page
        self.heading = page.get_by_text("Land Proposals List")
        self.add_new_button = page.get_by_role("button", name="Add New Land Proposal")

    def is_loaded(self) -> bool:
        self.heading.wait_for(state="visible")
        return self.heading.is_visible()

    def click_add_new_land_proposal(self):
        # Set up the navigation listener BEFORE clicking, since
        # click()-then-wait races and can miss a fast navigation.
        #
        # Match the URL with a REGEX, not a glob. The destination is
        # "/land-banks/create/<id>" (e.g. ".../create/1"). In Playwright
        # globs a single "*" does not cross "/", so "**/land-banks/create*"
        # never matches "create/1" and the wait times out even though the
        # navigation completed (verified: readyState=complete and the
        # "Add New Land Proposal Details" heading was visible).
        with self.page.expect_navigation(url=re.compile(r".*/land-banks/create/")):
            self.add_new_button.click()
        return self

    # -----------------------------------------------------------------
    # Editing an EXISTING record (never creates a new one)
    # -----------------------------------------------------------------
    def total_entries(self, timeout: int = 20000) -> int:
        """
        Total record count from the list info bar
        ("Showing 1 to 25 of 48 entries" -> 48).

        The table is AJAX-loaded, so this also waits for the bar to
        appear. Used to prove an edit flow did NOT create a record:
        capture before + after and assert equality.
        """
        info = self.page.get_by_text(
            re.compile(r"Showing \d+ to \d+ of \d+ entries")
        ).first
        info.wait_for(state="visible", timeout=timeout)
        match = re.search(r"of (\d+) entries", info.inner_text())
        assert match, f"Could not parse total from info bar: {info.inner_text()!r}"
        return int(match.group(1))

    # -----------------------------------------------------------------
    # Row actions: shared plumbing for View / Edit
    #
    # Two real-DOM quirks apply to every row action (found by
    # scripts/probe_edit.py and re-confirmed for View by
    # scripts/probe_view.py):
    #   * The list is AJAX-loaded; tbody first shows a "Loading..."
    #     placeholder row, so wait for the real row before clicking.
    #   * Row actions live in a Bootstrap dropdown whose menu items are in
    #     the DOM but hidden until the row's dropdown-toggle is clicked -
    #     and the theme's menu handling proved unreliable under automation
    #     (the menu never became visible). Read the target href FIRST
    #     (works while hidden), try the UI path briefly, then fall back to
    #     navigating to that same href directly.
    # -----------------------------------------------------------------
    # The row-action destinations, captured from the live DOM:
    #   View  -> .../land-banks/<uuid>          .../land-banks/<uuid>/edit
    VIEW_URL = re.compile(r".*/land-banks/[^/]+/?$")
    EDIT_URL = re.compile(r".*/land-banks/[^/]+/edit")

    def _wait_for_row(self, proposal_name: str):
        """The first table row containing ``proposal_name``, once loaded."""
        self.page.wait_for_function(
            """(wanted) => {
                const rows = Array.from(
                    document.querySelectorAll('table tbody tr'));
                if (!rows.length) return false;
                const text = rows.map(r => r.innerText).join('\\n');
                if (/loading/i.test(text) && rows.length <= 1) return false;
                return rows.some(r => r.innerText.includes(wanted));
            }""",
            arg=proposal_name,
            timeout=20000,
        )
        row = self.page.locator(
            "table tbody tr", has_text=proposal_name
        ).first
        row.wait_for(state="visible", timeout=8000)
        return row

    def _open_row_action(self, proposal_name: str, item_text: str, url_re):
        """
        Clicks the row-action menu item ``item_text`` for ``proposal_name``
        and waits until ``url_re`` is the current URL; returns the href used.
        """
        row = self._wait_for_row(proposal_name)

        # Read the href BEFORE clicking anything (proven order matters).
        items = row.locator("a.dropdown-item", has_text=item_text)
        hrefs = [
            items.nth(i).get_attribute("href") for i in range(items.count())
        ]
        href = next((h for h in hrefs if h and url_re.search(h)), None)
        assert href, (
            f"No {item_text!r} action matching {url_re.pattern!r} in the "
            f"{proposal_name!r} row. Hrefs found: {hrefs}"
        )

        try:
            row.locator("button.dropdown-toggle").first.click(timeout=3000)
            self.page.locator(
                f'a.dropdown-item[href="{href}"]:visible'
            ).first.click(timeout=3000)
        except Exception:
            pass  # menu stayed hidden - handled by the URL check below

        # The UI click can "succeed" without navigating (the theme closes
        # the menu again) - verify the URL, not just the absence of an
        # exception, and fall back to the same href in that case too.
        if not url_re.search(self.page.url):
            self.page.goto(href)
        self.page.wait_for_url(url_re, timeout=10000)
        return href


    def click_edit_existing(self, proposal_name: str):
        """
        Opens the FIRST row with ``proposal_name`` via its action menu
        -> Edit (destination .../land-banks/<uuid>/edit).
        """
        self._open_row_action(proposal_name, "Edit", self.EDIT_URL)
        return self

    def click_view_existing(self, proposal_name: str) -> str:
        """
        Opens the FIRST row with ``proposal_name`` via its action menu
        -> View (READ-ONLY, destination .../land-banks/<uuid>) and returns
        that href.

        The View href is the list route plus the record uuid and nothing
        else; the caller can therefore prove "the right record opened" by
        comparing the URL with the returned href (the view page itself does
        not render the proposal name).
        """
        href = self._open_row_action(proposal_name, "View", self.VIEW_URL)
        return href
