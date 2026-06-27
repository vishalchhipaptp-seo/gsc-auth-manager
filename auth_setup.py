"""
Chrome-based GSC auth capture.
Opens a REAL Chrome window (not automated) so Google allows sign-in.
Connects via CDP only to READ cookies after login is complete.
"""
import os
import sys
import json
import time
import socket
import subprocess
import urllib.request
from pathlib import Path

AUTH_DIR = Path(__file__).parent / "auth_states"
START_URL = "https://search.google.com/search-console/welcome"
AUTH_COOKIES = {"SAPISID", "__Secure-1PSID", "__Secure-3PSID", "SID", "APISID", "SSID", "HSID"}
WAIT_MINUTES = 10
PROFILE_ROOT = Path(__file__).parent / ".login_profiles"


def find_browser():
    # Prefer Chrome (Edge only as a last-resort fallback).
    cands = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    if sys.platform != "win32":
        cands = ["/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/usr/bin/chromium"]
    for c in cands:
        if Path(c).exists():
            return c
    return None


def free_port(preferred=9222):
    for port in (preferred, 9223, 9224, 9225, 0):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", port))
            p = s.getsockname()[1]
            s.close()
            return p
        except OSError:
            continue
    return preferred


def endpoint_up(port):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5)
        return True
    except Exception:
        return False


def to_storage_state(cdp_cookies):
    cookies = []
    for c in cdp_cookies:
        ss = c.get("sameSite")
        if ss not in ("Strict", "Lax", "None"):
            ss = "Lax"
        exp = c.get("expires", -1)
        if c.get("session") or exp in (None, -1) or exp < 0:
            exp = -1
        cookies.append({
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
            "expires": exp,
            "httpOnly": bool(c.get("httpOnly")),
            "secure": bool(c.get("secure")),
            "sameSite": ss,
        })
    return {"cookies": cookies, "origins": []}


def run_auth_setup(account_key, on_status=None, email=None):
    """
    Opens Chrome for the given account, waits for Google sign-in,
    captures cookies, and saves auth_state.

    on_status: callback(msg) for progress updates
    email: Google email to pre-select in the account chooser / pre-fill on login
    Returns: (success: bool, auth_state: dict|None, message: str)
    """
    def status(msg):
        if on_status:
            on_status(msg)

    AUTH_DIR.mkdir(exist_ok=True)
    PROFILE_ROOT.mkdir(exist_ok=True)
    out = AUTH_DIR / f"{account_key}.json"
    # ONE shared Chrome profile for all accounts. After you sign in to your Google
    # account(s) once, they stay logged in here — so setting up the next account
    # just opens the account chooser (no password re-entry, no re-adding).
    user_data_dir = PROFILE_ROOT / "_shared"

    browser_exe = find_browser()
    if not browser_exe:
        return False, None, "Chrome/Edge not found. Please install Chrome."

    port = free_port(9222)
    start_url = START_URL
    if email:
        import urllib.parse
        start_url = ("https://accounts.google.com/AccountChooser?"
                     + urllib.parse.urlencode({"Email": email, "continue": START_URL}))
    status(f"Opening Chrome for {email or account_key}...")

    proc = subprocess.Popen([
        browser_exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
        start_url,
    ])

    deadline = time.time() + 30
    while time.time() < deadline:
        if endpoint_up(port):
            break
        if proc.poll() is not None:
            return False, None, "Browser exited before it was ready."
        time.sleep(1)

    if not endpoint_up(port):
        try:
            proc.terminate()
        except Exception:
            pass
        return False, None, "Browser did not start in time."

    status("Waiting for Google sign-in... (sign in and wait for Search Console)")

    saved = False
    auth_state = None
    message = "No login detected — sign in was not completed."

    try:
        from patchright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")

            def acquire_cdp():
                ctx0 = browser.contexts[0]
                page0 = ctx0.pages[0] if ctx0.pages else ctx0.new_page()
                return ctx0.new_cdp_session(page0)

            cdp = acquire_cdp()
            deadline = time.time() + WAIT_MINUTES * 60

            while time.time() < deadline:
                if proc.poll() is not None:
                    message = "Browser was closed before login was detected."
                    break
                try:
                    cookies = cdp.send("Network.getAllCookies").get("cookies", [])
                except Exception:
                    try:
                        cdp = acquire_cdp()
                        cookies = cdp.send("Network.getAllCookies").get("cookies", [])
                    except Exception:
                        cookies = []

                names = {c.get("name") for c in cookies}
                if names & AUTH_COOKIES:
                    auth_state = to_storage_state(cookies)
                    out.write_text(json.dumps(auth_state, indent=2), encoding="utf-8")
                    saved = True
                    message = f"Auth saved ({len(auth_state['cookies'])} cookies)"
                    break
                time.sleep(3)

            try:
                browser.close()
            except Exception:
                pass
    except Exception as e:
        message = f"CDP error: {e}"

    try:
        proc.terminate()
    except Exception:
        pass

    return saved, auth_state, message
