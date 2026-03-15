"""Test the auth_cli cookie parsing with all 3 input methods."""

from notebooklm_mcp.auth_cli import (
    parse_input,
    validate_cookies,
    cookies_to_storage_state,
)
import json

# --- Test 1: cURL command ---
print("=== Test 1: cURL command ===")
curl_input = """curl 'https://notebooklm.google.com/' \
  -H 'accept: text/html,application/xhtml+xml' \
  -H 'accept-language: en-US,en;q=0.9' \
  -H 'Cookie: SID=abc123def456; HSID=xyz789; SSID=qqq111; APISID=www222; SAPISID=eee333; __Secure-1PSID=sec1val; NID=nid_val; OTHER_COOKIE=ignored_but_kept' \
  -H 'user-agent: Mozilla/5.0'"""

cookies = parse_input(curl_input)
print(f"  Parsed {len(cookies)} cookies")
for name in sorted(cookies):
    print(f"    {name} = {cookies[name]}")
issues = validate_cookies(cookies)
print(f"  Validation issues: {issues or 'None'}")
assert "SID" in cookies
assert cookies["SID"] == "abc123def456"
print("  PASS\n")

# --- Test 2: Raw Cookie header ---
print("=== Test 2: Raw Cookie header ===")
header_input = "SID=raw_sid_value; HSID=raw_hsid; SSID=raw_ssid; __Secure-1PSID=raw_secure"

cookies = parse_input(header_input)
print(f"  Parsed {len(cookies)} cookies")
for name in sorted(cookies):
    print(f"    {name} = {cookies[name]}")
issues = validate_cookies(cookies)
print(f"  Validation issues: {issues or 'None'}")
assert "SID" in cookies
assert cookies["SID"] == "raw_sid_value"
print("  PASS\n")

# --- Test 3: JSON array (browser extension) ---
print("=== Test 3: JSON array (browser extension export) ===")
json_input = json.dumps([
    {"name": "SID", "value": "json_sid", "domain": ".google.com"},
    {"name": "HSID", "value": "json_hsid", "domain": ".google.com"},
    {"name": "SSID", "value": "json_ssid", "domain": ".google.com"},
    {"name": "__Secure-1PSID", "value": "json_secure", "domain": ".google.com"},
])

cookies = parse_input(json_input)
print(f"  Parsed {len(cookies)} cookies")
for name in sorted(cookies):
    print(f"    {name} = {cookies[name]}")
issues = validate_cookies(cookies)
print(f"  Validation issues: {issues or 'None'}")
assert "SID" in cookies
assert cookies["SID"] == "json_sid"
print("  PASS\n")

# --- Test 4: Missing required cookie ---
print("=== Test 4: Validation - missing SID ===")
cookies = parse_input("HSID=only_this; SSID=and_this")
issues = validate_cookies(cookies)
print(f"  Issues: {issues}")
assert len(issues) > 0
assert "SID" in issues[0]
print("  PASS\n")

# --- Test 5: Storage state format ---
print("=== Test 5: Storage state format ===")
cookies = {"SID": "test123", "HSID": "test456"}
state = cookies_to_storage_state(cookies)
print(f"  Keys: {list(state.keys())}")
print(f"  Cookie count: {len(state['cookies'])}")
assert state["cookies"][0]["domain"] == ".google.com"
assert state["cookies"][0]["httpOnly"] is True
print(f"  Format: {json.dumps(state, indent=2)}")
print("  PASS\n")

# --- Test 6: Empty input ---
print("=== Test 6: Empty input ===")
cookies = parse_input("")
issues = validate_cookies(cookies)
print(f"  Issues: {issues}")
assert "No cookies" in issues[0]
print("  PASS\n")

print("=== All parsing tests passed ===")
