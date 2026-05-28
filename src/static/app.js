const state = {
  lastJson: {},
};

const $ = (selector) => document.querySelector(selector);
const transcript = $("#transcript");
const jsonOutput = $("#jsonOutput");

function sessionId() {
  return $("#sessionId").value.trim() || "demo-patient";
}

function setLoading(element, loading) {
  element.classList.toggle("loading", loading);
  for (const button of element.querySelectorAll("button")) {
    button.disabled = loading;
  }
}

async function api(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || response.statusText);
  }
  updateJson(data);
  return data;
}

function updateJson(data) {
  state.lastJson = data;
  jsonOutput.textContent = JSON.stringify(data, null, 2);
}

function addMessage(role, text) {
  const message = document.createElement("div");
  message.className = `message ${role}`;
  message.textContent = text;
  transcript.appendChild(message);
  transcript.scrollTop = transcript.scrollHeight;
}

function updateInspector(data) {
  if (data.llm_provider) {
    $("#providerLabel").textContent = data.llm_provider;
    $("#providerDetail").textContent = data.llm_provider.startsWith("openai")
      ? "This response was generated through your configured OpenAI API key."
      : "This response used the local fallback path.";
  }

  if (data.emotion) {
    const emotion = data.emotion;
    $("#emotionLabel").textContent = `${emotion.emotion} / ${emotion.risk_level}`;
    $("#emotionMeter").style.width = `${emotion.score * 10}%`;
    $("#comfortStrategy").textContent = emotion.comfort_strategy || "No comfort strategy returned.";
  }

  const safetyFlags = data.safety_flags || data.red_flags || [];
  $("#safetyCount").textContent = String(safetyFlags.length);
  $("#safetyList").innerHTML = safetyFlags
    .map((flag) => `<li class="warn"><strong>${escapeHtml(flag.code)}</strong><br>${escapeHtml(flag.message || flag.severity || "")}</li>`)
    .join("");

  const citations = data.citations || [];
  $("#citationCount").textContent = String(citations.length);
  $("#citationList").innerHTML = citations
    .map((citation) => {
      const title = escapeHtml(citation.title || "Medicare source");
      const backend = citation.backend ? ` via ${escapeHtml(citation.backend)}` : "";
      const url = citation.url ? `<a href="${escapeAttribute(citation.url)}" target="_blank" rel="noreferrer">${title}</a>` : title;
      return `<li>${url}<br><small>${escapeHtml(citation.coverage_area || "medicare")}${backend}</small></li>`;
    })
    .join("");
}

function showPanel(panelId) {
  for (const panel of document.querySelectorAll(".panel")) {
    panel.classList.toggle("active", panel.id === panelId);
  }
  for (const button of document.querySelectorAll(".tab-button")) {
    button.classList.toggle("active", button.dataset.panel === panelId);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

async function checkHealth() {
  try {
    const response = await fetch("/health");
    const data = await response.json();
    $("#statusDot").className = "dot ok";
    $("#serviceStatus").textContent = "API online";
    $("#serviceDetail").textContent = data.service;
  } catch (error) {
    $("#statusDot").className = "dot err";
    $("#serviceStatus").textContent = "API offline";
    $("#serviceDetail").textContent = error.message;
  }
}

$("#chatForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const message = $("#chatMessage").value.trim();
  if (!message) return;
  addMessage("user", message);
  $("#chatMessage").value = "";
  setLoading(form, true);
  try {
    const data = await api("/api/v1/chat", {
      session_id: sessionId(),
      message,
    });
    addMessage("agent", data.answer);
    updateInspector(data);
  } catch (error) {
    addMessage("agent", `Request failed: ${error.message}`);
  } finally {
    setLoading(form, false);
  }
});

$("#intakeForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  setLoading(form, true);
  try {
    const data = await api("/api/v1/symptom-intake", {
      session_id: sessionId(),
      text: $("#intakeText").value,
    });
    updateInspector(data);
    showPanel("chatPanel");
    addMessage("agent", `Intake triage: ${data.triage_level}\nMissing: ${data.missing_fields.join(", ") || "none"}\nNext: ${data.next_questions.join(" ") || "No follow-up questions."}`);
  } catch (error) {
    updateJson({ error: error.message });
  } finally {
    setLoading(form, false);
  }
});

$("#medicalForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  setLoading(form, true);
  try {
    const data = await api("/api/v1/forms/validate", {
      form_type: "medicare_intake",
      fields: {
        full_name: $("#fullName").value,
        date_of_birth: $("#dateOfBirth").value,
        medicare_number: $("#medicareNumber").value,
        consent_to_contact: $("#consentToContact").checked,
      },
    });
    updateInspector(data);
  } catch (error) {
    updateJson({ error: error.message });
  } finally {
    setLoading(form, false);
  }
});

$("#reminderForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  setLoading(form, true);
  try {
    const data = await api("/api/v1/reminders", {
      session_id: sessionId(),
      user_text: $("#reminderText").value,
      channel: $("#reminderChannel").value,
      recipient: $("#recipientId").value || null,
    });
    updateInspector(data);
  } catch (error) {
    updateJson({ error: error.message });
  } finally {
    setLoading(form, false);
  }
});

$("#ingestButton").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  try {
    const data = await api("/api/v1/knowledge/ingest", { use_offline_sample: true });
    updateInspector(data);
  } catch (error) {
    updateJson({ error: error.message });
  } finally {
    button.disabled = false;
  }
});

$("#clearChatButton").addEventListener("click", () => {
  transcript.innerHTML = "";
});

$("#copyJsonButton").addEventListener("click", async () => {
  await navigator.clipboard.writeText(JSON.stringify(state.lastJson, null, 2));
});

$("#newSessionButton").addEventListener("click", () => {
  $("#sessionId").value = `patient-${Math.random().toString(16).slice(2, 8)}`;
  transcript.innerHTML = "";
});

for (const button of document.querySelectorAll(".tab-button")) {
  button.addEventListener("click", () => showPanel(button.dataset.panel));
}

$("#sampleChestPain").addEventListener("click", () => {
  showPanel("chatPanel");
  $("#chatMessage").value = "I am anxious about chest pain. Does Medicare Part B cover preventive screening?";
  $("#chatForm").requestSubmit();
});

$("#sampleMedicare").addEventListener("click", () => {
  showPanel("chatPanel");
  $("#chatMessage").value = "Does Medicare Part B cover preventive screening services?";
  $("#chatForm").requestSubmit();
});

$("#sampleReminder").addEventListener("click", () => {
  showPanel("workflowPanel");
  $("#reminderText").value = "remind me tomorrow to follow up about blood pressure";
});

checkHealth();
addMessage("agent", "Ready. Try the chest pain demo, Medicare screening demo, or send a patient question.");
