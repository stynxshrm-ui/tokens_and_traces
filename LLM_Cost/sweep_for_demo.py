"""
sweep_for_demo.py — NOT one of the four story files. This generates the
data table embedded in the HTML payoff visualization by re-running the
exact same cost model across a range of router thresholds. Every number
in the demo traces back to this script, which traces back to common.py.

Run:  DEMO=1 python sweep_for_demo.py > demo_data.json
"""

import json
from common import simulate_day, summarize, TICKET_CATEGORIES, TOTAL_TICKETS_PER_DAY


def route_at_threshold(category, word_threshold):
    if category["word_count"] < word_threshold and not category["has_complex_kw"]:
        return "haiku"
    return "sonnet"


def main():
    points = []
    for threshold in range(0, 65, 2):
        route_fn = lambda cat, t=threshold: route_at_threshold(cat, t)
        results = simulate_day(route_fn, apply_cache=True)
        stats = summarize(results)
        # A category is "misrouted" when the router sends it to Haiku but its
        # true_complexity is complex. Count both the number of category TYPES
        # and the daily REQUEST volume they represent — the volume is the
        # number that actually turns into the cost-per-success blowup.
        misrouted_cats = [
            cat for cat in TICKET_CATEGORIES
            if route_fn(cat) == "haiku" and cat["true_complexity"] == "complex"
        ]
        n_misrouted = len(misrouted_cats)
        misrouted_requests = sum(cat["count"] for cat in misrouted_cats)
        points.append(dict(
            threshold=threshold,
            success_rate=round(stats["semantic_success_rate"] * 100, 2),
            cost_per_request=round(stats["cost_per_request"], 5),
            cost_per_success=round(stats["cost_per_successful_request"], 4),
            misrouted_categories=n_misrouted,
            misrouted_requests=misrouted_requests,
            misrouted_pct=round(misrouted_requests / TOTAL_TICKETS_PER_DAY * 100, 1),
        ))

    print(json.dumps(points, indent=2))


if __name__ == "__main__":
    main()
