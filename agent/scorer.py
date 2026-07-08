"""
scorer.py
Produces the final candidate score by combining:
  1. tfidf_score   - deterministic NLP similarity (similarity.py)
  2. llm_score     - the LLM's judgment-based fit score with reasoning,
                      grounded in the structured fields extracted earlier

Final score = weighted average of the two (see WEIGHTS below).
Combining a cheap deterministic signal with an LLM judgment signal is a
common, pragmatic pattern: the TF-IDF score anchors the ranking in actual
shared vocabulary (hard to hallucinate), while the LLM score captures
things TF-IDF can't -- e.g. that 7 years of Go/Python backend experience
is a strong match for a "3+ years Python" requirement even if the resume
never uses the JD's exact phrasing.
"""

import json
import os
import re

DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

WEIGHTS = {
    "tfidf": 0.35,
    "llm": 0.65,
}

SCORING_SYSTEM_PROMPT = """You are a fair, consistent technical recruiter.
You will be given a Job Description and a structured candidate profile
(already extracted from their resume). Score how well this candidate fits
the role.

Return ONLY a single JSON object, no markdown fences, no commentary:
{
  "score": number from 0 to 100,
  "reasoning": string (2-4 sentences explaining the score, citing specific
               overlaps or gaps between the candidate's profile and the JD),
  "strengths": array of short strings (specific matching qualifications),
  "gaps": array of short strings (specific missing or weak qualifications)
}

Scoring guidance:
- 85-100: Strong match on required skills, experience level, and education
- 60-84: Good match with some gaps in preferred (not required) skills
- 35-59: Partial match -- missing some required skills or experience level
- 0-34: Poor match -- role is largely unrelated to candidate's background
Be specific and evidence-based. Do not inflate scores out of politeness.
"""


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def llm_fit_score(job_description: str, profile: dict, model: str = DEFAULT_MODEL) -> dict:
    """Ask Groq's LLM to score the extracted profile against the JD."""
    from groq import Groq

    client = Groq()
    user_content = (
        f"JOB DESCRIPTION:\n{job_description}\n\n"
        f"CANDIDATE PROFILE (extracted from resume):\n{json.dumps(profile, indent=2)}"
    )
    response = client.chat.completions.create(
        model=model,
        max_tokens=600,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SCORING_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    raw_text = response.choices[0].message.content
    cleaned = _strip_json_fences(raw_text)
    return json.loads(cleaned)


def heuristic_fit_score(job_description: str, profile: dict) -> dict:
    """Offline fallback scorer used when no API key is available.

    Simple keyword-overlap heuristic between required JD skills and the
    candidate's extracted skills list. Used only for smoke-testing the
    pipeline without an API key -- not a substitute for the LLM judgment.
    """
    jd_lower = job_description.lower()
    candidate_skills = [s.lower() for s in profile.get("skills", [])]

    matched = [s for s in candidate_skills if s in jd_lower]
    missing_hint = []
    for required in ["python", "sql", "rest", "git", "test"]:
        if required not in " ".join(candidate_skills) and required not in jd_lower:
            continue
        if required not in " ".join(candidate_skills):
            missing_hint.append(required)

    base = 20 + min(len(matched) * 8, 60)
    score = min(base, 95)

    return {
        "score": score,
        "reasoning": (
            f"Heuristic fallback: {len(matched)} of the candidate's listed skills "
            f"appear directly in the job description text."
        ),
        "strengths": matched[:5],
        "gaps": missing_hint,
    }


def score_candidate(job_description: str, resume_text: str, profile: dict,
                     use_llm: bool = True, model: str = DEFAULT_MODEL) -> dict:
    """Compute the combined score for one candidate."""
    from .similarity import tfidf_similarity

    tfidf_score = tfidf_similarity(job_description, resume_text)

    if use_llm and os.environ.get("GROQ_API_KEY"):
        try:
            llm_result = llm_fit_score(job_description, profile, model=model)
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] LLM scoring failed ({exc}); using heuristic fallback.")
            llm_result = heuristic_fit_score(job_description, profile)
    else:
        llm_result = heuristic_fit_score(job_description, profile)

    llm_score = float(llm_result.get("score", 0))
    final_score = round(
        WEIGHTS["tfidf"] * tfidf_score + WEIGHTS["llm"] * llm_score, 2
    )

    return {
        "final_score": final_score,
        "tfidf_score": tfidf_score,
        "llm_score": llm_score,
        "reasoning": llm_result.get("reasoning", ""),
        "strengths": llm_result.get("strengths", []),
        "gaps": llm_result.get("gaps", []),
    }
