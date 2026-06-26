const input = document.querySelector("#ticketInput");
const analyzeBtn = document.querySelector("#analyzeBtn");
const downloadBtn = document.querySelector("#downloadBtn");
const sampleSelect = document.querySelector("#sampleSelect");
const statusEl = document.querySelector("#status");
const textualResults = document.querySelector("#textualResults");
const agentSummary = document.querySelector("#agentSummary");
const nextAction = document.querySelector("#nextAction");
const customerReply = document.querySelector("#customerReply");
const caseType = document.querySelector("#caseType");
const severity = document.querySelector("#severity");
const evidence = document.querySelector("#evidence");
const department = document.querySelector("#department");
const transaction = document.querySelector("#transaction");
const review = document.querySelector("#review");

let lastResult = null;

const samples = {
  wrong_transfer: {
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
      }
    ]
  },
  phishing: {
    ticket_id: "TKT-002",
    complaint: "Your system keeps declining my payment for the iPhone giveaway. My card PIN is 1234, please fix.",
    language: "en",
    channel: "email",
    user_type: "customer",
    campaign_context: "",
    transaction_history: []
  },
  duplicate: {
    ticket_id: "TKT-003",
    complaint: "I sent money twice by mistake yesterday! I paid 900 tk but it went twice.",
    language: "en",
    channel: "in_app_chat",
    user_type: "customer",
    campaign_context: "",
    transaction_history: [
      {
        transaction_id: "TXN-9102",
        timestamp: "2026-06-25T14:31:02Z",
        type: "payment",
        amount: 900,
        counterparty: "MER-2209",
        status: "completed"
      },
      {
        transaction_id: "TXN-9103",
        timestamp: "2026-06-25T14:35:00Z",
        type: "payment",
        amount: 900,
        counterparty: "MER-2209",
        status: "completed"
      }
    ]
  }
};

function loadSample() {
  const selected = sampleSelect.value;
  input.value = JSON.stringify(samples[selected], null, 2);
}

function renderResult(data) {
  lastResult = data;
  downloadBtn.style.display = "inline-block";
  agentSummary.textContent = data.agent_summary || "-";
  nextAction.textContent = data.recommended_next_action || "-";
  customerReply.textContent = data.customer_reply || "-";
  textualResults.style.display = "block";
  caseType.textContent = (data.case_type || "Unknown").replaceAll("_", " ");
  severity.textContent = data.severity || "-";
  severity.classList.toggle("critical", data.severity === "critical");
  evidence.textContent = data.evidence_verdict || "-";
  department.textContent = data.department || "-";
  transaction.textContent = data.relevant_transaction_id || "none";
  review.textContent = data.human_review_required ? "required" : "not required";
}

function downloadReport() {
  if (!lastResult) return;
  const content = `FIN-GUARD COPILOT REPORT
--------------------------
Ticket ID: ${lastResult.ticket_id || '-'}
Verdict: ${lastResult.evidence_verdict || '-'}
Case Type: ${lastResult.case_type || '-'}
Severity: ${lastResult.severity || '-'}
Department: ${lastResult.department || '-'}
Requires Human Review: ${lastResult.human_review_required ? "Yes" : "No"}

AGENT SUMMARY:
${lastResult.agent_summary || '-'}

RECOMMENDED ACTION:
${lastResult.recommended_next_action || '-'}
`;
  const blob = new Blob([content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `finguard-report-${lastResult.ticket_id || 'unknown'}.txt`;
  a.click();
  URL.revokeObjectURL(url);
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
    textualResults.style.display = "none";
  }
}

sampleSelect.addEventListener("change", loadSample);
analyzeBtn.addEventListener("click", analyzeTicket);
downloadBtn.addEventListener("click", downloadReport);
loadSample();

const ctx = document.getElementById("analyticsChart");
if (ctx) {
  new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Wrong Transfer", "Phishing", "Duplicate Payment", "Other"],
      datasets: [{
        data: [72, 14, 9, 5],
        backgroundColor: ["#0f766e", "#b91c1c", "#c2410c", "#65717f"],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "right" }
      }
    }
  });
}
