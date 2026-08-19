"""
Shared source of truth for the reranker length-bias build.

Every number that appears on camera is computed here or downstream of here.
No script computes cost, tokens, or scores independently of this module.

READ THIS BLOCK ON CAMERA. These are the assumptions the whole thesis rests on.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
from dataclasses import dataclass, field
from typing import Iterable

# ---------------------------------------------------------------------------
# ASSUMPTION BLOCK  (narrate these; every one is adjustable here and only here)
# ---------------------------------------------------------------------------

# A1. Reranker context window, in tokens. The chunk COUNT is what drives the
#     bias, not the window size -- a 140-page filing splits into many chunks at
#     512 and still splits into several at 32k.
#     VERIFY week of filming against the BAAI bge-reranker-v2-m3 model card.
#     Do not inherit this number from memory.
RERANK_WINDOW_TOKENS = 512

# A2. Vendor pooling scheme we are reproducing. Cohere's rerank-v4.0 docs
#     describe splitting long documents into ~32,764-token chunks and taking
#     relevance_score = max(per-chunk scores). rerank-v3.5 used ~4,093.
#     VERIFY week of filming -- this changed between model versions, which is
#     itself a production hazard called out in the script.
POOLING = "max"  # "max" reproduces the vendor scheme; "mean_top2" is the naive alt fix

# A3. Tokens-per-word ratio used to size chunks without a real tokenizer in
#     DEMO mode. Real mode uses the model's own tokenizer.
TOKENS_PER_WORD = 1.32

# A4. What counts as a successful request: the generated answer must be
#     grounded in the gold paragraph. In DEMO mode we score this structurally
#     (gold chunk present in the context window handed to the model, minus a
#     distraction penalty). In REAL mode a fixed rubric judges the actual text.
DISTRACTION_PENALTY = 0.12  # P(model misses the gold fact even when it's in context)

# A5. Pricing. DATED -- see README. Sonnet 5 is on an introductory rate that
#     EXPIRES 2026-08-31. From 2026-09-01 the rate is $3.00 / $15.00 per MTok.
#     If this video publishes on or after 2026-09-01, re-run every cost number
#     and re-render the thumbnail.
PRICING_VERIFIED_ON = "2026-08-06"
PRICING_EXPIRES_ON = "2026-08-31"  # Sonnet 5 introductory rate end date
PRICE_PER_MTOK = {
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},   # introductory, expires above
    "claude-sonnet-5-post-2026-09-01": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}
GEN_MODEL = "claude-sonnet-5"

# A6. Self-hosted rerank cost is modelled as amortised GPU time, not a per-call
#     API price. This is a modelling choice, not a measurement. Adjust here.
GPU_DOLLARS_PER_HOUR = 1.20
RERANK_MS_PER_CHUNK = 8.0

# A7. Output tokens per generated answer. Fixed estimate in DEMO mode.
OUTPUT_TOKENS_PER_ANSWER = 180

# A9/A10. Simulated cross-encoder score distributions (DEMO mode only).
#     These two numbers decide whether the bug is visible, so they are the
#     most important assumptions in the file and the first thing a skeptical
#     viewer should attack. Gold chunks score well but not confidently.
#     Irrelevant chunks score low WITH REAL SPREAD -- boilerplate that shares
#     vocabulary with the query scores higher by chance. That spread is the
#     entire mechanism: max over N draws climbs with N.
GOLD_SCORE_MEAN, GOLD_SCORE_SD = 0.82, 0.06
NOISE_SCORE_MEAN, NOISE_SCORE_SD = 0.27, 0.14

# A8. Corpus shape. Long filings are where the bias bites.
SHORT_DOC_PAGES = (2, 6)
LONG_DOC_PAGES = (60, 140)
WORDS_PER_PAGE = 450

SEED = 20260806
DEMO = os.environ.get("DEMO", "1") == "1"


# ---------------------------------------------------------------------------
# Corpus. Synthetic filings with real 10-K shape: mostly boilerplate risk
# language, one gold paragraph that actually answers a query.
# ---------------------------------------------------------------------------

BOILERPLATE = [
    "Our business is subject to risks and uncertainties that could cause actual results to differ materially from those anticipated.",
    "We face intense competition in each of the markets in which we operate, and competitive pressures may adversely affect our results.",
    "Changes in general economic conditions may reduce demand for our products and services.",
    "We depend on third-party suppliers, and disruptions in the supply chain could increase our costs.",
    "Failure to comply with applicable laws and regulations could subject us to fines, penalties, or other liabilities.",
    "Our information systems may be subject to security breaches, which could disrupt operations and harm our reputation.",
    "We may be unable to attract and retain qualified personnel necessary to operate our business effectively.",
    "Fluctuations in foreign currency exchange rates may adversely affect our reported financial results.",
    "Our indebtedness could limit our flexibility in planning for or reacting to changes in our business.",
    "Adverse outcomes in pending or future litigation could have a material effect on our financial condition.",
]


@dataclass
class Doc:
    doc_id: str
    company: str
    text: str
    pages: int
    gold_for: str | None = None      # query_id this doc answers, if any
    gold_offset: float = 0.0         # where the gold paragraph sits, 0.0-1.0
    scrambled: bool = False          # content-null twin

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def token_count(self) -> int:
        return int(self.word_count * TOKENS_PER_WORD)


@dataclass
class Query:
    query_id: str
    text: str
    gold_doc_id: str
    gold_sentence: str


@dataclass
class Chunk:
    doc_id: str
    idx: int
    text: str
    is_gold: float  # fraction of the gold sentence present in this chunk, 0.0-1.0

    @property
    def token_count(self) -> int:
        return int(len(self.text.split()) * TOKENS_PER_WORD)


GOLD_FACTS = [
    ("q1", "What was the effective tax rate and what drove the change?",
     "The effective tax rate was 21.4 percent, down from 26.8 percent, driven primarily by the resolution of a prior-year foreign audit."),
    ("q2", "How much of revenue came from the single largest customer?",
     "One customer accounted for 14.2 percent of consolidated revenue during the period, up from 9.6 percent."),
    ("q3", "What were the terms of the revolving credit facility amendment?",
     "The revolving credit facility was amended to extend maturity to 2031 and reduce the applicable margin by 25 basis points."),
    ("q4", "What was the total stock-based compensation expense for the period?",
     "Stock-based compensation expense totalled 187 million dollars, an increase of 22 percent driven by headcount growth in engineering."),
    ("q5", "What triggered the change in the company's segment reporting structure?",
     "The company realigned its reportable segments following a change in how the chief operating decision maker reviews performance."),
    # -- long-filing answers start here (index 5+) --
    ("q6", "What caused the goodwill impairment charge?",
     "A goodwill impairment charge of 312 million dollars was recorded following a sustained decline in the reporting unit's forecast."),
    ("q7", "What is the remaining performance obligation and when will it be recognized?",
     "Remaining performance obligations totalled 4.1 billion dollars, of which approximately 58 percent is expected to be recognized within twelve months."),
    ("q8", "What was the impact of the restructuring program on headcount?",
     "The restructuring program reduced headcount by approximately 2,400 positions and is substantially complete."),
    ("q9", "What is the status of the unresolved SEC comment letter?",
     "The company responded to all outstanding comments and considers the matter closed as of the filing date."),
    ("q10", "What drove the increase in the allowance for credit losses?",
     "The allowance for credit losses increased 68 million dollars, reflecting deterioration in macroeconomic forecasts used under the current expected credit loss model."),
]
LONG_GOLD_START_IDX = 5  # facts before this index are answered by short filings


def _rng(*parts: object) -> random.Random:
    """Deterministic RNG keyed by content -- same inputs always give same draw."""
    key = "|".join(str(p) for p in parts)
    h = hashlib.sha256(key.encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def _filler(n_words: int, rng: random.Random) -> str:
    out: list[str] = []
    while len(out) < n_words:
        out.extend(rng.choice(BOILERPLATE).split())
    return " ".join(out[:n_words])


def build_corpus() -> tuple[list[Doc], list[Query]]:
    """Ten gold docs (5 short, 5 long) plus length-matched distractors."""
    docs: list[Doc] = []
    queries: list[Query] = []

    for i, (qid, qtext, fact) in enumerate(GOLD_FACTS):
        rng = _rng("gold", qid)
        long_doc = i >= LONG_GOLD_START_IDX
        lo, hi = LONG_DOC_PAGES if long_doc else SHORT_DOC_PAGES
        pages = rng.randint(lo, hi)
        n_words = pages * WORDS_PER_PAGE
        offset = rng.uniform(0.45, 0.85) if long_doc else rng.uniform(0.2, 0.6)
        cut = int(n_words * offset)
        text = f"{_filler(cut, rng)} {fact} {_filler(n_words - cut, rng)}"
        doc_id = f"D{i:02d}"
        docs.append(Doc(doc_id, f"Company {chr(65+i)}", text, pages, qid, offset))
        queries.append(Query(qid, qtext, doc_id, fact))

    # Distractors: no gold content. Deliberately length-diverse -- this is what
    # makes the bias visible instead of theoretical. Scaled to keep the
    # gold:distractor ratio realistic as the golden set grows.
    for j in range(40):
        rng = _rng("distractor", j)
        long_doc = j % 2 == 0
        lo, hi = LONG_DOC_PAGES if long_doc else SHORT_DOC_PAGES
        pages = rng.randint(lo, hi)
        docs.append(Doc(f"X{j:02d}", f"Filer {j}", _filler(pages * WORDS_PER_PAGE, rng), pages))

    return docs, queries


def scrambled_twin(doc: Doc) -> Doc:
    """Content-null control: same length, same chunk count, no answer in it.

    This is the instrument the payoff rests on. If chunk+max were measuring
    relevance, these would score near zero.
    """
    rng = _rng("scramble", doc.doc_id)
    words = doc.text.split()
    rng.shuffle(words)
    return Doc(f"{doc.doc_id}~null", doc.company, " ".join(words),
               doc.pages, None, 0.0, scrambled=True)


# ---------------------------------------------------------------------------
# Chunking + scoring
# ---------------------------------------------------------------------------

def chunk_doc(doc: Doc, window_tokens: int = RERANK_WINDOW_TOKENS,
              gold_sentence: str | None = None) -> list[Chunk]:
    """Split a document into reranker-sized windows."""
    words_per_window = max(1, int(window_tokens / TOKENS_PER_WORD))
    words = doc.text.split()
    chunks: list[Chunk] = []
    for i in range(0, len(words), words_per_window):
        body = " ".join(words[i:i + words_per_window])
        overlap = _gold_overlap(body, gold_sentence) if gold_sentence else 0.0
        chunks.append(Chunk(doc.doc_id, len(chunks), body, overlap))
    return chunks


def _gold_overlap(body: str, gold_sentence: str) -> float:
    """Fraction of the gold sentence's 4-grams present in this chunk.

    A sentence that straddles a window boundary gets partial credit in BOTH
    windows rather than zero credit in either -- a binary in/out threshold
    silently zeroed out any query whose offset happened to land on a
    boundary, which is a simulator artifact, not the effect this build
    demonstrates. A real cross-encoder given half a relevant sentence does
    not score it as pure noise.
    """
    g = gold_sentence.split()
    grams = [" ".join(g[k:k + 4]) for k in range(len(g) - 3)]
    if not grams:
        return 0.0
    hits = sum(1 for gram in grams if gram in body)
    return hits / len(grams)


def score_pair(query: str, chunk: Chunk) -> float:
    """Cross-encoder relevance score for one (query, chunk) pair.

    DEMO mode: deterministic simulated cross-encoder. Same pair always returns
    the same score, exactly like a real model in eval mode. The distribution is
    the modelling assumption -- irrelevant chunks are not scored at a constant
    zero, they are scored with real variance, which is the entire reason a
    max over many chunks drifts upward.

    REAL mode: bge-reranker-v2-m3 via sentence-transformers.
    """
    if not DEMO:
        return _score_pair_real(query, chunk)
    r = _rng("score", query, chunk.doc_id, chunk.idx, chunk.text[:64])
    # A9/A10: interpolate between the noise distribution and the gold
    # distribution by how much of the gold sentence this chunk contains.
    # Credit rises faster than raw word-overlap (sqrt) -- a chunk holding half
    # a fact is still recognizably about that fact to a real cross-encoder,
    # it isn't half as relevant. This keeps a boundary-split sentence from
    # being scored as near-noise in either half.
    effective = chunk.is_gold ** 0.5
    mean = NOISE_SCORE_MEAN + effective * (GOLD_SCORE_MEAN - NOISE_SCORE_MEAN)
    sd = NOISE_SCORE_SD + effective * (GOLD_SCORE_SD - NOISE_SCORE_SD)
    return min(1.0, max(0.0, r.gauss(mean, sd)))


_REAL_MODEL = None


def _score_pair_real(query: str, chunk: Chunk) -> float:
    global _REAL_MODEL
    if _REAL_MODEL is None:
        from sentence_transformers import CrossEncoder  # noqa: PLC0415
        _REAL_MODEL = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=RERANK_WINDOW_TOKENS)
    return float(_REAL_MODEL.predict([(query, chunk.text)])[0])


def pool(scores: list[float], mode: str = POOLING) -> float:
    """Collapse per-chunk scores into one document score."""
    if not scores:
        return 0.0
    if mode == "max":
        return max(scores)
    if mode == "mean_top2":
        s = sorted(scores, reverse=True)[:2]
        return sum(s) / len(s)
    raise ValueError(mode)


def score_doc(query: Query, doc: Doc, mode: str = POOLING,
              truncate_only: bool = False) -> tuple[float, list[float]]:
    """Score a whole document. Returns (pooled_score, per_chunk_scores)."""
    chunks = chunk_doc(doc, gold_sentence=None if doc.scrambled else query.gold_sentence)
    if truncate_only:
        chunks = chunks[:1]  # the old bug: everything past the window is invisible
    per = [score_pair(query.text, c) for c in chunks]
    return pool(per, mode), per


# ---------------------------------------------------------------------------
# Retrieval stage 1 (bi-encoder + BM25 stand-in) -- deliberately cheap.
# Its only job is recall: get the gold doc into the candidate set.
# ---------------------------------------------------------------------------

def retrieve(query: Query, docs: list[Doc], k: int = 150) -> list[Doc]:
    """Stage-1 recall. Returns candidates in a deliberately mediocre order."""
    scored = []
    for d in docs:
        r = _rng("retrieve", query.query_id, d.doc_id)
        base = 0.55 if d.doc_id == query.gold_doc_id else 0.0
        scored.append((base + r.gauss(0.30, 0.22), d))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [d for _, d in scored[:k]]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def recall_at_k(ranked: list[Doc], gold_doc_id: str, k: int) -> int:
    return int(any(d.doc_id == gold_doc_id for d in ranked[:k]))


def semantic_success(query: Query, context_docs: list[Doc]) -> int:
    """A5/A4: did the answer get grounded in the gold paragraph?"""
    if not any(d.doc_id == query.gold_doc_id for d in context_docs):
        return 0
    r = _rng("gen", query.query_id, ",".join(d.doc_id for d in context_docs))
    return int(r.random() > DISTRACTION_PENALTY)


def generation_cost(context_docs: list[Doc], model: str = GEN_MODEL) -> float:
    in_tok = sum(d.token_count for d in context_docs) + 400
    p = PRICE_PER_MTOK[model]
    return (in_tok / 1e6) * p["input"] + (OUTPUT_TOKENS_PER_ANSWER / 1e6) * p["output"]


def rerank_cost(total_chunks: int) -> float:
    """A6: amortised GPU seconds, not an API price."""
    hours = (total_chunks * RERANK_MS_PER_CHUNK) / 3_600_000
    return hours * GPU_DOLLARS_PER_HOUR


def cost_per_successful_request(total_cost: float, successes: int) -> float:
    return total_cost / successes if successes else float("inf")


# ---------------------------------------------------------------------------
# Null calibration -- the fix. Expected max score under zero real relevance,
# as a function of chunk count.
# ---------------------------------------------------------------------------

@dataclass
class Calibration:
    table: dict[int, float] = field(default_factory=dict)

    def baseline_for(self, n_chunks: int) -> float:
        if not self.table:
            return 0.0
        keys = sorted(self.table)
        nearest = min(keys, key=lambda k: abs(k - n_chunks))
        return self.table[nearest]

    def margin(self, pooled: float, n_chunks: int) -> float:
        return pooled - self.baseline_for(n_chunks)


def calibration_from_export(path: str = "sweep_export.json") -> Calibration:
    """Load the null-calibration table measured by 03_instrumented.py.

    Deliberately NOT a second implementation of the noise-ceiling measurement.
    It's measured once, exported once, and consumed here. If 04 computed its
    own baseline, the fix would be validating itself against its own
    assumptions.
    """
    with open(path) as f:
        payload = json.load(f)
    cal = Calibration()
    for row in payload["noise_ceiling_curve"]:
        cal.table[row["n_chunks"]] = row["mean_score"]
    return cal


def save_json(path: str, payload: dict) -> None:
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


# A12. Documents handed to the generator per request.
TOP_K_CONTEXT_DEFAULT = 3
