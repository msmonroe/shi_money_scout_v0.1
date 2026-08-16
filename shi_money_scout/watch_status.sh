#!/usr/bin/env bash
set -euo pipefail

STATUS_FILE="${1:-output/status.json}"
INTERVAL="${2:-1}"

while true; do
  clear
  python3 - "$STATUS_FILE" <<'PY'
import json
import os
import sys
import time

status_file = sys.argv[1]


def fmt_duration(seconds):
    try:
        seconds = int(seconds)
    except Exception:
        return "unknown"
    if seconds < 0:
        seconds = 0
    mins, sec = divmod(seconds, 60)
    hrs, mins = divmod(mins, 60)
    if hrs:
        return f"{hrs}h {mins}m {sec}s"
    if mins:
        return f"{mins}m {sec}s"
    return f"{sec}s"


print("Shi Money Scout Status")
print("=" * 40)
print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Status file: {status_file}")
print("")

if not os.path.exists(status_file):
    print("Status file not found yet. Start python3 main.py first.")
    sys.exit(0)

try:
    with open(status_file, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as exc:
    print(f"Could not read status file: {exc}")
    sys.exit(0)

phase = data.get("phase", "unknown")
total = int(data.get("total_candidates", 0) or 0)
processed = int(data.get("processed_candidates", 0) or 0)
current = int(data.get("current_index", 0) or 0)
url = data.get("current_url", "")
elapsed = data.get("elapsed_seconds", 0)
eta = data.get("eta_seconds", 0)
complete = bool(data.get("complete", False))

pct = (processed / total * 100.0) if total > 0 else 0.0

print(f"Phase: {phase}")
print(f"Complete: {complete}")
print(f"Progress: {processed}/{total} ({pct:.1f}%)")
print(f"Current index: {current}")
print(f"Elapsed: {fmt_duration(elapsed)}")
print(f"ETA: {fmt_duration(eta)}")
print("")
if url:
    print("Current URL:")
    print(url)

if complete:
    print("\nRun complete. Press Ctrl+C to exit watcher.")
PY
  sleep "$INTERVAL"
done
