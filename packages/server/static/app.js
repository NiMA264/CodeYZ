const TOKEN_KEY = "codeyz_local_token";
let sessionId = null;
let selectedFile = "";

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const statusEl = document.getElementById("status");
const newChatBtn = document.getElementById("new-chat");
const addProjectBtn = document.getElementById("add-project");
const sendBtn = document.getElementById("send-btn");
const autoBtn = document.getElementById("auto-btn");

const tokenInput = document.getElementById("token-input");
const saveTokenBtn = document.getElementById("save-token");
const clearTokenBtn = document.getElementById("clear-token");

const currentProjectEl = document.getElementById("current-project");
const explorerEl = document.getElementById("explorer");
const selectedFileEl = document.getElementById("selected-file");
const workspaceSummaryEl = document.getElementById("workspace-summary");
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

async function apiPost(url, body) {
  const resp = await fetch(url, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(body),
  });
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
  autoBtn.disabled = isLoading;
  inputEl.disabled = isLoading;
}

function renderPre(el, value) {
  if (typeof value === "string") {
    el.textContent = value || "-";
    return;
  }
  el.textContent = JSON.stringify(value, null, 2);
}

function setSelectedFile(path) {
  selectedFile = path || "";
  selectedFileEl.textContent = selectedFile || "-";
}

function renderTreeNode(node, level = 0) {
  const item = document.createElement("div");
  item.className = "tree-item";
  item.style.paddingLeft = `${level * 12}px`;

  const label = document.createElement("span");
  label.textContent = `${node.type === "directory" ? "▸" : "•"} ${node.name}`;
  label.className = node.type === "file" ? "file" : "dir";
  item.appendChild(label);

  if (node.type === "file") {
    label.addEventListener("click", () => setSelectedFile(node.path));
  }

  explorerEl.appendChild(item);

  if (node.children && node.children.length) {
    for (const child of node.children) {
      renderTreeNode(child, level + 1);
    }
  }
}

function renderExplorer(tree) {
  explorerEl.innerHTML = "";
  if (!tree || !tree.children) {
    explorerEl.textContent = "-";
    return;
  }
  renderTreeNode(tree, 0);
}

async function refreshPanels() {
  try {
    const [workspace, projects, currentProject, tree, plugins, automations, gitStatus, gitDiff] = await Promise.all([
      apiGet("/workspace/summary"),
      apiGet("/projects"),
      apiGet("/projects/current"),
      apiGet("/projects/tree"),
      apiGet("/plugins"),
      apiGet("/automations"),
      apiGet("/git/status"),
      apiGet("/git/diff"),
    ]);

    renderPre(workspaceSummaryEl, workspace.summary || workspace);
    renderPre(projectsEl, projects.projects || projects);
    renderPre(currentProjectEl, currentProject.current || currentProject);
    renderExplorer(tree);
    renderPre(pluginsEl, plugins.plugins || plugins);
    renderPre(automationsEl, automations.automations || automations);
    renderPre(gitStatusEl, gitStatus.status || gitStatus);
    renderPre(gitDiffEl, gitDiff.diff || gitDiff);
  } catch (err) {
    const msg = `Fehler: ${err.message}`;
    workspaceSummaryEl.textContent = msg;
    projectsEl.textContent = msg;
    currentProjectEl.textContent = msg;
    explorerEl.textContent = msg;
    pluginsEl.textContent = msg;
    automationsEl.textContent = msg;
    gitStatusEl.textContent = msg;
    gitDiffEl.textContent = msg;
  }
}

async function sendMessage(message) {
  setLoading(true);
  try {
    const data = await apiPost("/chat", {
      message,
      session_id: sessionId || null,
      selected_file: selectedFile || null,
    });
    sessionId = data.session_id || sessionId;
    addMessage("assistant", data.response || "Keine Antwort.");
    await refreshPanels();
  } catch (err) {
    addMessage("assistant", `Fehler: ${err.message}`);
  } finally {
    setLoading(false);
  }
}

async function runAutonomousTask(task) {
  setLoading(true);
  addMessage("assistant", "Autonomous task gestartet...");
  try {
    const data = await apiPost("/task/auto", { task });
    const iterations = data.iterations || [];

    for (const step of iterations) {
      const lines = [];
      lines.push(`Iteration ${step.iteration}: ${step.status || ""}`);
      if (step.plan) lines.push(`Plan: ${step.plan}`);

      const patches = step.patches || [];
      for (const p of patches) {
        if (p.file) lines.push(`File: ${p.file}`);
        if (p.archive) lines.push(`Diff saved: ${p.archive}`);
        if (p.diff) lines.push(`Diff:\n${p.diff}`);
        if (p.error) lines.push(`Patch error: ${p.error}`);
      }

      if (step.build && step.build.output) lines.push(`Build:\n${step.build.output}`);
      if (step.tests && step.tests.output) lines.push(`Tests:\n${step.tests.output}`);
      if (step.error_summary) lines.push(`Errors:\n${step.error_summary}`);

      addMessage("assistant", lines.join("\n\n"));
    }

    if (!data.ok && data.error) {
      addMessage("assistant", `Autonomous task beendet mit Fehler: ${data.error}`);
    } else {
      addMessage("assistant", "Autonomous task abgeschlossen.");
    }

    await refreshPanels();
  } catch (err) {
    addMessage("assistant", `Autonomous task Fehler: ${err.message}`);
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

autoBtn.addEventListener("click", async () => {
  const task = inputEl.value.trim();
  if (!task) {
    addMessage("assistant", "Bitte zuerst eine Aufgabe im Input eingeben.");
    return;
  }
  addMessage("user", `[AUTO] ${task}`);
  await runAutonomousTask(task);
});

addProjectBtn.addEventListener("click", async () => {
  const path = prompt("Projektpfad hinzufügen:");
  if (!path) return;

  try {
    await apiPost("/projects", { path });
    await apiPost("/projects/current", { path });
    setSelectedFile("");
    await refreshPanels();
  } catch (err) {
    addMessage("assistant", `Projekt konnte nicht gesetzt werden: ${err.message}`);
  }
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
setSelectedFile("");
addMessage("assistant", "CodeYZ UI bereit.");
refreshPanels();
