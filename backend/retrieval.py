"""
Step 3 — Retrieval + confidence check.

Threshold of 1.3 was chosen empirically: known-good (in-scope) queries against
this corpus scored between 0.59 and 1.04 distance; known-bad (out-of-scope)
queries scored between 1.68 and 1.91. 1.3 sits cleanly in the gap.
"""

from pathlib import Path

import chromadb

BACKEND_DIR = Path(__file__).resolve().parent
CHROMA_DIR = BACKEND_DIR / "chroma_db"
COLLECTION_NAME = "bis_sahayak_demo"

CONFIDENCE_THRESHOLD = 1.3

_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
_collection = _client.get_collection(COLLECTION_NAME)


def get_all_chunks():
    """Return every clause chunk in the corpus.

    Used by /compliance-check instead of similarity search: a product
    description is a multi-topic paragraph, so a single embedding of it
    dilutes the signal for any one clause (e.g. a one-line mention of
    insulation voltage gets buried under kettle/handle/capacity terms).
    The corpus is small (tens of clauses), so checking against all of them
    is cheap and avoids silently skipping a clause the product violates.
    """
    res = _collection.get(include=["documents", "metadatas"])
    return [
        {"text": doc, "metadata": meta}
        for doc, meta in zip(res["documents"], res["metadatas"])
    ]


def retrieve(query: str, n_results: int = 4):
    res = _collection.query(query_texts=[query], n_results=n_results)
    documents = res["documents"][0]
    metadatas = res["metadatas"][0]
    distances = res["distances"][0]

    chunks = [
        {"text": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(documents, metadatas, distances)
    ]
    confident = bool(chunks) and chunks[0]["distance"] <= CONFIDENCE_THRESHOLD
    return {"confident": confident, "chunks": chunks}


if __name__ == "__main__":
    for q in ["insulation test voltage", "what is the capital of France"]:
        result = retrieve(q)
        print(q, "->", "confident" if result["confident"] else "NOT confident")
        print("  top distance:", result["chunks"][0]["distance"])
        print("  top match:", result["chunks"][0]["metadata"])
