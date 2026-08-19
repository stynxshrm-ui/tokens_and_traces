"""
04_fixed.py -- rank on calibrated margin, not raw max.

The fix is not "go back to truncation." It is: never let a raw max score
cross document lengths without accounting for how many rolls it got.

  1. Load the null-calibration table measured in 03 (expected max score under
     ZERO real relevance, per chunk count).
  2. Rank on margin = observed_max - null_baseline(n_chunks).
  3. Emit tokens_traces.rerank.* attributes alongside standard OTel GenAI
     attributes. Namespaced extension, not a custom logger.
  4. Fail closed: if nothing clears the margin threshold, surface the
     ambiguity instead of serving a confident wrong answer.

Requires: python 03_instrumented.py first (writes sweep_export.json).
Run: DEMO=1 python 04_fixed.py
"""

from common import (TOP_K_CONTEXT_DEFAULT, banner, build_corpus,
                    calibration_from_export, chunk_doc, generation_cost,
                    recall_at_k, retrieve, rerank_cost, save_json, score_doc,
                    semantic_success, cost_per_successful_request)

MARGIN_THRESHOLD = 0.15  # A11: minimum calibrated margin to serve. Tunable here.


def emit_span(query_id, doc, n_chunks, pooled, baseline, margin, flagged):
    """OTel GenAI semconv attributes + our namespaced extension."""
    return {
        "gen_ai.operation.name": "rerank",
        "gen_ai.request.model": "bge-reranker-v2-m3",
        "tokens_traces.rerank.chunk_count": n_chunks,
        "tokens_traces.rerank.pooled_score": round(pooled, 4),
        "tokens_traces.rerank.null_baseline": round(baseline, 4),
        "tokens_traces.rerank.calibrated_margin": round(margin, 4),
        "tokens_traces.rerank.length_bias_flag": flagged,
        "tokens_traces.rerank.doc_id": doc.doc_id,
        "tokens_traces.rerank.query_id": query_id,
    }


def main() -> None:
    docs, queries = build_corpus()
    cal = calibration_from_export()

    banner("FIXED: rank on calibrated margin, not raw max")
    print("  null-calibration table (measured in 03, not assumed):")
    for n, base in sorted(cal.table.items()):
        print(f"    {n:>4} chunks -> expected max under zero relevance: {base:.3f}")
    print(f"\n  margin threshold: {MARGIN_THRESHOLD}  (fails closed below this)\n")

    total_cost, successes, total_chunks, flagged_total = 0.0, 0, 0, 0
    spans, served = [], 0

    for q in queries:
        candidates = retrieve(q, docs, k=150)
        rows = []
        for d in candidates:
            pooled, per_chunk = score_doc(q, d)
            n = len(per_chunk)
            total_chunks += n
            base = cal.baseline_for(n)
            margin = pooled - base
            flagged = pooled >= base and margin < MARGIN_THRESHOLD and n >= 8
            flagged_total += int(flagged)
            spans.append(emit_span(q.query_id, d, n, pooled, base, margin, flagged))
            rows.append((margin, pooled, n, d))

        rows.sort(key=lambda t: t[0], reverse=True)
        eligible = [r for r in rows if r[0] >= MARGIN_THRESHOLD]

        if not eligible:
            print(f"  {q.query_id}  NO CANDIDATE CLEARS MARGIN -> fail closed, "
                  f"escalate (served nothing)")
            continue

        served += 1
        context = [d for _, _, _, d in eligible[:TOP_K_CONTEXT_DEFAULT]]
        ok = semantic_success(q, context)
        successes += ok
        total_cost += generation_cost(context)

        ranked = [d for _, _, _, d in rows]
        gold_rank = next(i + 1 for i, d in enumerate(ranked) if d.doc_id == q.gold_doc_id)
        margin, pooled, n, top = rows[0]
        print(f"  {q.query_id}  gold rank: {gold_rank:>3}   top: {top.doc_id} "
              f"({top.pages}pp, {n} chunks)  raw={pooled:.3f} margin={margin:.3f}"
              f"   {'OK' if ok else 'miss'}")

    total_cost += rerank_cost(total_chunks)
    n_q = len(queries)

    print(f"\n  semantic success rate       : {successes/n_q:.0%}")
    print(f"  cost per successful request : "
          f"${cost_per_successful_request(total_cost, successes):.4f}")
    print(f"  requests served             : {served}/{n_q} "
          f"({n_q - served} escalated rather than guessed)")

    banner("ALERT: length-bias flag firing")
    fired = [s for s in spans if s["tokens_traces.rerank.length_bias_flag"]][:3]
    print(f"  {flagged_total:,} of {len(spans):,} reranked documents flagged\n")
    for s in fired:
        print(f"  [ALERT] doc={s['tokens_traces.rerank.doc_id']} "
              f"query={s['tokens_traces.rerank.query_id']}")
        print(f"          chunk_count={s['tokens_traces.rerank.chunk_count']} "
              f"pooled={s['tokens_traces.rerank.pooled_score']} "
              f"baseline={s['tokens_traces.rerank.null_baseline']} "
              f"margin={s['tokens_traces.rerank.calibrated_margin']}")
        print(f"          rank driven by chunk count, not relevance -> demoted\n")

    save_json("fixed_spans.json", {"threshold": MARGIN_THRESHOLD, "spans": spans[:200]})
    print("  wrote fixed_spans.json")


if __name__ == "__main__":
    main()
