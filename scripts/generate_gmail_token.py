"""
One-time Gmail OAuth2 authorization script.
Run this locally to generate a GMAIL_REFRESH_TOKEN.

Usage:
  1. Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in your .env
  2. Run: uv run python scripts/generate_gmail_token.py
  3. A browser window will open - log in with akhileshwarsecondacc@gmail.com
  4. Copy the REFRESH TOKEN printed at the end into your .env and HF Space secrets
"""

import json
import os
import urllib.parse
import urllib.request
import webbrowser
import http.server
import threading
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ.get("GMAIL_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GMAIL_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8080"
SCOPE = "https://www.googleapis.com/auth/gmail.send"

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be set in your .env file.")
    exit(1)

# Store auth code
auth_code_holder = {"code": None}


class AuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            auth_code_holder["code"] = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
            <html><body style='font-family:sans-serif; padding:40px; background:#0f1d2c; color:#e2e8f0;'>
            <h2 style='color:#38bdf8'>Crown & Crest Gmail Authorization</h2>
            <p>Authorization successful! You can close this window and return to the terminal.</p>
            </body></html>
            """)
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing code parameter")

    def log_message(self, format, *args):
        pass  # Suppress server logs


def run_server(httpd):
    httpd.handle_request()


# Step 1: Build authorization URL
auth_params = {
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "response_type": "code",
    "scope": SCOPE,
    "access_type": "offline",
    "prompt": "consent",
}
auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(auth_params)

print("\n" + "="*60)
print("  Crown & Crest - Gmail OAuth2 Setup")
print("="*60)
print("\nStep 1: Opening Google login in your browser...")
print("        Log in with: akhileshwarsecondacc@gmail.com")
print("\nIf the browser doesn't open, visit this URL manually:")
print(f"\n  {auth_url}\n")

# Start local server BEFORE opening browser
httpd = http.server.HTTPServer(("localhost", 8080), AuthHandler)
server_thread = threading.Thread(target=run_server, args=(httpd,))
server_thread.daemon = True
server_thread.start()

webbrowser.open(auth_url)

print("Waiting for authorization callback...")
server_thread.join(timeout=120)

if not auth_code_holder["code"]:
    print("ERROR: No authorization code received. Did the browser open?")
    exit(1)

print(f"\nAuthorization code received!")

# Step 2: Exchange code for tokens
token_data = urllib.parse.urlencode({
    "code": auth_code_holder["code"],
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "grant_type": "authorization_code",
}).encode("utf-8")

token_req = urllib.request.Request(
    "https://oauth2.googleapis.com/token",
    data=token_data,
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    method="POST"
)

try:
    with urllib.request.urlopen(token_req) as response:
        token_response = json.loads(response.read().decode("utf-8"))
except Exception as e:
    print(f"ERROR exchanging code for token: {e}")
    exit(1)

refresh_token = token_response.get("refresh_token")
if not refresh_token:
    print("ERROR: No refresh token returned.")
    print("Full response:", token_response)
    exit(1)

print("\n" + "="*60)
print("  SUCCESS! Your Gmail Refresh Token:")
print("="*60)
print(f"\n  {refresh_token}\n")
print("="*60)
print("\nNext steps:")
print("  1. Add to your .env file:")
print(f"       GMAIL_REFRESH_TOKEN={refresh_token}")
print("\n  2. Add to your Hugging Face Space secrets:")
print(f"       Key:   GMAIL_REFRESH_TOKEN")
print(f"       Value: {refresh_token}")
print("\n  3. Also add GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET to HF secrets.")
print("="*60 + "\n")
