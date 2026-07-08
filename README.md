# Resume Screening Agent

Ranks a folder of resumes against a job description and outputs a scored,
ordered shortlist with reasoning — built for the Rooman AI Challenge
(Junior AI Research Associate selection round).

**One-sentence description:** *this agent takes a job description and a
folder of resumes (PDF/DOCX/TXT), and produces a ranked, scored,
reasoned shortlist (JSON + CSV).*

---

## How it works

```
Resumes (PDF/DOCX/TXT)          Job Description (TXT)
        │                                │
        ▼                                │
 1. Parse to raw text                    │
        │                                │
        ▼                                │
 2. Extract structured fields            │
    (Groq LLM: skills, years           │
    experience, education, summary)      │
        │                                │
        ▼                                ▼
 3. Score:  TF-IDF similarity  +  Groq LLM fit-score & reasoning
              (agent/similarity.py)     (agent/scorer.py)
        │
        ▼
 4. Combine into final_score, rank all candidates
        │
        ▼
 5. Save output/ranked_results.json + .csv
```

- **Extraction & judgment-based scoring** use the Groq API (fast, free-tier friendly LLM inference).
- **NLP similarity** uses TF-IDF + cosine similarity (`scikit-learn`) —
  a deterministic, zero-download similarity method that anchors the
  LLM's judgment in real shared vocabulary. See
  [`docs/scoring_method.md`](docs/scoring_method.md) for the full
  reasoning behind this combination.

---

## Setup

### 1. Clone and install dependencies   type these commands one by one in vs code terminal


```bash
git clone https://github.com/wahidcgr/resume-screening-agent
cd resume-screening-agent
python3 -m venv venv
venv\Scripts\Activate.ps1  -- (if error appears then type this - Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass and then again type   --- venv\Scripts\Activate.ps1 )   
pip install -r requirements.txt
```

### 2. Configure your Groq API key

```bash
cp .env.example .env
```

Edit `.env` and add your key from https://console.groq.com/keys (free
sign-up, no credit card required), then export it into your shell (or
use a tool like `python-dotenv` / `direnv` if you prefer auto-loading):

In .env folder type GROQ_API_KEY=your-key

```bash in terminal type-
$env:GROQ_API_KEY="your api key"
```

> **No API key?** The agent still runs end-to-end using a heuristic
> keyword-overlap fallback (see "Running without an API key" below) —
> useful for a quick smoke test, but the real intelligence comes from
> the LLM path.

### 3. Run it

Two ways to use FitBench: the **web dashboard** (recommended — visual, interactive) or the **CLI** (scriptable, good for batch/CI use).

---

## Option A: Web Dashboard (to run in browser)   --- you have resumes from this project itself inside data folder select it and also job description is available in same folder copy paste it in the browser for screening or you can use your won resume and job description


```bash
python app.py
```

Then open **http://localhost:5000** in your browser.

**What you'll see:**

1. **Dashboard (`/`)** — a control console. Choose your job description
   (bundled sample, paste your own, or upload a .pdf/.docx/.txt), add
   resumes (or leave empty to use the 11 bundled samples), toggle LLM
   scoring on/off, and hit **Run screening**. A live terminal-style log
   streams progress in real time as each resume is parsed, extracted, and
   scored — no page refresh needed (built on Server-Sent Events).

2. **Results (`/results?run_id=...`)** — you're redirected here
   automatically when the run finishes. Every candidate is shown as a
   "channel strip" with a graduated meter: a filled bar for the blended
   `final_score`, plus two small markers (**T** = TF-IDF signal, **L** =
   LLM judgment signal) showing exactly where each raw score landed on
   the same 0–100 scale — a direct visual readout of how `scorer.py`
   combined them. Click **Details** on any candidate for full reasoning,
   strengths, gaps, skills, and education. Search/filter by name or
   skill, re-sort by any score, or download the batch as JSON/CSV.

Each run gets its own `run_id`, so results from different JD/resume
combinations don't overwrite each other — they're saved under
`output/runs/<run_id>/`.

**Stopping the server:** `Ctrl+C` in the terminal where `python app.py`
is running.

---

## Option B: CLI (to run inside VS Code itself)

```bash
python main.py --jd data/job_description.txt --resumes data/resumes --output output
```

See the [CLI options](#cli-options) section below for flags.

---

## CLI options

```
python main.py [options]

--jd PATH         Path to job description text file (default: data/job_description.txt)
--resumes PATH    Folder of resume files, .pdf/.docx/.txt (default: data/resumes)
--output PATH     Folder to write ranked_results.json/.csv (default: output)
--no-llm          Force heuristic fallback mode even if a key is set
--model NAME      Override the Groq model ID (default: openai/gpt-oss-120b)
--top N           Number of top candidates to print to console (default: 5)
```

---

## Running without an API key

If `GROQ_API_KEY` isn't set (or you pass `--no-llm`), the agent
automatically switches to a simple keyword/heuristic extractor and
scorer (`extract_fields_heuristic`, `heuristic_fit_score` in
`agent/extractor.py` / `agent/scorer.py`). This exists so:

- Reviewers without a key handy can still see the full pipeline run
  end-to-end in seconds.
- The TF-IDF similarity path can be exercised independently.

It is **not** a substitute for the LLM path — reasoning quality and
nuance drop noticeably. `docs/sample_run.md` shows an actual fallback-mode
run and calls out exactly what improves with a real key.

---

## Project structure

```
resume-screening-agent/
├── main.py                    # CLI entry point
├── app.py                     # Flask backend for the web dashboard
├── templates/
│   ├── index.html               # Dashboard (control panel)
│   └── results.html             # Results page
├── static/
│   ├── css/style.css            # Design system (dark instrument-panel theme)
│   └── js/
│       ├── meter.js               # Builds the dual-probe score meter (SVG)
│       ├── dashboard.js           # Upload/run flow, live SSE progress log
│       └── results.js             # Results rendering, search, sort
├── agent/
│   ├── parser.py               # PDF/DOCX/TXT text extraction
│   ├── extractor.py            # Groq LLM-based structured field extraction (+ fallback)
│   ├── similarity.py           # TF-IDF cosine similarity (NLP similarity method)
│   ├── scorer.py                # Combines TF-IDF + Groq LLM judgment into final_score
│   └── ranker.py                # Orchestrates the pipeline (batch + streaming versions)
├── data/
│   ├── job_description.txt      # Sample JD: Backend Software Engineer (Python)
│   ├── resumes/                 # 11 sample resumes (varied match quality)
│   └── uploads/                 # Runtime: per-run uploaded JD/resumes (gitignored)
├── output/
│   ├── ranked_results.json      # Full structured output (CLI sample run included)
│   ├── ranked_results.csv
│   └── runs/                    # Runtime: per-run web dashboard output (gitignored)
├── docs/
│   ├── scoring_method.md        # Detailed scoring methodology
│   └── sample_run.md            # Captured example run + sanity check
├── requirements.txt
└── .env.example
```

---

## Sample data included

- **Job description:** Backend Software Engineer (Python) —
  `data/job_description.txt`
- **11 sample resumes** in `data/resumes/`, deliberately varied:
  - Strong matches: senior/mid-level Python backend engineers
  - Partial matches: data analyst (SQL/Python-adjacent), junior Python dev
  - Weak/no match: Java backend dev, frontend/JS dev, and a marketing
    profile with no technical background at all (included as a sanity
    check that unrelated candidates are correctly ranked last)

A full sample run and console output is in
[`docs/sample_run.md`](docs/sample_run.md), and the raw ranked output is
already committed in `output/ranked_results.json` / `.csv`.

---

## Tradeoffs & what I'd improve with more time

- **TF-IDF over neural embeddings:** chosen for zero-setup reproducibility
  (no model download, no GPU) at the cost of missing deeper semantic
  matches. With more time I'd add an optional embedding-based similarity
  mode (e.g. Voyage or OpenAI embeddings) behind a flag, and compare it
  against TF-IDF on a labeled set of resume/JD pairs.
- **Score weighting (35% TF-IDF / 65% LLM) is a reasonable default, not
  tuned.** With labeled ground-truth rankings I'd grid-search this
  weighting instead of hand-picking it.
- **Per-resume sequential API calls.** For 10-15 resumes this is fine;
  at scale I'd batch or parallelize the extraction/scoring calls.
- **Heuristic fallback is intentionally simple.** It's a keyword-overlap
  match, not a real NLP method — good enough for a no-key smoke test,
  not for production scoring.
- **PDF layout robustness.** Multi-column resumes or resumes with skills
  embedded in images (not text) can produce out-of-order or missing
  text. A production version would add OCR fallback (e.g. Tesseract) for
  image-based PDFs.
- **No resume de-duplication.** If the same candidate submits under two
  filenames, they'd currently be scored as two separate entries.
- **Validation is light.** I'd add a JSON-schema check on the LLM's
  extraction/scoring output before trusting it, beyond the current
  try/except-with-fallback.
- **Dashboard is single-user, local-only.** `app.py` uses Flask's dev
  server and stores runs as folders on disk keyed by a random id — fine
  for local/demo use, but a real deployment would need auth, a proper
  WSGI server (gunicorn/uwsgi), and a TTL/cleanup job for old runs under
  `data/uploads/` and `output/runs/`.

---

## Design choices (why)

- **Structured extraction before scoring** (rather than asking the LLM to
  score directly from raw resume text) makes each step independently
  testable and auditable — you can inspect exactly what the model
  "believed" about a candidate before it scored them.
- **Two independent scores kept in the output** (`tfidf_score`,
  `llm_score`) rather than only the blended `final_score`, so a reviewer
  can see how much of a ranking is driven by literal keyword overlap vs.
  LLM judgment.
- **Graceful fallback instead of hard failure** when a key is missing or
  a single LLM call errors, so one bad response doesn't crash the whole
  batch run.
