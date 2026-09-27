"""
Page Object for the Land Acquisition Dashboard.
"""


class DashboardPage:
    def __init__(self, page):
        self.page = page
        self.heading = page.get_by_text("Land Acquisition Dashboard")
        # The sidebar label is sometimes truncated on screen
        # ("Land Identification ..."), so match on a partial, case-sensitive
        # substring instead of the full exact text.
        self.land_identification_nav = page.get_by_text("Land Identification", exact=False)

    def is_loaded(self) -> bool:
        self.heading.wait_for(state="visible")
        return self.heading.is_visible()

    def go_to_land_identification(self):
        self.land_identification_nav.click()
        self.page.wait_for_url("**/land-banks*")
        return self
