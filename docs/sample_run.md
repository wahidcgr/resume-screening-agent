# Sample Run

The command below was run against the JD in `data/job_description.txt`
(Backend Software Engineer, Python) and the 11 sample resumes in
`data/resumes/` (10 varied real-world-style profiles + 1 clearly
unrelated marketing profile, included to sanity-check that the agent
correctly ranks off-topic candidates last).

> **Note:** this transcript was captured in **heuristic fallback mode**
> (`--no-llm`, no `GROQ_API_KEY` configured in the build/test
> environment) purely so the full pipeline could be smoke-tested without
> a live key. The code path, output shape, and ranking logic are
> identical when run with a real key — the only difference is that
> `llm_score` and `reasoning` come from the LLM's judgment instead of the
> keyword-overlap fallback, and reasoning/strengths/gaps become
> noticeably more specific. See `docs/scoring_method.md` for what changes.

```
$ python main.py --no-llm --top 11

[info] GROQ_API_KEY is not set -- running in heuristic fallback mode
(no LLM calls). See README for how to enable full LLM-based extraction
and scoring.

[1/11] Processing resume_01_ananya.txt ...
[2/11] Processing resume_02_vikram.txt ...
[3/11] Processing resume_03_priya.txt ...
[4/11] Processing resume_04_arjun.txt ...
[5/11] Processing resume_05_fatima.txt ...
[6/11] Processing resume_06_karan.txt ...
[7/11] Processing resume_07_neha.txt ...
[8/11] Processing resume_08_thomas.txt ...
[9/11] Processing resume_09_sara.txt ...
[10/11] Processing resume_10_manish.txt ...
[11/11] Processing resume_11_lakshmi.txt ...

Saved ranked results to:
  output/ranked_results.json
  output/ranked_results.csv

=== Top 11 Candidates ===

#1  Ananya Rao  (final score: 58.92/100)
    file: resume_01_ananya.txt
    tfidf_score: 19.77   llm_score: 80.0

#2  Manish Gupta  (final score: 58.08/100)
    file: resume_10_manish.txt
    tfidf_score: 17.37   llm_score: 80.0

#3  Priya Menon  (final score: 57.92/100)
    file: resume_03_priya.txt
    tfidf_score: 16.92   llm_score: 80.0

#4  Neha Iyer  (final score: 57.75/100)
    file: resume_07_neha.txt
    tfidf_score: 16.44   llm_score: 80.0

#5  Fatima Sheikh  (final score: 54.7/100)
    file: resume_05_fatima.txt
    tfidf_score: 15.14   llm_score: 76.0

#6  Thomas George  (final score: 52.97/100)
    file: resume_08_thomas.txt
    tfidf_score: 10.21   llm_score: 76.0

#7  Karan Malhotra  (final score: 37.74/100)
    file: resume_06_karan.txt
    tfidf_score: 11.25   llm_score: 52.0

#8  Sara D'Souza  (final score: 37.16/100)
    file: resume_09_sara.txt
    tfidf_score: 9.61    llm_score: 52.0

#9  Arjun Sharma  (final score: 31.48/100)
    file: resume_04_arjun.txt
    tfidf_score: 8.22    llm_score: 44.0

#10  Vikram Nair  (final score: 25.42/100)
    file: resume_02_vikram.txt
    tfidf_score: 5.77    llm_score: 36.0

#11  Lakshmi Venkatesan  (final score: 19.98/100)
    file: resume_11_lakshmi.txt
    tfidf_score: 5.1     llm_score: 28.0
```

## Sanity check

The ranking lines up with intuition even in fallback mode:

- **Top 6** are all backend/Python-adjacent engineers with REST API, SQL,
  and Docker/cloud experience — a direct match to the JD.
- **Middle** (`Karan`, data analyst; `Sara`, junior Python/Flask dev) are
  partial matches — real but limited overlap with the JD.
- **Bottom 2** (`Vikram`, frontend/JS dev; `Lakshmi`, marketing, no dev
  background at all) are correctly pushed to the bottom, with Lakshmi
  (the deliberately unrelated profile) scoring lowest of all 11.

Full field-by-field output (skills, education, reasoning, strengths,
gaps) for every candidate is in `output/ranked_results.json` and
`output/ranked_results.csv`.
