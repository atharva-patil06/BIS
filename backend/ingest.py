"""
Step 2 — Ingestion.

Reads each .txt file in data/demo_corpus/, splits it into chunks by clause
(split on lines starting with "Clause <number>"), and stores each chunk in
a local persistent ChromaDB collection with metadata: {is_number, clause, source_file}.

Embedding function: no Voyage AI key was found in .env, so this uses
ChromaDB's built-in default embedding function (all-MiniLM-L6-v2 via onnxruntime,
downloaded automatically on first run). Swap in Voyage AI here later if a key
becomes available.
"""

import os
import re
from pathlib import Path

import chromadb

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
CORPUS_DIR = PROJECT_ROOT / "data" / "demo_corpus"
CHROMA_DIR = BACKEND_DIR / "chroma_db"
COLLECTION_NAME = "bis_sahayak_demo"

CLAUSE_RE = re.compile(r"^Clause\s+([\w.]+)\s*[—-]\s*(.+)$")
TITLE_RE = re.compile(r"^(.*?)\s*\(DEMO\)")


def extract_is_number(text: str) -> str:
    for line in text.splitlines()[:5]:
        m = TITLE_RE.search(line)
        if m:
            return m.group(1).strip()
    return "UNKNOWN"


def chunk_file(path: Path):
    text = path.read_text(encoding="utf-8")
    is_number = extract_is_number(text)
    lines = text.splitlines()

    chunks = []
    current_clause = None
    current_title = None
    current_lines = []

    def flush():
        if current_clause is not None and current_lines:
            body = "\n".join(current_lines).strip()
            full_text = f"{is_number}, Clause {current_clause} — {current_title}\n{body}"
            chunks.append(
                {
                    "id": f"{path.stem}_{current_clause}",
                    "text": full_text,
                    "metadata": {
                        "is_number": is_number,
                        "clause": current_clause,
                        "source_file": path.name,
                    },
                }
            )

    for line in lines:
        m = CLAUSE_RE.match(line.strip())
        if m:
            flush()
            current_clause = m.group(1)
            current_title = m.group(2).strip()
            current_lines = [line.strip()]
        elif current_clause is not None:
            current_lines.append(line.strip())
    flush()

    return chunks


def build_index():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    # Drop and recreate so re-running ingest is idempotent.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION_NAME)

    all_chunks = []
    for path in sorted(CORPUS_DIR.glob("*.txt")):
        file_chunks = chunk_file(path)
        print(f"  {path.name}: {len(file_chunks)} clauses")
        all_chunks.extend(file_chunks)

    collection.add(
        ids=[c["id"] for c in all_chunks],
        documents=[c["text"] for c in all_chunks],
        metadatas=[c["metadata"] for c in all_chunks],
    )
    print(f"Indexed {len(all_chunks)} clause chunks into '{COLLECTION_NAME}' at {CHROMA_DIR}")
    return collection


if __name__ == "__main__":
    print(f"Reading corpus from: {CORPUS_DIR}")
    build_index()
