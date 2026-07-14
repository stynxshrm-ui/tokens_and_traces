"""
01_clean.py — baseline. Every ticket goes to Sonnet 5. No routing, no caching.

Expensive, but it works. This is the number the rest of the video protects:
cost per SUCCESSFUL request. Not cost per request.

Run:  DEMO=1 python 01_broken.py
"""

import argparse
from common import simulate_day, summarize, fmt_money, naive_route, TICKET_CATEGORIES, TOTAL_TICKETS_PER_DAY


def main():

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Baseline: all traffic on Sonnet 5")
    parser.add_argument(
        "--tsr", 
        type=str, 
        default="False",
        choices=["True", "False"],
        help="Toggle printing of Cost per successful request (TSR = True Success Rate). Default: True"
    )
    args = parser.parse_args()
    
    # Convert string to boolean
    show_tsr = args.tsr == "True"      

    results = simulate_day(naive_route, apply_cache=False)
    stats = summarize(results)

    print("=" * 64)
    print("01_broken.py — routing by word count + keyword presence")
    print("=" * 64)
    print(f"Tickets/day:                    {TOTAL_TICKETS_PER_DAY:,}")
    print(f"Total daily API cost:            {fmt_money(stats['total_llm_cost'])}")
    print(f"Cost per request (API only):     {fmt_money(stats['cost_per_request'])}")
    if show_tsr:
        print(f"Cost per successful request:     {fmt_money(stats['cost_per_successful_request'])}")
        print(f"Semantic success rate:           {stats['semantic_success_rate']*100:.1f}%")
        print(f"Total daily true cost:           {fmt_money(stats['total_true_cost'])}  (API + escalations)")
    print(f"Steps-to-completion, p99:        {stats['steps_to_completion_p99']}")
    print()


if __name__ == "__main__":
    main()
