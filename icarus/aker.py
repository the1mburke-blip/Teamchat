"""
Icarus Aker - Autonomous Repository-Driven Runner Module
Handles state management, task polling, and execution handoff for the background runner loop.
"""

import os
import json
import datetime

VERSION = "1.0.0-aker"
STATUS_FILE = "icarus/runs/aker_status.json"

def log_status(status: str, details: dict = None):
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    record = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "status": status,
        "details": details or {},
        "version": VERSION
    }
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    print(f"[AKER] Status updated: {status} at {record['timestamp']}")

if __name__ == "__main__":
    print(f"Icarus Aker Runner v{VERSION} initialized.")
    log_status("HANDOFF_READY", {"message": "Autonomous repository runner loop active."})
