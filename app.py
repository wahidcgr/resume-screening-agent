"""
app.py
Flask backend for the FitBench web dashboard.

Routes:
  GET  /                              Dashboard (control panel)
  GET  /results                       Results page (reads ?run_id=...)
  GET  /api/status                    Reports whether Groq LLM is configured
  GET  /api/sample-jd                 Returns the bundled sample job description text
  POST /api/prepare                   Saves an uploaded/pasted JD + resumes for a run, returns {run_id}
  GET  /api/run/<run_id>/stream       Server-Sent Events stream of screening progress
  GET  /api/results/<run_id>          Ranked results JSON for a completed run
  GET  /api/download/<run_id>/<fmt>   Download ranked_results.json or .csv for a run

Run with:  python app.py
"""

import json
import os
import shutil
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_file, abort

from agent.parser import extract_text
from agent.ranker import run_screening_stream

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_JD_PATH = BASE_DIR / "data" / "job_description.txt"
SAMPLE_RESUMES_DIR = BASE_DIR / "data" / "resumes"
UPLOAD_ROOT = BASE_DIR / "data" / "uploads"
OUTPUT_ROOT = BASE_DIR / "output" / "runs"

UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25MB total upload cap


@app.route("/")
def dashboard():
    return render_template("index.html")


@app.route("/results")
def results_page():
    return render_template("results.html")


@app.route("/api/status")
def api_status():
    return jsonify({
        "llm_configured": bool(os.environ.get("GROQ_API_KEY")),
        "model": os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
    })


@app.route("/api/sample-jd")
def api_sample_jd():
    if not SAMPLE_JD_PATH.exists():
        return jsonify({"text": ""})
    return jsonify({"text": SAMPLE_JD_PATH.read_text(encoding="utf-8")})


@app.route("/api/prepare", methods=["POST"])
def api_prepare():
    run_id = uuid.uuid4().hex[:10]
    run_dir = UPLOAD_ROOT / run_id
    resumes_dir = run_dir / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)

    jd_mode = request.form.get("jd_mode", "sample")

    try:
        if jd_mode == "paste":
            jd_text = (request.form.get("jd_text") or "").strip()
            if not jd_text:
                return jsonify({"error": "Job description text is empty."}), 400
            (run_dir / "job_description.txt").write_text(jd_text, encoding="utf-8")

        elif jd_mode == "upload":
            jd_file = request.files.get("jd_file")
            if not jd_file or not jd_file.filename:
                return jsonify({"error": "No job description file was uploaded."}), 400
            ext = Path(jd_file.filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                return jsonify({"error": f"Unsupported JD file type '{ext}'."}), 400
            temp_path = run_dir / f"jd_upload{ext}"
            jd_file.save(temp_path)
            text = extract_text(str(temp_path))
            if not text.strip():
                return jsonify({"error": "Could not extract any text from the uploaded JD file."}), 400
            (run_dir / "job_description.txt").write_text(text, encoding="utf-8")

        else:  # sample
            if not SAMPLE_JD_PATH.exists():
                return jsonify({"error": "Bundled sample job description is missing."}), 500
            shutil.copy(SAMPLE_JD_PATH, run_dir / "job_description.txt")

        resume_files = [f for f in request.files.getlist("resumes") if f and f.filename]
        if resume_files:
            saved = 0
            for f in resume_files:
                ext = Path(f.filename).suffix.lower()
                if ext not in ALLOWED_EXTENSIONS:
                    continue
                dest = resumes_dir / Path(f.filename).name
                f.save(dest)
                saved += 1
            if saved == 0:
                return jsonify({"error": "None of the uploaded resumes had a supported file type (.pdf/.docx/.txt)."}), 400
        else:
            if not SAMPLE_RESUMES_DIR.exists():
                return jsonify({"error": "Bundled sample resumes folder is missing."}), 500
            for p in SAMPLE_RESUMES_DIR.iterdir():
                if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS:
                    shutil.copy(p, resumes_dir / p.name)

    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Failed to prepare run: {exc}"}), 500

    return jsonify({"run_id": run_id})


@app.route("/api/run/<run_id>/stream")
def api_run_stream(run_id):
    run_dir = UPLOAD_ROOT / run_id
    jd_path = run_dir / "job_description.txt"
    resumes_dir = run_dir / "resumes"

    if not jd_path.exists() or not resumes_dir.exists():
        def error_gen():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Run not found or expired. Please start again.'})}\n\n"
        return Response(error_gen(), mimetype="text/event-stream")

    use_llm = request.args.get("use_llm", "true").lower() != "false"
    output_dir = OUTPUT_ROOT / run_id

    def generate():
        try:
            for event in run_screening_stream(str(jd_path), str(resumes_dir), str(output_dir), use_llm=use_llm):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.route("/api/results/<run_id>")
def api_results(run_id):
    json_path = OUTPUT_ROOT / run_id / "ranked_results.json"
    if not json_path.exists():
        return jsonify({"error": "Results not found for this run."}), 404
    return jsonify(json.loads(json_path.read_text(encoding="utf-8")))


@app.route("/api/download/<run_id>/<fmt>")
def api_download(run_id, fmt):
    if fmt not in ("json", "csv"):
        abort(404)
    path = OUTPUT_ROOT / run_id / f"ranked_results.{fmt}"
    if not path.exists():
        abort(404)
    return send_file(path, as_attachment=True, download_name=f"ranked_results.{fmt}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\nFitBench dashboard running at http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
