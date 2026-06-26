# FinGuard-Copilot

Flask service and plain HTML/CSS/JS frontend for the **SUST CSE Carnival 2026 – Codex Community Hackathon** preliminary challenge.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, Flask 3.0 |
| Frontend | HTML, CSS, vanilla JavaScript |
| Deployment | Gunicorn (production), Docker |
| AI approach | Deterministic rule-based investigator — no external model or API key required |

---

## Run Locally

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # Linux / macOS
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` for the interactive frontend.

---

## API

### GET `/health`

Returns:

```json
{"status": "ok"}
```

### POST `/analyze-ticket`

Accepts the challenge request schema and returns a structured JSON response.

**Request example:**

```bash
curl -X POST http://127.0.0.1:5000/analyze-ticket ^
  -H "Content-Type: application/json" ^
  -d @sample_input.json
```

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `ticket_id` | string | Echoed from request |
| `relevant_transaction_id` | string \| null | Transaction that the complaint refers to |
| `evidence_verdict` | enum | `consistent` / `inconsistent` / `insufficient_data` |
| `case_type` | enum | See taxonomy below |
| `severity` | enum | `low` / `medium` / `high` / `critical` |
| `department` | enum | Routing target |
| `agent_summary` | string | One-to-two sentence case summary |
| `recommended_next_action` | string | Operational next step for the agent |
| `customer_reply` | string | Safe, official reply to the customer |
| `human_review_required` | boolean | Escalation flag |
| `confidence` | float | 0–1 confidence estimate |
| `reason_codes` | array | Short labels explaining the decision |

**HTTP status codes:**

| Code | Meaning |
|---|---|
| 200 | Successful analysis |
| 400 | Malformed input (invalid JSON, missing required fields) |
| 422 | Valid schema but semantically invalid (e.g. empty complaint) |
| 500 | Internal error — no stack trace or secrets exposed |

---

## MODELS

> **No external model is used in this service.**

| Model / Component | Where it runs | Why chosen |
|---|---|---|
| Rule-based keyword classifier (`analyzer.py`) | In-process, Flask worker | Zero latency, zero cost, no API keys, fully transparent logic, deterministic output — ideal for a hackathon evaluation environment |
| Transaction evidence scorer | In-process, pure Python | Lightweight scoring by TXN ID mention, amount match, counterparty overlap, and transaction type — no ML overhead |
| Duplicate detector | In-process, pure Python | O(n) dictionary scan over the short history window (2–5 entries) |

### Cost reasoning

Because no external model is called, the per-request cost is **$0.00**. This keeps the service within the stated runtime profile (2 vCPU / 4 GB RAM) and removes any concern about rate limits, API outages, or credential exposure during evaluation.

### Why not use an LLM?

The problem statement explicitly states that a simple, reliable, safe API scores higher than a complex but unreliable one. A deterministic rule-based system:

- Always responds within the 30-second per-request timeout
- Never hallucinates enum values or safety violations
- Is fully auditable — every routing decision traces to explicit code

---

## AI Approach

The investigator works in five stages:

1. **Sanitize** — Strip prompt-injection phrases from complaint text before any processing.
2. **Classify** — Score each `case_type` by keyword hits against the complaint (English + Bangla + Banglish keywords). Boost merchant / agent types for the matching `user_type`.
3. **Match transaction** — Score each history entry by TXN-ID mention (+6), amount match (+3), counterparty overlap (+2), and type match (+1). Pick the highest scorer.
4. **Decide evidence** — Compare the matched transaction's `status` and `type` against what the case type predicts. Return `consistent`, `inconsistent`, or `insufficient_data`.
5. **Route and respond** — Derive severity, department, human-review flag, agent summary, next action, and customer reply from the above results.

---

## Safety Logic

All safety rules from Section 8 of the problem statement are enforced in code:

| Rule | Implementation |
|---|---|
| Never ask for PIN / OTP / password / CVV | `customer_reply` never contains credential-seeking language; `make_customer_reply()` adds an explicit reminder to *not* share credentials in every reply |
| Never confirm refund / reversal / recovery | Refund replies use "any eligible amount will be **returned** through official channels" — no promise language |
| Never refer to suspicious third parties | Replies only reference "official support channels" |
| Prompt injection resistance | `sanitize_complaint()` redacts injection trigger phrases (ignore instructions, act as, jailbreak, etc.) before classification |
| Ambiguous / high-value / disputed cases → human review | `human_review_required = True` when case type is dispute, severity is high/critical, evidence is not consistent, or amount ≥ 10,000 BDT |

---

## Evidence Reasoning

The analyzer reads both complaint text and transaction history:

- **TXN-ID match** — explicit ID mentioned in complaint scores highest (+6 per match).
- **Amount match** — complaint text parsed for BDT amounts; compared within ±0.01 to history amounts.
- **Counterparty match** — phone numbers extracted from complaint and cross-matched with history `counterparty` field.
- **Type match** — expected transaction types per case type (e.g. `wrong_transfer` expects `transfer` or `payment`).

Evidence verdict:

| Verdict | Condition |
|---|---|
| `consistent` | Transaction matches complaint, status/type aligns with the reported case |
| `inconsistent` | Transaction found but status/type contradicts the complaint |
| `insufficient_data` | No history, no match, or match score too low |

---

## Docker

```bash
docker build -t queuestorm-investigator .
docker run --rm -p 5000:5000 queuestorm-investigator
```

---

## Assumptions and Limitations

- Bangla and Banglish support is keyword-based, not full natural-language understanding.
- Hidden cases with unusual phrasing may need additional keyword tuning.
- Duplicate detection relies on identical (type, amount, counterparty, status) tuples within the provided history window; duplicates across longer histories will not be caught.
- The service is an internal copilot and does not perform real financial operations.
- No real customer data, no real payment-system integration, and no production-grade deployment is required or used.
