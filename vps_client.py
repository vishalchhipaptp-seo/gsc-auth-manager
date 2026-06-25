"""
VPS API client — communicates with james-seo-tools on the VPS.
Handles login, account listing, auth status checks, and auth_state upload.
"""
import json
import requests


class VPSClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.http = requests.Session()

    def login(self, email, password):
        try:
            r = self.http.post(
                f"{self.base_url}/api/auth/login",
                json={"email": email, "password": password},
                headers={"Content-Type": "application/json"},
            )
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to VPS. Check the URL."
        except Exception as e:
            return False, str(e)

        if r.status_code != 200:
            try:
                return False, r.json().get("error", "Login failed")
            except Exception:
                return False, f"HTTP {r.status_code}"

        data = r.json()
        if data.get("ok"):
            return True, "Logged in"
        return False, data.get("error", "Login failed")

    def get_accounts(self):
        try:
            r = self.http.get(f"{self.base_url}/api/accounts")
            if r.status_code != 200:
                return []
            return r.json().get("accounts", [])
        except Exception:
            return []

    def get_auth_status(self, account_key):
        try:
            r = self.http.get(
                f"{self.base_url}/api/accounts/screenshot-status",
                params={"accountKey": account_key},
            )
            if r.status_code != 200:
                return {"hasAuthState": False}
            return r.json()
        except Exception:
            return {"hasAuthState": False}

    def upload_auth_state(self, account_key, auth_state):
        try:
            r = self.http.post(
                f"{self.base_url}/api/accounts/upload-auth-state",
                json={"accountKey": account_key, "authState": auth_state},
            )
            if r.status_code != 200:
                try:
                    return False, r.json().get("error", "Upload failed")
                except Exception:
                    return False, f"HTTP {r.status_code}"
            return True, "Uploaded"
        except Exception as e:
            return False, str(e)
