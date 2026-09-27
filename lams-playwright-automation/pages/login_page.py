"""
Page Object for the Login page.

Captcha is intentionally NOT handled here - this UAT test account has it
disabled. If your environment enforces a real captcha, this page object
will need a solving/bypass strategy added before it can log in reliably.
"""


class LoginPage:
    def __init__(self, page):
        self.page = page
        self.email_input = page.locator("input[type='text']").first
        self.password_input = page.locator("input[type='password']")
        self.sign_in_button = page.get_by_role("button", name="Sign In")

    def open(self, base_url: str):
        self.page.goto(base_url)
        return self

    def login(self, email: str, password: str):
        self.email_input.fill(email)
        self.password_input.fill(password)
        self.sign_in_button.click()
        # Wait for navigation to the OTP (Two Step Verification) screen.
        self.page.wait_for_url("**/validate-otp*")
        return self
