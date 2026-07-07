#!/usr/bin/env python3
"""
05_agent_fixed.py
─────────────────
The fixed, production-ready agent with full LangSmith tracing.

What changed from 04_agent_traced.py:
  1. `parse_category()` — validates the raw model output against a known enum.
     Raises ValueError if the output doesn't match. A controlled exception that
     pages you is better than a silent success that sends bad replies for three days.

  2. The system prompt is reverted to the clean format (single word, lowercase).

  3. load_dotenv() is called before langsmith imports — LangSmith reads env vars
     at import time, so dotenv must run first.

Usage:
    python 05_agent_fixed.py
"""

# ── load_dotenv MUST come before any langsmith import ──────────────────────────
# LangSmith reads env vars at import time. If dotenv loads after, it's too late.
import os
from dotenv import load_dotenv
load_dotenv()
# ───────────────────────────────────────────────────────────────────────────────

import sys
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI
from langsmith import traceable
from langsmith.wrappers import wrap_openai

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "support_kb"
EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o"

openai_client = wrap_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

VALID_CATEGORIES = {"billing", "technical", "account", "general"}

ROUTING = {
    "billing":   {"team": "Billing Team",    "priority": "normal", "sla_hours": 24},
    "technical": {"team": "Engineering",     "priority": "high",   "sla_hours": 4},
    "account":   {"team": "Account Team",    "priority": "normal", "sla_hours": 12},
    "general":   {"team": "General Support", "priority": "low",    "sla_hours": 48},
}
FALLBACK_ROUTE = {"team": "General Support", "priority": "low", "sla_hours": 48}


# ── THE FIX ────────────────────────────────────────────────────────────────────
def parse_category(raw: str) -> str:
    """
    Validate raw model output against the known category enum.

    Strips parenthetical suffixes (handles any future format drift),
    then raises explicitly if the core word is not a valid category.

    A ValueError here pages your on-call. That's correct behaviour.
    Silent success with bad data is not.
    """
    category = raw.split("(")[0].strip().lower()
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"Unexpected classification: {raw!r}. "
            f"Expected one of: {sorted(VALID_CATEGORIES)}"
        )
    return category


@traceable(name="classify_ticket", run_type="llm")
def classify_ticket(ticket: str) -> str:
    """Clean prompt — returns a single lowercase word."""
    response = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a support ticket classifier. "
                    "Classify the ticket into exactly one of these categories: "
                    "billing, technical, account, general. "
                    "Respond with ONLY the category name — lowercase, no punctuation, "
                    "nothing else."
                ),
            },
            {"role": "user", "content": ticket},
        ],
    )
    raw = response.choices[0].message.content.strip()
    return parse_category(raw)


@traceable(name="search_kb", run_type="retriever")
def search_kb(ticket: str, category: str, n_results: int = 3) -> list[dict]:
    """
    `category` is now always a clean, validated string.
    The where-filter reliably matches documents.
    LangSmith trace now shows 3 articles returned.
    """
    chroma = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name=EMBED_MODEL,
    )
    collection = chroma.get_collection(name=COLLECTION_NAME, embedding_function=ef)

    results = collection.query(
        query_texts=[ticket],
        n_results=n_results,
        where={"category": category},
    )

    articles = []
    for i, doc in enumerate(results["documents"][0]):
        articles.append(
            {
                "id": results["metadatas"][0][i]["id"],
                "title": results["metadatas"][0][i]["title"],
                "content": doc,
            }
        )
    return articles


@traceable(name="draft_reply", run_type="llm")
def draft_reply(ticket: str, kb_articles: list[dict]) -> str:
    """KB articles are present. Context is real. Reply is grounded."""
    if kb_articles:
        context = "\n\n".join(
            f"[{a['id']}] {a['title']}\n{a['content']}" for a in kb_articles
        )
    else:
        context = "No relevant articles found."

    response = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0.3,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful customer support agent. "
                    "Use the provided knowledge base articles to write a clear, "
                    "concise, and accurate reply to the customer. "
                    "Cite specific steps from the articles where relevant. "
                    "If no articles are available, acknowledge the issue and promise "
                    "to escalate to a specialist."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Customer ticket:\n{ticket}\n\n"
                    f"Knowledge base:\n{context}"
                ),
            },
        ],
    )
    return response.choices[0].message.content.strip()


@traceable(name="route_ticket", run_type="chain")
def route_ticket(classification: str) -> dict:
    """Direct lookup — no split() hacks needed with a clean classification."""
    return ROUTING.get(classification, FALLBACK_ROUTE)


@traceable(
    name="support_triage_agent",
    run_type="chain",
    tags=["production", "triage"],
    metadata={"agent_version": "1.3.0", "environment": "production"},
)
def run_agent(ticket: str, ticket_id: str = None, user_id: str = None) -> dict:
    divider = "=" * 60

    print(f"\n{divider}")
    print(f"TICKET [{ticket_id}]:\n{ticket}")
    print(divider)

    print("\n[1/4] Classifying ticket...")
    classification = classify_ticket(ticket)
    print(f"  → Classification: {classification}")

    print("\n[2/4] Searching knowledge base...")
    kb_articles = search_kb(ticket, classification)
    print(f"  → Found {len(kb_articles)} relevant articles")
    for a in kb_articles:
        print(f"       [{a['id']}] {a['title']}")

    print("\n[3/4] Drafting reply...")
    reply = draft_reply(ticket, kb_articles)
    print(f"  → Reply drafted ({len(reply)} chars)")

    print("\n[4/4] Routing ticket...")
    routing = route_ticket(classification)
    print(f"  → Routed to: {routing['team']}  |  Priority: {routing['priority']}  |  SLA: {routing['sla_hours']}h")

    result = {
        "classification": classification,
        "kb_articles_used": [a["id"] for a in kb_articles],
        "reply": reply,
        "routing": routing,
    }

    print(f"\n{divider}")
    print("FINAL REPLY TO CUSTOMER:")
    print(divider)
    print(reply)
    print(f"\nRouting: {routing}")
    print(f"\n✓   Compare this trace to 04_agent_traced.py in LangSmith.")
    print(f"    search_kb now shows 3 articles, not [].")
    print(f"\n🔍  View trace → https://smith.langchain.com  (project: support-triage-agent)")

    return result


if __name__ == "__main__":
    missing = []
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not os.getenv("LANGSMITH_API_KEY"):
        missing.append("LANGSMITH_API_KEY")
    if missing:
        print(f"ERROR: Missing env vars: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in your keys.")
        sys.exit(1)

    ticket = (
        "Hi, I tried to update my credit card yesterday but the page keeps "
        "throwing an error after I enter the card number. I'm worried my next "
        "invoice won't go through and I'll lose access. Can you help?"
    )

    run_agent(
        ticket=ticket,
        ticket_id="TKT-2024-00847",
        user_id="usr_k3m9p2",
    )