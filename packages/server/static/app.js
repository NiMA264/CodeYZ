const TOKEN_KEY = "codeyz_local_token";
let sessionId = null;

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const statusEl = document.getElementById("status");
const newChatBtn = document.getElementById("new-chat");
const sendBtn = document.getElementById("send-btn");

const tokenInput = document.getElementById("token-input");
const saveTokenBtn = document.getElementById("save-token");
const clearTokenBtn = document.getElementById("clear-token");

const projectsEl = document.getElementById("projects");
const pluginsEl = document.getElementById("plugins");
const automationsEl = document.getElementById("automations");
const gitStatusEl = document.getElementById("git-status");
const gitDiffEl = document.getElementById("git-diff");

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function buildHeaders() {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["x-api-key"] = token;
  return headers;
}

async function apiGet(url) {
  const resp = await fetch(url, { headers: buildHeaders() });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`HTTP ${resp.status}: ${text}`);
  }
  return resp.json();
}

function addMessage(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.textContent = text;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setLoading(isLoading) {
  statusEl.hidden = !isLoading;
  statusEl.textContent = isLoading ? "Lade..." : "";
  sendBtn.disabled = isLoading;
  inputEl.disabled = isLoading;
}

function renderPre(el, value) {
  if (typeof value === "string") {
    el.textContent = value || "-";
    return;
  }
  el.textContent = JSON.stringify(value, null, 2);
}

async function refreshPanels() {
  try {
    const [projects, plugins, automations, gitStatus, gitDiff] = await Promise.all([
      apiGet("/projects"),
      apiGet("/plugins"),
      apiGet("/automations"),
      apiGet("/git/status"),
      apiGet("/git/diff"),
    ]);

    renderPre(projectsEl, projects.projects || projects);
    renderPre(pluginsEl, plugins.plugins || plugins);
    renderPre(automationsEl, automations.automations || automations);
    renderPre(gitStatusEl, gitStatus.status || gitStatus);
    renderPre(gitDiffEl, gitDiff.diff || gitDiff);
  } catch (err) {
    const msg = `Fehler: ${err.message}`;
    projectsEl.textContent = msg;
    pluginsEl.textContent = msg;
    automationsEl.textContent = msg;
    gitStatusEl.textContent = msg;
    gitDiffEl.textContent = msg;
  }
}

async function sendMessage(message) {
  setLoading(true);
  try {
    const resp = await fetch("/chat", {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify({ message, session_id: sessionId || null })
    });

    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${text}`);
    }

    const data = await resp.json();
    sessionId = data.session_id || sessionId;
    addMessage("assistant", data.response || "Keine Antwort.");
    await refreshPanels();
  } catch (err) {
    addMessage("assistant", `Fehler: ${err.message}`);
  } finally {
    setLoading(false);
  }
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = inputEl.value.trim();
  if (!message) return;

  addMessage("user", message);
  inputEl.value = "";
  await sendMessage(message);
});

newChatBtn.addEventListener("click", () => {
  sessionId = null;
  messagesEl.innerHTML = "";
  addMessage("assistant", "Neuer Chat gestartet.");
});

saveTokenBtn.addEventListener("click", async () => {
  localStorage.setItem(TOKEN_KEY, tokenInput.value.trim());
  await refreshPanels();
});

clearTokenBtn.addEventListener("click", async () => {
  localStorage.removeItem(TOKEN_KEY);
  tokenInput.value = "";
  await refreshPanels();
});

tokenInput.value = getToken();
addMessage("assistant", "CodeYZ UI bereit.");
refreshPanels();
