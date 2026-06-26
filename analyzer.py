import re
from datetime import datetime
from math import isfinite

# Prompt injection patterns that should be stripped / blocked
_INJECTION_PATTERNS = re.compile(
    r"(ignore(?: all| previous| prior)* instructions?|forget(?: all| previous| prior)* instructions?"
    r"|new instruction|disregard|system prompt|you are now|act as|pretend (you are|to be)"
    r"|jailbreak|override|roleplay as)",
    flags=re.IGNORECASE,
)


CASE_TYPES = {
    "wrong_transfer",
    "payment_failed",
    "refund_request",
    "duplicate_payment",
    "merchant_settlement_delay",
    "agent_cash_in_issue",
    "phishing_or_social_engineering",
    "other",
}

DEPARTMENTS = {
    "wrong_transfer": "dispute_resolution",
    "payment_failed": "payments_ops",
    "refund_request": "dispute_resolution",
    "duplicate_payment": "payments_ops",
    "merchant_settlement_delay": "merchant_operations",
    "agent_cash_in_issue": "agent_operations",
    "phishing_or_social_engineering": "fraud_risk",
    "other": "customer_support",
}

SENSITIVE_TERMS = (
    "pin",
    "otp",
    "password",
    "passcode",
    "verification code",
    "security code",
    "full card",
    "cvv",
)

CASE_KEYWORDS = {
    "phishing_or_social_engineering": (
        "otp",
        "pin",
        "password",
        "scam",
        "fraud",
        "phishing",
        "fake",
        "suspicious call",
        "unknown link",
        "verify account",
        "account blocked",
        "ভেরিফাই",
        "পিন",
        "ওটিপি",
        "পাসওয়ার্ড",
        "প্রতার",
    ),
    "duplicate_payment": (
        "duplicate",
        "twice",
        "double",
        "charged two",
        "paid two",
        "same payment",
        "দুইবার",
        "ডাবল",
    ),
    "merchant_settlement_delay": (
        "settlement",
        "merchant settlement",
        "merchant",
        "settled",
        "payout",
        "মার্চেন্ট",
        "সেটেলমেন্ট",
    ),
    "agent_cash_in_issue": (
        "cash in",
        "cash-in",
        "cashin",
        "agent",
        "deposit",
        "balance not added",
        "ক্যাশ ইন",
        "এজেন্ট",
        "জমা",
    ),
    "wrong_transfer": (
        "wrong number",
        "wrong recipient",
        "wrong account",
        "mistake",
        "sent to wrong",
        "send to wrong",
        "ভুল নম্বর",
        "ভুল নাম্বার",
        "ভুলে",
    ),
    "payment_failed": (
        "failed",
        "unsuccessful",
        "not successful",
        "deducted",
        "balance cut",
        "payment did not go",
        "transaction failed",
        "পেমেন্ট হয়নি",
        "কেটে",
        "ফেইল",
    ),
    "refund_request": (
        "refund",
        "return my money",
        "money back",
        "cashback",
        "reverse",
        "reversal",
        "রিফান্ড",
        "ফেরত",
    ),
}


def analyze_ticket(payload):
    # Sanitize complaint to prevent prompt injection before any processing
    raw_complaint = str(payload.get("complaint", "")).strip()
    complaint = sanitize_complaint(raw_complaint)
    history = payload.get("transaction_history") or []
    user_type = str(payload.get("user_type", "unknown")).lower()

    case_type = classify_case(complaint, user_type)
    relevant_txn, match_score = find_relevant_transaction(complaint, history, case_type)
    duplicate_pair = find_duplicate_transactions(history)

    if case_type == "duplicate_payment" and duplicate_pair:
        relevant_txn = duplicate_pair[0]
        match_score = max(match_score, 4)

    evidence_verdict = decide_evidence(case_type, relevant_txn, history, duplicate_pair, match_score)
    amount = safe_number(relevant_txn.get("amount")) if relevant_txn else amount_from_text(complaint)
    severity = decide_severity(case_type, evidence_verdict, amount, complaint)
    department = DEPARTMENTS.get(case_type, "customer_support")
    if case_type == "refund_request" and severity == "low":
        department = "customer_support"

    human_review_required = (
        case_type in {"wrong_transfer", "refund_request", "phishing_or_social_engineering"}
        or severity in {"high", "critical"}
        or evidence_verdict != "consistent"
        or amount >= 10000
    )

    reason_codes = build_reason_codes(case_type, evidence_verdict, relevant_txn, match_score, amount)
    confidence = estimate_confidence(case_type, evidence_verdict, match_score, complaint)

    return {
        "ticket_id": payload.get("ticket_id"),
        "relevant_transaction_id": relevant_txn.get("transaction_id") if relevant_txn else None,
        "evidence_verdict": evidence_verdict,
        "case_type": case_type,
        "severity": severity,
        "department": department,
        "agent_summary": make_agent_summary(case_type, evidence_verdict, relevant_txn, amount),
        "recommended_next_action": make_next_action(case_type, evidence_verdict, relevant_txn),
        "customer_reply": make_customer_reply(case_type, evidence_verdict, relevant_txn, complaint),
        "human_review_required": human_review_required,
        "confidence": confidence,
        "reason_codes": reason_codes,
    }


def validate_payload(payload):
    if not isinstance(payload, dict):
        return "Request body must be a JSON object.", 400
    for field in ("ticket_id", "complaint"):
        if field not in payload:
            return f"Missing required field: {field}.", 400
    if not isinstance(payload.get("ticket_id"), str):
        return "ticket_id must be a string.", 400
    if not isinstance(payload.get("complaint"), str):
        return "complaint must be a string.", 400
    if not payload["complaint"].strip():
        return "Complaint must not be empty.", 422
    history = payload.get("transaction_history", [])
    if history is not None:
        if not isinstance(history, list):
            return "transaction_history must be an array when provided.", 400
        for i, txn in enumerate(history):
            if not isinstance(txn, dict):
                return f"transaction_history[{i}] must be an object.", 400
    return None, None


def classify_case(complaint, user_type):
    text = normalize(complaint)
    scores = {}
    for case_type, keywords in CASE_KEYWORDS.items():
        scores[case_type] = sum(1 for keyword in keywords if has_keyword(text, keyword))

    if user_type == "merchant":
        scores["merchant_settlement_delay"] = scores.get("merchant_settlement_delay", 0) + 1
    if user_type == "agent":
        scores["agent_cash_in_issue"] = scores.get("agent_cash_in_issue", 0) + 1

    best_case = max(scores, key=scores.get)
    return best_case if scores[best_case] > 0 else "other"


def find_relevant_transaction(complaint, history, case_type):
    if not history:
        return None, 0

    text = normalize(complaint)
    explicit_ids = set(re.findall(r"\b[a-z]{2,6}-?\d{3,}\b", text, flags=re.IGNORECASE))
    complaint_amount = amount_from_text(complaint)
    complaint_counterparties = set(re.findall(r"\+?\d{6,15}", complaint))

    best_txn = None
    best_score = -1
    for txn in history:
        if not isinstance(txn, dict):
            continue
        score = 0
        txn_id = normalize(str(txn.get("transaction_id", "")))
        if txn_id and (txn_id in text or txn_id.replace("-", "") in text.replace("-", "")):
            score += 6
        if txn_id in explicit_ids:
            score += 6
        if complaint_amount and almost_equal(safe_number(txn.get("amount")), complaint_amount):
            score += 3
        counterparty = str(txn.get("counterparty", ""))
        if counterparty and any(cp in counterparty or counterparty in cp for cp in complaint_counterparties):
            score += 2
        if transaction_type_matches(case_type, str(txn.get("type", ""))):
            score += 1
        if score > best_score:
            best_txn = txn
            best_score = score

    if best_score <= 0:
        return None, 0
    return best_txn, best_score


def decide_evidence(case_type, txn, history, duplicate_pair, match_score):
    if case_type == "phishing_or_social_engineering":
        return "consistent"
    if case_type == "duplicate_payment":
        return "consistent" if duplicate_pair else ("insufficient_data" if history else "insufficient_data")
    if not history:
        return "insufficient_data"
    if not txn:
        return "insufficient_data"
    if match_score < 3:
        return "insufficient_data"

    status = normalize(str(txn.get("status", "")))
    txn_type = normalize(str(txn.get("type", "")))

    if case_type == "payment_failed":
        return "consistent" if status in {"failed", "pending"} else "inconsistent"
    if case_type == "wrong_transfer":
        return "consistent" if status == "completed" and txn_type in {"transfer", "payment"} else "inconsistent"
    if case_type == "merchant_settlement_delay":
        return "consistent" if status in {"pending", "failed"} or txn_type == "settlement" else "inconsistent"
    if case_type == "agent_cash_in_issue":
        return "consistent" if txn_type == "cash_in" and status in {"failed", "pending"} else "insufficient_data"
    if case_type == "refund_request":
        if status in {"failed", "pending", "reversed"}:
            return "consistent"
        return "insufficient_data"
    return "consistent" if match_score >= 3 else "insufficient_data"


def find_duplicate_transactions(history):
    seen = {}
    for txn in history:
        if not isinstance(txn, dict):
            continue
        key = (
            normalize(str(txn.get("type", ""))),
            round(safe_number(txn.get("amount")), 2),
            normalize(str(txn.get("counterparty", ""))),
            normalize(str(txn.get("status", ""))),
        )
        if key[1] > 0 and key[3] == "completed":
            if key in seen:
                prev_txn = seen[key]
                t1 = parse_time(prev_txn.get("timestamp"))
                t2 = parse_time(txn.get("timestamp"))
                if t1 and t2:
                    if abs((t1 - t2).total_seconds()) <= 86400:  # 24 hours
                        return prev_txn, txn
                else:
                    return prev_txn, txn
            seen[key] = txn
    return None


def decide_severity(case_type, verdict, amount, complaint):
    text = normalize(complaint)
    if case_type == "phishing_or_social_engineering":
        return "critical" if any(has_keyword(text, term) for term in SENSITIVE_TERMS) else "high"
    if amount >= 50000:
        return "critical"
    if amount >= 10000:
        return "high"
    if verdict in {"inconsistent", "insufficient_data"} and case_type != "other":
        return "high"
    if case_type in {"wrong_transfer", "duplicate_payment", "merchant_settlement_delay"}:
        return "high"
    if case_type in {"payment_failed", "refund_request", "agent_cash_in_issue"}:
        return "medium"
    return "low"


def make_agent_summary(case_type, verdict, txn, amount):
    txn_text = f"Transaction {txn.get('transaction_id')}" if txn else "No matching transaction"
    amount_text = f" for {amount:g} BDT" if amount else ""
    labels = {
        "wrong_transfer": "Customer reports a wrong transfer",
        "payment_failed": "Customer reports a failed or deducted payment",
        "refund_request": "Customer is asking about a refund or reversal",
        "duplicate_payment": "Customer reports a possible duplicate charge",
        "merchant_settlement_delay": "Merchant reports a settlement delay",
        "agent_cash_in_issue": "Customer or agent reports a cash-in posting issue",
        "phishing_or_social_engineering": "Customer reports suspicious contact or credential-seeking activity",
        "other": "Customer submitted a support request outside the main taxonomy",
    }
    return f"{labels.get(case_type, labels['other'])}{amount_text}. {txn_text} was assessed as {verdict.replace('_', ' ')} against the provided history."


def make_next_action(case_type, verdict, txn):
    txn_id = txn.get("transaction_id") if txn else "the provided details"
    if case_type == "phishing_or_social_engineering":
        return "Escalate to fraud risk, preserve the suspicious message or caller details, and remind the customer to use only official support channels."
    if verdict == "inconsistent":
        return f"Review {txn_id} manually and compare ledger status before making any customer-facing commitment."
    if verdict == "insufficient_data":
        return "Request non-sensitive identifying details through official support workflow and review the account ledger before deciding the case."
    if case_type == "wrong_transfer":
        return f"Verify {txn_id} in the ledger and route to dispute handling; do not promise recovery before approval."
    if case_type == "payment_failed":
        return f"Check payment switch and ledger state for {txn_id}, then advise on normal reversal handling if eligible."
    if case_type == "duplicate_payment":
        return f"Compare duplicate-looking transactions around {txn_id} and initiate the approved duplicate-charge review process."
    if case_type == "merchant_settlement_delay":
        return f"Check settlement batch status for {txn_id} and route to merchant operations if the batch is pending or delayed."
    if case_type == "agent_cash_in_issue":
        return f"Review agent cash-in records for {txn_id} and reconcile against the customer balance ledger."
    return "Handle through standard customer support workflow and escalate if additional risk indicators appear."


def make_customer_reply(case_type, verdict, txn, complaint):
    txn_ref = f" transaction {txn.get('transaction_id')}" if txn else " your report"
    prefix = f"We have noted your concern about{txn_ref}."
    safety_note = " For your security, never share your PIN, OTP, password, or card details with anyone, including support agents."

    text = normalize(complaint)
    credential_risk = any(has_keyword(text, term) for term in SENSITIVE_TERMS)

    if case_type == "phishing_or_social_engineering" or credential_risk:
        return (
            f"{prefix} Please do not share any PIN, OTP, password, or security code with anyone, "
            "including anyone claiming to be a support agent. Our team will review the report "
            "and contact you only through official support channels."
        )
    if verdict == "inconsistent":
        return (
            f"{prefix} The details need further verification. Our support team will review the "
            f"official records and update you through authorized channels.{safety_note}"
        )
    if verdict == "insufficient_data":
        return (
            f"{prefix} We need to review the official transaction records before any decision "
            f"can be made. Please continue only through official support channels.{safety_note}"
        )
    if case_type == "refund_request":
        return (
            f"{prefix} Our team will check eligibility under the official process, and any "
            f"eligible amount will be returned through official channels.{safety_note}"
        )
    return (
        f"{prefix} Our support team will review the official records and guide you through "
        f"the approved next steps.{safety_note}"
    )


def build_reason_codes(case_type, verdict, txn, match_score, amount):
    codes = [case_type, verdict]
    if txn:
        codes.append("transaction_match" if match_score >= 3 else "weak_transaction_match")
    else:
        codes.append("no_transaction_match")
    if amount >= 10000:
        codes.append("high_value")
    if case_type == "phishing_or_social_engineering":
        codes.append("credential_risk")
    return codes


def estimate_confidence(case_type, verdict, match_score, complaint):
    score = 0.45
    if case_type != "other":
        score += 0.18
    if verdict == "consistent":
        score += 0.17
    elif verdict == "inconsistent":
        score += 0.08
    score += min(match_score, 6) * 0.03
    if len(complaint.strip()) > 20:
        score += 0.05
    return round(max(0.1, min(0.98, score)), 2)


def transaction_type_matches(case_type, txn_type):
    expected = {
        "wrong_transfer": {"transfer", "payment"},
        "payment_failed": {"payment", "transfer"},
        "refund_request": {"payment", "transfer", "refund"},
        "duplicate_payment": {"payment"},
        "merchant_settlement_delay": {"settlement", "payment"},
        "agent_cash_in_issue": {"cash_in"},
    }
    return normalize(txn_type) in expected.get(case_type, set())


def amount_from_text(text):
    text = text or ""
    
    # Map Bangla digits to English
    bangla_to_english = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
    text = text.translate(bangla_to_english)
    
    money_matches = re.findall(
        r"(?<![\w+])(\d{2,7}(?:,\d{3})*(?:\.\d+)?)\s*(?:bdt|tk|taka)",
        text,
        flags=re.IGNORECASE,
    )
    matches = money_matches or re.findall(r"(?<![\w+])(\d{2,7}(?:,\d{3})*(?:\.\d+)?)(?![\w-])", text)
    if not matches:
        return 0
    values = []
    for match in matches:
        value = safe_number(match.replace(",", ""))
        if 0 < value <= 1000000:
            values.append(value)
    return max(values) if values else 0


def safe_number(value):
    try:
        number = float(value)
        return number if isfinite(number) else 0
    except (TypeError, ValueError):
        return 0


def almost_equal(left, right):
    return abs(left - right) < 0.01


def normalize(value):
    return str(value or "").casefold().strip()


def sanitize_complaint(text):
    """Remove prompt-injection attempts from complaint text.

    The actual complaint content is preserved; only injection trigger
    phrases are redacted so classifiers still work on genuine words.
    """
    return _INJECTION_PATTERNS.sub("[redacted]", text)


def has_keyword(text, keyword):
    return bool(re.search(rf"\b{re.escape(keyword)}\b", text))


def parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
