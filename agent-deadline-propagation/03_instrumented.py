"""
03_instrumented.py — same retry bug as 02_broken.py, but every call now
checks a shared DeadlineContext before starting. Nothing about the retry
logic changed. What changed is that new work now has somewhere to check.

Budget policy: 10.0s. Chosen as roughly 1.5x the clean-path total (6.24s
from 01_clean.py) — enough slack for one real retry, not enough to absorb
an unbounded one. Named explicitly, adjustable in one place
(DEADLINE_BUDGET_S below).

Script: 5:30-6:45 "INSTRUMENTED walkthrough" + 6:45-8:15 "PAYOFF."
"""

import time
from common import (
    DeadlineContext,
    DeadlineExceeded,
    call_check_account,
    call_search_logs,
    call_draft_response,
    cost_of,
    log_event,
    user_abandonment_time,
)

DEADLINE_BUDGET_S = 10.0  # the modelling assumption 


def handle_request(session_id: str, cold_index: bool = True):
    ctx = DeadlineContext(budget_seconds=DEADLINE_BUDGET_S)
    log_event("request.start", session=session_id, deadline_budget_s=DEADLINE_BUDGET_S)

    calls = []
    steps_planned = 3  # check_account, search_logs, draft_response

    try:
        calls.append(call_check_account(ctx))
        log_event("tool.complete", session=session_id,
                   budget_remaining_s=round(ctx.remaining(), 2), **calls[-1])

        for attempt in range(1, 4):
            result = call_search_logs(ctx, cold_index=cold_index, attempt=attempt)
            calls.append(result)
            log_event("tool.complete", session=session_id,
                       budget_remaining_s=round(ctx.remaining(), 2), **result)
            if result["ok"]:
                break

        calls.append(call_draft_response(ctx))
        log_event("tool.complete", session=session_id,
                   budget_remaining_s=round(ctx.remaining(), 2), **calls[-1])

        outcome = "success"
        steps_completed = 3

    except DeadlineExceeded as e:
        # Finish in-flight work (nothing is mid-call here — the exception
        # fires BEFORE the next call starts, never mid-call). Block new
        # work. This is the "fails closed, not silent" branch.
        log_event("deadline.exceeded", session=session_id, reason=str(e),
                   action="abort_new_work")
        outcome = "deadline_exceeded"
        # steps_completed counts fully-successful distinct tool types.
        steps_completed = sum(1 for t in ("check_account", "draft_response")
                               if any(c["tool"] == t and c["ok"] for c in calls))
        if any(c["tool"] == "search_logs" and c["ok"] for c in calls):
            steps_completed += 1

    narrated_total = round(sum(c["duration_s"] for c in calls), 2)
    abandon_at = user_abandonment_time()

    log_event(
        "agent.complete",
        session=session_id,
        response_sent=(outcome == "success"),
        total_narrated_s=narrated_total,
        cost_usd=cost_of(calls),
        user_abandoned_at_s=abandon_at,
        steps_completed=f"{steps_completed}/{steps_planned}",
        outcome=outcome,
        cost_after_abandonment_usd=cost_of(calls) if narrated_total > abandon_at else 0.0,
    )
    return calls


if __name__ == "__main__":
    handle_request(session_id="8f2a")
