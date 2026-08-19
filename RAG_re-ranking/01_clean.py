"""
01_clean.py -- reranking working exactly as advertised.

Short filings only. Documents still get chunked, but every candidate has a
COMPARABLE chunk count, so whatever bias pooling introduces applies equally to
all of them and cancels out of the ranking. This is the case every reranking
blog post is about, and it works.

Run: DEMO=1 python 01_clean.py
"""

from common import (banner, build_corpus, recall_at_k, retrieve, score_doc,
                    RERANK_WINDOW_TOKENS)


def main() -> None:
    docs, queries = build_corpus()
    short_docs = [d for d in docs if d.pages <= 6]
    short_queries = [q for q in queries if any(d.doc_id == q.gold_doc_id for d in short_docs)]

    banner("CLEAN: short filings, comparable chunk counts")
    print(f"corpus: {len(short_docs)} docs, all <= 6 pages")
    print(f"reranker window: {RERANK_WINDOW_TOKENS} tokens")
    chunk_counts = sorted({len(d.text.split()) * 132 // 100 // RERANK_WINDOW_TOKENS + 1
                           for d in short_docs})
    print(f"chunks per doc: {chunk_counts[0]}-{chunk_counts[-1]}  (comparable -> bias cancels)\n")

    pre_hits = post_hits = 0
    for q in short_queries:
        candidates = retrieve(q, short_docs, k=150)
        pre_hits += recall_at_k(candidates, q.gold_doc_id, 5)

        reranked = sorted(candidates, key=lambda d: score_doc(q, d)[0], reverse=True)
        post_hits += recall_at_k(reranked, q.gold_doc_id, 5)

        rank = next(i + 1 for i, d in enumerate(reranked) if d.doc_id == q.gold_doc_id)
        print(f"  {q.query_id}  gold={q.gold_doc_id}  rank after rerank: {rank}")

    n = len(short_queries)
    print(f"\n  recall@5 before rerank : {pre_hits}/{n}  ({pre_hits/n:.0%})")
    print(f"  recall@5 after  rerank : {post_hits}/{n}  ({post_hits/n:.0%})")
    print("\n  This is the reranking everyone writes about. No argument here.")


if __name__ == "__main__":
    main()
