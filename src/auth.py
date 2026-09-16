"""OAuth handling for Gmail + Google Tasks.

Both APIs live in the same Google Cloud project, so one credentials.json
and one token.json cover both. token.json is created on first run and
auto-refreshed after that.
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Requested up front so we never have to re-consent when Step 3 lands.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/tasks",
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def get_credentials():
    """Return valid OAuth credentials, refreshing or prompting as needed."""
    creds = None

    # token.json holds the access + refresh tokens from a previous run.
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Normal path after the first run: silent refresh, no browser.
            creds.refresh(Request())
        else:
            # First run only: opens a browser for the consent screen.
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds