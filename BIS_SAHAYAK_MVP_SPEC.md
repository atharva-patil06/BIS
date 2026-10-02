# BIS Sahayak — MVP Build Spec (deadline: tomorrow's internal round)

**Priority instruction for Claude Code:** Speed to a working, demoable prototype beats completeness. Build in the exact order below. After each step, actually run it and confirm it works before moving to the next — do not write Step 4's code while Step 2 is still broken. If you're running low on time, cut scope from the "Cut if short on time" list, never from the four demo moments in Step 7.

---

## What "done" means for tomorrow

A person can open the app, and:
1. Ask a real question → get an answer with a visible citation (standard number + clause).
2. Ask an unrelated/out-of-scope question → get a clear "no matching standard found" response, not a guess.
3. Paste a product description → get a compliance check against the demo standards, with a visible disclaimer that it's not official certification.
4. (Nice to have, cut if short on time) Ask a question in Hindi → get an answer in Hindi.

That's the whole bar. Everything else in this doc exists to support those four moments.

---

## Tech stack (keep it minimal — do not add anything not listed here)

- **Backend:** FastAPI (Python)
- **LLM:** Claude API (`anthropic` Python SDK)
- **Vector store:** ChromaDB, local persistent mode (no external service, no auth setup)
- **Frontend:** Single-page React app OR plain HTML/JS if React setup risks eating time — Claude Code should pick whichever it can get running fastest
- **No database needed for tomorrow.** Skip SQLite, skip feedback storage, skip admin endpoints. Add later.

---

## Step 1 — Demo corpus (do this first, takes 10 minutes, unblocks everything else)

Real BIS PDFs are not available tonight. Create **5–8 short, clearly-labeled mock standard documents** as plain text files, not real PDFs — skip PDF parsing entirely for tomorrow. Structure each with numbered clauses so chunking is trivial.

Scope: pick **one product category** (recommend: household electrical appliances, e.g. kettles) so the demo is coherent. Example structure for one file:

```
IS 302-1 (DEMO) — Household Electrical Appliances — Safety — Part 1: General Requirements
[This is a simulated standard created for prototype demonstration. Not official BIS text.]

Clause 5.1 — Marking: The appliance shall be marked with rated voltage, rated power input, and manufacturer's name or trademark.
Clause 7.2 — Insulation: Live parts shall be inaccessible. Basic insulation shall withstand a test voltage of 1250V for Class I appliances.
Clause 9.4 — Heating: Temperature rise of accessible surfaces during normal operation shall not exceed 60°C above ambient.
```

Write 2–3 such files covering related clauses (e.g., a general-requirements doc + a kettle-specific doc + a cabling-reference doc). **Label every file and every UI surface clearly as demo/simulated data** — do not let it look like verified real BIS text, since that would misrepresent it if shown out of context later.

Save as `.txt` files in `backend/data/demo_corpus/`.

---

## Step 2 — Ingestion (keep it simple)

- Write a small script that reads each `.txt` file, splits it into chunks by clause (split on lines starting with `Clause \d`), and stores each chunk in ChromaDB with metadata: `{is_number, clause, source_file}`.
- Use ChromaDB's default embedding function if you don't have an embeddings API key configured — do not block on sourcing a separate embeddings API key tonight. If Voyage AI key is available, use it; otherwise fall back to ChromaDB's built-in default embedder without asking — just note in a code comment which one is active.
- **Test:** query ChromaDB directly for a term you know is in the corpus (e.g., "insulation") and confirm it returns the right chunk before writing any more code.

---

## Step 3 — Retrieval + confidence check

- One function: given a query string, embed it, run ChromaDB similarity search (top 3–5 results), and check the top result's distance/score against a threshold.
- Start with a threshold that works for your actual corpus — test empirically with 2–3 known-good and 2–3 known-bad queries, adjust until both classify correctly. Don't guess a number and move on without testing it.
- **Test:** confirm an in-scope query returns confident=true with the right chunk, and an out-of-scope query (e.g., "what is the capital of France") returns confident=false.

---

## Step 4 — Grounded answer generation

- System prompt must enforce: answer only from the provided chunks, cite every claim as `(IS <number>, Clause <clause>)`, and if the chunks don't support a confident answer, say so explicitly instead of filling gaps.
- Ask Claude to respond in the same language the question was asked in.
- Wire this into a `/query` endpoint: retrieve → if not confident, return a fixed "no matching standard found" message without calling Claude at all → if confident, call Claude with the retrieved chunks as context and return the answer + citations.
- **Test:** hit the endpoint with a real question and confirm the citation in the response actually matches a real chunk you put in the corpus (not a hallucinated one).

---

## Step 5 — Compliance checker

- One more endpoint, `/compliance-check`: takes a product description, retrieves relevant chunks the same way, asks Claude to check the description against each clause and return a verdict per clause (meets / does not meet / unclear).
- The response must always include this exact line, every time, regardless of the verdicts: *"This is a text-based check against the standard's written requirements. It is not a substitute for official BIS certification and laboratory testing."*
- **Test:** describe a product that clearly violates one clause (e.g., a kettle with a 2-meter cord when the demo standard says max 1 meter) and confirm the verdict correctly flags it.

---

## Step 6 — Frontend (last, once the backend actually works)

- One chat screen. Input box, message list, send button.
- Assistant messages that came back confident: show the answer with a visibly distinct citation chip (standard number + clause) — this needs to be obvious at a glance, since "it shows its proof" is the whole pitch.
- Assistant messages that came back not-confident: render with a clearly different style (different border/background color) so "it says when it doesn't know" is visually obvious without you having to explain it.
- A second simple mode/tab for the compliance checker: textarea + button + a small table of verdicts, disclaimer always visible underneath.
- Skip: login, chat history persistence, settings, animations, mobile responsiveness polish. None of that helps tomorrow.

---

## Step 7 — Rehearse these four moments before you sleep

1. Ask a real question from your corpus → point at the citation.
2. Ask something unrelated → point at the "no match" response and say out loud why that matters (no guessing).
3. Paste a spec that fails one clause → point at the verdict and the disclaimer line.
4. If Hindi support made it in: ask the same question in Hindi.

If something breaks during rehearsal, fix it or quietly drop that demo moment — don't discover a broken flow live in front of judges.

---

## Cut if short on time (in this order)

1. Hindi/multilingual support — cut first, it's the least load-bearing demo moment.
2. Compliance-checker polish (a plain verdict list instead of a styled table is fine).
3. Multiple demo documents — two is enough if three is taking too long.
4. Any styling beyond "clean and readable." A working ugly app beats a broken pretty one.

**Never cut:** the citation display, and the "no match found" state. Those two are the actual point of the whole project.
