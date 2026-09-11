"""GitHub compare-and-swap claims shared by concurrent Actions runners.

An uncertain Telegram send is never automatically retried: pending claims are
reported for reconciliation. No token/chat ID/message content is persisted.
"""
import base64
import hashlib
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

class Ledger:
    def __init__(self):
        self.token = os.environ.get("GH_TOKEN", "")
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if not self.token or not repo:
            raise RuntimeError("Shared ledger requires GH_TOKEN and GITHUB_REPOSITORY")
        self.url = f"https://api.github.com/repos/{repo}/contents/output/delivery_ledger.json"

    def request(self, method, payload=None):
        req = urllib.request.Request(self.url, method=method,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json", "User-Agent": "JobFinder"})
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.load(response)

    def read(self):
        try:
            obj = self.request("GET")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {}, None
            raise RuntimeError(f"Ledger read HTTP {exc.code}") from None
        return json.loads(base64.b64decode(obj["content"])), obj["sha"]

    def write(self, data, sha):
        payload = {"message": "chore: persist delivery claim", "content": base64.b64encode(json.dumps(data, sort_keys=True).encode()).decode()}
        if sha:
            payload["sha"] = sha
        try:
            self.request("PUT", payload)
            return True
        except urllib.error.HTTPError as exc:
            if exc.code in (409, 422):
                return False
            raise RuntimeError(f"Ledger write HTTP {exc.code}") from None

    def claim(self, key):
        for _ in range(8):
            data, sha = self.read()
            if key in data:
                return data[key]["status"]
            data[key] = {"status": "pending", "at": datetime.now(timezone.utc).isoformat()}
            if self.write(data, sha):
                return "claimed"
        raise RuntimeError("Ledger conflict retries exhausted; no message sent")

    def finish(self, key):
        for _ in range(8):
            data, sha = self.read()
            data[key] = {"status": "sent", "at": datetime.now(timezone.utc).isoformat()}
            if self.write(data, sha):
                return
        raise RuntimeError("Ledger finalization conflict; pending claim retained")

def receipt_key(role, material):
    return hashlib.sha256((role + "\n" + material).encode()).hexdigest()
