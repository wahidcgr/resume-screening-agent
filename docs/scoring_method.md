# Scoring Method

Each resume gets a **final_score (0-100)** made of two independent signals:

## 1. TF-IDF Similarity (35% weight) — `agent/similarity.py`

A classic NLP similarity method: both the Job Description and the resume
text are vectorized with **TF-IDF** (unigrams + bigrams, English stop
words removed, light synonym normalization e.g. "postgres" → "postgresql"),
then compared with **cosine similarity**.

Why TF-IDF and not a neural embedding model (e.g. sentence-transformers)?
- **Zero setup friction.** No model weights to download, no GPU, no
  network call to a model hub — it runs instantly after `pip install`,
  which matters a lot for a reviewer trying to run this in minutes.
- **Deterministic and auditable.** The same JD/resume pair always
  produces the same score, and the score is directly traceable to shared
  vocabulary — useful for explaining a candidate's ranking.
- **Known limitation:** it only sees lexical overlap, not deep semantic
  meaning. It won't know "led a team of engineers" implies management
  experience unless similar words appear in the JD. This is exactly why
  it's only one of two signals, not the whole score.

## 2. LLM Judgment Score (65% weight) — `agent/scorer.py`

The LLM (via Groq) is given:
- The full job description
- The candidate's **structured profile** (already extracted in the
  extraction step: skills, years of experience, education, summary)

...and asked to return a 0-100 fit score **plus reasoning, strengths, and
gaps**, grounded in explicit scoring bands (e.g. 85-100 = strong match on
required skills + experience + education). This is where most of the
"judgement" comes from — it can recognize that a candidate with 7 years
of Go/Python backend experience satisfies a "3+ years Python" requirement
even if the resume never uses the JD's exact wording, which TF-IDF alone
would miss or under-score.

## Why combine them instead of using just one?

- LLM-only scoring can be inconsistent run-to-run and is harder to sanity
  check — a bad extraction or a leading prompt can quietly inflate a
  score with no way to catch it.
- TF-IDF-only scoring is transparent but blind to real equivalence
  (e.g. "Go" experience being reasonably close to a Python-only ask).
- The blend anchors the LLM's judgment against an evidence-based, hard to
  hallucinate signal (**tfidf_score**), while still letting reasoning
  quality drive most of the ranking (**llm_score** carries 65% weight).

Both raw components (`tfidf_score`, `llm_score`) are kept in the output
alongside `final_score` so a reviewer can see exactly how each candidate's
score was built, not just the blended number.

## Offline / no-API-key fallback

If `GROQ_API_KEY` is not set (or `--no-llm` is passed), the agent
falls back to a simple keyword-overlap heuristic for both extraction and
scoring (see `extract_fields_heuristic` / `heuristic_fit_score`). This
exists purely so the full pipeline can be smoke-tested end-to-end without
a live key — it is **not** a substitute for the LLM path and produces
noticeably less nuanced reasoning. The included `output/` sample was
generated in this fallback mode (see `docs/sample_run.md` for details and
tradeoff notes on what changes with a real key).

## Known failure cases

- Resumes with unusual formatting (tables-as-images, multi-column PDFs)
  may extract text out of order, which can confuse both scorers.
- Skill synonyms not covered by the normalization list (e.g. "k8s" vs
  "Kubernetes") may be under-counted by TF-IDF.
- The LLM extraction can occasionally return a slightly malformed JSON
  object for unusually long or noisy resumes; the code catches this and
  falls back to the heuristic extractor for that candidate rather than
  crashing the whole batch.
