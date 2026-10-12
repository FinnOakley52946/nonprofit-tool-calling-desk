"""Submit one observable donor-receipt workflow to the local service."""

import json
import urllib.request


payload = {
    "instruction": (
        "Send a donor receipt with action_id receipt-2026-0042 to Avery Chen at "
        "chenhua@changba.com for a 7500-cent donation made on 2026-09-25."
    )
}
request = urllib.request.Request(
    "http://127.0.0.1:8000/automations/run",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request) as response:
    print(json.dumps(json.load(response), indent=2))
