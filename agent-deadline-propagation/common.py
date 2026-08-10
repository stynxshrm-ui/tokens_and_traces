"""
common.py — single source of truth for the deadline-propagation video.

Owns:
  - DeadlineContext: absolute-epoch deadline, threaded through every call
  - Tool definitions + mock latencies (DEMO=1 mode)
  - Cost math (pricing constants live in ONE place)
  - Structured logging, OTel GenAI semantic-convention attribute names
    where they exist, `tokens_traces.*` prefix for the ones that don't

No script in this repo computes a cost or a timestamp independently of
this module. If a number appears on camera, it was produced here.
"""

import os
import time
import json
import random

# ---------------------------------------------------------------------------
# Pricing — ASSUMPTION, NAMED ON CAMERA (see script 4:45, README "Assumptions")
# ---------------------------------------------------------------------------
# Illustrative per-request pricing for a mid-size tool-using model, priced
# per call rather than per-token for narration simplicity. This is NOT a
# live model's real per-token price — it's a stand-in cost-per-call chosen
# to make the "wasted spend" number legible on camera. If you re-film this
# with real per-token pricing, replace COST_PER_CALL below and re-render
# every [COMPUTE] number in the script + the thumbnail.
COST_PER_CALL = {
    "check_account": 0.001,
    "search_logs": 0.004,      # charged per attempt, including retries
    "draft_response": 0.009,   # the generation call
}

DEMO = os.environ.get("DEMO", "0") == "1"


# ---------------------------------------------------------------------------
# DeadlineContext
# ---------------------------------------------------------------------------
class DeadlineExceeded(Exception):
    """Raised when a tool is about to start new work past the deadline."""


class DeadlineContext:
    """
    Absolute epoch-time deadline, set once at request start and threaded
    unmodified through every nested call. Deliberately NOT a duration —
    a duration recomputed at each hop drifts with clock skew and with how
    long it took to get there. An absolute timestamp doesn't.

    Mirrors the shape of a gRPC deadline / Python contextvars deadline.

    NOTE on the virtual clock: `elapsed_s` advances by each call's
    *narrated* duration (see common.py._sleep_or_mock), not by real
    wall-clock time. In real mode those are identical. In DEMO mode we
    compress the actual sleep to keep filming sane, but the deadline
    math has to run on story-time or the deadline would never fire on
    camera. This is the one place DEMO mode and real mode could
    silently diverge — flagged here on purpose.
    """

    def __init__(self, budget_seconds: float):
        self.budget_seconds = budget_seconds
        self.elapsed_s = 0.0

    def advance(self, narrated_seconds: float):
        """Called once per completed call, by the call_* functions,
        with the duration that was actually narrated on screen."""
        self.elapsed_s += narrated_seconds

    def remaining(self) -> float:
        return max(0.0, self.budget_seconds - self.elapsed_s)

    def expired(self) -> bool:
        return self.remaining() <= 0.0

    def require(self, min_budget: float, tool_name: str):
        """
        Call before starting ANY new unit of work (a tool call, a retry
        attempt, a generation call). Does not touch work already in
        flight — see script 5:30, "finish in-flight, block new work."
        """
        if self.remaining() < min_budget:
            raise DeadlineExceeded(
                f"{tool_name}: needs {min_budget}s, only {self.remaining():.2f}s left"
            )


# ---------------------------------------------------------------------------
# Tool budgets — the modelling assumption named in the script (8:15, card 4)
# ---------------------------------------------------------------------------
# Minimum remaining budget required before starting each tool. These are
# NOT arbitrary — they're set to roughly the tool's own p50 latency, so a
# tool never starts work it can't plausibly finish inside what's left.
# Change these here; nothing else in the repo hardcodes them.
MIN_BUDGET = {
    "check_account": 0.5,
    "search_logs": 3.0,
    "draft_response": 5.0,
}


# ---------------------------------------------------------------------------
# Structured logging — OTel GenAI semconv attrs + tokens_traces.* extension
# ---------------------------------------------------------------------------
def log_event(event_name: str, **attrs):
    """
    Emits one structured line. Uses OTel GenAI semantic convention
    attribute names where they exist (gen_ai.*), and the tokens_traces.*
    namespace for the metric this video introduces
    (tokens_traces.cost_after_abandonment) which is NOT one of the four
    locked alerting metrics for this series — it's a distinct signal,
    left standalone on purpose. See script closing note.
    """
    record = {
        "timestamp": time.time(),
        "event": event_name,
        **attrs,
    }
    print(f"[COMPUTE] {json.dumps(record, sort_keys=True)}")
    return record


# ---------------------------------------------------------------------------
# Mock latency injection (DEMO=1) — deterministic across takes
# ---------------------------------------------------------------------------
def _sleep_or_mock(real_seconds: float, mock_seconds: float):
    """
    Real mode sleeps real time (used only if you re-run this against an
    actual slow dependency). DEMO mode sleeps a short, deterministic,
    filmable duration and reports the *narrated* duration in the log,
    not the wall-clock time actually spent sleeping — so filming doesn't
    require sitting through 43 real seconds of dead air.
    """
    if DEMO:
        time.sleep(min(mock_seconds, 0.4))  # compressed for filming
        return mock_seconds
    else:
        time.sleep(real_seconds)
        return real_seconds


def call_check_account(ctx: DeadlineContext):
    ctx.require(MIN_BUDGET["check_account"], "check_account")
    dur = _sleep_or_mock(real_seconds=0.04, mock_seconds=0.04)
    ctx.advance(dur)
    return {"tool": "check_account", "duration_s": dur, "ok": True}


def call_search_logs(ctx: DeadlineContext, cold_index: bool = False, attempt: int = 1):
    ctx.require(MIN_BUDGET["search_logs"], "search_logs")
    if cold_index and attempt < 3:
        # Simulates a cold index timing out — this is the "innocent"
        # degraded dependency, not a crash. It looks like a slow query.
        dur = _sleep_or_mock(real_seconds=4.0, mock_seconds=4.0)
        ctx.advance(dur)
        return {"tool": "search_logs", "duration_s": dur, "ok": False, "attempt": attempt}
    dur = _sleep_or_mock(real_seconds=0.2 if not cold_index else 3.0,
                          mock_seconds=0.2 if not cold_index else 3.0)
    ctx.advance(dur)
    return {"tool": "search_logs", "duration_s": dur, "ok": True, "attempt": attempt}


def call_draft_response(ctx: DeadlineContext):
    ctx.require(MIN_BUDGET["draft_response"], "draft_response")
    dur = _sleep_or_mock(real_seconds=6.0, mock_seconds=6.0)
    ctx.advance(dur)
    return {"tool": "draft_response", "duration_s": dur, "ok": True}


def cost_of(tool_calls: list[dict]) -> float:
    """
    ONE place cost is computed. tool_calls is a list of the dicts
    returned by the call_* functions above (each has a "tool" key).
    Retries are charged — a failed attempt still cost money.
    """
    return round(sum(COST_PER_CALL[c["tool"]] for c in tool_calls), 4)


def user_abandonment_time(patience_seconds: float = 5.0) -> float:
    """
    The point the script's cold open depends on: how long a real user
    waits before closing a live-chat widget. 5s is an illustrative
    assumption standing in for a measured p50 abandonment time on
    synchronous chat UI (short — people expect near-instant replies
    from a chat box, unlike an async job). If you have real product
    analytics on this, replace it here. Named explicitly in the README
    as the one number the thesis depends on.
    """
    return patience_seconds




