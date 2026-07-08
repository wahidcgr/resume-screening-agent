#!/usr/bin/env python3
"""
Resume Screening Agent -- CLI entry point.

Usage:
    python main.py --jd data/job_description.txt --resumes data/resumes --output output

Environment:
    GROQ_API_KEY   Your Groq API key (required for full LLM-based
                    extraction/scoring; falls back to a heuristic
                    mode if not set -- see README for details).
    GROQ_MODEL     Optional override for the Groq model ID
                    (default: openai/gpt-oss-120b).
"""

import argparse
import os
import sys

from agent.ranker import run_screening


def parse_args():
    parser = argparse.ArgumentParser(description="Resume Screening Agent")
    parser.add_argument("--jd", default="data/job_description.txt",
                         help="Path to the job description text file")
    parser.add_argument("--resumes", default="data/resumes",
                         help="Folder containing resume files (.pdf/.docx/.txt)")
    parser.add_argument("--output", default="output",
                         help="Folder to write ranked_results.json / .csv")
    parser.add_argument("--no-llm", action="store_true",
                         help="Force heuristic mode even if GROQ_API_KEY is set")
    parser.add_argument("--model", default=None,
                         help="Override the Groq model ID (default: openai/gpt-oss-120b)")
    parser.add_argument("--top", type=int, default=5,
                         help="Number of top candidates to print to the console")
    return parser.parse_args()


def main():
    args = parse_args()
    use_llm = not args.no_llm

    if use_llm and not os.environ.get("GROQ_API_KEY"):
        print("[info] GROQ_API_KEY is not set -- running in heuristic "
              "fallback mode (no LLM calls). See README for how to enable "
              "full LLM-based extraction and scoring.\n")

    try:
        results = run_screening(
            jd_path=args.jd,
            resumes_folder=args.resumes,
            output_folder=args.output,
            use_llm=use_llm,
            model=args.model,
        )
    except FileNotFoundError as exc:
        print(f"[error] {exc}")
        sys.exit(1)

    print(f"\n=== Top {min(args.top, len(results))} Candidates ===\n")
    for r in results[: args.top]:
        print(f"#{r['rank']}  {r['name']}  (final score: {r['final_score']}/100)")
        print(f"    file: {r['file']}")
        print(f"    tfidf_score: {r['tfidf_score']}   llm_score: {r['llm_score']}")
        print(f"    reasoning: {r['reasoning']}")
        print()


if __name__ == "__main__":
    main()
