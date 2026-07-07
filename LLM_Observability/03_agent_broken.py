#!/usr/bin/env python3
"""
03_agent_broken.py
──────────────────
THE PRODUCTION BUG.

A teammate updated the classifier system prompt to return confidence scores
alongside the category — useful for an internal analytics dashboard they were
building. The change went to prod on a Tuesday. Nobody was worried.

  Before: "billing"
  After:  "billing (confidence: high)"

The ChromaDB `where` filter does an exact-match on metadata.
"billing (confidence: high)" != "billing" → 0 KB results returned.
The reply is drafted with no knowledge base context — pure model hallucination.

NO EXCEPTION IS RAISED. Exit code is 0.
The reply looks plausible. Your monitoring shows green.
You have no idea this is happening.

This is what the video is about.

Usage:
    python 03_agent_broken.py
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

ROUTING = {
    "billing":   {"team": "Billing Team",    "priority": "normal", "sla_hours": 24},
    "technical": {"team": "Engineering",     "priority": "high",   "sla_hours": 4},
    "account":   {"team": "Account Team",    "priority": "normal", "sla_hours": 12},
    "general":   {"team": "General Support", "priority": "low",    "sla_hours": 48},
}
FALLBACK_ROUTE = {"team": "General Support", "priority": "low", "sla_hours": 48}


def classify_ticket(ticket: str) -> str:
    """
    PRODUCTION VERSION — prompt updated to return structured output
    for an analytics dashboard. Looks harmless. Breaks everything downstream.
    """
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a support ticket classifier. "
                    "Classify the ticket into one of these categories: "
                    "billing, technical, account, general. "
                    # ── THE BUG ───────────────────────────────────────────────
                    # Added to support a confidence score dashboard.
                    # The old parsing code just strips whitespace.
                    # It does not handle this new format.
                    "Return your answer in the format: "
                    "<category> (confidence: <high|medium|low>)"
                    # ─────────────────────────────────────────────────────────
                ),
            },
            {"role": "user", "content": ticket},
        ],
    )
    # Old parsing — just strip whitespace. Now returns "billing (confidence: high)"
    # instead of "billing". Nobody updated this line.
    return response.choices[0].message.content.strip().lower()


def search_kb(ticket: str, category: str, n_results: int = 3) -> list[dict]:
    """
    Receives "billing (confidence: high)" as `category`.
    The ChromaDB where-filter does exact string matching.
    No document has category == "billing (confidence: high)".
    Returns []. Silently.
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
            where={"category": category},  # ← exact match; malformed value matches nothing
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
        # ChromaDB raises if n_results > matching docs in some versions.
        # We catch silently — which hides the problem even further.
        return []


def draft_reply(ticket: str, kb_articles: list[dict]) -> str:
    """
    Receives an empty kb_articles list.
    Context is set to "No relevant articles found."
    Model hallucinates a plausible-sounding but unsupported reply.
    No error is raised.
    """
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


def route_ticket(classification: str) -> dict:
    """
    "billing (confidence: high)".split()[0] → "billing" — partially works
    because someone added a quick split() fix when they noticed routing was
    broken. But the KB search was never fixed. Two bugs, one commit, six months
    apart, neither caught because there were no traces.
    """
    key = classification.split()[0] if " " in classification else classification
    return ROUTING.get(key, FALLBACK_ROUTE)


def run_agent(ticket: str) -> dict:
    divider = "=" * 60

    print(f"\n{divider}")
    print(f"TICKET:\n{ticket}")
    print(divider)
    print("\n  ⚠  This is the BROKEN production version.")
    print("  ⚠  Watch the classification output and KB results carefully.\n")

    print("[1/4] Classifying ticket...")
    classification = classify_ticket(ticket)
    print(f"  → Classification: {classification}")  # "billing (confidence: high)"

    print("\n[2/4] Searching knowledge base...")
    kb_articles = search_kb(ticket, classification)
    print(f"\033[91m  → Found {len(kb_articles)} relevant articles\033[0m")  # 0

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
    print(divider)

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

    ticket = (
        "Hi, I tried to update my credit card yesterday but the page keeps "
        "throwing an error after I enter the card number. I'm worried my next "
        "invoice won't go through and I'll lose access. Can you help?"
    )
    run_agent(ticket)
