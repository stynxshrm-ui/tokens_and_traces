"""
02_broken.py -- the fix that is a new bug.

Same pipeline, full-length filings. Two passes:

  PASS 1 (old, known bug): truncate to the reranker window. Anything past the
          window is invisible. Recall collapses on long filings. This is the
          documented anti-pattern -- not the discovery of this video.

  PASS 2 (the "fix"): split each document into windows, score every window,
          keep the max. This is the scheme Cohere's rerank-v4.0 docs describe.
          Recall recovers. It looks fixed.

Run: DEMO=1 python 02_broken.py
"""

from common import (RERANK_WINDOW_TOKENS, banner, build_corpus, chunk_doc,
                    recall_at_k, retrieve, score_doc)


def n_chunks(doc, q) -> int:
    return len(chunk_doc(doc, gold_sentence=q.gold_sentence))


def evaluate(queries, docs, truncate_only: bool):
    hits = 0
    rows = []
    for q in queries:
        candidates = retrieve(q, docs, k=150)
        ranked = sorted(candidates,
                        key=lambda d: score_doc(q, d, truncate_only=truncate_only)[0],
                        reverse=True)
        hits += recall_at_k(ranked, q.gold_doc_id, 5)
        rank = next(i + 1 for i, d in enumerate(ranked) if d.doc_id == q.gold_doc_id)
        top = ranked[0]
        rows.append((q.query_id, rank, top.doc_id, top.pages, n_chunks(top, q)))
    return hits, rows


def report(label, queries, docs, truncate_only):
    hits, rows = evaluate(queries, docs, truncate_only)
    n = len(queries)
    for qid, rank, top_id, top_pages, top_chunks in rows:
        print(f"  {qid}  gold rank: {rank:>3}   top hit: {top_id} "
              f"({top_pages}pp, {top_chunks} chunks)")
    print(f"  -> {label} recall@5: {hits}/{n} ({hits/n:.0%})")
    return hits, rows, n


def main() -> None:
    docs, queries = build_corpus()
    by_id = {d.doc_id: d for d in docs}
    long_q = [q for q in queries if by_id[q.gold_doc_id].pages > 6]
    short_q = [q for q in queries if by_id[q.gold_doc_id].pages <= 6]

    banner("BROKEN PASS 1: naive truncation (the old, well-known bug)")
    print(f"reranker window: {RERANK_WINDOW_TOKENS} tokens -- everything past it is unread\n")
    print(" long-filing answers (gold paragraph sits past the window):")
    h1, _, n1 = report("long-gold", long_q, docs, truncate_only=True)
    print("\n short-filing answers (gold paragraph is inside the window):")
    h1s, _, n1s = report("short-gold", short_q, docs, truncate_only=True)
    print(f"\n  overall recall@5: {(h1+h1s)}/{n1+n1s} ({(h1+h1s)/(n1+n1s):.0%})")

    banner("BROKEN PASS 2: chunk + max-pool (the vendor 'fix')")
    print("scheme: split into windows, score each, document score = max(chunk scores)")
    print("source: Cohere rerank-v4.0 docs -- VERIFY week of filming\n")
    print(" long-filing answers:")
    h2, _, n2 = report("long-gold", long_q, docs, truncate_only=False)
    print("\n short-filing answers  <-- WATCH THIS ONE:")
    h2s, rows2s, n2s = report("short-gold", short_q, docs, truncate_only=False)
    print(f"\n  overall recall@5: {(h2+h2s)}/{n2+n2s} ({(h2+h2s)/(n2+n2s):.0%})")

    beaten = [(qid, top_id, pages, chunks) for qid, rank, top_id, pages, chunks in rows2s
              if rank > 1 and pages > 6]
    print("\n  Long filings now beating short, correct answers to the top slot:")
    for qid, top_id, pages, chunks in beaten:
        print(f"    {qid}: outranked by {top_id} -- {pages}pp, {chunks} chunks, "
              f"contains no answer")
    print("\n  Truncation dropped long documents. Max-pooling promotes them.")
    print("  Same aggregate metric. Opposite failure. 03_instrumented.py explains why.")


if __name__ == "__main__":
    main()
