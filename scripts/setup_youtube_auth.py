"""One-time YouTube OAuth 2.0 setup script.

Prerequisites:
1. Create a Google Cloud project at https://console.cloud.google.com/
2. Enable "YouTube Data API v3"
3. Create OAuth 2.0 Client ID (Desktop app)
4. Download credentials.json to the project root

Usage:
    python scripts/setup_youtube_auth.py

This opens a browser for Google login, then saves token.json
for automated uploads (auto-refreshes via refresh_token).
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> None:
    if not CREDENTIALS_FILE.exists():
        print(f"ERROR: {CREDENTIALS_FILE} not found.")
        print("Download it from Google Cloud Console → APIs & Services → Credentials")
        sys.exit(1)

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    print(f"Token saved: {TOKEN_FILE}")
    print("YouTube uploads are now authorized.")


if __name__ == "__main__":
    main()
