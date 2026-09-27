"""
Simple config for the LAMS UAT environment.
Edit these values if the URL, credentials, or test OTP change.
"""

BASE_URL = "https://uat.lamsapp.com/php8_4/product/advanced/current/auth/login"

LOGIN_EMAIL = "admin@lams.com"
LOGIN_PASSWORD = "123456"

# Fixed test OTP for this UAT account (captcha is disabled here too,
# so we don't handle it at all).
OTP = "123456"

INDUSTRY = "Renewable"
