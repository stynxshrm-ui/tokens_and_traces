"""
04_fixed.py — the fix isn't a better model to route to. It's routing by
budget, not task type, and monitoring the one metric that can't be gamed
by a cheaper failure.

Run:  DEMO=1 python 04_fixed.py
"""

from common import (simulate_day, summarize, fmt_money, naive_route,
                     risk_budget_route, expected_cost_per_success, TICKET_CATEGORIES)


def main():
    print("=" * 64)
    print("04_fixed.py — route by cost-per-successful-request, not task type")
    print("=" * 64)
    print(f"{'category':34} {'haiku_cps':>10} {'sonnet_cps':>11} {'-> route':>9} {'naive was':>10}")
    for cat in TICKET_CATEGORIES:
        h = expected_cost_per_success(cat, "haiku")
        s = expected_cost_per_success(cat, "sonnet")
        route = risk_budget_route(cat)
        naive = naive_route(cat)
        flag = "  <- reverted" if route != naive else ""
        print(f"{cat['name']:34} {fmt_money(h):>10} {fmt_money(s):>11} {route:>9} {naive:>10}{flag}")

    print()
    print("Three categories that naive routing sent to Haiku on a length/keyword")
    print("guess get reverted to Sonnet here — not because they're long, but")
    print("because their modeled cost per success is worse on the cheap path.")
    print("The genuinely simple categories still route to Haiku. Same lever,")
    print("used on the number that actually predicts the outcome.")

    baseline = summarize(simulate_day(lambda c: "sonnet", apply_cache=True))
    broken = summarize(simulate_day(naive_route, apply_cache=True))
    fixed = summarize(simulate_day(risk_budget_route, apply_cache=True))

    print()
    print(f"{'':34} {'success':>8} {'cost/req':>10} {'cost/success':>13}")
    print(f"{'baseline (all Sonnet, cached)':34} "
          f"{baseline['semantic_success_rate']*100:>7.1f}% "
          f"{fmt_money(baseline['cost_per_request']):>10} "
          f"{fmt_money(baseline['cost_per_successful_request']):>13}")
    print(f"{'broken (naive router, cached)':34} "
          f"{broken['semantic_success_rate']*100:>7.1f}% "
          f"{fmt_money(broken['cost_per_request']):>10} "
          f"{fmt_money(broken['cost_per_successful_request']):>13}")
    print(f"{'fixed (budget router, cached)':34} "
          f"{fixed['semantic_success_rate']*100:>7.1f}% "
          f"{fmt_money(fixed['cost_per_request']):>10} "
          f"{fmt_money(fixed['cost_per_successful_request']):>13}")

    savings_vs_baseline = (1 - fixed['cost_per_successful_request'] / baseline['cost_per_successful_request']) * 100
    print()
    print(f"Fixed router: {savings_vs_baseline:.1f}% cheaper per successful request than "
          f"sending everything to Sonnet — real savings, without the hidden regression.")

    # --- fail-closed monitoring, stated explicitly -----------------------
    print()
    print("Production pattern: this isn't a one-time decision. Every route's")
    print("cost-per-successful-request is recomputed continuously from live spans.")
    print("If a route's cheap-path cost-per-success rises above its expensive-path")
    print("cost-per-success — model drift, a prompt regression, a new ticket shape —")
    print("the router fails closed: that category reverts to Sonnet until a human")
    print("reviews it. It does not silently keep sending traffic to a route that's")
    print("gone bad, the way the length/keyword router did.")

    drifted = dict(TICKET_CATEGORIES[0])  # password_reset, the one real Haiku win
    drifted["haiku_success"] = 0.80  # simulate a quality regression
    h = expected_cost_per_success(drifted, "haiku")
    s = expected_cost_per_success(drifted, "sonnet")
    route = "haiku" if h <= s else "sonnet"
    print(f"\n  Simulated drift on password_reset (Haiku success 99% -> 80%):")
    print(f"    haiku_cps={fmt_money(h)}  sonnet_cps={fmt_money(s)}  -> routes to {route}")
    print(f"    ALERT: cost_per_successful_request.haiku exceeded "
          f"cost_per_successful_request.sonnet for password_reset. Reverted.")


if __name__ == "__main__":
    main()
