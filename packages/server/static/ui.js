import { apiDelete, apiGet, apiPost, getStored, getToken, setStored } from "./api.js";
import { addApiErrorMessage, addMessage, autoResizeTextarea, renderAttachments, runAutonomousTask, sendMessage } from "./chat.js";
import { loadFilePreview, renderExplorer, renderSearchResults, setSelectedFile } from "./explorer.js";
import { refreshPlugins } from "./plugins.js";
import { ACCESS_KEY, els, MODEL_KEY, MODE_KEY, PLAN_KEY, PROFILE_KEY, scrollChatToBottom, state, TOKEN_KEY } from "./state.js";
import { refreshRollbacks, refreshRuns } from "./timeline.js";

const COLLAPSE_KEY_PREFIX = "codeyz_ui_collapsed_";
const UI_MODE_KEY = "codeyz_ui_mode";
const UI_PREFS_KEY = "codeyz_ui_preferences";
const SIDEBAR_WIDTH_KEY = "codeyz_ui_sidebar_width";
const EXPLORER_WIDTH_KEY = "codeyz_ui_explorer_width";
const COMMAND_HISTORY_KEY = "codeyz_ui_command_history";
const LAST_RUN_KEY = "codeyz_ui_last_run_id";
const SCROLL_KEY = "codeyz_ui_scroll_top";
const SIDEBAR_MIN = 220;
const SIDEBAR_MAX = 480;
const EXPLORER_MIN = 260;
const EXPLORER_MAX = 560;
const MAIN_MIN = 520;
const SNAP_THRESHOLD = 12;
const SIDEBAR_SNAP_POINTS = [240, 320];
const EXPLORER_SNAP_POINTS = [300, 420];
const FOCUS_MODES = ["workflow", "code", "chat"];
const collapsiblePanels = new Map();
const MODE_PANELS = ["sidebar", "workflow", "settings", "explorer", "timeline", "plugins", "tool_decision"];
const MODE_DEFAULTS = {
  workflow: {
    sidebarWidth: 260,
    explorerWidth: 300,
    panels: { sidebar: false, workflow: false, settings: true, explorer: true, timeline: false, plugins: true, tool_decision: false },
  },
  code: {
    sidebarWidth: 320,
    explorerWidth: 420,
    panels: { sidebar: false, workflow: true, settings: false, explorer: false, timeline: true, plugins: true, tool_decision: true },
  },
  chat: {
    sidebarWidth: 220,
    explorerWidth: 260,
    panels: { sidebar: true, workflow: true, settings: false, explorer: true, timeline: true, plugins: true, tool_decision: true },
  },
};
let currentFocusMode = null;
let paletteSelectedIndex = 0;
let paletteWasFocused = null;
let commandActions = [];
let filteredCommandActions = [];
let toastTimer = null;
let paletteCloseTimer = null;
let shortcutCloseTimer = null;
let shortcutWasFocused = null;
const expandedSummaryDetails = new Set();
const undoStack = [];
const redoStack = [];
const MAX_HISTORY = 50;
let suspendHistory = false;
let commandInputDebounce = null;
let resizeDebounce = null;
let suspendProfileSync = false;

const PROFILE_DEFS = {
  review: {
    label: "Review",
    settings: {
      model: "gpt-5.4-mini",
      mode: "Review",
      access: "Nur lesen",
      planMode: true,
      multiAgent: false,
      budget: 0.5,
      roleModels: { planner: "gpt-5.4", coder: "gpt-5.4-mini", tester: "gpt-5.4-mini", reviewer: "gpt-5.5", fixer: "gpt-5.4-mini" },
    },
  },
  fast_fix: {
    label: "Fast Fix",
    settings: {
      model: "gpt-5.4",
      mode: "Fix",
      access: "Dateien ändern",
      planMode: false,
      multiAgent: false,
      budget: 1.5,
      roleModels: { planner: "gpt-5.4-mini", coder: "gpt-5.4", tester: "gpt-5.4-mini", reviewer: "gpt-5.4", fixer: "gpt-5.4" },
    },
  },
  safe_mode: {
    label: "Safe Mode",
    settings: {
      model: "gpt-5.4-mini",
      mode: "Review",
      access: "Nur lesen",
      planMode: true,
      multiAgent: false,
      budget: 0.25,
      roleModels: { planner: "gpt-5.4-mini", coder: "gpt-5.4-mini", tester: "gpt-5.4-mini", reviewer: "gpt-5.4", fixer: "gpt-5.4-mini" },
    },
  },
  autonomous: {
    label: "Autonomous",
    settings: {
      model: "gpt-5.5",
      mode: "Code",
      access: "Autonom",
      planMode: false,
      multiAgent: true,
      budget: 5.0,
      roleModels: { planner: "gpt-5.5", coder: "gpt-5.4", tester: "gpt-5.4-mini", reviewer: "gpt-5.5", fixer: "gpt-5.4" },
    },
  },
};

function collapseStorageKey(panelId) {
  return `${COLLAPSE_KEY_PREFIX}${panelId}`;
}

function readPreferences() {
  const raw = localStorage.getItem(UI_PREFS_KEY);
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") return parsed;
    } catch {
      // fallback to legacy keys below
    }
  }
  const fallbackPanels = {};
  for (const panelId of MODE_PANELS) {
    fallbackPanels[panelId] = localStorage.getItem(collapseStorageKey(panelId)) === "1";
  }
  const fallbackLayout = readLayoutWidths();
  return {
    mode: localStorage.getItem(UI_MODE_KEY) || "workflow",
    panelState: fallbackPanels,
    layout: fallbackLayout,
    history: (() => {
      const hRaw = localStorage.getItem(COMMAND_HISTORY_KEY);
      if (!hRaw) return [];
      try {
        const parsed = JSON.parse(hRaw);
        return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string").slice(0, 20) : [];
      } catch {
        return [];
      }
    })(),
    session: {
      lastRunId: localStorage.getItem(LAST_RUN_KEY) || "",
      scrollTop: Number(localStorage.getItem(SCROLL_KEY) || "0") || 0,
    },
    modeStates: {},
    onboardingDismissed: false,
    lastUpdated: Date.now(),
  };
}

function writePreferences(prefs) {
  const safe = {
    mode: prefs.mode || "workflow",
    panelState: prefs.panelState || {},
    layout: prefs.layout || { sidebarWidth: 260, explorerWidth: 320 },
    history: Array.isArray(prefs.history) ? prefs.history.slice(0, 20) : [],
    session: prefs.session || { lastRunId: "", scrollTop: 0 },
    modeStates: prefs.modeStates && typeof prefs.modeStates === "object" ? prefs.modeStates : {},
    onboardingDismissed: !!prefs.onboardingDismissed,
    lastUpdated: Date.now(),
  };
  localStorage.setItem(UI_PREFS_KEY, JSON.stringify(safe));
}

function patchPreferences(patch) {
  const current = readPreferences();
  const next = {
    ...current,
    ...patch,
    panelState: { ...(current.panelState || {}), ...(patch.panelState || {}) },
    layout: { ...(current.layout || {}), ...(patch.layout || {}) },
    session: { ...(current.session || {}), ...(patch.session || {}) },
    onboardingDismissed: "onboardingDismissed" in patch ? !!patch.onboardingDismissed : !!current.onboardingDismissed,
  };
  writePreferences(next);
  return next;
}

function bindOnboardingHint(isFirstLoadWithoutPreferences) {
  const hintEl = document.getElementById("onboarding-hint");
  const gotItBtn = document.getElementById("onboarding-got-it");
  if (!hintEl || !gotItBtn) return;
  const prefs = readPreferences();
  const shouldShow = isFirstLoadWithoutPreferences && !prefs.onboardingDismissed;
  hintEl.classList.toggle("hidden", !shouldShow);
  gotItBtn.addEventListener("click", () => {
    patchPreferences({ onboardingDismissed: true });
    hintEl.classList.add("hidden");
  });
}

function hasLegacyUiKeys() {
  if (localStorage.getItem(UI_MODE_KEY)) return true;
  if (localStorage.getItem(SIDEBAR_WIDTH_KEY)) return true;
  if (localStorage.getItem(EXPLORER_WIDTH_KEY)) return true;
  if (localStorage.getItem(COMMAND_HISTORY_KEY)) return true;
  if (localStorage.getItem(LAST_RUN_KEY)) return true;
  if (localStorage.getItem(SCROLL_KEY)) return true;
  for (const panelId of MODE_PANELS) {
    if (localStorage.getItem(collapseStorageKey(panelId)) !== null) return true;
  }
  return false;
}

function clearLegacyUiKeys() {
  localStorage.removeItem(UI_MODE_KEY);
  localStorage.removeItem(SIDEBAR_WIDTH_KEY);
  localStorage.removeItem(EXPLORER_WIDTH_KEY);
  localStorage.removeItem(COMMAND_HISTORY_KEY);
  localStorage.removeItem(LAST_RUN_KEY);
  localStorage.removeItem(SCROLL_KEY);
  for (const panelId of MODE_PANELS) {
    localStorage.removeItem(collapseStorageKey(panelId));
  }
}

function migrateLegacyPreferencesIfNeeded() {
  if (localStorage.getItem(UI_PREFS_KEY)) {
    clearLegacyUiKeys();
    return;
  }
  if (!hasLegacyUiKeys()) return;
  const migrated = readPreferences();
  writePreferences(migrated);
  clearLegacyUiKeys();
}

function applyCollapsedState(panel, collapsed) {
  panel.classList.toggle("collapsed", collapsed);
  const toggle = panel.querySelector("[data-collapse-toggle]");
  if (toggle) toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
}

function sanitizeMode(rawMode) {
  return FOCUS_MODES.includes(rawMode) ? rawMode : "workflow";
}

function equalHistoryState(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function pushHistoryAction(action) {
  if (suspendHistory) return;
  if (!action || !action.type) return;
  if (equalHistoryState(action.before, action.after)) return;
  undoStack.push(action);
  if (undoStack.length > MAX_HISTORY) undoStack.shift();
  redoStack.length = 0;
}

function applyHistoryState(type, payload) {
  if (type === "mode_change") {
    applyFocusMode(String(payload?.mode || "workflow"), true, { source: "history" });
    return;
  }
  if (type === "panel_toggle") {
    const panelId = String(payload?.panelId || "");
    if (!panelId) return;
    setPanelCollapsed(panelId, !!payload?.collapsed, true);
    if (currentFocusMode) saveFocusModeState(currentFocusMode);
    return;
  }
  if (type === "resize_change") {
    const sidebarWidth = Number(payload?.sidebarWidth);
    const explorerWidth = Number(payload?.explorerWidth);
    if (!Number.isFinite(sidebarWidth) || !Number.isFinite(explorerWidth)) return;
    setLayoutWidths(sidebarWidth, explorerWidth);
    const widths = readCurrentLayoutWidths();
    patchPreferences({ layout: widths });
    if (currentFocusMode) saveFocusModeState(currentFocusMode);
  }
}

function applyHistoryAction(action, direction) {
  if (!action || !action.type) return;
  const payload = direction === "undo" ? action.before : action.after;
  applyHistoryState(action.type, payload);
}

function initCollapsibles() {
  const prefs = readPreferences();
  const panels = Array.from(document.querySelectorAll("[data-collapsible][data-panel-id]"));
  for (const panel of panels) {
    const panelId = panel.getAttribute("data-panel-id");
    if (!panelId) continue;
    collapsiblePanels.set(panelId, panel);
    applyCollapsedState(panel, !!prefs.panelState?.[panelId]);
    const toggle = panel.querySelector("[data-collapse-toggle]");
    const body = panel.querySelector(".collapsible-body");
    if (toggle && body) {
      if (!body.id) body.id = `${panelId}-collapsible-body`;
      toggle.setAttribute("aria-controls", body.id);
    }
    if (!toggle) continue;
    toggle.addEventListener("click", () => {
      const collapsed = !panel.classList.contains("collapsed");
      applyCollapsedState(panel, collapsed);
      patchPreferences({ panelState: { [panelId]: collapsed } });
    });
  }
}

function setPanelCollapsed(panelId, collapsed, persist = false) {
  const panel = collapsiblePanels.get(panelId);
  if (!panel) return;
  applyCollapsedState(panel, collapsed);
  if (persist) {
    patchPreferences({ panelState: { [panelId]: collapsed } });
  }
}

function togglePanelCollapsed(panelId, persist = true) {
  const current = isPanelCollapsed(panelId);
  const next = !current;
  setPanelCollapsed(panelId, next, persist);
  if (currentFocusMode) saveFocusModeState(currentFocusMode);
  pushHistoryAction({
    type: "panel_toggle",
    before: { panelId, collapsed: current },
    after: { panelId, collapsed: next },
  });
}

function isPanelCollapsed(panelId) {
  const panel = collapsiblePanels.get(panelId);
  return panel ? panel.classList.contains("collapsed") : false;
}

function clamp(value, minValue, maxValue) {
  return Math.max(minValue, Math.min(maxValue, value));
}

function snapNear(value, points) {
  let best = value;
  let bestDistance = SNAP_THRESHOLD + 1;
  for (const point of points) {
    const distance = Math.abs(value - point);
    if (distance < bestDistance && distance <= SNAP_THRESHOLD) {
      best = point;
      bestDistance = distance;
    }
  }
  return best;
}

function setLayoutWidths(sidebarWidth, explorerWidth) {
  if (!els.layoutEl) return;
  const total = els.layoutEl.clientWidth || window.innerWidth;
  const maxSidebar = Math.min(SIDEBAR_MAX, total - EXPLORER_MIN - MAIN_MIN - 16);
  const maxExplorer = Math.min(EXPLORER_MAX, total - SIDEBAR_MIN - MAIN_MIN - 16);
  const snappedSidebar = snapNear(sidebarWidth, SIDEBAR_SNAP_POINTS);
  const snappedExplorer = snapNear(explorerWidth, EXPLORER_SNAP_POINTS);
  const nextSidebar = clamp(snappedSidebar, SIDEBAR_MIN, Math.max(SIDEBAR_MIN, maxSidebar));
  const nextExplorer = clamp(snappedExplorer, EXPLORER_MIN, Math.max(EXPLORER_MIN, maxExplorer));

  document.documentElement.style.setProperty("--sidebar-w", `${nextSidebar}px`);
  document.documentElement.style.setProperty("--explorer-w", `${nextExplorer}px`);
  updateResizeAriaValues(nextSidebar, nextExplorer);
}

function updateResizeAriaValues(sidebarWidth, explorerWidth) {
  if (els.leftResizeHandleEl) {
    els.leftResizeHandleEl.setAttribute("aria-valuemin", String(SIDEBAR_MIN));
    els.leftResizeHandleEl.setAttribute("aria-valuemax", String(SIDEBAR_MAX));
    els.leftResizeHandleEl.setAttribute("aria-valuenow", String(Math.round(sidebarWidth)));
  }
  if (els.rightResizeHandleEl) {
    els.rightResizeHandleEl.setAttribute("aria-valuemin", String(EXPLORER_MIN));
    els.rightResizeHandleEl.setAttribute("aria-valuemax", String(EXPLORER_MAX));
    els.rightResizeHandleEl.setAttribute("aria-valuenow", String(Math.round(explorerWidth)));
  }
}

function readLayoutWidths() {
  const prefs = readPreferences();
  const sidebarRaw = Number(prefs.layout?.sidebarWidth);
  const explorerRaw = Number(prefs.layout?.explorerWidth);
  const sidebarWidth = Number.isFinite(sidebarRaw) && sidebarRaw > 0 ? sidebarRaw : 260;
  const explorerWidth = Number.isFinite(explorerRaw) && explorerRaw > 0 ? explorerRaw : 320;
  return { sidebarWidth, explorerWidth };
}

function readCurrentLayoutWidths() {
  const sidebarPx = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--sidebar-w"), 10);
  const explorerPx = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--explorer-w"), 10);
  return {
    sidebarWidth: Number.isFinite(sidebarPx) && sidebarPx > 0 ? sidebarPx : readLayoutWidths().sidebarWidth,
    explorerWidth: Number.isFinite(explorerPx) && explorerPx > 0 ? explorerPx : readLayoutWidths().explorerWidth,
  };
}

function saveFocusModeState(mode) {
  if (!FOCUS_MODES.includes(mode)) return;
  const widths = readCurrentLayoutWidths();
  const panels = {};
  for (const panelId of MODE_PANELS) {
    panels[panelId] = isPanelCollapsed(panelId);
  }
  localStorage.setItem(
    UI_PREFS_KEY,
    JSON.stringify({
      ...readPreferences(),
      modeStates: {
        ...(readPreferences().modeStates || {}),
        [mode]: {
          sidebarWidth: widths.sidebarWidth,
          explorerWidth: widths.explorerWidth,
          panels,
        },
      },
      mode,
      panelState: panels,
      layout: { sidebarWidth: widths.sidebarWidth, explorerWidth: widths.explorerWidth },
      lastUpdated: Date.now(),
    }),
  );
}

function loadFocusModeState(mode) {
  const fallback = MODE_DEFAULTS[mode] || MODE_DEFAULTS.workflow;
  const modeState = readPreferences().modeStates?.[mode];
  if (!modeState) return fallback;
  try {
    const parsed = modeState;
    const sidebarWidth = Number(parsed?.sidebarWidth);
    const explorerWidth = Number(parsed?.explorerWidth);
    const panels = {};
    for (const panelId of MODE_PANELS) {
      const value = parsed?.panels?.[panelId];
      panels[panelId] = typeof value === "boolean" ? value : fallback.panels[panelId];
    }
    return {
      sidebarWidth: Number.isFinite(sidebarWidth) ? sidebarWidth : fallback.sidebarWidth,
      explorerWidth: Number.isFinite(explorerWidth) ? explorerWidth : fallback.explorerWidth,
      panels,
    };
  } catch {
    return fallback;
  }
}

function applyFocusModeState(stateForMode) {
  setLayoutWidths(stateForMode.sidebarWidth, stateForMode.explorerWidth);
  for (const panelId of MODE_PANELS) {
    const collapsed = !!stateForMode.panels[panelId];
    setPanelCollapsed(panelId, collapsed);
  }
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
    patchPreferences({ layout: { sidebarWidth: sidebarPx, explorerWidth: explorerPx } });
    if (currentFocusMode) saveFocusModeState(currentFocusMode);
  };

  const onKeyboardResize = (type, direction, step) => {
    const before = readCurrentLayoutWidths();
    if (type === "left") {
      setLayoutWidths(before.sidebarWidth + direction * step, before.explorerWidth);
    } else {
      setLayoutWidths(before.sidebarWidth, before.explorerWidth - direction * step);
    }
    const widths = readCurrentLayoutWidths();
    patchPreferences({ layout: { sidebarWidth: widths.sidebarWidth, explorerWidth: widths.explorerWidth } });
    if (currentFocusMode) saveFocusModeState(currentFocusMode);
    pushHistoryAction({
      type: "resize_change",
      before: { sidebarWidth: before.sidebarWidth, explorerWidth: before.explorerWidth },
      after: { sidebarWidth: widths.sidebarWidth, explorerWidth: widths.explorerWidth },
    });
  };

  const bindHandle = (handle, type) => {
    handle.addEventListener("pointerdown", (downEvent) => {
      if (downEvent.button !== undefined && downEvent.button !== 0) return;
      downEvent.preventDefault();
      const dragStart = readCurrentLayoutWidths();
      els.layoutEl.classList.add("resizing");
      if (typeof handle.setPointerCapture === "function") {
        handle.setPointerCapture(downEvent.pointerId);
      }

      const move = (moveEvent) => onDrag(type, moveEvent);
      const stop = (upEvent) => {
        els.layoutEl.classList.remove("resizing");
        const dragEnd = readCurrentLayoutWidths();
        pushHistoryAction({
          type: "resize_change",
          before: { sidebarWidth: dragStart.sidebarWidth, explorerWidth: dragStart.explorerWidth },
          after: { sidebarWidth: dragEnd.sidebarWidth, explorerWidth: dragEnd.explorerWidth },
        });
        if (typeof handle.releasePointerCapture === "function") {
          try {
            handle.releasePointerCapture(upEvent.pointerId);
          } catch {
            // ignore stale pointer releases
          }
        }
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", stop);
        handle.removeEventListener("pointercancel", stop);
      };

      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", stop);
      handle.addEventListener("pointercancel", stop);
    });

    handle.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const direction = event.key === "ArrowRight" ? 1 : -1;
      const step = event.shiftKey ? 32 : 12;
      onKeyboardResize(type, direction, step);
    });
  };

  bindHandle(els.leftResizeHandleEl, "left");
  bindHandle(els.rightResizeHandleEl, "right");

  window.addEventListener("resize", () => {
    if (resizeDebounce) clearTimeout(resizeDebounce);
    resizeDebounce = setTimeout(() => {
      const mode = currentFocusMode || readPreferences().mode || "workflow";
      const modeState = loadFocusModeState(mode);
      applyFocusModeState(modeState);
      saveFocusModeState(mode);
    }, 80);
  });
}

function setActiveFocusButton(mode) {
  const map = {
    workflow: els.focusWorkflowBtn,
    code: els.focusCodeBtn,
    chat: els.focusChatBtn,
  };
  for (const [name, el] of Object.entries(map)) {
    if (!el) continue;
    const active = name === mode;
    el.classList.toggle("active", active);
    el.setAttribute("aria-pressed", active ? "true" : "false");
  }
}

function buildCommandActions() {
  return [
    { id: "mode-workflow", label: "Switch to Workflow Mode", run: () => applyFocusMode("workflow"), feedback: "Switched to Workflow Mode" },
    { id: "mode-code", label: "Switch to Code Mode", run: () => applyFocusMode("code"), feedback: "Switched to Code Mode" },
    { id: "mode-chat", label: "Switch to Chat Mode", run: () => applyFocusMode("chat"), feedback: "Switched to Chat Mode" },
    { id: "toggle-workflow", label: "Toggle Workflow Panel", run: () => togglePanelCollapsed("workflow", true), feedback: "Workflow toggled" },
    { id: "toggle-explorer", label: "Toggle Explorer Panel", run: () => togglePanelCollapsed("explorer", true), feedback: "Explorer toggled" },
    { id: "toggle-timeline", label: "Toggle Timeline Panel", run: () => togglePanelCollapsed("timeline", true), feedback: "Timeline toggled" },
    { id: "toggle-plugins", label: "Toggle Plugins Panel", run: () => togglePanelCollapsed("plugins", true), feedback: "Plugins toggled" },
    { id: "toggle-tool-decision", label: "Toggle Tool Decision Panel", run: () => togglePanelCollapsed("tool_decision", true), feedback: "Tool Decision toggled" },
  ];
}

function readCommandHistory() {
  const prefs = readPreferences();
  if (Array.isArray(prefs.history)) return prefs.history.slice(0, 20);
  const raw = localStorage.getItem(COMMAND_HISTORY_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string").slice(0, 20) : [];
  } catch {
    return [];
  }
}

function saveCommandHistory(actionId) {
  const current = readCommandHistory().filter((id) => id !== actionId);
  current.unshift(actionId);
  patchPreferences({ history: current.slice(0, 20) });
}

function scoreAndHighlight(label, query) {
  const text = String(label || "");
  const lower = text.toLowerCase();
  const q = String(query || "").toLowerCase().trim();
  if (!q) return { matched: true, score: 3, indices: [] };
  if (lower.startsWith(q)) {
    return { matched: true, score: 0, indices: Array.from({ length: q.length }, (_, i) => i) };
  }
  const subIdx = lower.indexOf(q);
  if (subIdx >= 0) {
    return { matched: true, score: 1, indices: Array.from({ length: q.length }, (_, i) => subIdx + i) };
  }
  const indices = [];
  let qPos = 0;
  for (let i = 0; i < lower.length && qPos < q.length; i += 1) {
    if (lower[i] === q[qPos]) {
      indices.push(i);
      qPos += 1;
    }
  }
  if (qPos === q.length) {
    return { matched: true, score: 2, indices };
  }
  return { matched: false, score: 99, indices: [] };
}

function buildHighlightedLabel(label, indices) {
  const frag = document.createDocumentFragment();
  const text = String(label || "");
  const indexSet = new Set(indices);
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (indexSet.has(i)) {
      const span = document.createElement("span");
      span.className = "cmd-highlight";
      span.textContent = ch;
      frag.appendChild(span);
    } else {
      frag.appendChild(document.createTextNode(ch));
    }
  }
  return frag;
}

function buildFilteredActions() {
  const q = String(els.commandInputEl?.value || "").trim();
  const history = readCommandHistory();
  const historySet = new Set(history);

  if (!q) {
    const byId = new Map(commandActions.map((a) => [a.id, a]));
    const recents = history.map((id) => byId.get(id)).filter(Boolean).map((action) => ({
      action,
      score: -1,
      highlightIndices: [],
      isRecent: true,
    }));
    const rest = commandActions.filter((a) => !historySet.has(a.id)).map((action) => ({
      action,
      score: 3,
      highlightIndices: [],
      isRecent: false,
    }));
    return [...recents, ...rest];
  }

  const rows = [];
  for (const action of commandActions) {
    const labelMatch = scoreAndHighlight(action.label, q);
    const idMatch = scoreAndHighlight(action.id, q);
    const match = labelMatch.matched ? labelMatch : idMatch;
    if (!match.matched) continue;
    rows.push({
      action,
      score: match.score,
      highlightIndices: labelMatch.matched ? labelMatch.indices : [],
      isRecent: historySet.has(action.id),
    });
  }
  rows.sort((a, b) => a.score - b.score || Number(b.isRecent) - Number(a.isRecent) || a.action.label.localeCompare(b.action.label));
  return rows;
}

function showToast(message) {
  if (!els.uiToastEl || !message) return;
  els.uiToastEl.textContent = message;
  els.uiToastEl.classList.remove("hidden");
  els.uiToastEl.classList.add("show");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    els.uiToastEl?.classList.remove("show");
    setTimeout(() => els.uiToastEl?.classList.add("hidden"), 180);
  }, 1400);
}

function runCommandAction(action) {
  action.run();
  saveCommandHistory(action.id);
  if (action.feedback) showToast(action.feedback);
}

function getPanelStateLabel(panelId, visibleText, hiddenText) {
  return isPanelCollapsed(panelId) ? hiddenText : visibleText;
}

function getSummaryFieldText(detailEl) {
  return detailEl && !detailEl.classList.contains("hidden") ? "details hidden" : "details shown";
}

function bindSummaryDetails() {
  const items = [
    ["task", els.wfSummaryTaskEl, els.wfDetailTaskEl],
    ["patch", els.wfSummaryPatchEl, els.wfDetailPatchEl],
    ["tests", els.wfSummaryTestsEl, els.wfDetailTestsEl],
    ["risk", els.wfSummaryRiskEl, els.wfDetailRiskEl],
    ["decision", els.wfSummaryDecisionEl, els.wfDetailDecisionEl],
  ];
  for (const [key, btn, detail] of items) {
    if (!btn || !detail) continue;
    btn.addEventListener("click", () => {
      if (detail.classList.contains("hidden")) {
        detail.classList.remove("hidden");
        expandedSummaryDetails.add(String(key));
      } else {
        detail.classList.add("hidden");
        expandedSummaryDetails.delete(String(key));
      }
      showToast(`Summary ${key} ${getSummaryFieldText(detail)}`);
    });
  }
}

function applySummaryDetailExpansion() {
  const mapping = [
    ["task", els.wfDetailTaskEl],
    ["patch", els.wfDetailPatchEl],
    ["tests", els.wfDetailTestsEl],
    ["risk", els.wfDetailRiskEl],
    ["decision", els.wfDetailDecisionEl],
  ];
  for (const [key, detail] of mapping) {
    if (!detail) continue;
    detail.classList.toggle("hidden", !expandedSummaryDetails.has(String(key)));
  }
}

function getFilteredActions() {
  return buildFilteredActions();
}

function fuzzyIncludes(haystack, needle) {
  const text = String(haystack || "");
  const result = scoreAndHighlight(text, needle);
  return result.matched;
}

function getCommandDisplayLabel(action, highlightIndices, isRecent) {
  const wrapper = document.createDocumentFragment();
  wrapper.appendChild(buildHighlightedLabel(action.label, highlightIndices));
  if (isRecent) {
    const tag = document.createElement("span");
    tag.className = "cmd-recent";
    tag.textContent = "recent";
    wrapper.appendChild(tag);
  }
  return wrapper;
}

function getFilteredActionsCount() {
  return filteredCommandActions.length;
}

function getFilteredActionAt(idx) {
  return filteredCommandActions[idx] || null;
}

function setPaletteSelectedIndex(idx) {
  paletteSelectedIndex = idx;
}

function normalizePaletteSelection() {
  if (paletteSelectedIndex >= getFilteredActionsCount()) setPaletteSelectedIndex(0);
}

function getSelectedPaletteAction() {
  const item = getFilteredActionAt(paletteSelectedIndex);
  return item ? item.action : null;
}

function getSelectedPaletteItem() {
  return getFilteredActionAt(paletteSelectedIndex);
}

function getRecentIdsSet() {
  return new Set(readCommandHistory());
}

function getActionFeedbackForShortcut(actionId) {
  const action = commandActions.find((a) => a.id === actionId);
  return action && action.feedback ? action.feedback : null;
}

function registerShortcutFeedback(actionId) {
  saveCommandHistory(actionId);
  const msg = getActionFeedbackForShortcut(actionId);
  if (msg) showToast(msg);
}

function exportLayoutPreferences() {
  const prefs = readPreferences();
  const json = JSON.stringify(prefs, null, 2);
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard
      .writeText(json)
      .then(() => showToast("Layout exported to clipboard"))
      .catch(() => {
        prompt("Copy layout JSON:", json);
        showToast("Layout export shown");
      });
  } else {
    prompt("Copy layout JSON:", json);
    showToast("Layout export shown");
  }
}

function sanitizeImportedPreferences(raw) {
  if (!raw || typeof raw !== "object") throw new Error("Invalid object");
  const mode = FOCUS_MODES.includes(raw.mode) ? raw.mode : "workflow";
  const panelState = {};
  for (const panelId of MODE_PANELS) {
    panelState[panelId] = typeof raw.panelState?.[panelId] === "boolean" ? raw.panelState[panelId] : false;
  }
  const sidebarWidth = Number(raw.layout?.sidebarWidth);
  const explorerWidth = Number(raw.layout?.explorerWidth);
  const history = Array.isArray(raw.history) ? raw.history.filter((x) => typeof x === "string").slice(0, 20) : [];
  return {
    mode,
    panelState,
    layout: {
      sidebarWidth: Number.isFinite(sidebarWidth) ? sidebarWidth : 260,
      explorerWidth: Number.isFinite(explorerWidth) ? explorerWidth : 320,
    },
    history,
    session: {
      lastRunId: typeof raw.session?.lastRunId === "string" ? raw.session.lastRunId : "",
      scrollTop: Number(raw.session?.scrollTop || 0) || 0,
    },
  };
}

function importLayoutPreferences() {
  const input = prompt("Paste layout JSON:");
  if (!input) return;
  try {
    const parsed = JSON.parse(input);
    const sanitized = sanitizeImportedPreferences(parsed);
    writePreferences(sanitized);
    suspendHistory = true;
    try {
      setLayoutWidths(sanitized.layout.sidebarWidth, sanitized.layout.explorerWidth);
      for (const panelId of MODE_PANELS) {
        setPanelCollapsed(panelId, !!sanitized.panelState[panelId], true);
      }
      applyFocusMode(sanitized.mode, true, { source: "import" });
    } finally {
      suspendHistory = false;
    }
    currentFocusMode = sanitized.mode;
    showToast("Layout imported");
  } catch {
    showToast("Invalid layout JSON");
  }
}

function applyRecentOrdering(actions) {
  return actions;
}

function getCommandActionById(actionId) {
  return commandActions.find((a) => a.id === actionId) || null;
}

function getIsRecentAction(actionId, historySet) {
  return historySet.has(actionId);
}

function getHighlightedIndicesForAction(action, query) {
  return scoreAndHighlight(action.label, query).indices;
}

function scoreActionForQuery(action, query) {
  const label = scoreAndHighlight(action.label, query);
  const idScore = scoreAndHighlight(action.id, query);
  if (label.matched) return { score: label.score, indices: label.indices, matched: true };
  if (idScore.matched) return { score: idScore.score, indices: [], matched: true };
  return { score: 99, indices: [], matched: false };
}

function buildActionRows(query) {
  const q = String(query || "").trim();
  const historySet = getRecentIdsSet();
  if (!q) return getFilteredActions();
  const rows = [];
  for (const action of commandActions) {
    const scored = scoreActionForQuery(action, q);
    if (!scored.matched) continue;
    rows.push({
      action,
      score: scored.score,
      highlightIndices: scored.indices,
      isRecent: getIsRecentAction(action.id, historySet),
    });
  }
  rows.sort((a, b) => a.score - b.score || Number(b.isRecent) - Number(a.isRecent) || a.action.label.localeCompare(b.action.label));
  return rows;
}

function renderCommandPalette() {
  if (!els.commandListEl) return;
  const query = String(els.commandInputEl?.value || "").trim();
  filteredCommandActions = buildActionRows(query);
  normalizePaletteSelection();
  els.commandListEl.innerHTML = "";
  els.commandListEl.setAttribute("aria-activedescendant", "");
  if (filteredCommandActions.length === 0) {
    const empty = document.createElement("div");
    empty.className = "command-empty";
    empty.textContent = "No results";
    els.commandListEl.appendChild(empty);
    return;
  }

  if (!query) {
    const popularLabel = document.createElement("div");
    popularLabel.className = "command-group-label";
    popularLabel.textContent = "Popular commands";
    els.commandListEl.appendChild(popularLabel);

    const popularItems = [
      "Switch to Workflow Mode",
      "Toggle Explorer",
      "Open Timeline",
    ];
    for (const text of popularItems) {
      const hint = document.createElement("div");
      hint.className = "command-help-item";
      hint.textContent = text;
      els.commandListEl.appendChild(hint);
    }

    const shortcutLabel = document.createElement("div");
    shortcutLabel.className = "command-group-label";
    shortcutLabel.textContent = "Shortcuts";
    els.commandListEl.appendChild(shortcutLabel);

    const shortcuts = document.createElement("div");
    shortcuts.className = "command-help-item";
    shortcuts.textContent = "Ctrl+K, Ctrl+1/2/3, Ctrl+B, Ctrl+E, Ctrl+Z, Ctrl+Shift+Z";
    els.commandListEl.appendChild(shortcuts);
  }

  let recentDividerShown = false;
  let otherDividerShown = false;
  filteredCommandActions.forEach((item, idx) => {
    if (!query && item.isRecent && !recentDividerShown) {
      const recent = document.createElement("div");
      recent.className = "command-group-label";
      recent.textContent = "Recent Commands";
      els.commandListEl.appendChild(recent);
      recentDividerShown = true;
    }
    if (!query && !item.isRecent && recentDividerShown && !otherDividerShown) {
      const all = document.createElement("div");
      all.className = "command-group-label";
      all.textContent = "All Commands";
      els.commandListEl.appendChild(all);
      otherDividerShown = true;
    }
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "command-item";
    btn.id = `command-option-${idx}`;
    btn.setAttribute("role", "option");
    btn.setAttribute("aria-selected", idx === paletteSelectedIndex ? "true" : "false");
    if (idx === paletteSelectedIndex) btn.classList.add("active");
    if (idx === paletteSelectedIndex) els.commandListEl.setAttribute("aria-activedescendant", btn.id);
    btn.appendChild(getCommandDisplayLabel(item.action, item.highlightIndices || [], !!item.isRecent));
    btn.addEventListener("click", () => {
      closeCommandPalette();
      requestAnimationFrame(() => runCommandAction(item.action));
    });
    els.commandListEl.appendChild(btn);
  });
}

function openCommandPalette() {
  if (!els.commandPaletteEl || !els.commandPanelEl) return;
  if (paletteCloseTimer) {
    clearTimeout(paletteCloseTimer);
    paletteCloseTimer = null;
  }
  paletteWasFocused = document.activeElement;
  commandActions = buildCommandActions();
  filteredCommandActions = [...commandActions];
  paletteSelectedIndex = 0;
  els.commandPaletteEl.classList.remove("hidden");
  requestAnimationFrame(() => els.commandPaletteEl?.classList.add("is-open"));
  renderCommandPalette();
  if (els.commandInputEl) {
    els.commandInputEl.value = "";
    els.commandInputEl.focus();
  } else {
    els.commandPanelEl.focus();
  }
}

function closeCommandPalette() {
  if (!els.commandPaletteEl) return;
  els.commandPaletteEl.classList.remove("is-open");
  if (paletteCloseTimer) clearTimeout(paletteCloseTimer);
  paletteCloseTimer = setTimeout(() => {
    els.commandPaletteEl?.classList.add("hidden");
    paletteCloseTimer = null;
    if (paletteWasFocused && paletteWasFocused instanceof HTMLElement) {
      paletteWasFocused.focus();
    }
  }, 170);
}

function paletteIsOpen() {
  return !!els.commandPaletteEl && !els.commandPaletteEl.classList.contains("hidden");
}

function movePaletteSelection(delta) {
  if (!filteredCommandActions.length) return;
  paletteSelectedIndex = (paletteSelectedIndex + delta + filteredCommandActions.length) % filteredCommandActions.length;
  renderCommandPalette();
}

function executePaletteSelection() {
  const selected = getSelectedPaletteItem();
  if (!selected) return;
  closeCommandPalette();
  requestAnimationFrame(() => runCommandAction(selected.action));
}

function shortcutHelpIsOpen() {
  const overlay = document.getElementById("shortcut-help-overlay");
  return !!overlay && !overlay.classList.contains("hidden");
}

function openShortcutHelp() {
  const overlay = document.getElementById("shortcut-help-overlay");
  if (!overlay) return;
  if (shortcutCloseTimer) {
    clearTimeout(shortcutCloseTimer);
    shortcutCloseTimer = null;
  }
  shortcutWasFocused = document.activeElement;
  overlay.classList.remove("hidden");
  requestAnimationFrame(() => overlay.classList.add("is-open"));
  const closeBtn = document.getElementById("shortcut-help-close");
  if (closeBtn instanceof HTMLElement) closeBtn.focus();
}

function closeShortcutHelp() {
  const overlay = document.getElementById("shortcut-help-overlay");
  if (!overlay) return;
  overlay.classList.remove("is-open");
  if (shortcutCloseTimer) clearTimeout(shortcutCloseTimer);
  shortcutCloseTimer = setTimeout(() => {
    overlay.classList.add("hidden");
    shortcutCloseTimer = null;
    if (shortcutWasFocused && shortcutWasFocused instanceof HTMLElement) shortcutWasFocused.focus();
  }, 170);
}

function bindShortcutHelpOverlay() {
  const closeBtn = document.getElementById("shortcut-help-close");
  const backdrop = document.getElementById("shortcut-help-backdrop");
  if (closeBtn) closeBtn.addEventListener("click", closeShortcutHelp);
  if (backdrop) backdrop.addEventListener("click", closeShortcutHelp);
}

function runUndo() {
  if (!undoStack.length) return;
  const action = undoStack.pop();
  redoStack.push(action);
  suspendHistory = true;
  try {
    applyHistoryAction(action, "undo");
  } finally {
    suspendHistory = false;
  }
  showToast("Undo");
}

function runRedo() {
  if (!redoStack.length) return;
  const action = redoStack.pop();
  undoStack.push(action);
  suspendHistory = true;
  try {
    applyHistoryAction(action, "redo");
  } finally {
    suspendHistory = false;
  }
  showToast("Redo");
}

function isEditableTarget(target) {
  if (!target || !(target instanceof Element)) return false;
  const tag = target.tagName.toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  if (target.hasAttribute("contenteditable")) return true;
  return Boolean(target.closest("[contenteditable='true']"));
}

function bindKeyboardShortcuts() {
  window.addEventListener("keydown", (event) => {
    if (shortcutHelpIsOpen()) {
      if (String(event.key || "").toLowerCase() === "escape") {
        event.preventDefault();
        closeShortcutHelp();
      }
      return;
    }

    if (paletteIsOpen()) {
      const key = String(event.key || "").toLowerCase();
      if (key === "escape") {
        event.preventDefault();
        closeCommandPalette();
        return;
      }
      if (key === "arrowdown") {
        event.preventDefault();
        movePaletteSelection(1);
        return;
      }
      if (key === "arrowup") {
        event.preventDefault();
        movePaletteSelection(-1);
        return;
      }
      if (key === "enter") {
        event.preventDefault();
        executePaletteSelection();
        return;
      }
    }

    if (event.defaultPrevented) return;
    if (!event.ctrlKey || event.metaKey || event.altKey) return;
    if (isEditableTarget(event.target)) return;

    const key = String(event.key || "").toLowerCase();
    if (key === "/") {
      event.preventDefault();
      openShortcutHelp();
      return;
    }
    if (key === "z" && event.shiftKey) {
      event.preventDefault();
      runRedo();
      return;
    }
    if (key === "z" && !event.shiftKey) {
      event.preventDefault();
      runUndo();
      return;
    }
    if (event.shiftKey) return;
    if (key === "1") {
      event.preventDefault();
      applyFocusMode("workflow");
      registerShortcutFeedback("mode-workflow");
      return;
    }
    if (key === "2") {
      event.preventDefault();
      applyFocusMode("code");
      registerShortcutFeedback("mode-code");
      return;
    }
    if (key === "3") {
      event.preventDefault();
      applyFocusMode("chat");
      registerShortcutFeedback("mode-chat");
      return;
    }
    if (key === "k") {
      event.preventDefault();
      openCommandPalette();
      return;
    }
    if (key === "b") {
      event.preventDefault();
      togglePanelCollapsed("sidebar", true);
      if (currentFocusMode) saveFocusModeState(currentFocusMode);
      showToast(getPanelStateLabel("sidebar", "Sidebar shown", "Sidebar hidden"));
      return;
    }
    if (key === "e") {
      event.preventDefault();
      togglePanelCollapsed("explorer", true);
      if (currentFocusMode) saveFocusModeState(currentFocusMode);
      showToast(getPanelStateLabel("explorer", "Explorer shown", "Explorer hidden"));
    }
  });
}

function applyFocusMode(rawMode, persist = true, options = {}) {
  const mode = sanitizeMode(rawMode);
  const previousMode = sanitizeMode(currentFocusMode || readPreferences().mode || "workflow");
  const shouldRecord = options.source !== "history" && options.source !== "import";
  if (currentFocusMode && currentFocusMode !== mode) {
    saveFocusModeState(currentFocusMode);
  }

  document.body.classList.remove("mode-workflow", "mode-code", "mode-chat");
  document.body.classList.add(`mode-${mode}`);
  setActiveFocusButton(mode);
  const modeState = loadFocusModeState(mode);
  applyFocusModeState(modeState);
  currentFocusMode = mode;
  if (persist) patchPreferences({ mode });
  saveFocusModeState(mode);
  if (shouldRecord && previousMode !== mode) {
    pushHistoryAction({
      type: "mode_change",
      before: { mode: previousMode },
      after: { mode },
    });
  }
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

function currentRoleModels() {
  return {
    planner: els.rmPlannerEl.value,
    coder: els.rmCoderEl.value,
    tester: els.rmTesterEl.value,
    reviewer: els.rmReviewerEl.value,
    fixer: els.rmFixerEl.value,
  };
}

function applyRoleModels(roleModels) {
  if (!roleModels || typeof roleModels !== "object") return;
  if (roleModels.planner) els.rmPlannerEl.value = String(roleModels.planner);
  if (roleModels.coder) els.rmCoderEl.value = String(roleModels.coder);
  if (roleModels.tester) els.rmTesterEl.value = String(roleModels.tester);
  if (roleModels.reviewer) els.rmReviewerEl.value = String(roleModels.reviewer);
  if (roleModels.fixer) els.rmFixerEl.value = String(roleModels.fixer);
}

function normalizeBudgetValue(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return Math.round(n * 100) / 100;
}

function getCurrentSettingsSnapshot() {
  return {
    model: String(els.modelSelect.value || ""),
    mode: String(els.modeSelect.value || ""),
    access: String(els.accessSelect.value || ""),
    planMode: !!els.planModeEl.checked,
    multiAgent: !!els.multiAgentEl.checked,
    budget: normalizeBudgetValue(els.budgetInputEl.value),
    roleModels: currentRoleModels(),
  };
}

function isSameProfileSettings(settings, snapshot) {
  const budgetA = normalizeBudgetValue(settings?.budget);
  const budgetB = normalizeBudgetValue(snapshot?.budget);
  const rolesA = settings?.roleModels || {};
  const rolesB = snapshot?.roleModels || {};
  return (
    String(settings?.model || "") === String(snapshot?.model || "") &&
    String(settings?.mode || "") === String(snapshot?.mode || "") &&
    String(settings?.access || "") === String(snapshot?.access || "") &&
    !!settings?.planMode === !!snapshot?.planMode &&
    !!settings?.multiAgent === !!snapshot?.multiAgent &&
    budgetA === budgetB &&
    String(rolesA.planner || "") === String(rolesB.planner || "") &&
    String(rolesA.coder || "") === String(rolesB.coder || "") &&
    String(rolesA.tester || "") === String(rolesB.tester || "") &&
    String(rolesA.reviewer || "") === String(rolesB.reviewer || "") &&
    String(rolesA.fixer || "") === String(rolesB.fixer || "")
  );
}

function updateProfileUi(profileKey) {
  const key = PROFILE_DEFS[profileKey] ? profileKey : "custom";
  if (els.profileSelect) els.profileSelect.value = key;
  if (els.profileStateEl) {
    const label = PROFILE_DEFS[key]?.label || "Custom";
    els.profileStateEl.textContent = label;
  }
}

function syncProfileStateFromCurrentSettings() {
  if (suspendProfileSync) return;
  const snapshot = getCurrentSettingsSnapshot();
  for (const [key, profile] of Object.entries(PROFILE_DEFS)) {
    if (isSameProfileSettings(profile.settings, snapshot)) {
      setStored(PROFILE_KEY, key);
      updateProfileUi(key);
      return;
    }
  }
  setStored(PROFILE_KEY, "custom");
  updateProfileUi("custom");
}

function applyProfile(profileKey) {
  const profile = PROFILE_DEFS[profileKey];
  if (!profile) {
    updateProfileUi("custom");
    return;
  }
  const settings = profile.settings;
  suspendProfileSync = true;
  try {
    els.modelSelect.value = settings.model;
    els.modeSelect.value = settings.mode;
    els.accessSelect.value = settings.access;
    els.planModeEl.checked = !!settings.planMode;
    els.multiAgentEl.checked = !!settings.multiAgent;
    els.budgetInputEl.value = String(settings.budget);
    applyRoleModels(settings.roleModels);
    setStored(MODEL_KEY, els.modelSelect.value);
    setStored(MODE_KEY, els.modeSelect.value);
    setStored(ACCESS_KEY, els.accessSelect.value);
    setStored(PLAN_KEY, els.planModeEl.checked ? "1" : "0");
    setStored(PROFILE_KEY, profileKey);
    updateProfileUi(profileKey);
  } finally {
    suspendProfileSync = false;
  }
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

  els.modelSelect.addEventListener("change", () => {
    setStored(MODEL_KEY, els.modelSelect.value);
    syncProfileStateFromCurrentSettings();
  });
  els.modeSelect.addEventListener("change", () => {
    setStored(MODE_KEY, els.modeSelect.value);
    syncProfileStateFromCurrentSettings();
  });
  els.accessSelect.addEventListener("change", () => {
    setStored(ACCESS_KEY, els.accessSelect.value);
    syncProfileStateFromCurrentSettings();
  });
  els.planModeEl.addEventListener("change", () => {
    setStored(PLAN_KEY, els.planModeEl.checked ? "1" : "0");
    syncProfileStateFromCurrentSettings();
  });
  if (els.profileSelect) {
    els.profileSelect.addEventListener("change", () => {
      const key = String(els.profileSelect.value || "custom");
      if (key === "custom") {
        setStored(PROFILE_KEY, "custom");
        updateProfileUi("custom");
        return;
      }
      applyProfile(key);
    });
  }
  if (els.multiAgentEl) {
    els.multiAgentEl.addEventListener("change", syncProfileStateFromCurrentSettings);
  }
  if (els.budgetInputEl) {
    els.budgetInputEl.addEventListener("input", syncProfileStateFromCurrentSettings);
    els.budgetInputEl.addEventListener("change", syncProfileStateFromCurrentSettings);
  }
  [els.rmPlannerEl, els.rmCoderEl, els.rmTesterEl, els.rmReviewerEl, els.rmFixerEl].forEach((el) => {
    if (!el) return;
    el.addEventListener("change", syncProfileStateFromCurrentSettings);
  });

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
  if (els.toggleSettingsBtn) {
    els.toggleSettingsBtn.addEventListener("click", () => {
      setPanelCollapsed("settings", false, true);
      if (currentFocusMode) saveFocusModeState(currentFocusMode);
      const panel = document.getElementById("settings-panel");
      if (panel instanceof HTMLElement) panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
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
  const isFirstLoadWithoutPreferences = !localStorage.getItem(UI_PREFS_KEY);
  migrateLegacyPreferencesIfNeeded();
  els.tokenInput.value = getToken();
  els.modelSelect.value = getStored(MODEL_KEY, "gpt-5.4-mini");
  els.modeSelect.value = getStored(MODE_KEY, "Chat");
  els.accessSelect.value = getStored(ACCESS_KEY, "Nur lesen");
  els.planModeEl.checked = getStored(PLAN_KEY, "0") === "1";
  const storedProfile = getStored(PROFILE_KEY, "custom");

  setSelectedFile("");
  autoResizeTextarea();
  renderAttachments();
  initCollapsibles();
  initResizablePanels();
  bindEvents();
  bindShortcutHelpOverlay();
  bindKeyboardShortcuts();
  bindOnboardingHint(isFirstLoadWithoutPreferences);
  applyFocusMode(readPreferences().mode || "workflow", false);
  applySummaryDetailExpansion();
  const prefs = readPreferences();
  if (els.messagesEl && prefs.session?.scrollTop) {
    els.messagesEl.scrollTop = Number(prefs.session.scrollTop) || 0;
  }
  if (prefs.session?.lastRunId) patchPreferences({ session: { lastRunId: prefs.session.lastRunId } });
  if (PROFILE_DEFS[storedProfile]) {
    applyProfile(storedProfile);
  } else {
    updateProfileUi("custom");
    syncProfileStateFromCurrentSettings();
  }
  addMessage("assistant", "CodeYZ UI bereit.");
  if (prefs.session?.lastRunId) showToast("Session restored");
  if (!prefs.session?.lastRunId) scrollChatToBottom();
  void refreshPanels();
}
