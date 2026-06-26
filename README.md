# FinGuard-Copilot

Flask service and plain HTML/CSS/JS frontend for the SUST CSE Carnival 2026 preliminary challenge.

## Tech Stack

- Backend: Python, Flask
- Frontend: HTML, CSS, vanilla JavaScript
- Deployment: Gunicorn and optional Docker
- AI approach: deterministic rule-based investigator; no external model or API key required

## Run Locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` for the frontend.

## API

### GET `/health`

Returns:

```json
{"status":"ok"}
```

### POST `/analyze-ticket`

Accepts the challenge request schema and returns:

- `ticket_id`
- `relevant_transaction_id`
- `evidence_verdict`
- `case_type`
- `severity`
- `department`
- `agent_summary`
- `recommended_next_action`
- `customer_reply`
- `human_review_required`
- `confidence`
- `reason_codes`

Example:

```bash
curl -X POST http://127.0.0.1:5000/analyze-ticket ^
  -H "Content-Type: application/json" ^
  -d @sample_input.json
```

## Safety Logic

The service never asks customers for PIN, OTP, password, security code, CVV, or full card details. It avoids promising refunds, reversals, recovery, or account changes. Ambiguous, inconsistent, suspicious, disputed, and high-value cases are marked for human review.

## Evidence Reasoning

The analyzer reads both complaint text and transaction history. It scores candidate transactions using transaction ID mentions, amount matches, counterparty matches, and transaction type. It then chooses `consistent`, `inconsistent`, or `insufficient_data` based on the selected case type and transaction status.

## Models

No external model is used. The system runs fully inside the Flask process using transparent rules, which keeps latency low and avoids API cost or secret handling during evaluation.

## Docker

```bash
docker build -t queuestorm-investigator .
docker run --rm -p 5000:5000 queuestorm-investigator
```

## Assumptions and Limitations

- Bangla and Banglish support is keyword based, not full natural-language understanding.
- Hidden cases with unusual phrasing may need additional keyword tuning.
- The service is an internal copilot and does not perform real financial operations.
