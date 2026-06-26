import logging
from flask import Flask, jsonify, request, send_from_directory

from analyzer import analyze_ticket, validate_payload


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__, static_folder="frontend", static_url_path="")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/analyze-ticket")
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
