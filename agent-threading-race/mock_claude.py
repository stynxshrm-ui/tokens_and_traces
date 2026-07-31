"""
mock_claude.py
Deterministic stand-in for the Anthropic SDK so every take produces
identical output with no API key and no token spend. Real mode would
swap this for `anthropic.Anthropic().messages.create(...)`.

The script is a fixed 3-turn plan: two turns request tool calls,
the third returns a final answer. The mock does NOT look at the
history it's given -- it just plays back the plan. That's the point:
the bugs we're diagnosing corrupt bookkeeping around the loop, not
the model's behavior, so the model's turns stay identical across
every file in this series. Only the harness output changes.
"""

import time

# turn -> list of (tool_name, args, simulated_latency_seconds)
# latencies are deliberately uneven so concurrent execution actually
# interleaves instead of finishing in lockstep.
TURN_PLAN = [
    [
        ("get_weather", {"city": "Austin"}, 0.15),
        ("get_calendar_events", {"date": "2026-07-24"}, 0.16),
        ("send_email", {"to": "ops@acme.io", "subject": "status"}, 0.15),
    ],
    [
        ("get_weather", {"city": "Denver"}, 0.15),
        ("get_calendar_events", {"date": "2026-07-25"}, 0.16),
    ],
    [],  # turn 3: no tool calls, model gives a final answer
]

FINAL_ANSWER = "Here's the weather and schedule summary you asked for."


class MockClaude:
    """Plays back TURN_PLAN. call_count is 1-indexed per .next_turn() call."""

    def __init__(self):
        self.call_count = 0

    def next_turn(self):
        """Returns (tool_calls, is_final). tool_calls is a list of
        (tool_name, args, simulated_latency_seconds)."""
        idx = self.call_count
        self.call_count += 1
        if idx >= len(TURN_PLAN):
            return [], True
        calls = TURN_PLAN[idx]
        is_final = len(calls) == 0
        return calls, is_final


def execute_tool(name, args, latency):
    """Simulated tool execution. Real mode would hit a real API/db."""
    time.sleep(latency)
    if name == "get_weather":
        return f"{args['city']}: 89F, clear"
    if name == "get_calendar_events":
        return f"{args['date']}: 3 events"
    if name == "send_email":
        return f"sent to {args['to']}"
    return "unknown tool"
