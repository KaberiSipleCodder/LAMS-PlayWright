"""
Shared utilities for the LAMS suite.

Nothing in this package contains page/locator logic (that lives in
``pages/``) - it only supports the *execution* side of the framework:

    paths.py             where screenshots/reports live + test identity
                         (test case id, module/page name)
    screenshots.py       captures the PNG for a failed test
    failure_records.py   builds + writes the per-module failure details
    summary.py           the end-of-run Total/Passed/Failed/Skipped block
    reporting.py         the small result registry the pytest hooks in
                         tests/conftest.py talk to

Keeping it here (instead of inside conftest.py) means the tests stay
declarative and the reporting rules live in one readable place.
"""
