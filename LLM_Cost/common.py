"""
common.py — shared across 01_clean.py, 02_broken.py, 03_instrumented.py, 04_fixed.py

Everything in TICKET_CATEGORIES and PRICING is the single source of truth for
every number that appears on camera. No script computes a number that isn't
derived from these tables plus a fixed seed.

PRICING — verify week of filming (introductory Sonnet 5 pricing ends Aug 31 2026)
Source: docs.claude.com/en/docs/about-claude/pricing, checked 2026-07-03.
"""

import os
import random

DEMO_MODE = os.environ.get("DEMO", "1") == "1"

# ---------------------------------------------------------------------------
# PRICING (USD per token). Introductory Sonnet 5 pricing is in effect through
# 2026-08-31, after which it reverts to $3/$15 per MTok. If filming after
# that date, update SONNET_INPUT/SONNET_OUTPUT below.
# ---------------------------------------------------------------------------
SONNET_MODEL = "claude-sonnet-5"
SONNET_INPUT = 2.00 / 1_000_000
SONNET_OUTPUT = 10.00 / 1_000_000

HAIKU_MODEL = "claude-haiku-4-5-20251001"
HAIKU_INPUT = 1.00 / 1_000_000
HAIKU_OUTPUT = 5.00 / 1_000_000

# Prompt caching (5-minute TTL): write = 1.25x base input, read = 0.10x base input
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10

# ASSUMPTION, stated on screen: a failed resolution doesn't just vanish, it
# escalates to a human support agent, and a harder ticket costs more to hand
# off (more context for the agent to absorb, more back-and-forth). Escalation
# cost scales with steps-to-completion as a proxy for ticket difficulty:
# a 1-step miss (password reset) is a quick human fix; a 3-step miss
# (enterprise contract dispute) eats a senior agent's time. This is the cost
# that makes "cost per request" lie: the LLM call was cheap, the failure
# it caused wasn't.
ESCALATION_COST_BY_STEPS = {1: 2.00, 2: 8.00, 3: 15.00}

# Shared system prompt for the ticket-triage agent (policy doc, tool defs,
# routing instructions) — the same block sent on every single request,
# which is exactly what prompt caching is for.
SHARED_SYSTEM_PROMPT_TOKENS = 2400

# Router heuristic constants (the bug in 02_broken.py)
COMPLEX_KEYWORDS = {"api", "webhook", "integration", "contract", "dispute",
                     "enterprise", "migrate", "sso", "sla"}
LENGTH_THRESHOLD_WORDS = 25

# ---------------------------------------------------------------------------
# Ticket categories. `count` = tickets/day. `word_count` and `has_complex_kw`
# are what the naive router sees. `true_complexity` + the two success-rate
# columns are what actually determines whether the model gets it right —
# these two things are NOT the same signal, which is the entire point.
# ---------------------------------------------------------------------------
TICKET_CATEGORIES = [
    # name, count/day, word_count, has_complex_kw, true_complexity,
    # sonnet_success, haiku_success, avg_input_tok, avg_output_tok,
    # duplicate_rate (for semantic cache), steps
    # Genuinely simple categories: Haiku is just as reliable as Sonnet here —
    # this is the real case FOR routing. No accuracy tax, pure cost savings.
    dict(name="password_reset", count=1400, word_count=9, has_complex_kw=False,
         true_complexity="simple", sonnet_success=0.99, haiku_success=0.99,
         input_tok=180, output_tok=90, duplicate_rate=0.35, steps=1),
    dict(name="order_status", count=1100, word_count=8, has_complex_kw=False,
         true_complexity="simple", sonnet_success=0.99, haiku_success=0.99,
         input_tok=200, output_tok=90, duplicate_rate=0.30, steps=1),
    dict(name="shipping_address_change", count=600, word_count=14, has_complex_kw=False,
         true_complexity="simple", sonnet_success=0.98, haiku_success=0.98,
         input_tok=220, output_tok=110, duplicate_rate=0.15, steps=1),
    dict(name="billing_duplicate_charge", count=380, word_count=11, has_complex_kw=False,
         true_complexity="complex", sonnet_success=0.97, haiku_success=0.58,
         input_tok=260, output_tok=320, duplicate_rate=0.05, steps=2),
    dict(name="subscription_downgrade_proration", count=340, word_count=16, has_complex_kw=False,
         true_complexity="complex", sonnet_success=0.96, haiku_success=0.55,
         input_tok=280, output_tok=300, duplicate_rate=0.04, steps=2),
    dict(name="refund_policy_exception", count=310, word_count=7, has_complex_kw=False,
         true_complexity="complex", sonnet_success=0.96, haiku_success=0.52,
         input_tok=210, output_tok=280, duplicate_rate=0.03, steps=2),
    dict(name="technical_integration_error", count=240, word_count=44, has_complex_kw=True,
         true_complexity="complex", sonnet_success=0.95, haiku_success=0.61,
         input_tok=520, output_tok=430, duplicate_rate=0.02, steps=3),
    dict(name="enterprise_contract_dispute", count=90, word_count=61, has_complex_kw=True,
         true_complexity="complex", sonnet_success=0.93, haiku_success=0.44,
         input_tok=680, output_tok=520, duplicate_rate=0.01, steps=3),
]

TOTAL_TICKETS_PER_DAY = sum(c["count"] for c in TICKET_CATEGORIES)


def expected_cost_per_success(category: dict, model: str) -> float:
    """What a risk-budget router checks before committing traffic to a
    route: modeled cost per successful resolution for this category on
    this model, using the category's known token profile and the success
    rate that would come from 03_instrumented.py's aggregated spans in a
    real deployment. Assumes prompt caching is already on (the safe lever,
    always applied first)."""
    success_p = category["sonnet_success"] if model == "sonnet" else category["haiku_success"]
    llm_cost = cost_of_request(model, category["input_tok"], category["output_tok"],
                                apply_cache=True, is_cache_write=False)
    expected_true_cost = llm_cost + (1 - success_p) * ESCALATION_COST_BY_STEPS[category["steps"]]
    return expected_true_cost / success_p


def risk_budget_route(category: dict) -> str:
    """The fix: route by expected cost-per-successful-request per category,
    not by task-type proxy signals. Same categories can land on either
    model — what matters is whether the cheap path's modeled cost per
    success beats the expensive path's, escalation cost included."""
    haiku_cps = expected_cost_per_success(category, "haiku")
    sonnet_cps = expected_cost_per_success(category, "sonnet")
    return "haiku" if haiku_cps <= sonnet_cps else "sonnet"


def naive_route(category: dict) -> str:
    """The bug: route on word count + keyword presence instead of actual
    complexity. Three of the categories above are short and keyword-free
    but genuinely complex — this function will get all three wrong."""
    if category["word_count"] < LENGTH_THRESHOLD_WORDS and not category["has_complex_kw"]:
        return "haiku"
    return "sonnet"


def cost_of_request(model: str, ticket_input_tok: int, output_tok: int,
                     apply_cache: bool = False, is_cache_write: bool = False) -> float:
    """Single source of truth for per-request cost.

    Every request carries two input components: the ticket-specific text
    (always billed fresh — it's unique per request) and the shared
    system prompt (policy doc + tool defs + routing instructions, same
    ~2.4k tokens on every call). Without caching the system prompt is
    billed fresh every time. With caching it's billed once at the
    1.25x write rate, then at the 0.10x read rate on every call after.
    """
    if model == "sonnet":
        base_in, base_out = SONNET_INPUT, SONNET_OUTPUT
    elif model == "haiku":
        base_in, base_out = HAIKU_INPUT, HAIKU_OUTPUT
    else:
        raise ValueError(model)

    cost = ticket_input_tok * base_in
    if apply_cache:
        multiplier = CACHE_WRITE_MULTIPLIER if is_cache_write else CACHE_READ_MULTIPLIER
        cost += SHARED_SYSTEM_PROMPT_TOKENS * base_in * multiplier
    else:
        cost += SHARED_SYSTEM_PROMPT_TOKENS * base_in
    cost += output_tok * base_out
    return cost


def simulate_day(route_fn, seed: int = 42, apply_cache: bool = False):
    """Expand every category into individual ticket outcomes for one day,
    using a fixed seed so results are identical on every take.

    route_fn(category) -> "sonnet" | "haiku"
    Returns a list of per-ticket result dicts.
    """
    rng = random.Random(seed)
    rng_cache = random.Random(seed + 1)  # independent stream: caching on/off
    # must never perturb success/token/latency draws, or "same success rate
    # with and without caching" would stop being true by construction.
    results = []
    for cat in TICKET_CATEGORIES:
        model = route_fn(cat)
        success_p = cat["sonnet_success"] if model == "sonnet" else cat["haiku_success"]
        for i in range(cat["count"]):
            success = rng.random() < success_p
            is_dup = apply_cache and rng_cache.random() < cat["duplicate_rate"]
            # tiny per-ticket jitter on tokens so terminal output looks real,
            # not perfectly uniform — still fully deterministic under the seed
            input_tok = cat["input_tok"] + rng.randint(-15, 15)
            output_tok = cat["output_tok"] + rng.randint(-20, 20)
            latency_ms = (120 if model == "haiku" else 340) + rng.randint(-30, 60)

            is_cache_write = apply_cache and i == 0  # first ticket of the category writes the cache
            llm_cost = 0.0 if (apply_cache and is_dup) else cost_of_request(
                model, input_tok, output_tok, apply_cache, is_cache_write)
            # true_cost = what it actually cost the business: the API call,
            # plus escalation to a human if the model didn't resolve it.
            # A cost-per-request dashboard fed only by LLM API spend never
            # sees this second number — that's the lie.
            true_cost = llm_cost if success else llm_cost + ESCALATION_COST_BY_STEPS[cat["steps"]]

            results.append(dict(
                category=cat["name"], model=model, success=success,
                input_tok=input_tok, output_tok=output_tok,
                llm_cost=llm_cost, true_cost=true_cost,
                latency_ms=latency_ms, steps=cat["steps"],
                semantic_cache_hit=is_dup,
            ))
    return results


def summarize(results):
    total = len(results)
    successes = sum(r["success"] for r in results)
    total_llm_cost = sum(r["llm_cost"] for r in results)
    total_true_cost = sum(r["true_cost"] for r in results)
    cost_per_request = total_llm_cost / total  # the naive, dashboarded number
    cost_per_success = total_true_cost / successes if successes else float("inf")
    success_rate = successes / total
    steps_p99 = sorted(r["steps"] for r in results)[int(total * 0.99) - 1]
    return dict(
        total_requests=total,
        semantic_success_rate=success_rate,
        total_llm_cost=total_llm_cost,
        total_true_cost=total_true_cost,
        cost_per_request=cost_per_request,
        cost_per_successful_request=cost_per_success,
        steps_to_completion_p99=steps_p99,
    )


def fmt_money(x):
    """$2 decimals for totals, more precision for sub-cent per-request costs."""
    if x >= 1:
        return f"${x:,.2f}"
    return f"${x:,.4f}"
