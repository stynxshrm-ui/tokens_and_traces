# You Can't Debug What You Can't See
### LLM Observability in Production — Code for the YouTube video

> **Video:** [Link in description once published]
> **Series:** AI Engineering in Production — EP01

---

## What this repo demonstrates

A customer support triage agent that **works perfectly in development** and
**silently produces wrong output in production** after a one-line prompt change.
Then: how adding LangSmith tracing lets you diagnose the failure in under two minutes,
from a trace, without a single print statement added after the fact.

---

## The bug (don't skip this)

A teammate updated the classifier system prompt to return confidence scores:

```
# Before (working)
"Respond with ONLY the category name — lowercase, nothing else."
# → "billing"

# After (broken)  
"Return your answer in the format: <category> (confidence: <high|medium|low>)"
# → "billing (confidence: high)"
```

The ChromaDB `where` filter does exact-string matching on metadata.
`"billing (confidence: high)"` matches nothing → **0 KB results returned**.
The LLM drafts a reply with no knowledge base context. No exception is raised.
Exit code: 0. Your monitoring: green.

---

## Architecture

```
Incoming ticket
      │
      ▼
[1] classify_ticket   ← GPT-4o  │ span: llm
      │
      ▼
[2] search_kb         ← ChromaDB (filtered by category) │ span: retriever
      │
      ▼
[3] draft_reply       ← GPT-4o + KB context │ span: llm
      │
      ▼
[4] route_ticket      ← deterministic routing map │ span: chain
      │
      ▼
  Result: { classification, kb_articles_used, reply, routing }
```

---

## Setup

**Requirements:** Python 3.11+, an OpenAI API key, a LangSmith account (free).

```bash
git clone <this-repo>
cd support-triage-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in OPENAI_API_KEY and LANGCHAIN_API_KEY in .env
```

---

## Run the demo in order

### 1. Seed the knowledge base
```bash
python 01_setup_kb.py
```
Seeds ChromaDB with 12 support articles across 4 categories, using
`text-embedding-3-small` for embeddings.

### 2. The clean agent (dev — works)
```bash
python 02_agent.py
```
Classifies correctly, retrieves 3 relevant KB articles, drafts a grounded reply.
This is what ships.

### 3. The broken agent (prod — silent failure)
```bash
python 03_agent_broken.py
```
Same ticket. Classification returns `"billing (confidence: high)"`.
KB search returns 0 results. Reply is ungrounded. **Exit code: 0.**

### 4. The broken agent with LangSmith tracing
```bash
python 04_agent_traced.py
```
Identical to `03_agent_broken.py` — same bug, same output.
But now every step is a span. Open LangSmith, click the trace,
and you'll see the malformed classification in < 30 seconds.

### 5. The fixed agent (with tracing kept on)
```bash
python 05_agent_fixed.py
```
`parse_category()` validates the model output against a known enum and raises
explicitly if format is wrong. Clean classification → KB results → grounded reply.
The LangSmith trace shows a healthy waterfall.

---

## What to look at in LangSmith

After running `04_agent_traced.py`, open [smith.langchain.com](https://smith.langchain.com):

| Span | What to look for |
|------|-----------------|
| `classify_ticket` | Output: `"billing (confidence: high)"` — the bug, right there |
| `search_kb` | Output: `[]` — the downstream consequence |
| `draft_reply` | User message: `"Knowledge base: No relevant articles found."` |
| `route_ticket` | Input: malformed string; output: accidentally correct due to split() hack |

After running `05_agent_fixed.py`, compare:

| Span | Fixed version |
|------|--------------|
| `classify_ticket` | Output: `"billing"` |
| `search_kb` | Output: 3 articles with IDs and content |
| `draft_reply` | User message contains real KB context |

---

## The fix (five lines)

```python
VALID_CATEGORIES = {"billing", "technical", "account", "general"}

def parse_category(raw: str) -> str:
    category = raw.split("(")[0].strip().lower()
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Unexpected classification: {raw!r}")
    return category
```

A `ValueError` that pages your on-call is better than a silent success
that sends wrong information to customers for three days.

---

## Production patterns covered in the video

- **Metadata tagging** — `agent_version`, `environment`, `ticket_id`, `user_id` on every trace
- **Sampling** — 100% in staging, 10–20% in prod, 100% during A/B prompt tests
- **Human feedback** — LangSmith feedback API for piping QA reviews back to traces

---

## Series

| EP | Topic | Tool |
|----|-------|------|
| **01** | **Tracing: catch the failure that looks like a success** | **LangSmith** |
| 02 | Evals: catch regressions before they ship | Braintrust |
| 03 | Cost + latency dashboards at scale | Arize |

---

## Note on tool versions

The LLMOps tooling space moves monthly. If something in this repo has drifted
since filming, check the dates in the video description and verify against:
- LangSmith docs: [docs.smith.langchain.com](https://docs.smith.langchain.com)
- ChromaDB docs: [docs.trychroma.com](https://docs.trychroma.com)
- OpenAI API: [platform.openai.com/docs](https://platform.openai.com/docs)
