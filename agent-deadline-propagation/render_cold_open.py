"""
render_cold_open.py — produces the exact two lines shown at 0:00-0:15.

Pulls real numbers from 02_broken.py (via common.py, same functions the
video runs) rather than hand-typing a timestamp gap into the script.
Anchors both lines to an arbitrary but fixed wall-clock start so the
displayed times read naturally on screen; the GAP between them is the
real computed number, not invented.
"""

import datetime
from common import user_abandonment_time
import importlib

broken = importlib.import_module("02_broken") if False else None  # noqa

# Re-run the same request the video runs, capturing just the two numbers
# the cold open needs: when the user disconnected, when the agent
# actually finished.
import subprocess, json

result = subprocess.run(
    ["python3", "02_broken.py"],
    cwd=".", capture_output=True, text=True, env={"DEMO": "1", "PATH": "/usr/bin:/bin"}
)
lines = [l for l in result.stdout.splitlines() if l.startswith("[COMPUTE]")]
final = json.loads(lines[-1][len("[COMPUTE] "):])

total_narrated_s = final["total_narrated_s"]
abandon_at_s = final["user_abandoned_at_s"]

base = datetime.datetime(2026, 3, 4, 14, 22, 0)
disconnect_time = base + datetime.timedelta(seconds=abandon_at_s)
complete_time = base + datetime.timedelta(seconds=total_narrated_s)

fmt = "%H:%M:%S.%f"


def render(t):
    return t.strftime(fmt)[:-3]


print(f"{render(disconnect_time)}  ws.disconnect   session=8f2a  reason=client_closed")
print(f"{render(complete_time)}  agent.complete  session=8f2a  response_sent=true")
print()
print(f"gap: {round(total_narrated_s - abandon_at_s, 2)}s of work after the user left")
