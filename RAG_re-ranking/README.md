# Your reranker's fix for long documents is a new bug

Chunking long documents and taking `max(chunk scores)` is the standard fix for
a cross-encoder reranker's context limit — it's the scheme
[Cohere's rerank-v4.0 docs](https://docs.cohere.com) describe. It doesn't fix
the token limit. It creates a noise ceiling that climbs with chunk count, and
occasionally that's enough to bury a correct answer under an irrelevant
document that's just longer.

Companion video: **[https://youtu.be/juLE2heSbBA]**

## The finding

400 documents with **zero real content**, scored at their own natural length —
no truncation, nothing hand-picked:

| chunks | mean score |
|---|---|
| ≤4 | 0.383 |
| ≤8 | 0.437 |
| ≤128 | 0.619 |
| 150+ | 0.652 |

Real answers usually still win when paired against their own scrambled twin.
Not always: one query in this run fell from rank 1 to rank 18, beaten by a
62-page filing with 73 chunks and no answer in it anywhere. An aggregate
recall@5 that looked like a clean win (90%) was blending a genuinely-fixed
long-document bucket (100%) with a quietly-degraded short-document one (80%).

## Run it

```bash
git clone [repo]
cd rerank-length-bias
pip install -r requirements.txt

DEMO=1 python 01_clean.py          # reranking working as advertised
DEMO=1 python 02_broken.py         # the "fix" and what it breaks
DEMO=1 python 03_instrumented.py   # the noise-ceiling experiment
python build_tables.py             # renders the two result tables
DEMO=1 python 04_fixed.py          # null-calibrated fix
```

`DEMO=1` (default) uses a deterministic simulated cross-encoder — no API key,
no GPU, no weights download, identical output every run. Set `DEMO=0` to route
scoring through a real `bge-reranker-v2-m3` via `sentence-transformers`
instead — install `sentence-transformers` first, and expect the exact numbers
above to shift; the mechanism doesn't depend on the simulation, the magnitudes
do.

## Files

```
common.py              corpus, chunking, scoring, cost math -- single source of truth
01_clean.py             short filings, reranking works as advertised
02_broken.py             the truncation bug, then the chunk+max "fix"
03_instrumented.py      noise-ceiling experiment + real-vs-twin pairs -> sweep_export.json
04_fixed.py             null-calibrated ranking, fails closed
build_tables.py         renders diagrams/*_table.html from sweep_export.json
diagrams/               architecture + result cards (svg/html + rendered png)
```

Every number in `diagrams/` is templated from `sweep_export.json` — nothing is
typed in by hand. Regenerate the export, rerun `build_tables.py`, the cards
update.

## License

MIT
