export const TOKEN_KEY = "codeyz_local_token";
export const MODEL_KEY = "codeyz_model";
export const MODE_KEY = "codeyz_mode";
export const ACCESS_KEY = "codeyz_access";
export const PLAN_KEY = "codeyz_plan_mode";

export const state = {
  sessionId: null,
  selectedFile: "",
  currentProject: "",
  treeData: null,
  attachments: [],
  pinnedFiles: [],
  selectedRollbackId: "",
  collapsedDirs: new Set(),
};

export const els = {
  messagesEl: document.getElementById("messages"),
  formEl: document.getElementById("chat-form"),
  inputEl: document.getElementById("message-input"),
  statusEl: document.getElementById("status"),
  attachmentsEl: document.getElementById("attachments"),

  newChatBtn: document.getElementById("new-chat"),
  addProjectBtn: document.getElementById("add-project"),
  sendBtn: document.getElementById("send-btn"),
  autoBtn: document.getElementById("auto-btn"),
  toggleExplorerBtn: document.getElementById("toggle-explorer"),
  pinSelectedBtn: document.getElementById("pin-selected"),
  previewPinBtn: document.getElementById("preview-pin"),

  runsListEl: document.getElementById("runs-list"),
  runReplayContentEl: document.getElementById("run-replay-content"),
  tdSearchEl: document.getElementById("td-search"),
  tdFilesEl: document.getElementById("td-files"),
  tdTestsEl: document.getElementById("td-tests"),
  tdPluginsEl: document.getElementById("td-plugins"),
  tdReasoningEl: document.getElementById("td-reasoning"),
  rollbackListEl: document.getElementById("rollback-list"),
  rollbackDetailEl: document.getElementById("rollback-detail"),
  rollbackApplyBtn: document.getElementById("rollback-apply"),

  modelSelect: document.getElementById("model-select"),
  modeSelect: document.getElementById("mode-select"),
  accessSelect: document.getElementById("access-select"),
  planModeEl: document.getElementById("plan-mode"),
  multiAgentEl: document.getElementById("multi-agent"),
  budgetInputEl: document.getElementById("budget-input"),
  contextCostEl: document.getElementById("context-cost"),
  rmPlannerEl: document.getElementById("rm-planner"),
  rmCoderEl: document.getElementById("rm-coder"),
  rmTesterEl: document.getElementById("rm-tester"),
  rmReviewerEl: document.getElementById("rm-reviewer"),
  rmFixerEl: document.getElementById("rm-fixer"),
  attachBtn: document.getElementById("attach-btn"),
  fileInputEl: document.getElementById("file-input"),
  contextProjectEl: document.getElementById("context-project"),
  contextSelectedFileEl: document.getElementById("context-selected-file"),
  contextPinnedEl: document.getElementById("context-pinned"),

  tokenInput: document.getElementById("token-input"),
  saveTokenBtn: document.getElementById("save-token"),
  clearTokenBtn: document.getElementById("clear-token"),

  currentProjectEl: document.getElementById("current-project"),
  explorerWorkspaceEl: document.getElementById("explorer-workspace"),
  explorerEl: document.getElementById("explorer"),
  filterEl: document.getElementById("file-filter"),
  previewEl: document.getElementById("file-preview"),
  selectedFileEl: document.getElementById("selected-file"),
  pinnedCountEl: document.getElementById("pinned-count"),
  pinnedListEl: document.getElementById("pinned-list"),
  pluginsListEl: document.getElementById("plugins-list"),
  searchInputEl: document.getElementById("search-input"),
  searchBuildBtn: document.getElementById("search-build"),
  searchResultsEl: document.getElementById("search-results"),
  systemStatusEl: document.getElementById("system-status"),
  uiVersionEl: document.getElementById("ui-version"),
};

export function scrollChatToBottom() {
  els.messagesEl.scrollTop = els.messagesEl.scrollHeight;
}

export function getComposerState() {
  return {
    selectedModel: els.modelSelect.value,
    selectedMode: els.modeSelect.value,
    accessLevel: els.accessSelect.value,
    planMode: els.planModeEl.checked,
    maxCostUsd: els.budgetInputEl.value ? Number(els.budgetInputEl.value) : null,
    roleModels: {
      planner: els.rmPlannerEl.value,
      coder: els.rmCoderEl.value,
      tester: els.rmTesterEl.value,
      reviewer: els.rmReviewerEl.value,
      fixer: els.rmFixerEl.value,
    },
    attachments: state.attachments.map((f) => ({ name: f.name, size: f.size, type: f.type || "unknown" })),
  };
}
