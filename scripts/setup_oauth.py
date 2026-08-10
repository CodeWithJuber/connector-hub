#!/usr/bin/env python3
"""Interactive OAuth2 setup wizard for the Gmail connector (connectors/email/gmail_oauth.py).

Run this LOCALLY (it needs a browser). For each Gmail account it:
  1. prints the Google consent URL (scopes: gmail.modify + gmail.send),
  2. accepts the pasted authorization code (or full redirect URL),
  3. exchanges the code for tokens,
  4. appends GMAIL_REFRESH_TOKEN_<LABEL>=... to the hub .env file.

Stdlib only. Secrets are never printed back after entry.
"""
import argparse
import getpass
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error

TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
# Loopback redirect: Google shows the result by redirecting the browser to
# http://localhost/?code=... — the user pastes the URL (or just the code) back.
REDIRECT_URI = "http://localhost"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

DEFAULT_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")

SETUP_INSTRUCTIONS = """
======================================================================
 Gmail OAuth setup — one-time per Google Cloud project + account
======================================================================
You need a Google Cloud OAuth client (Desktop app type):

  1. Go to https://console.cloud.google.com/ and create (or select) a project.
  2. Enable the Gmail API:
       APIs & Services > Library > search "Gmail API" > Enable.
  3. Configure the consent screen:
       APIs & Services > OAuth consent screen > External (or Internal)
       > fill app name + your email > add scopes:
         https://www.googleapis.com/auth/gmail.modify
         https://www.googleapis.com/auth/gmail.send
       > under "Test users" add every Gmail address you will connect.
  4. Create credentials:
       APIs & Services > Credentials > Create Credentials
       > OAuth client ID > Application type: "Desktop app".
  5. Copy the Client ID and Client Secret shown.

You will paste those two values below (they are stored only in your .env,
which is gitignored, if you choose to save them).
======================================================================
"""


def parse_code(pasted):
    """Accept a raw auth code or a full redirect URL and return the code."""
    pasted = pasted.strip()
    if pasted.startswith("http"):
        query = urllib.parse.urlparse(pasted).query
        params = urllib.parse.parse_qs(query)
        if "error" in params:
            sys.exit(f"Google returned an error: {params['error'][0]}")
        if "code" in params:
            return params["code"][0]
        sys.exit("Could not find 'code' in the pasted URL. Try pasting just the code.")
    return pasted


def post_form(data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"Token endpoint error HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
    except urllib.error.URLError as e:
        sys.exit(f"Cannot reach {TOKEN_URL}: {e.reason}")


def exchange_code(client_id, client_secret, code):
    return post_form({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })


def upsert_env(path, key, value):
    """Append key=value to .env, replacing the line if the key already exists."""
    lines = []
    if os.path.exists(path):
        with open(path) as f:
            lines = f.read().splitlines()
    prefix = key + "="
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return replaced


def consent_url(client_id, email):
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    if email:
        params["login_hint"] = email
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def main():
    parser = argparse.ArgumentParser(
        description="Interactive Gmail OAuth2 setup wizard for the Omni Connector Hub.",
        epilog="Stdlib only; writes GMAIL_REFRESH_TOKEN_<LABEL> lines to the .env file.",
    )
    parser.add_argument(
        "env_path", nargs="?", default=os.path.abspath(DEFAULT_ENV_PATH),
        help="path to the .env file to update (default: <connector-hub>/.env)",
    )
    args = parser.parse_args()
    env_path = args.env_path

    print(SETUP_INSTRUCTIONS)
    print(f".env file: {env_path}\n")

    client_id = os.environ.get("GOOGLE_CLIENT_ID") or input("Google Client ID: ").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET") or getpass.getpass(
        "Google Client Secret (hidden): ").strip()
    if not client_id or not client_secret:
        sys.exit("Client ID and Client Secret are required.")

    if input("Save GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET to .env? [y/N] ").strip().lower() == "y":
        upsert_env(env_path, "GOOGLE_CLIENT_ID", client_id)
        upsert_env(env_path, "GOOGLE_CLIENT_SECRET", client_secret)
        print("  saved.")

    existing_pairs = []
    while True:
        print("\n--- Add a Gmail account (empty label to finish) ---")
        label = input("Account label (e.g. work): ").strip()
        if not label:
            break
        label = label.upper()
        email = input(f"Gmail address for '{label.lower()}' (optional, used as login hint): ").strip()

        url = consent_url(client_id, email)
        print("\nOpen this URL in your browser and approve access:\n")
        print(f"  {url}\n")
        print("After approving, the browser will be redirected to a localhost URL")
        print("that fails to load — that is expected. Copy the FULL URL from the")
        print("address bar (it contains ?code=...) and paste it below.")
        pasted = input("\nPaste redirect URL or auth code: ")
        code = parse_code(pasted)

        tokens = exchange_code(client_id, client_secret, code)
        refresh = tokens.get("refresh_token")
        if not refresh:
            sys.exit(
                "No refresh_token in the response. This usually means consent was "
                "already granted without prompt=consent; revoke access at "
                "https://myaccount.google.com/permissions and re-run this wizard."
            )

        key = f"GMAIL_REFRESH_TOKEN_{label}"
        replaced = upsert_env(env_path, key, refresh)
        print(f"  wrote {key}=<hidden> to .env ({'updated' if replaced else 'appended'}).")
        if email:
            existing_pairs.append(f"{label.lower()}:{email}")

    if existing_pairs:
        # merge with any GMAIL_ACCOUNTS line already present
        current = os.environ.get("GMAIL_ACCOUNTS", "")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("GMAIL_ACCOUNTS="):
                        current = line.strip().split("=", 1)[1]
        merged = [p for p in current.split(",") if p.strip()] if current else []
        for pair in existing_pairs:
            lbl = pair.split(":", 1)[0]
            merged = [p for p in merged if not p.startswith(lbl + ":")]
            merged.append(pair)
        upsert_env(env_path, "GMAIL_ACCOUNTS", ",".join(merged))
        print(f"\nUpdated GMAIL_ACCOUNTS={','.join(merged)}")

    print("\nDone. The 'gmail' connector should now leave mock mode once")
    print("GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and the refresh tokens are in the environment.")


if __name__ == "__main__":
    main()
