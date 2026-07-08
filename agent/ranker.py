"""
ranker.py
Orchestrates the full pipeline for one run:
  parse resumes -> extract structured fields -> score against JD -> rank -> save

Provides two entry points:
  - run_screening()         batch version used by the CLI (main.py)
  - run_screening_stream()  generator version used by the web dashboard
                             (app.py) to push live per-resume progress events
                             over Server-Sent Events
"""

import csv
import json
from pathlib import Path

from .parser import extract_text, list_resume_files
from .extractor import extract_fields
from .scorer import score_candidate


def _process_one(file_path: str, job_description: str, use_llm: bool, model: str | None) -> dict:
    """Parse, extract, and score a single resume file. Returns a candidate
    dict (without 'rank', which is assigned after sorting the full batch),
    or a dict with an 'error' key if the file could not be processed."""
    file_name = Path(file_path).name
    kwargs = {"use_llm": use_llm}
    if model:
        kwargs["model"] = model

    try:
        resume_text = extract_text(file_path)
    except Exception as exc:  # noqa: BLE001
        return {"file": file_name, "error": f"Could not read file: {exc}"}

    if not resume_text.strip():
        return {"file": file_name, "error": "No extractable text found in file"}

    profile = extract_fields(resume_text, **kwargs)
    score_result = score_candidate(job_description, resume_text, profile, **kwargs)

    return {
        "file": file_name,
        "name": profile.get("name", "Unknown"),
        "email": profile.get("email"),
        "phone": profile.get("phone"),
        "total_experience_years": profile.get("total_experience_years"),
        "skills": profile.get("skills", []),
        "education": profile.get("education", []),
        "summary": profile.get("summary", ""),
        "final_score": score_result["final_score"],
        "tfidf_score": score_result["tfidf_score"],
        "llm_score": score_result["llm_score"],
        "reasoning": score_result["reasoning"],
        "strengths": score_result["strengths"],
        "gaps": score_result["gaps"],
    }


def _rank(results: list) -> list:
    results.sort(key=lambda r: r["final_score"], reverse=True)
    for rank, r in enumerate(results, start=1):
        r["rank"] = rank
    return results


def run_screening(jd_path: str, resumes_folder: str, output_folder: str,
                   use_llm: bool = True, model: str | None = None) -> list:
    """Run the resume screening pipeline end-to-end and return ranked results.
    Used by the CLI (main.py). Prints progress to stdout."""
    job_description = Path(jd_path).read_text(encoding="utf-8")
    resume_files = list_resume_files(resumes_folder)

    if not resume_files:
        raise FileNotFoundError(f"No supported resume files found in {resumes_folder}")

    results = []
    for i, file_path in enumerate(resume_files, start=1):
        print(f"[{i}/{len(resume_files)}] Processing {Path(file_path).name} ...")
        candidate = _process_one(file_path, job_description, use_llm, model)
        if "error" in candidate:
            print(f"  [warn] {candidate['file']}: {candidate['error']}; skipping.")
            continue
        results.append(candidate)

    results = _rank(results)
    _save_outputs(results, output_folder)
    return results


def run_screening_stream(jd_path: str, resumes_folder: str, output_folder: str,
                          use_llm: bool = True, model: str | None = None):
    """Generator version of run_screening for use behind an SSE endpoint.

    Yields dicts describing progress as it goes:
      {"type": "start", "total": N}
      {"type": "progress", "index": i, "total": N, "file": name, "status": "processing"}
      {"type": "candidate", "index": i, "total": N, "candidate": {...}}   (unranked)
      {"type": "skipped", "index": i, "total": N, "file": name, "reason": "..."}
      {"type": "done", "results": [...ranked...], "output": {"json": path, "csv": path}}
      {"type": "error", "message": "..."}
    """
    try:
        job_description = Path(jd_path).read_text(encoding="utf-8")
        resume_files = list_resume_files(resumes_folder)
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": f"Could not read job description or resumes: {exc}"}
        return

    if not resume_files:
        yield {"type": "error", "message": f"No supported resume files found in {resumes_folder}"}
        return

    total = len(resume_files)
    yield {"type": "start", "total": total}

    results = []
    for i, file_path in enumerate(resume_files, start=1):
        file_name = Path(file_path).name
        yield {"type": "progress", "index": i, "total": total, "file": file_name, "status": "processing"}

        candidate = _process_one(file_path, job_description, use_llm, model)

        if "error" in candidate:
            yield {"type": "skipped", "index": i, "total": total, "file": file_name, "reason": candidate["error"]}
            continue

        results.append(candidate)
        yield {"type": "candidate", "index": i, "total": total, "candidate": candidate}

    results = _rank(results)
    out_paths = _save_outputs(results, output_folder)
    yield {"type": "done", "results": results, "output": out_paths}


def _save_outputs(results: list, output_folder: str) -> dict:
    out_dir = Path(output_folder)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "ranked_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    csv_path = out_dir / "ranked_results.csv"
    fieldnames = [
        "rank", "name", "file", "email", "phone", "total_experience_years",
        "final_score", "tfidf_score", "llm_score", "reasoning",
        "strengths", "gaps", "skills", "education",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = dict(r)
            row["skills"] = "; ".join(row.get("skills", []))
            row["education"] = "; ".join(row.get("education", []))
            row["strengths"] = "; ".join(row.get("strengths", []))
            row["gaps"] = "; ".join(row.get("gaps", []))
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    print(f"\nSaved ranked results to:\n  {json_path}\n  {csv_path}")
    return {"json": str(json_path), "csv": str(csv_path)}
