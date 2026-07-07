#!/usr/bin/env python3
"""
04_agent_traced.py
──────────────────
The BROKEN agent — now with full LangSmith observability.

Every function is a traceable span. Every prompt, every model response,
every ChromaDB result, every token count is captured and sent to LangSmith.

After running this, open https://smith.langchain.com and click into the trace.
You will see exactly where the chain broke and why — in under two minutes.

Prerequisites:
  1. python 01_setup_kb.py (seed ChromaDB)
  2. Add to .env:
       LANGSMITH_API_KEY=ls__your_key_here
       LANGSMITH_TRACING=true
       LANGSMITH_PROJECT=support-triage-agent

Usage:
    python 04_agent_traced.py
"""

# ── load_dotenv MUST come before any langsmith import ──────────────────────────
# LangSmith reads env vars at import time. If dotenv loads after, it's too late.
import os
from dotenv import load_dotenv
load_dotenv(".env")
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

# ── wrap_openai intercepts every call and ships it to LangSmith ──────────────
# Model name, full prompt, full completion, token counts, latency — all captured.
# One line. No other changes to how the client is used.
openai_client = wrap_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

ROUTING = {
    "billing":   {"team": "Billing Team",    "priority": "normal", "sla_hours": 24},
    "technical": {"team": "Engineering",     "priority": "high",   "sla_hours": 4},
    "account":   {"team": "Account Team",    "priority": "normal", "sla_hours": 12},
    "general":   {"team": "General Support", "priority": "low",    "sla_hours": 48},
}
FALLBACK_ROUTE = {"team": "General Support", "priority": "low", "sla_hours": 48}


@traceable(name="classify_ticket", run_type="llm")
def classify_ticket(ticket: str) -> str:
    """
    LangSmith captures:
      - Input: ticket text
      - System prompt (including THE BUG — format instruction)
      - Model output: "billing (confidence: high)"
      - Token usage and latency
    You will see the malformed output in the span immediately.
    """
    response = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a support ticket classifier. "
                    "Classify the ticket into one of these categories: "
                    "billing, technical, account, general. "
                    # THE BUG — still present, now visible in the trace
                    "Return your answer in the format: "
                    "<category> (confidence: <high|medium|low>)"
                ),
            },
            {"role": "user", "content": ticket},
        ],
    )
    return response.choices[0].message.content.strip().lower()


@traceable(name="search_kb", run_type="retriever")
def search_kb(ticket: str, category: str, n_results: int = 3) -> list[dict]:
    """
    LangSmith captures:
      - Input: ticket + category ("billing (confidence: high)")
      - Output: [] — empty list
    In the trace you will see: bad category in → zero results out.
    The causal link is right there.
    """
    chroma = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name=EMBED_MODEL,
    )
    collection = chroma.get_collection(name=COLLECTION_NAME, embedding_function=ef)

    try:
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
    except Exception:
        return []


@traceable(name="draft_reply", run_type="llm")
def draft_reply(ticket: str, kb_articles: list[dict]) -> str:
    """
    LangSmith captures:
      - Full prompt sent to the model
      - You will see "Knowledge base: No relevant articles found." in the user message
      - The model's reply drafted without any grounding
    """
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
    key = classification.split()[0] if " " in classification else classification
    return ROUTING.get(key, FALLBACK_ROUTE)


@traceable(
    name="support_triage_agent",
    run_type="chain",
    tags=["production", "triage", "ep1-demo"],
    metadata={"agent_version": "1.2.0", "environment": "production"},
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