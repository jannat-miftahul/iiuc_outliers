const input = document.querySelector("#ticketInput");
const analyzeBtn = document.querySelector("#analyzeBtn");
const sampleBtn = document.querySelector("#sampleBtn");
const statusEl = document.querySelector("#status");
const output = document.querySelector("#output");
const caseType = document.querySelector("#caseType");
const severity = document.querySelector("#severity");
const evidence = document.querySelector("#evidence");
const department = document.querySelector("#department");
const transaction = document.querySelector("#transaction");
const review = document.querySelector("#review");

const sampleTicket = {
  ticket_id: "TKT-001",
  complaint: "I sent 5000 taka to a wrong number around 2pm today. Please help me recover it.",
  language: "en",
  channel: "in_app_chat",
  user_type: "customer",
  campaign_context: "boishakh_bonanza_day_1",
  transaction_history: [
    {
      transaction_id: "TXN-9101",
      timestamp: "2026-04-14T14:08:22Z",
      type: "transfer",
      amount: 5000,
      counterparty: "+8801719876543",
      status: "completed"
    },
    {
      transaction_id: "TXN-9102",
      timestamp: "2026-04-14T14:31:02Z",
      type: "payment",
      amount: 900,
      counterparty: "MER-2209",
      status: "completed"
    }
  ]
};

function loadSample() {
  input.value = JSON.stringify(sampleTicket, null, 2);
}

function renderResult(data) {
  output.textContent = JSON.stringify(data, null, 2);
  caseType.textContent = (data.case_type || "Unknown").replaceAll("_", " ");
  severity.textContent = data.severity || "-";
  severity.classList.toggle("critical", data.severity === "critical");
  evidence.textContent = data.evidence_verdict || "-";
  department.textContent = data.department || "-";
  transaction.textContent = data.relevant_transaction_id || "none";
  review.textContent = data.human_review_required ? "required" : "not required";
}

async function analyzeTicket() {
  statusEl.textContent = "Analyzing...";
  try {
    const payload = JSON.parse(input.value);
    const response = await fetch("/analyze-ticket", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    renderResult(data);
    statusEl.textContent = response.ok ? "Done" : `Error ${response.status}`;
  } catch (error) {
    statusEl.textContent = "Invalid JSON or request failed";
    output.textContent = JSON.stringify({ error: error.message }, null, 2);
  }
}

sampleBtn.addEventListener("click", loadSample);
analyzeBtn.addEventListener("click", analyzeTicket);
loadSample();
