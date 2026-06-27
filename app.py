"""
GSC Auth Manager — Desktop companion app for james-seo-tools.
Handles Google auth setup locally (where Chrome works) and uploads
auth_states to VPS automatically.
"""
import json
import sys
import os
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify

from vps_client import VPSClient
from auth_setup import run_auth_setup, AUTH_DIR

app = Flask(__name__)
vps = VPSClient("")
setup_status = {}  # accountKey -> {running, message, success}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    vps_url = data.get("vpsUrl", "").strip().rstrip("/")
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not vps_url or not email or not password:
        return jsonify({"ok": False, "error": "All fields required"})

    vps.base_url = vps_url
    ok, msg = vps.login(email, password)
    return jsonify({"ok": ok, "error": msg if not ok else None})


@app.route("/api/accounts")
def accounts():
    accs = vps.get_accounts()
    result = []
    for a in accs:
        key = a.get("accountKey", "")
        status = vps.get_auth_status(key)
        local_file = AUTH_DIR / f"{key}.json"
        result.append({
            **a,
            "hasAuthState": status.get("hasAuthState", False),
            "hasLocalAuth": local_file.exists(),
            "setupStatus": setup_status.get(key, {}).get("message", ""),
            "setupRunning": setup_status.get(key, {}).get("running", False),
        })
    return jsonify({"accounts": result})


@app.route("/api/setup", methods=["POST"])
def setup():
    data = request.json
    account_key = data.get("accountKey", "").strip()
    email = data.get("email", "").strip()
    if not account_key:
        return jsonify({"ok": False, "error": "accountKey required"})

    if setup_status.get(account_key, {}).get("running"):
        return jsonify({"ok": False, "error": "Already running"})

    setup_status[account_key] = {"running": True, "message": "Starting...", "success": False}

    def run():
        def on_status(msg):
            setup_status[account_key]["message"] = msg

        try:
            ok, auth_state, msg = run_auth_setup(account_key, on_status, email=email)
            setup_status[account_key]["message"] = msg
            setup_status[account_key]["success"] = ok

            if ok and auth_state:
                on_status("Uploading to VPS...")
                upload_ok, upload_msg = vps.upload_auth_state(account_key, auth_state)
                if upload_ok:
                    setup_status[account_key]["message"] = "Done — uploaded to VPS"
                else:
                    setup_status[account_key]["message"] = f"Auth saved locally but upload failed: {upload_msg}"
        except Exception as e:
            setup_status[account_key]["success"] = False
            setup_status[account_key]["message"] = f"Error: {e}"
        finally:
            setup_status[account_key]["running"] = False

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return jsonify({"ok": True})


@app.route("/api/upload", methods=["POST"])
def upload():
    data = request.json
    account_key = data.get("accountKey", "").strip()
    if not account_key:
        return jsonify({"ok": False, "error": "accountKey required"})

    local_file = AUTH_DIR / f"{account_key}.json"
    if not local_file.exists():
        return jsonify({"ok": False, "error": "No local auth_state file"})

    auth_state = json.loads(local_file.read_text(encoding="utf-8"))
    ok, msg = vps.upload_auth_state(account_key, auth_state)
    return jsonify({"ok": ok, "error": msg if not ok else None})


@app.route("/api/status")
def status():
    account_key = request.args.get("accountKey", "")
    s = setup_status.get(account_key, {"running": False, "message": "", "success": False})
    return jsonify(s)


def start_app():
    use_webview = "--no-webview" not in sys.argv
    port = 5199

    if use_webview:
        try:
            import webview
            t = threading.Thread(target=lambda: app.run(port=port, debug=False, use_reloader=False), daemon=True)
            t.start()
            webview.create_window(
                "GSC Auth Manager",
                f"http://localhost:{port}",
                width=1100,
                height=750,
                resizable=True,
            )
            webview.start()
        except ImportError:
            print(f"pywebview not installed. Opening in browser at http://localhost:{port}")
            import webbrowser
            webbrowser.open(f"http://localhost:{port}")
            app.run(port=port, debug=False)
    else:
        import webbrowser
        webbrowser.open(f"http://localhost:{port}")
        app.run(port=port, debug=False)


if __name__ == "__main__":
    start_app()
