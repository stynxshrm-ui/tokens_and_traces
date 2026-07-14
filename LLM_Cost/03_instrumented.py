"""
03_instrumented.py — same bug, same router, but now every request emits a
real OTel span (GenAI semconv), and we measure the two cost levers
separately: prompt caching (safe) vs routing (what's actually broken).

Run:  DEMO=1 python 03_instrumented.py
"""

from common import (simulate_day, summarize, fmt_money, naive_route,
                     TICKET_CATEGORIES, SHARED_SYSTEM_PROMPT_TOKENS)
from otel_setup import get_tracer, emit_span


def main():
    tracer = get_tracer("tokens-traces.ticket-triage", verbose_console=False)
    tracer_console = get_tracer("tokens-traces.ticket-triage.sample", verbose_console=True)

    print("=" * 64)
    print("03_instrumented.py — same router, now measured")
    print("=" * 64)

    # --- Lever 1: routing (the risky one) ------------------------------
    results = simulate_day(naive_route, apply_cache=False)
    sample_shown = 0
    for r in results:
        r["routing_reason"] = "length+keyword:haiku" if r["model"] == "haiku" else "length+keyword:sonnet"
        # Real OTel console export for 3 illustrative spans — a misrouted
        # category, so the exported attributes tell the whole story on
        # their own (routing_reason=haiku, semantic_success=False).
        if r["category"] == "billing_duplicate_charge" and not r["success"] and sample_shown < 1:
            print("\n[real OTel span, ConsoleSpanExporter output]")
            emit_span(tracer_console, r)
            sample_shown += 1
        else:
            emit_span(tracer, r)

    stats = summarize(results)
    print()
    print(f"\nRouting lever:")
    print(f"  Semantic success rate:          {stats['semantic_success_rate']*100:.1f}%")
    print(f"  Cost per request (API only):    {fmt_money(stats['cost_per_request'])}")
    print(f"  Cost per successful request:    {fmt_money(stats['cost_per_successful_request'])}")

    # --- Lever 2: prompt caching (the safe one) -------------------------
    # Same routing decisions, same success rates — caching doesn't touch
    # accuracy at all, only the cost of the shared system-prompt tokens.
    cached_results = simulate_day(naive_route, apply_cache=True)
    cached_stats = summarize(cached_results)

    print(f"\nCaching lever (shared {SHARED_SYSTEM_PROMPT_TOKENS}-token system prompt, "
          f"cache_control: ephemeral):")
    print(f"  Cost per request (API only):    {fmt_money(cached_stats['cost_per_request'])} "
          f"(was {fmt_money(stats['cost_per_request'])})")
    api_cost_delta = (1 - cached_stats['cost_per_request'] / stats['cost_per_request']) * 100
    print(f"  API cost reduction from caching: {api_cost_delta:.1f}%")
    print(f"  Semantic success rate:          {cached_stats['semantic_success_rate']*100:.1f}% "
          f"(unchanged — caching carries no accuracy risk)")

    dup_hits = sum(r["semantic_cache_hit"] for r in cached_results)
    print(f"\n  Semantic/result cache (exact-duplicate tickets): {dup_hits} of "
          f"{len(cached_results)} requests were near-duplicates and skipped the "
          f"model call entirely — that's a second, separate cache with its own risk: "
          f"a stale or wrong cache hit serves a wrong answer with no model in the loop "
          f"to catch it. Ship it with a similarity threshold you've tuned, not a default.")

    print(f"\nCaching cut cost. It did nothing to the number that actually broke: "
          f"{fmt_money(stats['cost_per_successful_request'])} cost per successful request "
          f"is still the routing problem, unsolved.")


if __name__ == "__main__":
    main()
