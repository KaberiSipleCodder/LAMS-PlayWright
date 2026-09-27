"""
Page Object for the "Select Your Industry Type" screen and the
confirmation modal ("<Industry> Selected" / "Proceed") that follows it.
"""


class IndustrySelectionPage:
    def __init__(self, page):
        self.page = page
        self.heading = page.get_by_text("Select Your Industry Type")
        self.proceed_button = page.get_by_role("button", name="Proceed")

    def select_industry(self, industry_name: str):
        self.heading.wait_for(state="visible")
        select_button = self.page.get_by_role("button", name=f"Select {industry_name}")

        # The industry card <div> visually overlaps the <button>, which can
        # cause a normal click to land on the card instead of the button.
        # A JS click bypasses that overlap issue.
        select_button.evaluate("el => el.click()")

        # Wait for the confirmation modal, e.g. "Renewable Selected".
        self.page.get_by_text(f"{industry_name} Selected").wait_for(state="visible")
        return self

    def confirm_proceed(self):
        self.proceed_button.click()
        self.page.wait_for_url("**/dashboard*")
        return self
