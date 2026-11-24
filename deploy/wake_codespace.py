"""Wake the Codespace before the scheduled data update (uses GH_PAT secret)."""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN = os.environ.get("GH_TOKEN", "").strip()
NAME = os.environ.get("CODESPACE_NAME", "").strip()
if not TOKEN or not NAME:
    print("wake skipped: GH_TOKEN or CODESPACE_NAME missing")
    sys.exit(0)

PATH = "/user/codespaces/" + urllib.parse.quote(NAME)


def call(path, method="GET"):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        data=None,
        method=method,
        headers={
            "Authorization": "Bearer " + TOKEN,
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", "replace")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        print("wake HTTP %s: %s" % (exc.code, detail[:300]))
        return {}


state = call(PATH).get("state")
print("codespace state: %s" % state)
if state != "Available":
    call(PATH + "/start", "POST")
    for _ in range(30):
        time.sleep(10)
        state = call(PATH).get("state")
        print("codespace state: %s" % state)
        if state == "Available":
            break
