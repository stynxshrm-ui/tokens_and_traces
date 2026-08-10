"""
04_fixed.py — same bug (retry loop, cold index) as 02_broken.py, same
DeadlineContext as 03_instrumented.py. What's added here is the
production shape: a loud, unmissable failure signal instead of a
silently-swallowed early return, and the deadline header shown being
forwarded downstream (production reality #3 from the script, 8:15).

A silent early return here would be worse than the original bug — you'd
stop wasting the compute, but you'd also stop knowing it happened.
Script: 9:45-11:30 "FIX."
"""

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

DEADLINE_BUDGET_S = 10.0  # same policy value as 03_instrumented.py

RED = "\033[91m"
RESET = "\033[0m"


def downstream_headers(ctx: DeadlineContext) -> dict:
    """
    Production reality #3 (script 8:15): if you cancel locally but don't
    forward the deadline to a downstream service, that service runs to
    completion anyway. This is the header that would ship on any outbound
    call this agent makes — not exercised further in this demo, but the
    shape is real: forward remaining budget, not the original total.
    """
    return {"x-deadline-remaining-s": round(ctx.remaining(), 2)}


def handle_request(session_id: str, cold_index: bool = True):
    ctx = DeadlineContext(budget_seconds=DEADLINE_BUDGET_S)
    log_event("request.start", session=session_id, deadline_budget_s=DEADLINE_BUDGET_S)

    calls = []
    steps_planned = 3

    try:
        calls.append(call_check_account(ctx))
        log_event("tool.complete", session=session_id,
                   budget_remaining_s=round(ctx.remaining(), 2),
                   downstream_headers=downstream_headers(ctx), **calls[-1])

        for attempt in range(1, 4):
            result = call_search_logs(ctx, cold_index=cold_index, attempt=attempt)
            calls.append(result)
            log_event("tool.complete", session=session_id,
                       budget_remaining_s=round(ctx.remaining(), 2),
                       downstream_headers=downstream_headers(ctx), **result)
            if result["ok"]:
                break

        calls.append(call_draft_response(ctx))
        log_event("tool.complete", session=session_id,
                   budget_remaining_s=round(ctx.remaining(), 2), **calls[-1])

        outcome = "success"
        steps_completed = 3

    except DeadlineExceeded as e:
        # LOUD on purpose. This prints in red and gets its own event name
        # (deadline.exceeded) — it is not folded into agent.complete as
        # an afterthought, and outcome is never "success" when this fires.
        print(f"{RED}[COMPUTE] DEADLINE EXCEEDED — aborting new work, "
              f"not the request that's already in flight{RESET}")
        log_event("deadline.exceeded", session=session_id, reason=str(e),
                   action="abort_new_work", severity="warning")
        outcome = "deadline_exceeded"
        steps_completed = sum(1 for t in ("check_account", "draft_response")
                               if any(c["tool"] == t and c["ok"] for c in calls))
        if any(c["tool"] == "search_logs" and c["ok"] for c in calls):
            steps_completed += 1

    narrated_total = round(sum(c["duration_s"] for c in calls), 2)
    abandon_at = user_abandonment_time()
    cost = cost_of(calls)

    log_event(
        "agent.complete",
        session=session_id,
        response_sent=(outcome == "success"),
        total_narrated_s=narrated_total,
        cost_usd=cost,
        user_abandoned_at_s=abandon_at,
        steps_completed=f"{steps_completed}/{steps_planned}",
        outcome=outcome,  # never silently reported as success
        # This is the metric this video introduces — deliberately NOT
        # folded into the series' four locked alerting metrics. It's a
        # distinct signal: spend incurred strictly after the point the
        # user stopped waiting. See README "Why this metric is separate."
        tokens_traces_cost_after_abandonment_usd=(
            cost if narrated_total > abandon_at else 0.0
        ),
    )
    return calls


if __name__ == "__main__":
    handle_request(session_id="8f2a")
