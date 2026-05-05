import { apiDelete, apiGet, apiPost, getStored, getToken, setStored } from "./api.js";
import { addApiErrorMessage, addMessage, autoResizeTextarea, renderAttachments, runAutonomousTask, sendMessage } from "./chat.js";
import { loadFilePreview, renderExplorer, renderSearchResults, setSelectedFile } from "./explorer.js";
import { refreshPlugins } from "./plugins.js";
import { ACCESS_KEY, els, MODEL_KEY, MODE_KEY, PLAN_KEY, scrollChatToBottom, state, TOKEN_KEY } from "./state.js";
import { refreshRollbacks, refreshRuns } from "./timeline.js";

const COLLAPSE_KEY_PREFIX = "codeyz_ui_collapsed_";
const SIDEBAR_WIDTH_KEY = "codeyz_ui_sidebar_width";
const EXPLORER_WIDTH_KEY = "codeyz_ui_explorer_width";
const SIDEBAR_MIN = 220;
const SIDEBAR_MAX = 480;
const EXPLORER_MIN = 260;
const EXPLORER_MAX = 560;
const MAIN_MIN = 520;

function collapseStorageKey(panelId) {
  return `${COLLAPSE_KEY_PREFIX}${panelId}`;
}

function applyCollapsedState(panel, collapsed) {
  panel.classList.toggle("collapsed", collapsed);
  const toggle = panel.querySelector("[data-collapse-toggle]");
  if (toggle) toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
}

function initCollapsibles() {
  const panels = Array.from(document.querySelectorAll("[data-collapsible][data-panel-id]"));
  for (const panel of panels) {
    const panelId = panel.getAttribute("data-panel-id");
    if (!panelId) continue;
    const saved = localStorage.getItem(collapseStorageKey(panelId));
    applyCollapsedState(panel, saved === "1");
    const toggle = panel.querySelector("[data-collapse-toggle]");
    if (!toggle) continue;
    toggle.addEventListener("click", () => {
      const collapsed = !panel.classList.contains("collapsed");
      applyCollapsedState(panel, collapsed);
      localStorage.setItem(collapseStorageKey(panelId), collapsed ? "1" : "0");
    });
  }
}

function clamp(value, minValue, maxValue) {
  return Math.max(minValue, Math.min(maxValue, value));
}

function setLayoutWidths(sidebarWidth, explorerWidth) {
  if (!els.layoutEl) return;
  const total = els.layoutEl.clientWidth || window.innerWidth;
  const maxSidebar = Math.min(SIDEBAR_MAX, total - EXPLORER_MIN - MAIN_MIN - 16);
  const maxExplorer = Math.min(EXPLORER_MAX, total - SIDEBAR_MIN - MAIN_MIN - 16);
  const nextSidebar = clamp(sidebarWidth, SIDEBAR_MIN, Math.max(SIDEBAR_MIN, maxSidebar));
  const nextExplorer = clamp(explorerWidth, EXPLORER_MIN, Math.max(EXPLORER_MIN, maxExplorer));

  document.documentElement.style.setProperty("--sidebar-w", `${nextSidebar}px`);
  document.documentElement.style.setProperty("--explorer-w", `${nextExplorer}px`);
}

function readLayoutWidths() {
  const sidebarRaw = Number(localStorage.getItem(SIDEBAR_WIDTH_KEY) || "");
  const explorerRaw = Number(localStorage.getItem(EXPLORER_WIDTH_KEY) || "");
  const sidebarWidth = Number.isFinite(sidebarRaw) && sidebarRaw > 0 ? sidebarRaw : 260;
  const explorerWidth = Number.isFinite(explorerRaw) && explorerRaw > 0 ? explorerRaw : 320;
  return { sidebarWidth, explorerWidth };
}

function initResizablePanels() {
  if (!els.layoutEl || !els.leftResizeHandleEl || !els.rightResizeHandleEl) return;

  const restored = readLayoutWidths();
  setLayoutWidths(restored.sidebarWidth, restored.explorerWidth);

  const onDrag = (type, event) => {
    const rect = els.layoutEl.getBoundingClientRect();
    const current = readLayoutWidths();
    if (type === "left") {
      const nextSidebar = event.clientX - rect.left;
      setLayoutWidths(nextSidebar, current.explorerWidth);
    } else {
      const nextExplorer = rect.right - event.clientX;
      setLayoutWidths(current.sidebarWidth, nextExplorer);
    }
    const sidebarPx = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--sidebar-w"), 10);
    const explorerPx = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--explorer-w"), 10);
    localStorage.setItem(SIDEBAR_WIDTH_KEY, String(sidebarPx));
    localStorage.setItem(EXPLORER_WIDTH_KEY, String(explorerPx));
  };

  const bindHandle = (handle, type) => {
    handle.addEventListener("mousedown", (downEvent) => {
      downEvent.preventDefault();
      els.layoutEl.classList.add("resizing");
      const move = (moveEvent) => onDrag(type, moveEvent);
      const up = () => {
        els.layoutEl.classList.remove("resizing");
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
      };
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
    });
  };

  bindHandle(els.leftResizeHandleEl, "left");
  bindHandle(els.rightResizeHandleEl, "right");

  window.addEventListener("resize", () => {
    const saved = readLayoutWidths();
    setLayoutWidths(saved.sidebarWidth, saved.explorerWidth);
  });
}


function renderPinnedList() {
  els.pinnedListEl.innerHTML = "";
  els.pinnedCountEl.textContent = `Pinned: ${state.pinnedFiles.length}`;
  els.contextPinnedEl.textContent = `Pinned: ${state.pinnedFiles.length}`;

  for (const file of state.pinnedFiles) {
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
      renderExplorer(onFileClick);
    });

    row.appendChild(name);
    row.appendChild(removeBtn);
    els.pinnedListEl.appendChild(row);
  }
}

async function refreshPinned() {
  const data = await apiGet("/context/pinned");
  state.pinnedFiles = data.pinned_files || [];
  renderPinnedList();
}

function renderSystemStatus(data) {
  const items = [
    ["Server", data.status === "ok"],
    ["OpenAI", data.openai === "ok"],
    ["Index", data.index === "built"],
    ["Plugins", Number(data.plugins || 0) > 0],
    ["Workspace", !!data.workspace],
  ];
  els.systemStatusEl.innerHTML = "";
  for (const [label, ok] of items) {
    const row = document.createElement("div");
    row.className = "status-row";
    row.textContent = `${ok ? "✔" : "✖"} ${label}`;
    els.systemStatusEl.appendChild(row);
  }
  els.uiVersionEl.textContent = `v${data.version || "unknown"}`;
}

function friendlyError(err) {
  const msg = String(err && err.message ? err.message : err);
  if (msg.includes("Server nicht erreichbar")) return msg;
  if (msg.includes("401") || msg.includes("Unauthorized")) return "Auth fehlgeschlagen. Lösung: gültiges Token speichern.";
  if (msg.includes("403")) return "Zugriff verweigert. Lösung: Access-Level oder Auth prüfen.";
  return `Fehler: ${msg}`;
}

function renderPre(el, value) {
  if (typeof value === "string") el.textContent = value || "-";
  else el.textContent = JSON.stringify(value, null, 2);
}

function onFileClick(rel) {
  setSelectedFile(rel);
  renderExplorer(onFileClick);
  void loadFilePreview(rel);
}

async function runSearch() {
  const q = (els.searchInputEl.value || "").trim();
  if (!q) {
    els.searchResultsEl.innerHTML = "";
    return;
  }
  try {
    const data = await apiGet(`/index/search?q=${encodeURIComponent(q)}`);
    renderSearchResults(data.results || [], async (path) => {
      setSelectedFile(path);
      renderExplorer(onFileClick);
      await loadFilePreview(path);
    });
  } catch (err) {
    addApiErrorMessage("Search-Fehler", err);
  }
}

async function pinSelectedFile() {
  if (!state.selectedFile) {
    addMessage("assistant", "Keine Datei ausgewählt.");
    return;
  }
  try {
    await apiPost("/context/pinned", { path: state.selectedFile });
    await refreshPinned();
    renderExplorer(onFileClick);
  } catch (err) {
    addApiErrorMessage("Pin fehlgeschlagen", err);
  }
}

export async function refreshPanels() {
  try {
    const [health, current, tree] = await Promise.all([
      apiGet("/health"),
      apiGet("/projects/current"),
      apiGet("/projects/tree"),
    ]);

    renderSystemStatus(health || {});
    state.currentProject = current.current || "";
    state.treeData = tree;

    renderPre(els.currentProjectEl, state.currentProject || "-");
    renderPre(els.explorerWorkspaceEl, state.currentProject || "-");
    els.contextProjectEl.textContent = `Projekt: ${state.currentProject || "-"}`;
    await refreshPinned();
    await refreshRuns();
    await refreshRollbacks();
    await refreshPlugins((text) => addMessage("assistant", text), () => els.accessSelect.value);
    renderExplorer(onFileClick);
  } catch (err) {
    const msg = friendlyError(err);
    [els.currentProjectEl, els.explorerWorkspaceEl].forEach((el) => {
      el.textContent = msg;
    });
    els.explorerEl.textContent = msg;
    if (els.systemStatusEl) els.systemStatusEl.textContent = msg;
  }
}

function bindEvents() {
  els.formEl.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = els.inputEl.value.trim();
    if (!message) return;
    addMessage("user", message);
    els.inputEl.value = "";
    autoResizeTextarea();
    await sendMessage(message, refreshPanels);
  });

  els.inputEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      els.formEl.requestSubmit();
    }
  });
  els.inputEl.addEventListener("input", autoResizeTextarea);

  els.attachBtn.addEventListener("click", () => els.fileInputEl.click());
  els.fileInputEl.addEventListener("change", () => {
    state.attachments = [...state.attachments, ...Array.from(els.fileInputEl.files || [])];
    els.fileInputEl.value = "";
    renderAttachments();
  });

  els.modelSelect.addEventListener("change", () => setStored(MODEL_KEY, els.modelSelect.value));
  els.modeSelect.addEventListener("change", () => setStored(MODE_KEY, els.modeSelect.value));
  els.accessSelect.addEventListener("change", () => setStored(ACCESS_KEY, els.accessSelect.value));
  els.planModeEl.addEventListener("change", () => setStored(PLAN_KEY, els.planModeEl.checked ? "1" : "0"));

  els.autoBtn.addEventListener("click", async () => {
    const task = els.inputEl.value.trim();
    if (!task) return addMessage("assistant", "Bitte zuerst eine Aufgabe im Eingabefeld eingeben.");
    addMessage("user", `[AUTO] ${task}`);
    await runAutonomousTask(task, refreshRuns, refreshRollbacks);
  });

  els.pinSelectedBtn.addEventListener("click", pinSelectedFile);
  els.previewPinBtn.addEventListener("click", pinSelectedFile);

  els.rollbackApplyBtn.addEventListener("click", async () => {
    if (!state.selectedRollbackId) {
      addMessage("assistant", "Kein Rollback ausgewählt.");
      return;
    }
    try {
      await apiPost(`/rollback/${encodeURIComponent(state.selectedRollbackId)}/apply`, {});
      addMessage("assistant", `Rollback angewendet: ${state.selectedRollbackId}`);
      await refreshRollbacks();
      await refreshRuns();
      await refreshPanels();
    } catch (err) {
      addApiErrorMessage("Rollback fehlgeschlagen", err);
    }
  });

  els.newChatBtn.addEventListener("click", () => {
    state.sessionId = null;
    els.messagesEl.innerHTML = "";
    els.messagesEl.scrollTop = 0;
    addMessage("assistant", "Neuer Chat gestartet.");
    scrollChatToBottom();
  });

  els.addProjectBtn.addEventListener("click", async () => {
    const path = prompt("Projektpfad hinzufügen:");
    if (!path) return;
    try {
      await apiPost("/projects", { path });
      await apiPost("/projects/current", { path });
      setSelectedFile("");
      renderExplorer(onFileClick);
      await refreshPanels();
    } catch (err) {
      addApiErrorMessage("Projekt konnte nicht gesetzt werden", err);
    }
  });

  els.saveTokenBtn.addEventListener("click", async () => {
    localStorage.setItem(TOKEN_KEY, els.tokenInput.value.trim());
    await refreshPanels();
  });
  els.clearTokenBtn.addEventListener("click", async () => {
    localStorage.removeItem(TOKEN_KEY);
    els.tokenInput.value = "";
    await refreshPanels();
  });

  els.filterEl.addEventListener("input", () => renderExplorer(onFileClick));
  els.searchInputEl.addEventListener("input", () => {
    void runSearch();
  });
  els.searchBuildBtn.addEventListener("click", async () => {
    try {
      await apiGet("/index/build");
      await runSearch();
      addMessage("assistant", "Index gebaut.");
    } catch (err) {
      addApiErrorMessage("Index-Fehler", err);
    }
  });

  els.toggleExplorerBtn.addEventListener("click", () => {
    const pane = document.getElementById("explorer-pane");
    pane.classList.toggle("hidden");
    els.toggleExplorerBtn.textContent = pane.classList.contains("hidden") ? "Einblenden" : "Ausblenden";
  });

  if (els.focusWorkflowBtn) {
    els.focusWorkflowBtn.addEventListener("click", () => applyFocusMode("workflow"));
  }
  if (els.focusCodeBtn) {
    els.focusCodeBtn.addEventListener("click", () => applyFocusMode("code"));
  }
  if (els.focusChatBtn) {
    els.focusChatBtn.addEventListener("click", () => applyFocusMode("chat"));
  }
  if (els.commandBackdropEl) {
    els.commandBackdropEl.addEventListener("click", closeCommandPalette);
  }
  if (els.commandInputEl) {
    els.commandInputEl.addEventListener("input", () => {
      if (commandInputDebounce) clearTimeout(commandInputDebounce);
      commandInputDebounce = setTimeout(() => {
        paletteSelectedIndex = 0;
        renderCommandPalette();
      }, 60);
    });
  }
  if (els.exportLayoutBtn) els.exportLayoutBtn.addEventListener("click", exportLayoutPreferences);
  if (els.importLayoutBtn) els.importLayoutBtn.addEventListener("click", importLayoutPreferences);
  if (els.messagesEl) {
    els.messagesEl.addEventListener("scroll", () => {
      patchPreferences({ session: { scrollTop: els.messagesEl.scrollTop } });
    });
  }
  bindSummaryDetails();
}

export function initUi() {
  migrateLegacyPreferencesIfNeeded();
  els.tokenInput.value = getToken();
  els.modelSelect.value = getStored(MODEL_KEY, "gpt-5.4-mini");
  els.modeSelect.value = getStored(MODE_KEY, "Chat");
  els.accessSelect.value = getStored(ACCESS_KEY, "Nur lesen");
  els.planModeEl.checked = getStored(PLAN_KEY, "0") === "1";

  setSelectedFile("");
  autoResizeTextarea();
  renderAttachments();
  initCollapsibles();
  initResizablePanels();
  bindEvents();
  bindKeyboardShortcuts();
  applyFocusMode(readPreferences().mode || "workflow", false);
  applySummaryDetailExpansion();
  const prefs = readPreferences();
  if (els.messagesEl && prefs.session?.scrollTop) {
    els.messagesEl.scrollTop = Number(prefs.session.scrollTop) || 0;
  }
  if (prefs.session?.lastRunId) patchPreferences({ session: { lastRunId: prefs.session.lastRunId } });
  addMessage("assistant", "CodeYZ UI bereit.");
  if (prefs.session?.lastRunId) showToast("Session restored");
  if (!prefs.session?.lastRunId) scrollChatToBottom();
  void refreshPanels();
}
