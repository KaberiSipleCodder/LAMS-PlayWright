"""
Rerun ONLY the test cases that failed in the previous run.

This is a MANUAL, single-pass rerun - nothing retries automatically and nothing
can loop: the script runs pytest once over the failures that
``tests/conftest.py`` recorded in ``reports/failed_tests.txt`` and then stops.
After it finishes, the file is overwritten by that run's own result, so running
it again only ever re-tests what is still broken.

Usage (project root, venv active):

    python scripts/run_failed_tests.py                 # rerun every failure
    python scripts/run_failed_tests.py --module land_bank
    python scripts/run_failed_tests.py --slowmo=0       # extra pytest args
    python scripts/run_failed_tests.py --last-failed    # use pytest's own --lf
"""

import argparse
import os
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FAILED_FILE = os.path.join(_ROOT, "reports", "failed_tests.txt")


def read_failed_node_ids() -> list:
    """The node ids written at the end of the last run (comments ignored)."""
    if not os.path.isfile(_FAILED_FILE):
        return []

    node_ids = []
    with open(_FAILED_FILE, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#"):
                node_ids.append(line)
    return node_ids


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rerun only the tests that failed in the last run."
    )
    parser.add_argument(
        "--module",
        help="only rerun failures inside one module folder, e.g. land_bank",
    )
    parser.add_argument(
        "--last-failed",
        action="store_true",
        help="let pytest pick the failures from its own cache (--lf) instead of "
        "reports/failed_tests.txt",
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="anything else is passed straight to pytest, e.g. --slowmo=0",
    )
    args = parser.parse_args()

    command = [sys.executable, "-m", "pytest"]

    if args.last_failed:
        command.append("--lf")
    else:
        node_ids = read_failed_node_ids()
        if args.module:
            wanted = args.module.replace("\\", "/").strip("/")
            node_ids = [
                node_id
                for node_id in node_ids
                if f"/{wanted}/" in node_id.replace("\\", "/")
            ]
        if not node_ids:
            print(
                f"Nothing to rerun: no failed test cases recorded in "
                f"{os.path.relpath(_FAILED_FILE, _ROOT)}"
                + (f" for module '{args.module}'." if args.module else ".")
            )
            return 0
        print(f"Rerunning {len(node_ids)} failed test case(s):")
        for node_id in node_ids:
            print(f"  - {node_id}")
        command += node_ids

    command += args.pytest_args
    print("\n" + " ".join(command) + "\n")
    return subprocess.call(command, cwd=_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
