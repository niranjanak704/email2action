"""Ties Gmail fetching, Gemini classification, and Task creation together.

This is the file GitHub Actions will run every morning.
"""

import sys
import time

from src.gmail_fetcher import fetch_new_emails, get_last_run_timestamp, write_last_run_timestamp
from src.gemini_processor import classify_emails
from src.tasks_creator import create_tasks_from_emails


def main():
    run_started_at = int(time.time())

    last_run_ts = get_last_run_timestamp()
    print(f"[main] last run: {last_run_ts}")

    emails = fetch_new_emails(last_run_ts=last_run_ts)
    print(f"[main] fetched {len(emails)} new email(s)")

    if not emails:
        # Nothing new — still a successful run, so still advance the checkpoint.
        write_last_run_timestamp(run_started_at)
        print("[main] no new emails, checkpoint advanced, done")
        return 0

    actionable = classify_emails(emails)
    print(f"[main] {len(actionable)} of {len(emails)} flagged as actionable")

    created, failed = create_tasks_from_emails(actionable)
    print(f"[main] {created} task(s) created, {failed} failed")

    # Advance the checkpoint using the timestamp from when this run STARTED,
    # not "now" — any email that arrived while we were processing should be
    # picked up next run, not silently skipped.
    write_last_run_timestamp(run_started_at)
    print("[main] checkpoint advanced, done")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())