"""Browser-free CLI authentication for NotebookLM.

Guides the user through copying cookies from their browser
and saves them in the notebooklm-py storage_state.json format.
No Playwright or browser automation required.
"""

from __future__ import annotations

import json
import os
import re
import sys
from http.cookies import SimpleCookie
from pathlib import Path

# Where notebooklm-py expects its auth state
DEFAULT_STORAGE_DIR = Path(
    os.environ.get("NOTEBOOKLM_HOME", Path.home() / ".notebooklm")
)
STORAGE_FILE = DEFAULT_STORAGE_DIR / "storage_state.json"

NOTEBOOKLM_URL = "https://notebooklm.google.com/"

# Minimum cookie required by notebooklm-py
MINIMUM_REQUIRED = {"SID"}

# Cookies we care about (Google auth cookies)
GOOGLE_AUTH_COOKIES = {
    "SID", "HSID", "SSID", "APISID", "SAPISID",
    "SIDCC", "NID", "OSID",
    "__Secure-1PSID", "__Secure-3PSID",
    "__Secure-1PAPISID", "__Secure-3PAPISID",
    "__Secure-1PSIDTS", "__Secure-3PSIDTS",
    "__Secure-1PSIDCC", "__Secure-3PSIDCC",
}

JS_SNIPPET = """\
// Run this in the browser console on notebooklm.google.com:
// (Note: this only gets non-httpOnly cookies. For full cookies, use Method 2)
document.cookie"""

INSTRUCTIONS = f"""\
╔══════════════════════════════════════════════════════════════╗
║           NotebookLM CLI Authentication                     ║
╚══════════════════════════════════════════════════════════════╝

Open this URL in your browser and log in:

  {NOTEBOOKLM_URL}

Once logged in, copy your cookies using ONE of these methods:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Method 1: Copy as cURL (recommended)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. Open DevTools (F12)
  2. Go to Network tab
  3. Refresh the page (F5)
  4. Right-click the first request (notebooklm.google.com)
  5. Copy > Copy as cURL
  6. Paste the entire curl command below

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Method 2: Copy Cookie header
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. Open DevTools (F12)
  2. Go to Network tab
  3. Refresh the page (F5)
  4. Click the first request (notebooklm.google.com)
  5. In Headers, find "Cookie:" and copy its value
  6. Paste below

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Method 3: Browser extension export (JSON)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Use "EditThisCookie" or similar extension to export
  cookies as JSON array and paste below

"""


def parse_curl_cookies(text: str) -> dict[str, str]:
    """Extract cookies from a 'Copy as cURL' command."""
    cookies: dict[str, str] = {}
    # Match -H 'Cookie: ...' or --header 'Cookie: ...' (single or double quotes)
    patterns = [
        r"""-H\s+['"]Cookie:\s*([^'"]+)['"]""",
        r"""--header\s+['"]Cookie:\s*([^'"]+)['"]""",
        # Also handle -b 'cookie=value'
        r"""-b\s+['"]([^'"]+)['"]""",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            cookie_str = match.group(1)
            cookies.update(parse_cookie_header(cookie_str))
    return cookies


def parse_cookie_header(text: str) -> dict[str, str]:
    """Parse a raw Cookie header value: 'name1=val1; name2=val2; ...'"""
    cookies: dict[str, str] = {}
    for part in text.split(";"):
        part = part.strip()
        if "=" in part:
            name, _, value = part.partition("=")
            name = name.strip()
            value = value.strip()
            if name:
                cookies[name] = value
    return cookies


def parse_json_cookies(text: str) -> dict[str, str]:
    """Parse cookies from JSON array (browser extension export)."""
    data = json.loads(text)
    cookies: dict[str, str] = {}
    if isinstance(data, list):
        for c in data:
            if isinstance(c, dict) and "name" in c and "value" in c:
                cookies[c["name"]] = c["value"]
    elif isinstance(data, dict):
        if "cookies" in data:
            return parse_json_cookies(json.dumps(data["cookies"]))
        cookies = {k: v for k, v in data.items() if isinstance(v, str)}
    return cookies


def parse_input(text: str) -> dict[str, str]:
    """Auto-detect input format and extract cookies."""
    text = text.strip()

    # Try JSON first
    if text.startswith("[") or text.startswith("{"):
        try:
            return parse_json_cookies(text)
        except json.JSONDecodeError:
            pass

    # Try cURL
    if "curl" in text.lower() or "-H" in text or "--header" in text:
        result = parse_curl_cookies(text)
        if result:
            return result

    # Treat as raw Cookie header
    if "=" in text and ";" in text:
        return parse_cookie_header(text)

    # Single cookie (unlikely but handle it)
    if "=" in text:
        return parse_cookie_header(text)

    return {}


def cookies_to_storage_state(cookies: dict[str, str]) -> dict:
    """Convert a name->value cookie dict to Playwright storage_state format."""
    cookie_list = []
    for name, value in cookies.items():
        cookie_list.append({
            "name": name,
            "value": value,
            "domain": ".google.com",
            "path": "/",
            "expires": -1,
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
        })
    return {"cookies": cookie_list}


def save_storage_state(storage_state: dict, path: Path | None = None) -> Path:
    """Save to disk in notebooklm-py format."""
    target = path or STORAGE_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(storage_state, indent=2))
    target.chmod(0o600)
    return target


def validate_cookies(cookies: dict[str, str]) -> list[str]:
    """Return list of issues, empty if OK."""
    issues = []
    if not cookies:
        issues.append("No cookies were found in the input.")
        return issues
    missing = MINIMUM_REQUIRED - set(cookies.keys())
    if missing:
        issues.append(f"Missing required cookies: {', '.join(sorted(missing))}")
    return issues


def interactive_login(output_path: Path | None = None) -> Path:
    """Run the interactive CLI login flow."""
    print(INSTRUCTIONS)

    # Read multi-line input (cURL commands can be very long)
    print("Paste your cookies below (press Enter twice when done):")
    print("─" * 60)

    lines: list[str] = []
    empty_count = 0
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "":
            empty_count += 1
            if empty_count >= 2:
                break
            lines.append(line)
        else:
            empty_count = 0
            lines.append(line)

    raw = "\n".join(lines).strip()
    if not raw:
        print("\nNo input received. Aborting.")
        sys.exit(1)

    # Parse
    cookies = parse_input(raw)

    # Filter to known Google auth cookies + any __Secure- prefixed ones
    filtered = {}
    for name, value in cookies.items():
        if name in GOOGLE_AUTH_COOKIES or name.startswith("__Secure-"):
            filtered[name] = value

    # If filtering removed everything, keep all (user might know better)
    if not filtered and cookies:
        filtered = cookies

    # Validate
    issues = validate_cookies(filtered)
    if issues:
        print("\nWarning:")
        for issue in issues:
            print(f"  - {issue}")
        print()
        if "No cookies were found" in issues[0]:
            print("Could not parse any cookies from input. Check the format and try again.")
            sys.exit(1)

    # Show what we got
    print(f"\nFound {len(filtered)} cookies:")
    for name in sorted(filtered.keys()):
        val_preview = filtered[name][:20] + "..." if len(filtered[name]) > 20 else filtered[name]
        print(f"  {name} = {val_preview}")

    # Save
    storage_state = cookies_to_storage_state(filtered)
    target = save_storage_state(storage_state, output_path)
    print(f"\nSaved to: {target}")
    print("Authentication complete. You can now use the NotebookLM MCP server.")
    return target


def main():
    import argparse
    parser = argparse.ArgumentParser(description="NotebookLM CLI authentication (no Playwright)")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help=f"Output path for storage_state.json (default: {STORAGE_FILE})",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify existing auth by fetching CSRF token",
    )
    args = parser.parse_args()

    if args.verify:
        verify_auth(args.output)
    else:
        interactive_login(args.output)


def verify_auth(path: Path | None = None):
    """Quick auth verification — try to fetch CSRF token."""
    target = path or STORAGE_FILE
    if not target.exists():
        print(f"No auth file found at {target}")
        print("Run this command without --verify to authenticate first.")
        sys.exit(1)

    state = json.loads(target.read_text())
    cookies = {c["name"]: c["value"] for c in state.get("cookies", [])}
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())

    print(f"Auth file: {target}")
    print(f"Cookies: {len(cookies)} found")
    print(f"Verifying against {NOTEBOOKLM_URL} ...")

    try:
        import urllib.request

        req = urllib.request.Request(
            NOTEBOOKLM_URL,
            headers={
                "Cookie": cookie_header,
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            final_url = resp.url

        if "accounts.google.com" in final_url:
            print("FAILED: Redirected to login page. Cookies may be expired.")
            print("Re-run without --verify to re-authenticate.")
            sys.exit(1)

        # Try extracting CSRF token
        csrf_match = re.search(r'"SNlM0e"\s*:\s*"([^"]+)"', html)
        session_match = re.search(r'"FdrFJe"\s*:\s*"([^"]+)"', html)

        if csrf_match and session_match:
            print(f"CSRF token: {csrf_match.group(1)[:20]}...")
            print(f"Session ID: {session_match.group(1)[:20]}...")
            print("\nAuthentication is VALID.")
        else:
            print("WARNING: Could not extract tokens. Auth may be expired.")
            sys.exit(1)
    except Exception as e:
        print(f"Verification failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
