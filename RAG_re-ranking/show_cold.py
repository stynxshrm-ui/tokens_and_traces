# show_cold_open.py
from common import build_corpus, retrieve, score_doc, RERANK_WINDOW_TOKENS

docs, queries = build_corpus()
q4 = [q for q in queries if q.query_id == "q4"][0]

# Candidate set (same as the pipeline uses)
candidates = retrieve(q4, docs, k=150)

# Score with truncation (the "should win" case) — 01_clean behavior
truncated_scores = []
for d in candidates:
    score, _ = score_doc(q4, d, truncate_only=True)
    truncated_scores.append((score, d))
truncated_scores.sort(key=lambda x: x[0], reverse=True)

# Score with chunk+max (the "broken" case) — 02_broken behavior
chunked_scores = []
for d in candidates:
    score, per_chunk = score_doc(q4, d, truncate_only=False)
    chunked_scores.append((score, len(per_chunk), d))
chunked_scores.sort(key=lambda x: x[0], reverse=True)

# Find ranks
trunc_rank = next(i+1 for i, (_, d) in enumerate(truncated_scores) if d.doc_id == q4.gold_doc_id)
chunk_rank = next(i+1 for i, (_, _, d) in enumerate(chunked_scores) if d.doc_id == q4.gold_doc_id)
top_trunc = truncated_scores[0]
top_chunk = chunked_scores[0]
gold_doc = [d for d in docs if d.doc_id == q4.gold_doc_id][0]

print("=== COLD OPEN: q4 ===")
print()
print("LEFT (should win, and does):")
print(f"  q4 gold answer: {gold_doc.doc_id} ({gold_doc.pages} pages, {len(score_doc(q4, gold_doc, truncate_only=True)[1])} chunks)")
print(f"  rank: {trunc_rank}")
print()
print("RIGHT (should NOT win, but does with chunk+max):")
print(f"  X36 (62 pages, 73 chunks, NO ANSWER): rank {[i+1 for i, (_, _, d) in enumerate(chunked_scores) if d.doc_id == 'X36'][0]}")
print(f"  q4 gold answer demoted to rank: {chunk_rank}")
print()
print("=== SPLIT SCREEN: left shows rank 1, right shows rank 18 ===")