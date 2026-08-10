"""
01_clean.py — the support agent as it ships first. No deadline anywhere.

Sequence: check_account -> search_logs -> draft_response.
Everything is fast. This is the version that gets demoed and approved.
Script: 2:00-3:15 "CLEAN walkthrough."
"""

from common import (
    DeadlineContext,
    call_check_account,
    call_search_logs,
    call_draft_response,
    cost_of,
    log_event,
)


def handle_request(session_id: str):
    # No real deadline in this version — inf budget means "never blocks."
    ctx = DeadlineContext(budget_seconds=float("inf"))

    log_event("request.start", session=session_id)

    calls = []
    calls.append(call_check_account(ctx))
    log_event("tool.complete", session=session_id, **calls[-1])

    calls.append(call_search_logs(ctx))
    log_event("tool.complete", session=session_id, **calls[-1])

    calls.append(call_draft_response(ctx))
    log_event("tool.complete", session=session_id, **calls[-1])

    # Narrated total = sum of each call's story-time duration, not the
    # compressed real wall-clock time DEMO mode actually sleeps for.
    # This is what's shown on camera; see common.py._sleep_or_mock.
    narrated_total = round(sum(c["duration_s"] for c in calls), 2)
    log_event(
        "agent.complete",
        session=session_id,
        response_sent=True,
        total_narrated_s=narrated_total,
        cost_usd=cost_of(calls),
        outcome="success",
    )
    return calls


if __name__ == "__main__":
    handle_request(session_id="8f2a-clean")
