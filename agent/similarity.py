"""
similarity.py
Computes a deterministic NLP similarity score between a job description and
a resume using TF-IDF vectorization + cosine similarity.

Why TF-IDF instead of a neural embedding model?
- No model download required (works fully offline, no external API/model
  weights to fetch) -- reviewers can run this instantly after `pip install`.
- Deterministic and explainable: the score is a direct function of shared,
  discriminative vocabulary between the JD and the resume.
- Fast enough to run on hundreds of resumes with no GPU.

Tradeoff: TF-IDF only sees surface-level word overlap, not semantic
meaning (e.g. it won't know "Postgres" and "PostgreSQL" are related unless
normalized). We mitigate this partially by lowercasing and light
normalization, and we treat this score as ONE signal that's combined with
the LLM's judgment-based score (see scorer.py) rather than the sole score.
"""

import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _normalize(text: str) -> str:
    text = text.lower()
    # light normalization for a few common variants
    replacements = {
        "postgres": "postgresql",
        "js": "javascript",
        "node": "nodejs",
        "aws ec2": "aws",
        "amazon web services": "aws",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9\+\.\#\s]", " ", text)
    return text


def tfidf_similarity(job_description: str, resume_text: str) -> float:
    """Return a 0-100 similarity score between a JD and a resume using
    TF-IDF cosine similarity."""
    docs = [_normalize(job_description), _normalize(resume_text)]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    try:
        tfidf_matrix = vectorizer.fit_transform(docs)
    except ValueError:
        # Empty vocabulary (e.g. resume had no extractable text)
        return 0.0
    sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    return round(float(sim) * 100, 2)
