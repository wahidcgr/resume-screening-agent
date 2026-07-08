"""
extractor.py
Uses the Groq API to extract structured fields (skills, experience,
education, summary) from raw resume text.

If no GROQ_API_KEY is set, falls back to a simple keyword/heuristic
extractor so the pipeline can still be run end-to-end for a quick smoke
test. The heuristic fallback is intentionally basic -- it exists for
demo/testing convenience, not as a replacement for the LLM extraction.
"""

import json
import os
import re

DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

EXTRACTION_SYSTEM_PROMPT = """You are a precise resume-parsing assistant.
Given the raw text of a resume, extract structured information and return
ONLY a single JSON object -- no markdown fences, no commentary, no preamble.

The JSON object must have exactly these keys:
{
  "name": string,
  "email": string or null,
  "phone": string or null,
  "total_experience_years": number (estimate from work history; 0 if none),
  "skills": array of strings (normalize casing, dedupe, no duplicates),
  "education": array of strings (degree + institution, one entry each),
  "summary": string (2-3 sentence neutral summary of the candidate's background)
}

Rules:
- Base every field only on what is actually present in the resume text.
- Never invent skills, employers, or degrees that are not stated or clearly implied.
- If a field is not present, use null (for strings) or an empty array/0 (for others).
- Return valid JSON only.
"""


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def extract_fields_llm(resume_text: str, model: str = DEFAULT_MODEL) -> dict:
    """Call the Groq API to extract structured fields from resume text."""
    from groq import Groq

    client = Groq()  # reads GROQ_API_KEY from env
    response = client.chat.completions.create(
        model=model,
        max_tokens=1000,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": resume_text},
        ],
    )
    raw_text = response.choices[0].message.content
    cleaned = _strip_json_fences(raw_text)
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Heuristic fallback (used only when no API key is configured)
# ---------------------------------------------------------------------------

_COMMON_SKILLS = [
    "python", "java", "javascript", "typescript", "react", "node.js", "django",
    "flask", "fastapi", "sql", "postgresql", "mysql", "mongodb", "redis",
    "docker", "kubernetes", "aws", "gcp", "azure", "git", "ci/cd", "jenkins",
    "github actions", "kafka", "rabbitmq", "terraform", "pandas", "numpy",
    "scikit-learn", "power bi", "tableau", "excel", "spring boot", "hibernate",
    "pytest", "graphql", "rest apis", "grpc", "linux", "sqlite",
]


def extract_fields_heuristic(resume_text: str) -> dict:
    """Very simple rule-based extractor used as an offline fallback.

    This does NOT replace the LLM extraction -- it exists so the full
    pipeline (parsing -> extraction -> scoring -> ranking) can be smoke
    tested without an API key.
    """
    text_lower = resume_text.lower()

    # Name: assume first non-empty line
    lines = [l.strip() for l in resume_text.splitlines() if l.strip()]
    name = lines[0] if lines else "Unknown"

    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", resume_text)
    email = email_match.group(0) if email_match else None

    phone_match = re.search(r"(\+?\d[\d\-\s]{8,}\d)", resume_text)
    phone = phone_match.group(0).strip() if phone_match else None

    skills_found = sorted({s for s in _COMMON_SKILLS if s in text_lower})

    # crude years-of-experience guess: look for "N years"
    years_match = re.search(r"(\d+)\+?\s*years?", text_lower)
    total_experience_years = float(years_match.group(1)) if years_match else 0

    education = []
    for line in lines:
        if re.search(r"\b(b\.?tech|b\.?e\.?|m\.?tech|b\.?sc|m\.?sc|b\.?com|b\.?a\.?|m\.?s\.?)\b",
                      line.lower()):
            education.append(line)

    summary = (
        f"Candidate with approximately {total_experience_years:.0f} years of "
        f"experience. Key listed skills: {', '.join(skills_found[:6]) or 'none detected'}."
    )

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "total_experience_years": total_experience_years,
        "skills": [s.title() for s in skills_found],
        "education": education,
        "summary": summary,
    }


def extract_fields(resume_text: str, use_llm: bool = True, model: str = DEFAULT_MODEL) -> dict:
    """Extract structured fields, preferring the LLM and falling back to
    the heuristic extractor if no API key is available or the call fails.
    """
    if use_llm and os.environ.get("GROQ_API_KEY"):
        try:
            return extract_fields_llm(resume_text, model=model)
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] LLM extraction failed ({exc}); using heuristic fallback.")
            return extract_fields_heuristic(resume_text)
    else:
        return extract_fields_heuristic(resume_text)
