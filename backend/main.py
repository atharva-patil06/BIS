import json
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.llm import ask_llm
from backend.retrieval import get_all_chunks, retrieve

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="BIS Sahayak (Demo Prototype)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NO_MATCH_MESSAGE = (
    "No matching demo standard found for this question. I won't guess — "
    "this prototype only answers from the simulated BIS documents it was given."
)

DISCLAIMER = (
    "This is a text-based check against the standard's written requirements. "
    "It is not a substitute for official BIS certification and laboratory testing."
)

QUERY_SYSTEM_PROMPT = """You are BIS Sahayak, a demo assistant that answers questions ONLY using \
the simulated standard excerpts provided below. These are NOT real BIS standards — they are \
fictional text created for a prototype demonstration.

Rules:
- Answer only using information present in the provided excerpts. Never use outside knowledge.
- Every factual claim you make must be immediately followed by a citation in the exact form \
(IS <number>, Clause <clause>), using the IS number and clause number shown in the excerpt headers.
- If the excerpts do not actually support a confident answer to the question, say so explicitly \
instead of filling gaps or guessing.
- Respond in the same language the question was asked in.
- Keep the answer concise (a few sentences).
- Always remind the reader, briefly, that these are simulated/demo standards, not verified BIS text.
"""


COMPLIANCE_SYSTEM_PROMPT = """You are BIS Sahayak, a demo assistant that checks a product \
description against simulated standard clauses. These are NOT real BIS standards — they are \
fictional text created for a prototype demonstration.

You will be given several simulated clauses and a product description. For EACH clause given, \
decide whether the product description indicates the product "meets", "does not meet", or is \
"unclear" (genuinely relevant to this product but not addressed in the description) with respect \
to that clause.

Only include a clause in your response if it is substantively relevant to this specific product \
(e.g. skip generic "Scope"/"Definitions" clauses, and skip clauses about a completely different \
part of the product than what's described). Do not pad the response with every clause you were \
given — a focused, relevant list is better than an exhaustive one.

Respond with ONLY a JSON array (no markdown fences, no extra text), where each element is:
{"is_number": "...", "clause": "...", "verdict": "meets" | "does not meet" | "unclear", "reasoning": "one short sentence"}
The "clause" field must be ONLY the bare clause number exactly as it appears in the excerpt header \
(e.g. "7.2"), never the clause title.

Base every verdict strictly on the clause text given and the product description text given — \
do not use outside knowledge of real BIS standards.
"""


class QueryRequest(BaseModel):
    question: str


class ComplianceRequest(BaseModel):
    product_description: str


def format_context(chunks):
    return "\n\n---\n\n".join(c["text"] for c in chunks)


CITATION_RE = re.compile(r"\(([A-Za-z0-9 .\-]+?),\s*Clause\s+([\w.]+)\)")


def citations_actually_used(answer_text, chunks):
    """Only surface citations that (a) the model actually wrote inline in the
    answer and (b) correspond to a real chunk we retrieved — this is what
    guarantees the UI never shows a hallucinated citation."""
    known = {(c["metadata"]["is_number"], c["metadata"]["clause"]): c["metadata"] for c in chunks}
    seen = set()
    citations = []
    for is_number, clause in CITATION_RE.findall(answer_text):
        key = (is_number.strip(), clause.strip())
        if key in known and key not in seen:
            seen.add(key)
            citations.append(
                {
                    "is_number": known[key]["is_number"],
                    "clause": known[key]["clause"],
                    "source_file": known[key]["source_file"],
                }
            )
    return citations


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query")
def query(req: QueryRequest):
    result = retrieve(req.question)

    if not result["confident"]:
        return {
            "confident": False,
            "answer": NO_MATCH_MESSAGE,
            "citations": [],
        }

    top_chunks = result["chunks"][:3]
    context = format_context(top_chunks)
    user_message = (
        f"Simulated standard excerpts:\n\n{context}\n\n"
        f"Question: {req.question}"
    )
    answer = ask_llm(QUERY_SYSTEM_PROMPT, user_message)

    return {
        "confident": True,
        "answer": answer,
        "citations": citations_actually_used(answer, top_chunks),
    }


CLAUSE_NUMBER_RE = re.compile(r"([\w.]+)")


def normalize_clause(raw_clause: str) -> str:
    """Model sometimes returns 'Clause 7.1 — Maintenance' instead of '7.1' —
    pull out just the leading clause-number token to match our metadata."""
    text = raw_clause.strip()
    if text.lower().startswith("clause"):
        text = text[len("clause"):].strip()
    m = CLAUSE_NUMBER_RE.match(text)
    return m.group(1) if m else text


def resolve_clause_key(is_number: str, raw_clause: str, known: set) -> tuple | None:
    """Model sometimes cites a sub-numbered line ('7.2.2') instead of the
    clause-level number ('7.2') our metadata uses. Try the clause as given,
    then progressively drop trailing '.N' segments until it matches."""
    clause = normalize_clause(raw_clause)
    parts = clause.split(".")
    for end in range(len(parts), 0, -1):
        candidate = (is_number, ".".join(parts[:end]))
        if candidate in known:
            return candidate
    return None


def parse_verdicts(raw_text, chunks):
    known = {(c["metadata"]["is_number"], c["metadata"]["clause"]) for c in chunks}
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        return []

    verdicts = []
    for item in items:
        is_number = str(item.get("is_number", "")).strip()
        key = resolve_clause_key(is_number, str(item.get("clause", "")), known)
        if key is None:
            continue
        verdicts.append(
            {
                "is_number": key[0],
                "clause": key[1],
                "verdict": item.get("verdict", "unclear"),
                "reasoning": item.get("reasoning", ""),
            }
        )
    return verdicts


@app.post("/compliance-check")
def compliance_check(req: ComplianceRequest):
    chunks = get_all_chunks()
    context = format_context(chunks)
    user_message = (
        f"Simulated standard clauses:\n\n{context}\n\n"
        f"Product description:\n{req.product_description}"
    )
    raw = ask_llm(COMPLIANCE_SYSTEM_PROMPT, user_message, max_tokens=8000)
    verdicts = parse_verdicts(raw, chunks)

    return {
        "verdicts": verdicts,
        "disclaimer": DISCLAIMER,
    }


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
