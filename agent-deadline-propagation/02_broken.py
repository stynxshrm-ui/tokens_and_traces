"""
02_broken.py — one innocent change from 01_clean.py: a retry loop around
search_logs, added because the index goes cold under real load.

No budget check anywhere. Every individual call is fine. The chain is not.
Script: 3:15-4:45 "THE BUG."
"""

import time
from common import (
    DeadlineContext,
    call_check_account,
    call_search_logs,
    call_draft_response,
    cost_of,
    log_event,
    user_abandonment_time,
)


def handle_request(session_id: str, cold_index: bool = True):
    ctx = DeadlineContext(budget_seconds=float("inf"))  # still no deadline
    log_event("request.start", session=session_id)

    calls = []
    calls.append(call_check_account(ctx))
    log_event("tool.complete", session=session_id, **calls[-1])

    # --- THE BUG: three attempts, no backoff cap, no budget check ---
    for attempt in range(1, 4):
        result = call_search_logs(ctx, cold_index=cold_index, attempt=attempt)
        calls.append(result)
        log_event("tool.complete", session=session_id, **result)
        if result["ok"]:
            break
    # ------------------------------------------------------------------

    calls.append(call_draft_response(ctx))
    log_event("tool.complete", session=session_id, **calls[-1])

    narrated_total = round(sum(c["duration_s"] for c in calls), 2)
    abandon_at = user_abandonment_time()

    log_event(
        "agent.complete",
        session=session_id,
        response_sent=True,
        total_narrated_s=narrated_total,
        cost_usd=cost_of(calls),
        user_abandoned_at_s=abandon_at,
        wasted_work_after_abandon_s=round(max(0.0, narrated_total - abandon_at), 2),
        outcome="success",  # every call succeeded — this is the whole point
    )
    return calls


if __name__ == "__main__":
    handle_request(session_id="8f2a")
