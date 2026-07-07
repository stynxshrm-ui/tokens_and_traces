#!/usr/bin/env python3
"""
02_agent.py
───────────
Customer support triage agent — clean, no observability.
Works perfectly in development.

Steps:
  1. classify_ticket  — GPT-4o classifies into: billing | technical | account | general
  2. search_kb        — ChromaDB semantic search filtered by category
  3. draft_reply      — GPT-4o drafts a grounded reply using KB articles as context
  4. route_ticket     — deterministic routing map → team + SLA

Usage:
    python 02_agent.py
"""

import os
import sys
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "support_kb"
EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ── Routing config ─────────────────────────────────────────────────────────────
ROUTING = {
    "billing":   {"team": "Billing Team",    "priority": "normal", "sla_hours": 24},
    "technical": {"team": "Engineering",     "priority": "high",   "sla_hours": 4},
    "account":   {"team": "Account Team",    "priority": "normal", "sla_hours": 12},
    "general":   {"team": "General Support", "priority": "low",    "sla_hours": 48},
}
FALLBACK_ROUTE = {"team": "General Support", "priority": "low", "sla_hours": 48}


# ── Step 1: Classify ───────────────────────────────────────────────────────────
def classify_ticket(ticket: str) -> str:
    """Classify a support ticket into one of four categories."""
    response = client.chat.completions.create(
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
    return response.choices[0].message.content.strip().lower()


# ── Step 2: Search KB ──────────────────────────────────────────────────────────
def search_kb(ticket: str, category: str, n_results: int = 3) -> list[dict]:
    """Semantic search over ChromaDB filtered by category."""
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


# ── Step 3: Draft reply ────────────────────────────────────────────────────────
def draft_reply(ticket: str, kb_articles: list[dict]) -> str:
    """Draft a support reply grounded in KB articles."""
    if kb_articles:
        context = "\n\n".join(
            f"[{a['id']}] {a['title']}\n{a['content']}" for a in kb_articles
        )
    else:
        context = "No relevant articles found."

    response = client.chat.completions.create(
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


# ── Step 4: Route ──────────────────────────────────────────────────────────────
def route_ticket(classification: str) -> dict:
    """Map classification to team and SLA."""
    return ROUTING.get(classification, FALLBACK_ROUTE)


# ── Orchestrator ───────────────────────────────────────────────────────────────
def run_agent(ticket: str) -> dict:
    divider = "=" * 60

    print(f"\n{divider}")
    print(f"TICKET:\n{ticket}")
    print(divider)

    print("\n[1/4] Classifying ticket...")
    classification = classify_ticket(ticket)
    print(f"  → Classification: {classification}")

    print("\n[2/4] Searching knowledge base...")
    kb_articles = search_kb(ticket, classification)
    print(f"\033[92m  → Found {len(kb_articles)} relevant articles\033[0m")
    for a in kb_articles:
        print(f"       [{a['id']}] {a['title']}")

    print("\n[3/4] Drafting reply...")
    reply = draft_reply(ticket, kb_articles)
    print(f"  → Reply drafted ({len(reply)} chars)")

    print("\n[4/4] Routing ticket...")
    routing = route_ticket(classification)
    print(f"  → Routed to: {routing['team']}  |  Priority: {routing['priority']}  |  SLA: {routing['sla_hours']}h")

    print(f"\n{divider}")
    print("FINAL REPLY TO CUSTOMER:")
    print(divider)
    print(reply)
    print(f"\nRouting: {routing}")
    print(f"\n{divider}")
    print("\033[92mEXIT CODE: 0  |  ERRORS: 0  |  YOUR MONITORING: GREEN\033[0m")
    print(f"\n{divider}")

    return {
        "classification": classification,
        "kb_articles_used": [a["id"] for a in kb_articles],
        "reply": reply,
        "routing": routing,
    }


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set.")
        sys.exit(1)

    # This ticket should classify as "billing" and surface KB001/KB002
    ticket = (
        "Hi, I tried to update my credit card yesterday but the page keeps "
        "throwing an error after I enter the card number. I'm worried my next "
        "invoice won't go through and I'll lose access. Can you help?"
    )
    run_agent(ticket)
