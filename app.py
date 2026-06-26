import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from analyzer import analyze_ticket, validate_payload


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__, static_folder="frontend", static_url_path="")

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/analyze-ticket")
@limiter.limit("30 per minute")
def analyze():
    payload = request.get_json(silent=True)
    error, status_code = validate_payload(payload)
    if error:
        return jsonify({"error": error}), status_code

    try:
        return jsonify(analyze_ticket(payload)), 200
    except Exception as e:
        logging.error(f"Error analyzing ticket: {e}", exc_info=True)
        return jsonify({"error": "Internal analysis error."}), 500


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
