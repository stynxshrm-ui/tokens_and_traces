#!/usr/bin/env python3
"""
01_setup_kb.py
──────────────
Seeds ChromaDB with support knowledge base articles using OpenAI embeddings.
Run this once before running any agent script.

Usage:
    python 01_setup_kb.py
"""

import os
import sys
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from kb_articles import KB_ARTICLES

load_dotenv()

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "support_kb"
EMBED_MODEL = "text-embedding-3-small"


def setup_knowledge_base() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    print("Setting up ChromaDB knowledge base...")
    print(f"  Embedding model : {EMBED_MODEL}")
    print(f"  Persist path    : {CHROMA_PATH}")
    print(f"  Articles        : {len(KB_ARTICLES)}")
    print()

    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # ── Wipe and recreate for a clean run ──────────────────────────────────
    try:
        client.delete_collection(COLLECTION_NAME)
        print("  Deleted existing collection.")
    except Exception:
        pass

    ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name=EMBED_MODEL,
    )

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    # ── Insert articles ────────────────────────────────────────────────────
    documents = [a["content"] for a in KB_ARTICLES]
    metadatas = [
        {"id": a["id"], "category": a["category"], "title": a["title"]}
        for a in KB_ARTICLES
    ]
    ids = [a["id"] for a in KB_ARTICLES]

    collection.add(documents=documents, metadatas=metadatas, ids=ids)

    # ── Summary ────────────────────────────────────────────────────────────
    categories = sorted(set(a["category"] for a in KB_ARTICLES))
    print(f"  Added {len(KB_ARTICLES)} articles.")
    print(f"  Categories: {', '.join(categories)}")
    print()
    print("Knowledge base ready. ✓")
    print()
    print("Sample articles:")
    for article in KB_ARTICLES[:3]:
        print(f"  [{article['id']}] ({article['category']}) {article['title']}")
    print(f"  ... and {len(KB_ARTICLES) - 3} more.")
    print()
    print("Next: python 02_agent.py")


if __name__ == "__main__":
    setup_knowledge_base()
