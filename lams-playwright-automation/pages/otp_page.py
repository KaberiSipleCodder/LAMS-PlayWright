"""
Page Object for the Two-Step Verification (OTP) page.

The 6-digit code is entered into 6 separate single-digit boxes rather than
one text field.
"""


class OtpPage:
    def __init__(self, page):
        self.page = page
        # Each digit box matches this selector (confirmed against the real
        # markup during a previous debugging session - see the build log).
        self.otp_boxes = page.locator("input.auth-input.numeral-mask[maxlength='1']")
        self.verify_button = page.get_by_role("button", name="Verify my account")

    def fill_otp(self, otp: str):
        """
        Types ``otp`` into the 6 single-digit boxes WITHOUT submitting.

        Split out of ``enter_otp()`` for the negative tests: a wrong code
        never gets past this page, so they must fill + submit themselves
        and then assert the error text instead of waiting for the
        post-success redirect that ``enter_otp()`` expects.
        """
        assert len(otp) == 6, "OTP must be exactly 6 digits"

        self.otp_boxes.first.wait_for(state="visible")

        # The page JS (two-step-auth.js) concatenates the 6 single-digit
        # boxes into a hidden input (#otp-input / [name="otp"]) only in a
        # handler bound to the "keyup" event. Playwright's .fill() sets the
        # value directly and does NOT emit keyup, so filling alone leaves the
        # hidden field empty and the form fails validation with
        # "Please enter OTP". Fill each box, then dispatch keyup so the page's
        # own concatenation handler runs, exactly as with real typing.
        for i, digit in enumerate(otp):
            box = self.otp_boxes.nth(i)
            box.fill(digit)
            box.dispatch_event("keyup")

        # The submit handler reads #otp-input.value. Guarantee it holds the
        # full code even if the keyup handler didn't run for any reason.
        hidden = self.page.locator("input[name='otp']")
        hidden.wait_for(state="attached")
        if hidden.input_value() != otp:
            self.page.eval_on_selector(
                "input[name='otp']",
                "(el, v) => { el.value = v;"
                " el.dispatchEvent(new Event('input', { bubbles: true })); }",
                otp,
            )
        return self

    def submit(self):
        """
        Clicks "Verify my account" and returns immediately.

        No success wait here on purpose - the negative tests submit a
        blank/wrong code, which keeps the page on /auth/validate-otp.
        """
        self.verify_button.click()
        return self

    def enter_otp(self, otp: str):
        self.fill_otp(otp)
        self.submit()
        # After a successful (first-time) login, LAMS routes to the
        # "Select Your Industry Type" screen before the dashboard.
        self.page.wait_for_url("**/select-types*")
        return self
