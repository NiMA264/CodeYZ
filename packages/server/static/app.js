const TOKEN_KEY = "codeyz_local_token";
const MODEL_KEY = "codeyz_model";
const MODE_KEY = "codeyz_mode";
const ACCESS_KEY = "codeyz_access";
const PLAN_KEY = "codeyz_plan_mode";

let sessionId = null;
let selectedFile = "";
let currentProject = "";
let treeData = null;
let attachments = [];
let pinnedFiles = [];
let selectedRollbackId = "";
const collapsedDirs = new Set();

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const statusEl = document.getElementById("status");
const attachmentsEl = document.getElementById("attachments");

const newChatBtn = document.getElementById("new-chat");
const addProjectBtn = document.getElementById("add-project");
const sendBtn = document.getElementById("send-btn");
const autoBtn = document.getElementById("auto-btn");
const toggleExplorerBtn = document.getElementById("toggle-explorer");
const pinSelectedBtn = document.getElementById("pin-selected");
const previewPinBtn = document.getElementById("preview-pin");

const runsListEl = document.getElementById("runs-list");
const runReplayContentEl = document.getElementById("run-replay-content");
const tdSearchEl = document.getElementById("td-search");
const tdFilesEl = document.getElementById("td-files");
const tdTestsEl = document.getElementById("td-tests");
const tdPluginsEl = document.getElementById("td-plugins");
const tdReasoningEl = document.getElementById("td-reasoning");
const rollbackListEl = document.getElementById("rollback-list");
const rollbackDetailEl = document.getElementById("rollback-detail");
const rollbackApplyBtn = document.getElementById("rollback-apply");

const modelSelect = document.getElementById("model-select");
const modeSelect = document.getElementById("mode-select");
const accessSelect = document.getElementById("access-select");
const planModeEl = document.getElementById("plan-mode");
const multiAgentEl = document.getElementById("multi-agent");
const budgetInputEl = document.getElementById("budget-input");
const contextCostEl = document.getElementById("context-cost");
const rmPlannerEl = document.getElementById("rm-planner");
const rmCoderEl = document.getElementById("rm-coder");
const rmTesterEl = document.getElementById("rm-tester");
const rmReviewerEl = document.getElementById("rm-reviewer");
const rmFixerEl = document.getElementById("rm-fixer");
const attachBtn = document.getElementById("attach-btn");
const fileInputEl = document.getElementById("file-input");
const contextProjectEl = document.getElementById("context-project");
const contextSelectedFileEl = document.getElementById("context-selected-file");
const contextPinnedEl = document.getElementById("context-pinned");

const tokenInput = document.getElementById("token-input");
const saveTokenBtn = document.getElementById("save-token");
const clearTokenBtn = document.getElementById("clear-token");

const currentProjectEl = document.getElementById("current-project");
const explorerWorkspaceEl = document.getElementById("explorer-workspace");
const explorerEl = document.getElementById("explorer");
const filterEl = document.getElementById("file-filter");
const previewEl = document.getElementById("file-preview");
const selectedFileEl = document.getElementById("selected-file");
const pinnedCountEl = document.getElementById("pinned-count");
const pinnedListEl = document.getElementById("pinned-list");
const pluginsListEl = document.getElementById("plugins-list");
const searchInputEl = document.getElementById("search-input");
const searchBuildBtn = document.getElementById("search-build");
const searchResultsEl = document.getElementById("search-results");
const systemStatusEl = document.getElementById("system-status");
const uiVersionEl = document.getElementById("ui-version");

function getToken() { return localStorage.getItem(TOKEN_KEY) || ""; }
function setStored(k, v) { localStorage.setItem(k, v); }
function getStored(k, d) { return localStorage.getItem(k) || d; }

function getComposerState() {
  return {
    selectedModel: modelSelect.value,
    selectedMode: modeSelect.value,
    accessLevel: accessSelect.value,
    planMode: planModeEl.checked,
    maxCostUsd: budgetInputEl.value ? Number(budgetInputEl.value) : null,
    roleModels: {
      planner: rmPlannerEl.value,
      coder: rmCoderEl.value,
      tester: rmTesterEl.value,
      reviewer: rmReviewerEl.value,
      fixer: rmFixerEl.value,
    },
    attachments: attachments.map((f) => ({ name: f.name, size: f.size, type: f.type || "unknown" })),
  };
}

function buildHeaders() {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["x-api-key"] = token;
  return headers;
}

async function apiGet(url) {
  let resp;
  try {
    resp = await fetch(url, { headers: buildHeaders() });
  } catch {
    throw new Error("Server nicht erreichbar. Lösung: 'codeyz server' starten und URL prüfen.");
  }
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
  return resp.json();
}

async function apiPost(url, body) {
  const resp = await fetch(url, { method: "POST", headers: buildHeaders(), body: JSON.stringify(body) });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
  return resp.json();
}

async function apiDelete(url) {
  const resp = await fetch(url, { method: "DELETE", headers: buildHeaders() });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
  return resp.json();
}

function autoResizeTextarea() {
  inputEl.style.height = "auto";
  inputEl.style.height = `${Math.min(inputEl.scrollHeight, 180)}px`;
}

function renderAttachments() {
  attachmentsEl.innerHTML = "";
  for (const file of attachments) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "attachment-chip";
    chip.textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;
    chip.addEventListener("click", () => {
      attachments = attachments.filter((f) => f !== file);
      renderAttachments();
    });
    attachmentsEl.appendChild(chip);
  }
}

function renderPinnedList() {
  pinnedListEl.innerHTML = "";
  pinnedCountEl.textContent = `Pinned: ${pinnedFiles.length}`;
  contextPinnedEl.textContent = `Pinned: ${pinnedFiles.length}`;

  for (const file of pinnedFiles) {
    const row = document.createElement("div");
    row.className = "pinned-row";

    const name = document.createElement("span");
    name.textContent = file;

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "Entfernen";
    removeBtn.addEventListener("click", async () => {
      await apiDelete(`/context/pinned?path=${encodeURIComponent(file)}`);
      await refreshPinned();
      renderExplorer();
    });

    row.appendChild(name);
    row.appendChild(removeBtn);
    pinnedListEl.appendChild(row);
  }
}

function setDecisionBadge(el, enabled) {
  if (!el) return;
  el.textContent = enabled ? "enabled" : "disabled";
  el.classList.toggle("enabled", !!enabled);
  el.classList.toggle("disabled", !enabled);
}

function renderToolDecision(events) {
  const event = (events || []).find((e) => e.event_type === "tool_decision");
  const data = event && event.data ? event.data : {};
  setDecisionBadge(tdSearchEl, !!data.use_search);
  setDecisionBadge(tdFilesEl, !!data.use_files);
  setDecisionBadge(tdTestsEl, !!data.use_tests);
  setDecisionBadge(tdPluginsEl, !!data.use_plugins);
  tdReasoningEl.textContent = data.reasoning || "Keine Tool-Entscheidung für diesen Run.";
}

function renderRuns(runs) {
  runsListEl.innerHTML = "";
  for (const run of runs.slice(0, 12)) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "run-item";
    btn.textContent = `${run.status} • ${run.task.slice(0, 40)}`;
    btn.addEventListener("click", async () => {
      const detail = await apiGet(`/task/runs/${encodeURIComponent(run.run_id)}`);
      renderToolDecision(detail.events || []);
      const lines = [];
      lines.push(`Run: ${detail.run_id}`);
      lines.push(`Task: ${detail.task}`);
      lines.push(`Status: ${detail.status}`);
      lines.push(`Summary: ${detail.summary || "-"}`);
      if (detail.estimated_total_cost_usd !== undefined) {
        lines.push(`Estimated total cost: $${detail.estimated_total_cost_usd}`);
      }
      lines.push("Events:");
      for (const event of detail.events || []) {
        lines.push(`- [${event.event_type}] (${event.agent_role || "-"}) ${event.title}`);
        if (event.data) lines.push(`  ${JSON.stringify(event.data, null, 2)}`);
      }
      runReplayContentEl.textContent = lines.join("\n");
    });
    runsListEl.appendChild(btn);
  }
}

function renderRollbacks(items) {
  rollbackListEl.innerHTML = "";
  for (const item of items.slice(0, 20)) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "run-item";
    btn.textContent = `${item.file_path} • ${item.created_at}`;
    btn.addEventListener("click", async () => {
      const detail = await apiGet(`/rollback/${encodeURIComponent(item.rollback_id)}`);
      selectedRollbackId = detail.rollback_id;
      rollbackDetailEl.textContent = [
        `Rollback: ${detail.rollback_id}`,
        `File: ${detail.file_path}`,
        `Time: ${detail.created_at}`,
        "Diff:",
        detail.diff || "-",
      ].join("\n");
    });
    rollbackListEl.appendChild(btn);
  }
}

async function refreshRollbacks() {
  const data = await apiGet("/rollback");
  renderRollbacks(data.rollbacks || []);
}

async function refreshRuns() {
  const data = await apiGet("/task/runs");
  renderRuns(data.runs || []);
}

function renderPlugins(items) {
  pluginsListEl.innerHTML = "";
  for (const item of items || []) {
    const row = document.createElement("div");
    row.className = "pinned-row";

    const info = document.createElement("span");
    const perms = Array.isArray(item.permissions) ? item.permissions.join(", ") : "-";
    info.textContent = `${item.name} (${item.enabled ? "on" : "off"}) [${perms}]`;

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.textContent = item.enabled ? "Disable" : "Enable";
    toggle.addEventListener("click", async () => {
      await apiPost(item.enabled ? "/plugins/disable" : "/plugins/enable", { name: item.name });
      await refreshPlugins();
    });

    const runBtn = document.createElement("button");
    runBtn.type = "button";
    runBtn.textContent = "Run";
    runBtn.addEventListener("click", async () => {
      try {
        const data = await apiPost("/plugins/run", { name: item.name, input_data: { name: "ui" }, access_level: accessSelect.value });
        addMessage("assistant", `Plugin ${item.name}: ${JSON.stringify(data.result)}`);
      } catch (err) {
        addMessage("assistant", `Plugin-Fehler: ${err.message}`);
      }
    });

    row.appendChild(info);
    row.appendChild(toggle);
    row.appendChild(runBtn);
    pluginsListEl.appendChild(row);
  }
}

async function refreshPlugins() {
  const data = await apiGet("/plugins");
  renderPlugins(data.plugins || []);
}

function renderSearchResults(results) {
  searchResultsEl.innerHTML = "";
  for (const item of results || []) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "run-item";
    const preview = String(item.content || "").slice(0, 90).replace(/\s+/g, " ");
    btn.textContent = `${item.path} (${item.score || 0}) :: ${preview}`;
    btn.addEventListener("click", async () => {
      setSelectedFile(item.path || "");
      await loadFilePreview(item.path || "");
    });
    searchResultsEl.appendChild(btn);
  }
}

async function runSearch() {
  const q = (searchInputEl.value || "").trim();
  if (!q) {
    searchResultsEl.innerHTML = "";
    return;
  }
  try {
    const data = await apiGet(`/index/search?q=${encodeURIComponent(q)}`);
    renderSearchResults(data.results || []);
  } catch (err) {
    addMessage("assistant", `Search-Fehler: ${err.message}`);
  }
}

async function refreshPinned() {
  const data = await apiGet("/context/pinned");
  pinnedFiles = data.pinned_files || [];
  renderPinnedList();
}

function addMessage(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.textContent = text;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function friendlyError(err) {
  const msg = String(err && err.message ? err.message : err);
  if (msg.includes("401") || msg.includes("Unauthorized")) {
    return "Auth fehlgeschlagen. Lösung: gültiges Token in 'Token' speichern.";
  }
  if (msg.includes("403")) {
    return "Zugriff verweigert. Lösung: Access-Level prüfen oder lokale Auth-Konfiguration prüfen.";
  }
  if (msg.includes("Budget")) {
    return "Budget überschritten. Lösung: Budget erhöhen oder kleinere Aufgabe senden.";
  }
  if (msg.includes("Plugin")) {
    return "Plugin-Fehler. Lösung: Plugin im Panel prüfen, ggf. deaktivieren/aktivieren.";
  }
  if (msg.includes("Server nicht erreichbar")) {
    return msg;
  }
  return `Fehler: ${msg}`;
}

function renderSystemStatus(data) {
  const items = [
    [`Server`, data.status === "ok"],
    [`OpenAI`, data.openai === "ok"],
    [`Index`, data.index === "built"],
    [`Plugins`, Number(data.plugins || 0) > 0],
    [`Workspace`, !!data.workspace],
  ];
  systemStatusEl.innerHTML = "";
  for (const [label, ok] of items) {
    const row = document.createElement("div");
    row.className = "status-row";
    row.textContent = `${ok ? "✔" : "✖"} ${label}`;
    systemStatusEl.appendChild(row);
  }
  uiVersionEl.textContent = `v${data.version || "unknown"}`;
}

function setLoading(isLoading) {
  statusEl.hidden = !isLoading;
  statusEl.textContent = isLoading ? "Lade..." : "";
  sendBtn.disabled = isLoading;
  autoBtn.disabled = isLoading;
  inputEl.disabled = isLoading;
}

function renderPre(el, value) {
  if (typeof value === "string") el.textContent = value || "-";
  else el.textContent = JSON.stringify(value, null, 2);
}

function toRelative(absolutePath) {
  if (!absolutePath || !currentProject) return absolutePath || "";
  const base = currentProject.toLowerCase();
  const path = absolutePath.toLowerCase();
  if (path.startsWith(base)) {
    const rel = absolutePath.slice(currentProject.length).replace(/^[/\\]+/, "");
    return rel || absolutePath;
  }
  return absolutePath;
}

function setSelectedFile(path) {
  selectedFile = path || "";
  selectedFileEl.textContent = selectedFile || "-";
  contextSelectedFileEl.textContent = `Selected: ${selectedFile || "-"}`;
  renderExplorer();
}

function matchesFilter(node, filter) {
  if (!filter) return true;
  const name = (node.name || "").toLowerCase();
  if (name.includes(filter)) return true;
  return (node.children || []).some((c) => matchesFilter(c, filter));
}

function renderNode(node, level, filter) {
  if (!matchesFilter(node, filter)) return;

  const row = document.createElement("div");
  row.className = "tree-item";
  row.style.paddingLeft = `${level * 12}px`;

  const isDir = node.type === "directory";
  const rel = toRelative(node.path);
  const collapsed = isDir && collapsedDirs.has(node.path);
  const isPinned = pinnedFiles.includes(rel);

  const label = document.createElement("span");
  label.className = isDir ? "dir" : "file";
  if (!isDir && rel === selectedFile) label.classList.add("active");
  if (!isDir && isPinned) label.classList.add("pinned");
  label.textContent = `${isDir ? (collapsed ? "▸" : "▾") : (isPinned ? "📌" : "•")} ${node.name}`;
  row.appendChild(label);

  if (isDir) {
    label.addEventListener("click", () => {
      if (collapsedDirs.has(node.path)) collapsedDirs.delete(node.path);
      else collapsedDirs.add(node.path);
      renderExplorer();
    });
  } else {
    label.addEventListener("click", async () => {
      setSelectedFile(rel);
      await loadFilePreview(rel);
    });
  }

  explorerEl.appendChild(row);

  if (isDir && !collapsed) {
    for (const child of (node.children || [])) renderNode(child, level + 1, filter);
  }
}

function renderExplorer() {
  explorerEl.innerHTML = "";
  if (!treeData) { explorerEl.textContent = "-"; return; }
  const filter = filterEl.value.trim().toLowerCase();
  renderNode(treeData, 0, filter);
}

async function loadFilePreview(relPath) {
  try {
    const data = await apiGet(`/files/read?path=${encodeURIComponent(relPath)}`);
    renderPre(previewEl, data.content || "");
  } catch {
    renderPre(previewEl, "Vorschau nicht verfügbar.");
  }
}

async function refreshPanels() {
  try {
    const [health, current, tree] = await Promise.all([
      apiGet("/health"),
      apiGet("/projects/current"),
      apiGet("/projects/tree"),
    ]);

    renderSystemStatus(health || {});
    currentProject = current.current || "";
    treeData = tree;

    renderPre(currentProjectEl, currentProject || "-");
    renderPre(explorerWorkspaceEl, currentProject || "-");
    contextProjectEl.textContent = `Projekt: ${currentProject || "-"}`;
    await refreshPinned();
    await refreshRuns();
    await refreshRollbacks();
    await refreshPlugins();
    renderExplorer();
  } catch (err) {
    const msg = friendlyError(err);
    [currentProjectEl, explorerWorkspaceEl].forEach((el) => { el.textContent = msg; });
    explorerEl.textContent = msg;
    if (systemStatusEl) systemStatusEl.textContent = msg;
  }
}

async function sendMessage(message) {
  setLoading(true);
  try {
    const state = getComposerState();
    const data = await apiPost("/chat", {
      message,
      session_id: sessionId || null,
      selected_file: selectedFile || null,
      model: state.selectedModel,
      mode: state.selectedMode,
      access_level: state.accessLevel,
      plan_mode: state.planMode,
      attachments_metadata: state.attachments,
    });
    sessionId = data.session_id || sessionId;
    addMessage("assistant", data.response || "Keine Antwort.");
    await refreshPanels();
  } catch (err) {
    addMessage("assistant", friendlyError(err));
  } finally { setLoading(false); }
}

async function runAutonomousTask(task) {
  setLoading(true);
  addMessage("assistant", "Autonomous task gestartet...");
  try {
    const state = getComposerState();
    const roleModels = state.roleModels;
    const payload = {
      task,
      model: state.selectedModel,
      access_level: state.accessLevel,
      multi_agent: !!multiAgentEl.checked,
      max_cost_usd: state.maxCostUsd,
      role_models: roleModels,
    };
    const data = await apiPost("/task/auto", payload);
    contextCostEl.textContent = `Estimated: $${(data.estimated_total_cost_usd || 0).toFixed(6)}`;
    addMessage("assistant", data.ok ? `Run abgeschlossen (run_id=${data.run_id})` : `Run fehlgeschlagen (run_id=${data.run_id}): ${data.error || "unknown"}`);
    await refreshRuns();
    await refreshRollbacks();
  } catch (err) {
    addMessage("assistant", friendlyError(err));
  } finally { setLoading(false); }
}

async function pinSelectedFile() {
  if (!selectedFile) {
    addMessage("assistant", "Keine Datei ausgewählt.");
    return;
  }
  try {
    await apiPost("/context/pinned", { path: selectedFile });
    await refreshPinned();
    renderExplorer();
  } catch (err) {
    addMessage("assistant", `Pin fehlgeschlagen: ${friendlyError(err)}`);
  }
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = inputEl.value.trim();
  if (!message) return;
  addMessage("user", message);
  inputEl.value = "";
  autoResizeTextarea();
  await sendMessage(message);
});

inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    formEl.requestSubmit();
  }
});
inputEl.addEventListener("input", autoResizeTextarea);

attachBtn.addEventListener("click", () => fileInputEl.click());
fileInputEl.addEventListener("change", () => {
  attachments = [...attachments, ...Array.from(fileInputEl.files || [])];
  fileInputEl.value = "";
  renderAttachments();
});

modelSelect.addEventListener("change", () => setStored(MODEL_KEY, modelSelect.value));
modeSelect.addEventListener("change", () => setStored(MODE_KEY, modeSelect.value));
accessSelect.addEventListener("change", () => setStored(ACCESS_KEY, accessSelect.value));
planModeEl.addEventListener("change", () => setStored(PLAN_KEY, planModeEl.checked ? "1" : "0"));

autoBtn.addEventListener("click", async () => {
  const task = inputEl.value.trim();
  if (!task) return addMessage("assistant", "Bitte zuerst eine Aufgabe im Eingabefeld eingeben.");
  addMessage("user", `[AUTO] ${task}`);
  await runAutonomousTask(task);
});

pinSelectedBtn.addEventListener("click", pinSelectedFile);
previewPinBtn.addEventListener("click", pinSelectedFile);

rollbackApplyBtn.addEventListener("click", async () => {
  if (!selectedRollbackId) {
    addMessage("assistant", "Kein Rollback ausgewählt.");
    return;
  }
  try {
    await apiPost(`/rollback/${encodeURIComponent(selectedRollbackId)}/apply`, {});
    addMessage("assistant", `Rollback angewendet: ${selectedRollbackId}`);
    await refreshRollbacks();
    await refreshRuns();
    await refreshPanels();
  } catch (err) {
    addMessage("assistant", `Rollback fehlgeschlagen: ${friendlyError(err)}`);
  }
});

newChatBtn.addEventListener("click", () => {
  sessionId = null;
  messagesEl.innerHTML = "";
  addMessage("assistant", "Neuer Chat gestartet.");
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
    addMessage("assistant", `Projekt konnte nicht gesetzt werden: ${friendlyError(err)}`);
  }
});

saveTokenBtn.addEventListener("click", async () => { localStorage.setItem(TOKEN_KEY, tokenInput.value.trim()); await refreshPanels(); });
clearTokenBtn.addEventListener("click", async () => { localStorage.removeItem(TOKEN_KEY); tokenInput.value = ""; await refreshPanels(); });

filterEl.addEventListener("input", () => renderExplorer());
searchInputEl.addEventListener("input", () => { void runSearch(); });
searchBuildBtn.addEventListener("click", async () => {
  try {
    await apiGet("/index/build");
    await runSearch();
    addMessage("assistant", "Index gebaut.");
  } catch (err) {
    addMessage("assistant", `Index-Fehler: ${friendlyError(err)}`);
  }
});

toggleExplorerBtn.addEventListener("click", () => {
  const pane = document.getElementById("explorer-pane");
  pane.classList.toggle("hidden");
  toggleExplorerBtn.textContent = pane.classList.contains("hidden") ? "Einblenden" : "Ausblenden";
});

tokenInput.value = getToken();
modelSelect.value = getStored(MODEL_KEY, "gpt-5.4-mini");
modeSelect.value = getStored(MODE_KEY, "Chat");
accessSelect.value = getStored(ACCESS_KEY, "Nur lesen");
planModeEl.checked = getStored(PLAN_KEY, "0") === "1";

setSelectedFile("");
autoResizeTextarea();
renderAttachments();
addMessage("assistant", "CodeYZ UI bereit.");
refreshPanels();

