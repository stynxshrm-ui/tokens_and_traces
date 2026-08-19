"""
03_instrumented.py -- measure it, then prove what it is.

Two parts:

  PART 1  Instrumented pipeline. Semantic success rate, cost per SUCCESSFUL
          request, and -- new for this pipeline -- chunk count and score margin
          logged per document. The aggregate looks good. One breakdown doesn't.

  PART 2  The control experiment. For each document, build a content-null twin:
          same length, same chunk count, words shuffled so nothing in it answers
          the query. If chunk+max measures relevance, these score near zero.

          They don't. That is the payoff.

Writes sweep_export.json -- the demo reads its numbers from that file and only
that file. Nothing is hand-entered into the HTML.

Run: DEMO=1 python 03_instrumented.py
"""

import statistics

from common import (GEN_MODEL, NOISE_SCORE_MEAN, NOISE_SCORE_SD,
                    PRICING_EXPIRES_ON, PRICING_VERIFIED_ON, banner,
                    build_corpus, chunk_doc, cost_per_successful_request,
                    generation_cost, pool, recall_at_k, rerank_cost, retrieve,
                    save_json, score_doc, score_pair, scrambled_twin,
                    semantic_success)

CHUNK_BUCKETS = (1, 2, 4, 8, 16, 32, 64, 128)
TOP_K_CONTEXT = 3


def instrumented_run(queries, docs, truncate_only: bool):
    """One full pass with per-stage metrics."""
    total_cost = 0.0
    successes = 0
    total_chunks = 0
    per_query = []

    for q in queries:
        candidates = retrieve(q, docs, k=150)
        scored = []
        for d in candidates:
            s, per_chunk = score_doc(q, d, truncate_only=truncate_only)
            total_chunks += len(per_chunk)
            scored.append((s, len(per_chunk), d))
        scored.sort(key=lambda t: t[0], reverse=True)

        context = [d for _, _, d in scored[:TOP_K_CONTEXT]]
        ok = semantic_success(q, context)
        successes += ok
        cost = generation_cost(context)
        total_cost += cost

        top_score, top_chunks, top_doc = scored[0]
        runner_up = scored[1][0]
        per_query.append({
            "query_id": q.query_id,
            "gold_doc": q.gold_doc_id,
            "gold_rank": next(i + 1 for i, (_, _, d) in enumerate(scored)
                              if d.doc_id == q.gold_doc_id),
            "top_doc": top_doc.doc_id,
            "top_pages": top_doc.pages,
            "top_chunks": top_chunks,
            "top_score": round(top_score, 4),
            "score_margin": round(top_score - runner_up, 4),
            "semantic_success": ok,
            "gen_cost_usd": round(cost, 6),
            "recall_at_5": recall_at_k([d for _, _, d in scored], q.gold_doc_id, 5),
        })

    total_cost += rerank_cost(total_chunks)
    return {
        "semantic_success_rate": successes / len(queries),
        "cost_per_successful_request": cost_per_successful_request(total_cost, successes),
        "total_cost_usd": total_cost,
        "total_chunks_scored": total_chunks,
        "per_query": per_query,
    }


def noise_ceiling(queries, distractor_docs):
    """How high does a PURE NOISE document's max-pooled score climb, as a
    function of its own natural chunk count -- no truncation, no twin
    construction, just real distractor documents (no gold content by
    construction) scored at full length. Large sample (40 docs x 10 queries),
    complements the 10 paired real-vs-twin points below.
    """
    points = []
    for d in distractor_docs:
        n = len(chunk_doc(d))
        for q in queries:
            chunks = chunk_doc(d)  # no gold_sentence -- distractors have none
            score = pool([score_pair(q.text, c) for c in chunks])
            points.append({"n_chunks": n, "score": round(score, 4)})
    return points


def bucket_noise_ceiling(points, buckets=CHUNK_BUCKETS):
    """Bin the noise-ceiling scatter into the same chunk-count buckets used
    on screen, for a clean chart line rather than a raw scatter."""
    out = []
    for lo, hi in zip([0] + list(buckets), list(buckets) + [10_000]):
        bucket_pts = [p["score"] for p in points if lo < p["n_chunks"] <= hi]
        if bucket_pts:
            out.append({
                "n_chunks": hi,
                "mean_score": round(statistics.mean(bucket_pts), 4),
                "p95_score": round(sorted(bucket_pts)[int(0.95 * len(bucket_pts)) - 1], 4),
                "n_samples": len(bucket_pts),
            })
    return out


def control_experiment(queries, docs):
    """Real document vs. its own content-null twin, at the document's OWN
    natural chunk count.

    Earlier version truncated long documents to a fixed prefix length per
    bucket. That's wrong: gold sentences in this corpus sit 45-85% of the way
    through a long filing, so short prefixes usually exclude the signal chunk
    entirely -- the 'real' curve at low N was measuring truncated documents
    that also didn't contain the answer, not real short documents. Comparing
    each document to its own full-length twin removes that confound: same
    document, same chunks, only the words are shuffled.
    """
    by_id = {d.doc_id: d for d in docs}
    rows = []
    for q in queries:
        d = by_id[q.gold_doc_id]
        real_chunks = chunk_doc(d, gold_sentence=q.gold_sentence)
        twin = scrambled_twin(d)
        null_chunks = chunk_doc(twin)
        real_score = pool([score_pair(q.text, c) for c in real_chunks])
        null_score = pool([score_pair(q.text, c) for c in null_chunks])
        rows.append({
            "query_id": q.query_id,
            "doc_id": d.doc_id,
            "n_chunks": len(real_chunks),
            "real_score": round(real_score, 4),
            "null_score": round(null_score, 4),
            "gap": round(real_score - null_score, 4),
        })
    rows.sort(key=lambda r: r["n_chunks"])
    return rows


def main() -> None:
    docs, queries = build_corpus()

    banner("PART 1: instrumented -- truncation vs chunk+max")
    before = instrumented_run(queries, docs, truncate_only=True)
    after = instrumented_run(queries, docs, truncate_only=False)

    print(f"  pricing model: {GEN_MODEL}  (verified {PRICING_VERIFIED_ON}, "
          f"introductory rate EXPIRES {PRICING_EXPIRES_ON})\n")
    print(f"  {'metric':<34}{'truncate':>14}{'chunk+max':>14}")
    print(f"  {'-'*62}")
    print(f"  {'semantic success rate':<34}"
          f"{before['semantic_success_rate']:>13.0%}{after['semantic_success_rate']:>14.0%}")
    print(f"  {'cost per successful request':<34}"
          f"${before['cost_per_successful_request']:>12.4f}"
          f"${after['cost_per_successful_request']:>13.4f}")
    print(f"  {'chunks scored':<34}"
          f"{before['total_chunks_scored']:>13,}{after['total_chunks_scored']:>14,}")

    long_top_before = sum(1 for r in before["per_query"] if r["top_pages"] > 6)
    long_top_after = sum(1 for r in after["per_query"] if r["top_pages"] > 6)
    n = len(queries)
    print(f"  {'top-1 slots won by long filings':<34}"
          f"{long_top_before:>10}/{n}{long_top_after:>11}/{n}   <-- RE-HOOK")

    banner("PART 2a: noise ceiling -- pure-noise documents, natural length")
    print("  40 distractor documents, no gold content by construction.")
    print("  Scored at their own real length, no truncation, no twin needed.\n")
    distractors = [d for d in docs if d.gold_for is None]
    noise_pts = noise_ceiling(queries, distractors)
    noise_curve = bucket_noise_ceiling(noise_pts)
    print(f"  {'chunks <=':>10}{'mean noise max':>18}{'p95':>10}{'n':>8}")
    print(f"  {'-'*48}")
    for row in noise_curve:
        print(f"  {row['n_chunks']:>10}{row['mean_score']:>18.3f}"
              f"{row['p95_score']:>10.3f}{row['n_samples']:>8}")
    lift = noise_curve[-1]["mean_score"] - noise_curve[0]["mean_score"]
    print(f"\n  pure noise climbs {lift:+.3f} from the smallest to largest bucket,")
    print(f"  on {sum(r['n_samples'] for r in noise_curve)} samples, zero gold content in any of them.")

    banner("PART 2b: paired real document vs. its own scrambled twin")
    print("  Same document, same chunk count. Words shuffled. No answer inside.\n")
    pairs = control_experiment(queries, docs)
    print(f"  {'query':<6}{'chunks':>8}{'real':>10}{'null (twin)':>14}{'gap':>10}")
    print(f"  {'-'*48}")
    for r in pairs:
        print(f"  {r['query_id']:<6}{r['n_chunks']:>8}{r['real_score']:>10.3f}"
              f"{r['null_score']:>14.3f}{r['gap']:>10.3f}")
    short_gap = statistics.mean(r["gap"] for r in pairs if r["n_chunks"] <= 10)
    long_gap = statistics.mean(r["gap"] for r in pairs if r["n_chunks"] > 10)
    flips = sum(1 for r in pairs if r["gap"] < 0.15)
    print(f"\n  mean gap, short docs (<=10 chunks): {short_gap:+.3f}")
    print(f"  mean gap, long docs  (>10 chunks) : {long_gap:+.3f}")
    print(f"\n  The real answer wins on average in both buckets -- this is not a")
    print(f"  guaranteed inversion. But {flips}/{len(pairs)} pairs land within 0.15,")
    print(f"  and 02_broken.py already showed what a single unlucky draw costs:")
    print(f"  q4 fell from rank 1 to rank 18 against exactly this variance.")
    print(f"  The noise ceiling above is the mechanism. This table is the risk")
    print(f"  it creates -- invisible in an aggregate metric, real per query.")

    save_json("sweep_export.json", {
        "meta": {
            "pricing_verified_on": PRICING_VERIFIED_ON,
            "pricing_expires_on": PRICING_EXPIRES_ON,
            "gen_model": GEN_MODEL,
            "noise_mean": NOISE_SCORE_MEAN,
            "noise_sd": NOISE_SCORE_SD,
        },
        "truncate": before,
        "chunk_max": after,
        "noise_ceiling_curve": noise_curve,
        "real_vs_twin_pairs": pairs,
    })
    print("\n  wrote sweep_export.json  (single source for the demo)")


if __name__ == "__main__":
    main()
