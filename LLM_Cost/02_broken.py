"""
02_broken.py — the innocent-looking change.

Someone adds a router: short tickets with no complex-sounding keywords go
to Haiku 4.5. Ten lines. Nobody would flag this in review.

Run:  DEMO=1 python 02_broken.py
"""

from common import simulate_day, summarize, fmt_money, naive_route, TICKET_CATEGORIES


def main():
    print("=" * 64)
    print("02_broken.py — routing by word count + keyword presence")
    print("=" * 64)
    print("Router: word_count < 25 and no complex keyword -> Haiku 4.5, else Sonnet 5")
    print()
    print(f"{'category':34} {'words':>6} {'kw?':>5} {'true':>9} {'routed':>8}")
    for cat in TICKET_CATEGORIES:
        routed = naive_route(cat)
        flag = " <-- misrouted" if (routed == "haiku" and cat["true_complexity"] == "complex") else ""
        print(f"{cat['name']:34} {cat['word_count']:>6} "
              f"{'yes' if cat['has_complex_kw'] else 'no':>5} "
              f"{cat['true_complexity']:>9} {routed:>8}{flag}")
    print()

    results = simulate_day(naive_route, apply_cache=False)
    stats = summarize(results)

    print(f"Semantic success rate:           {stats['semantic_success_rate']*100:.1f}%")
    print(f"Total daily API cost:            {fmt_money(stats['total_llm_cost'])}")
    print(f"Total daily true cost:           {fmt_money(stats['total_true_cost'])}  (API + escalations)")
    print(f"Cost per request (API only):     {fmt_money(stats['cost_per_request'])}   <- this is what shipped the launch")
    print(f"Cost per successful request:     {fmt_money(stats['cost_per_successful_request'])}   <- this is what actually happened")
    print()
    print("Cost per request dropped. That's the number on the dashboard.")
    print("Cost per successful request is the one nobody's tracking.")


if __name__ == "__main__":
    main()
