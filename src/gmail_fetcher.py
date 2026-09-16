"""Fetch emails received since the last successful run.

Run directly to test:  python -m src.gmail_fetcher
"""

import base64
import os
import re
import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.auth import get_credentials

LAST_RUN_FILE = "last_run.txt"
DEFAULT_LOOKBACK_SECONDS = 24 * 60 * 60  # first-run fallback: last 24 hours


# ---------- timestamp handling ----------

def get_last_run_timestamp():
    """Epoch seconds of the last successful run, or None if never run."""
    if not os.path.exists(LAST_RUN_FILE):
        return None
    try:
        with open(LAST_RUN_FILE) as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        # Corrupt or unreadable file — treat as a first run rather than crash.
        return None


def write_last_run_timestamp(ts):
    """Record a successful run. Called by main.py only after the full batch."""
    with open(LAST_RUN_FILE, "w") as f:
        f.write(str(int(ts)))


def build_query(last_run_ts=None):
    """Gmail search query for messages after the cutoff.

    Gmail's `after:` accepts a raw epoch-seconds value, which avoids any
    timezone ambiguity you'd get from a YYYY/MM/DD date.
    """
    cutoff = last_run_ts if last_run_ts else int(time.time()) - DEFAULT_LOOKBACK_SECONDS
    return f"after:{cutoff}"


# ---------- body extraction ----------

def _decode(data):
    """Gmail returns body data as URL-safe base64."""
    return base64.urlsafe_b64decode(data.encode("ASCII")).decode("utf-8", errors="replace")


def _strip_html(html):
    """Crude HTML-to-text. Good enough to hand to an LLM; no extra dependency."""
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>", "\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"[ \t]{2,}", " ", text)


def extract_body(payload):
    """Walk the MIME tree and return the message body as plain text.

    Emails are often multipart with both text/plain and text/html versions,
    and can nest several levels deep. We prefer plain text and fall back to
    stripped HTML.
    """
    plain_parts, html_parts = [], []

    def walk(part):
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data:
            if mime == "text/plain":
                plain_parts.append(_decode(data))
            elif mime == "text/html":
                html_parts.append(_decode(data))
        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)

    if plain_parts:
        return "\n".join(plain_parts).strip()
    if html_parts:
        return _strip_html("\n".join(html_parts)).strip()
    return ""


def _header(headers, name):
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


# ---------- main fetch ----------

def fetch_new_emails(service=None, last_run_ts=None, max_results=50):
    """Return a list of dicts: id, subject, sender, date, body."""
    if service is None:
        service = build("gmail", "v1", credentials=get_credentials())

    query = build_query(last_run_ts)
    print(f"[gmail] query: {query}")

    try:
        listing = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
    except HttpError as e:
        print(f"[gmail] ERROR listing messages: {e}")
        return []

    message_ids = [m["id"] for m in listing.get("messages", [])]
    print(f"[gmail] {len(message_ids)} message(s) matched")

    emails = []
    for mid in message_ids:
        # One failing message shouldn't kill the batch.
        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=mid, format="full")
                .execute()
            )
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            emails.append({
                "id": mid,
                "subject": _header(headers, "Subject"),
                "sender": _header(headers, "From"),
                "date": _header(headers, "Date"),
                "body": extract_body(payload),
            })
        except HttpError as e:
            print(f"[gmail] ERROR fetching message {mid}: {e}")
            continue

    return emails


if __name__ == "__main__":
    # Test harness: prints what WOULD be fetched. Writes nothing.
    results = fetch_new_emails(last_run_ts=get_last_run_timestamp())
    for i, e in enumerate(results, 1):
        print("\n" + "=" * 70)
        print(f"[{i}] FROM:    {e['sender']}")
        print(f"    SUBJECT: {e['subject']}")
        print(f"    DATE:    {e['date']}")
        print(f"    BODY ({len(e['body'])} chars):")
        print("-" * 70)
        print(e["body"][:800])
        if len(e["body"]) > 800:
            print(f"... [{len(e['body']) - 800} more chars]")