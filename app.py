"""
Provenance Guard — Flask app.
Milestone 5: adds rate limiting on /submit and the POST /appeal endpoint.
Labels + confidence scoring unchanged from M4.
"""

import uuid
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

load_dotenv()

from scoring import score_content
from labels import get_attribution, get_label_text
from audit_log import append_log, get_log, find_by_content_id

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json(silent=True) or {}
    text = data.get("text")
    creator_id = data.get("creator_id")

    if not text or not creator_id:
        return jsonify({"error": "Both 'text' and 'creator_id' are required."}), 400

    content_id = str(uuid.uuid4())

    result = score_content(text)
    confidence = result["confidence"]
    attribution = get_attribution(confidence)
    label = get_label_text(confidence)

    log_entry = {
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": result["llm_score"],
        "stylometric_score": result["stylometric_score"],
        "status": "classified",
    }
    append_log(log_entry)

    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
    })


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True) or {}
    content_id = data.get("content_id")
    creator_reasoning = data.get("creator_reasoning")

    if not content_id or not creator_reasoning:
        return jsonify({"error": "Both 'content_id' and 'creator_reasoning' are required."}), 400

    original = find_by_content_id(content_id)
    if original is None:
        return jsonify({"error": f"No submission found for content_id '{content_id}'."}), 404

    # Log the appeal as a new entry — status flips to under_review, and we keep a
    # pointer back to the original decision so a reviewer sees both side by side.
    # No automated re-classification, per spec.
    append_log({
        "content_id": content_id,
        "creator_id": original.get("creator_id"),
        "status": "under_review",
        "appeal_reasoning": creator_reasoning,
        "original_attribution": original.get("attribution"),
        "original_confidence": original.get("confidence"),
        "original_llm_score": original.get("llm_score"),
        "original_stylometric_score": original.get("stylometric_score"),
    })

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": "Appeal received and logged for review.",
    })


@app.route("/log", methods=["GET"])
def log():
    return jsonify({"entries": get_log()})


if __name__ == "__main__":
    app.run(debug=True, port=5000)