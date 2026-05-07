import { apiGet, apiPost } from "./api.js";
import { formatTimelineEvent } from "./event_format.js";
import { els, state } from "./state.js";
import {
  buildDecisionExplanation,
  buildReplayNavigation,
  collectDiffFilesFromEvents,
  extractApprovalActions,
  groupReplaySections,
  normalizeReplayEvents,
} from "./timeline_helpers.js";

const PHASE_KEYS = ["task", "plan", "patch", "tests", "diff", "approval"];
const PHASE_EVENT_MAP = {
  plan: ["plan"],
  patch: ["diff", "approval_required", "approval_applied"],
  tests: ["test"],
  diff: ["diff"],
};
const PHASE_LABELS = {
  created: "Created",
  planning: "Planning",
  analyzing: "Analyzing",
  tool_selection: "Selecting tools",
  patching: "Generating patch",
  testing: "Running tests",
  approval_required: "Waiting for approval",
  applying: "Applying patch",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
  unknown: "Unknown",
};
let lastRenderedRunIds = "";
const RUN_ROW_HEIGHT = 30;
const RUN_BUFFER = 6;
const UI_PREFS_KEY = "codeyz_ui_preferences";
let allRuns = [];
let visibleRange = { start: -1, end: -1 };
let pendingVirtualFrame = 0;
let currentDiffFiles = [];
let selectedDiffFile = "";
let selectedResumeCheckpointId = "";
let selectedResumeTargetPhase = "";
let pendingResumeValidationToken = 0;
const GROUP_WINDOW_MS = 12_000;
const GROUP_LABELS = {
  test: "Test Events",
  diff: "Patch Updates",
  approval_required: "Approval Checks",
  approval_applied: "Approval Applies",
  plan: "Plan Events",
  analyze: "Task Events",
  build: "Build Events",
  tool_decision: "Tool Decisions",
  policy_warning: "Policy Warnings",
  policy_block: "Policy Blocks",
  policy_approval_required: "Policy Approvals",
  resume_phase_requested: "Resume Requests",
  resume_phase_started: "Resume Starts",
  resume_phase_completed: "Resume Completions",
  resume_phase_failed: "Resume Failures",
  error: "Errors",
};

function readPrefs() {
  const raw = localStorage.getItem(UI_PREFS_KEY);
  if (!raw) return {};
  try {
    return JSON.parse(raw) || {};
  } catch {
    return {};
  }
}

function writePrefs(patch) {
  const current = readPrefs();
  const next = {
    ...current,
    ...patch,
    session: { ...(current.session || {}), ...(patch.session || {}) },
    lastUpdated: Date.now(),
  };
  localStorage.setItem(UI_PREFS_KEY, JSON.stringify(next));
}

function setPhaseBadge(el, status) {
  if (!el) return;
  const safe = ["pending", "running", "done", "failed", "skipped"].includes(status) ? status : "pending";
  el.textContent = safe;
  el.className = `phase-badge ${safe}`;
}

function deriveWorkflowStatus(detail) {
  const status = {
    task: "pending",
    plan: "pending",
    patch: "pending",
    tests: "pending",
    diff: "pending",
    approval: "pending",
  };
  const runStatus = detail && detail.status ? String(detail.status) : "idle";
  const events = Array.isArray(detail && detail.events) ? detail.events : [];

  if (detail && detail.run_id) status.task = "running";
  if (events.length > 0) status.task = "done";

  for (const event of events) {
    const type = event && event.event_type ? event.event_type : "";
    const data = event && event.data ? event.data : {};
    if ((PHASE_EVENT_MAP.plan || []).includes(type)) status.plan = "done";
    if ((PHASE_EVENT_MAP.patch || []).includes(type)) status.patch = "done";
    if ((PHASE_EVENT_MAP.diff || []).includes(type)) status.diff = "done";

    if (type === "test") {
      const output = String(data && data.output ? data.output : "").toLowerCase();
      if (typeof data.ok === "boolean") status.tests = data.ok ? "done" : "failed";
      else if (output.includes("not permitted")) status.tests = "skipped";
      else status.tests = "done";
    }

    if (type === "approval_required") status.approval = "running";
    if (type === "approval_applied") status.approval = "done";
  }

  if (runStatus === "failed") {
    for (const key of PHASE_KEYS) {
      if (status[key] === "running") status[key] = "failed";
    }
    if (status.tests === "pending" && status.patch === "done") status.tests = "failed";
  }

  if (runStatus === "done") {
    if (status.task === "running") status.task = "done";
    if (status.approval === "pending") status.approval = "skipped";
    if (status.tests === "pending") status.tests = "skipped";
  }

  if (runStatus === "running") {
    if (status.plan === "pending") status.plan = "running";
    else if (status.patch === "pending") status.patch = "running";
    else if (status.tests === "pending") status.tests = "running";
  }

  return status;
}

function deriveRunSummary(detail) {
  const events = Array.isArray(detail && detail.events) ? detail.events : [];
  const runStatus = detail && detail.status ? String(detail.status) : "unknown";
  const taskRaw = detail && detail.task ? String(detail.task).trim() : "";
  const task = taskRaw ? taskRaw.slice(0, 72) : "No task";

  const diffEvents = events.filter((e) => e && e.event_type === "diff");
  const patchFiles = new Set();
  for (const ev of diffEvents) {
    const data = ev && ev.data ? ev.data : {};
    if (data && data.file) patchFiles.add(String(data.file));
    const title = ev && ev.title ? String(ev.title) : "";
    const marker = "diff ";
    const idx = title.lastIndexOf(marker);
    if (idx >= 0) {
      const candidate = title.slice(idx + marker.length).trim();
      if (candidate) patchFiles.add(candidate);
    }
  }
  const patch = patchFiles.size > 0 ? `${patchFiles.size} file${patchFiles.size === 1 ? "" : "s"} changed` : "unknown";

  const testEvents = events.filter((e) => e && e.event_type === "test");
  let tests = "unknown";
  for (let i = testEvents.length - 1; i >= 0; i -= 1) {
    const data = testEvents[i] && testEvents[i].data ? testEvents[i].data : {};
    const output = String(data && data.output ? data.output : "");
    if (typeof data.ok === "boolean") {
      tests = data.ok ? "passed" : "failed";
      break;
    }
    if (output.toLowerCase().includes("not permitted")) {
      tests = "skipped";
      break;
    }
  }

  const riskEvents = events.filter((e) => e && e.event_type === "approval_required");
  let risk = "unknown";
  if (riskEvents.length > 0) {
    const levels = riskEvents.map((e) => String(e?.data?.risk_level || "unknown"));
    if (levels.includes("high")) risk = "high";
    else if (levels.includes("medium")) risk = "medium";
    else if (levels.includes("low")) risk = "low";
  }

  const approvalRequired = riskEvents.length > 0;
  const approvalApplied = events.some((e) => e && e.event_type === "approval_applied");
  let decision = "unknown";
  if (runStatus === "running") decision = "running";
  else if (runStatus === "failed") decision = "failed";
  else if (approvalRequired && !approvalApplied) decision = "ready for approval";
  else if (tests === "failed") decision = "needs revision";

  return { task, patch, tests, risk, decision };
}

function renderRunSummary(detail) {
  const summary = deriveRunSummary(detail);
  if (els.wfSummaryTaskEl) els.wfSummaryTaskEl.textContent = summary.task;
  if (els.wfSummaryPatchEl) els.wfSummaryPatchEl.textContent = summary.patch;
  if (els.wfSummaryTestsEl) els.wfSummaryTestsEl.textContent = summary.tests;
  if (els.wfSummaryRiskEl) els.wfSummaryRiskEl.textContent = summary.risk;
  if (els.wfSummaryDecisionEl) els.wfSummaryDecisionEl.textContent = summary.decision;
}

function renderWorkflowCard(detail) {
  const runLabel = detail && detail.run_id
    ? `${detail.status || "running"} · ${detail.run_id.slice(0, 8)}`
    : "Kein Run ausgewählt";
  if (els.workflowRunStateEl) els.workflowRunStateEl.textContent = runLabel;

  const wf = deriveWorkflowStatus(detail);
  setPhaseBadge(els.wfTaskEl, wf.task);
  setPhaseBadge(els.wfPlanEl, wf.plan);
  setPhaseBadge(els.wfPatchEl, wf.patch);
  setPhaseBadge(els.wfTestsEl, wf.tests);
  setPhaseBadge(els.wfDiffEl, wf.diff);
  setPhaseBadge(els.wfApprovalEl, wf.approval);
  renderRunSummary(detail);
}

function setDecisionBadge(el, enabled) {
  if (!el) return;
  el.textContent = enabled ? "enabled" : "disabled";
  el.classList.toggle("enabled", !!enabled);
  el.classList.toggle("disabled", !enabled);
}

export function renderToolDecision(events) {
  const event = (events || []).find((e) => e.event_type === "tool_decision");
  const data = event && event.data ? event.data : {};
  setDecisionBadge(els.tdSearchEl, !!data.use_search);
  setDecisionBadge(els.tdFilesEl, !!data.use_files);
  setDecisionBadge(els.tdTestsEl, !!data.use_tests);
  setDecisionBadge(els.tdPluginsEl, !!data.use_plugins);
  els.tdReasoningEl.textContent = data.reasoning || "Keine Tool-Entscheidung für diesen Run.";
}

function renderDiffHunks(fileEntry) {
  if (!els.diffHunksEl) return;
  els.diffHunksEl.innerHTML = "";
  if (!fileEntry || !Array.isArray(fileEntry.hunks) || fileEntry.hunks.length === 0) {
    const empty = document.createElement("div");
    empty.className = "event-group-empty";
    empty.textContent = "Keine Diff-Hunks verfügbar.";
    els.diffHunksEl.appendChild(empty);
    return;
  }

  for (const hunk of fileEntry.hunks) {
    const block = document.createElement("div");
    block.className = "diff-hunk";

    const header = document.createElement("div");
    header.className = "diff-hunk-header";
    header.textContent = hunk.header || "@@";
    block.appendChild(header);

    const lines = document.createElement("div");
    lines.className = "diff-lines";
    for (const line of hunk.lines || []) {
      const row = document.createElement("div");
      row.className = `diff-line ${line.type || "context"}`;
      row.textContent = String(line.text || "");
      lines.appendChild(row);
    }
    block.appendChild(lines);
    els.diffHunksEl.appendChild(block);
  }
}

function renderDiffViewer(events) {
  if (!els.diffFilesListEl || !els.diffFileMetaEl || !els.diffHunksEl) return;
  currentDiffFiles = collectDiffFilesFromEvents(events || []);
  els.diffFilesListEl.innerHTML = "";

  if (currentDiffFiles.length === 0) {
    selectedDiffFile = "";
    els.diffFileMetaEl.textContent = "Keine Patch-Dateien für diesen Run.";
    renderDiffHunks(null);
    return;
  }

  const hasSelected = currentDiffFiles.some((entry) => entry.file === selectedDiffFile);
  if (!hasSelected) selectedDiffFile = currentDiffFiles[0].file;

  for (const entry of currentDiffFiles) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `diff-file-btn status-${entry.status || "modified"}${entry.file === selectedDiffFile ? " active" : ""}`;
    btn.textContent = `${entry.file} (${entry.status || "modified"})`;
    btn.addEventListener("click", () => {
      selectedDiffFile = entry.file;
      renderDiffViewer(events);
    });
    els.diffFilesListEl.appendChild(btn);
  }

  const selected = currentDiffFiles.find((entry) => entry.file === selectedDiffFile) || currentDiffFiles[0];
  const hunkCount = Number(selected.hunksCount || (Array.isArray(selected.hunks) ? selected.hunks.length : 0)) || 0;
  const add = Number(selected.addedLines || 0) || 0;
  const rem = Number(selected.removedLines || 0) || 0;
  els.diffFileMetaEl.textContent = `Datei: ${selected.file} | Status: ${selected.status || "unknown"} | Hunks: ${hunkCount} | +${add}/-${rem}`;
  renderDiffHunks(selected);
}

function formatDuration(durationMs) {
  const n = Number(durationMs || 0);
  if (!Number.isFinite(n) || n <= 0) return "0s";
  const totalSec = Math.floor(n / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  if (min <= 0) return `${sec}s`;
  return `${min}m ${sec}s`;
}

function normalizePhase(rawPhase) {
  const phase = String(rawPhase || "").trim().toLowerCase();
  return PHASE_LABELS[phase] ? phase : "unknown";
}

function derivePhase(detail) {
  const explicit = normalizePhase(detail?.phase);
  if (explicit !== "unknown") return explicit;
  const metricsPhase = normalizePhase(detail?.metrics?.current_phase);
  if (metricsPhase !== "unknown") return metricsPhase;
  const status = String(detail?.status || "").toLowerCase();
  if (status === "done") return "completed";
  if (status === "failed" || status === "blocked" || status === "budget_blocked") return "failed";
  if (status === "cancelled" || status === "canceled") return "cancelled";
  return "unknown";
}

function renderCurrentAction(detail) {
  if (!els.currentActionSummaryEl) return;
  const metrics = detail && typeof detail.metrics === "object" ? detail.metrics : {};
  const phase = derivePhase(detail);
  const action = PHASE_LABELS[phase] || PHASE_LABELS.unknown;
  const rows = [
    ["Action", action],
    ["Phase", phase],
    ["Elapsed", formatDuration(metrics.duration_ms)],
    ["Files changed", metrics.files_changed_count ?? "0"],
    ["Risk", metrics.risk_level_summary || "unknown"],
    ["Status", metrics.final_status || detail?.status || "unknown"],
  ];
  els.currentActionSummaryEl.innerHTML = "";
  for (const [key, value] of rows) {
    const k = document.createElement("span");
    k.className = "run-metric-key";
    k.textContent = `${key}:`;
    const v = document.createElement("span");
    v.className = "run-metric-value";
    v.textContent = String(value ?? "-");
    els.currentActionSummaryEl.appendChild(k);
    els.currentActionSummaryEl.appendChild(v);
  }
}

function renderResumePanel(detail) {
  if (!els.resumeSummaryEl) return;
  const resume = detail && typeof detail.resume_state === "object" ? detail.resume_state : {};
  const rows = [
    ["State", resume.state || "unknown"],
    ["Candidate", resume.resume_candidate ? "yes" : "no"],
    ["Phase", resume.resumable_phase || "unknown"],
    ["Checkpoint", resume.latest_checkpoint_id ? String(resume.latest_checkpoint_id).slice(0, 8) : "-"],
    ["Reason", resume.reason || "-"],
    ["Pending approvals", Array.isArray(resume.pending_approvals) ? resume.pending_approvals.length : 0],
  ];
  els.resumeSummaryEl.innerHTML = "";
  for (const [k, v] of rows) {
    const keyEl = document.createElement("span");
    keyEl.className = "run-metric-key";
    keyEl.textContent = `${k}:`;
    const valEl = document.createElement("span");
    valEl.className = "run-metric-value";
    valEl.textContent = String(v);
    els.resumeSummaryEl.appendChild(keyEl);
    els.resumeSummaryEl.appendChild(valEl);
  }
  renderResumeSelectors(detail, resume);
  void refreshResumeValidationPreview(detail);
}

function populateSelectOptions(selectEl, options, selectedValue, emptyLabel) {
  if (!selectEl) return;
  selectEl.innerHTML = "";
  const safeOptions = Array.isArray(options) ? options : [];
  if (safeOptions.length === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = emptyLabel;
    selectEl.appendChild(opt);
    selectEl.disabled = true;
    return;
  }
  selectEl.disabled = false;
  for (const option of safeOptions) {
    const opt = document.createElement("option");
    opt.value = String(option.value || "");
    opt.textContent = String(option.label || option.value || "-");
    if (String(opt.value) === String(selectedValue || "")) opt.selected = true;
    selectEl.appendChild(opt);
  }
}

function renderResumeSelectors(detail, resume) {
  const checkpoints = Array.isArray(detail?.checkpoints) ? detail.checkpoints : [];
  const selectedRun = String(detail?.run_id || "");
  const defaultCheckpoint =
    selectedRun && state.selectedRunId === selectedRun && selectedResumeCheckpointId
      ? selectedResumeCheckpointId
      : String(resume.latest_checkpoint_id || "");
  const checkpointOptions = checkpoints.map((cp) => {
    const checkpointId = String(cp?.checkpoint_id || "");
    const shortId = checkpointId ? checkpointId.slice(0, 8) : "-";
    const phase = String(cp?.phase || "unknown");
    const seq = Number(cp?.sequence || 0);
    const reason = String(cp?.reason || cp?.current_action || "-");
    const pendingApprovals = Array.isArray(cp?.pending_approvals) ? cp.pending_approvals.length : 0;
    const candidate = cp?.resume_candidate ? "candidate" : "non-candidate";
    return {
      value: checkpointId,
      label: `${shortId} · phase=${phase} · seq=${seq} · approvals=${pendingApprovals} · ${candidate} · ${reason}`,
    };
  });
  selectedResumeCheckpointId = defaultCheckpoint;
  populateSelectOptions(els.resumeCheckpointSelectEl, checkpointOptions, selectedResumeCheckpointId, "Keine Checkpoints");
  if (els.resumeCheckpointSelectEl && els.resumeCheckpointSelectEl.value) {
    selectedResumeCheckpointId = els.resumeCheckpointSelectEl.value;
  }

  const transition = resume && typeof resume.transition === "object" ? resume.transition : {};
  const defaultTarget = transition.target_phase || resume.resumable_phase || "";
  if (!selectedResumeTargetPhase || selectedRun !== state.selectedRunId) {
    selectedResumeTargetPhase = String(defaultTarget || "");
  }
  const targetOptions = [];
  if (defaultTarget) {
    const source = String(transition.source_phase || resume.resumable_phase || "unknown");
    const executor = String(transition.executor || "unknown_executor");
    const allowed = transition.allowed === false ? "blocked" : "allowed";
    targetOptions.push({
      value: String(defaultTarget),
      label: `${source} -> ${defaultTarget} · ${executor} · ${allowed}`,
    });
  }
  populateSelectOptions(els.resumeTargetPhaseSelectEl, targetOptions, selectedResumeTargetPhase, "Keine Zielphase");
  if (els.resumeTargetPhaseSelectEl && els.resumeTargetPhaseSelectEl.value) {
    selectedResumeTargetPhase = els.resumeTargetPhaseSelectEl.value;
  }
}

async function fetchResumeValidation(runId) {
  const params = new URLSearchParams();
  if (selectedResumeCheckpointId) params.set("checkpoint_id", selectedResumeCheckpointId);
  if (selectedResumeTargetPhase) params.set("target_phase", selectedResumeTargetPhase);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const payload = await apiGet(`/task/runs/${encodeURIComponent(runId)}/resume-validation${suffix}`);
  return payload && typeof payload.validation === "object" ? payload.validation : {};
}

function renderResumeValidation(validation) {
  if (!els.resumeValidationPreviewEl) return;
  const rows = [
    ["Allowed", validation?.allowed ? "yes" : "no"],
    ["Transition", validation?.transition || "-"],
    ["Phase executor", validation?.phase_executor || "-"],
    ["Attempts", `${validation?.attempts_used ?? 0}/${validation?.attempts_limit ?? 0}`],
    ["Resume state", validation?.resume_state || "unknown"],
    ["Policy", validation?.policy_summary || "-"],
    ["Reasons", Array.isArray(validation?.reasons) ? validation.reasons.join(", ") || "-" : "-"],
    ["Blocking", Array.isArray(validation?.blocking_conditions) ? validation.blocking_conditions.join(", ") || "-" : "-"],
    ["Required actions", Array.isArray(validation?.required_actions) ? validation.required_actions.join(", ") || "-" : "-"],
  ];
  els.resumeValidationPreviewEl.innerHTML = "";
  for (const [k, v] of rows) {
    const keyEl = document.createElement("span");
    keyEl.className = "run-metric-key";
    keyEl.textContent = `${k}:`;
    const valEl = document.createElement("span");
    valEl.className = "run-metric-value";
    valEl.textContent = String(v);
    els.resumeValidationPreviewEl.appendChild(keyEl);
    els.resumeValidationPreviewEl.appendChild(valEl);
  }
}

function renderResumeBlockedExplanation(validation) {
  if (!els.resumeBlockedExplanationEl) return;
  const blocks = Array.isArray(validation?.blocking_conditions) ? validation.blocking_conditions : [];
  const actions = Array.isArray(validation?.required_actions) ? validation.required_actions : [];
  if (validation?.allowed) {
    els.resumeBlockedExplanationEl.className = "event-group-empty";
    els.resumeBlockedExplanationEl.textContent = "Resume erlaubt.";
    return;
  }
  const items = [];
  for (const block of blocks) items.push(`blocked: ${block}`);
  for (const action of actions) items.push(`required: ${action}`);
  els.resumeBlockedExplanationEl.className = "event-group-empty";
  els.resumeBlockedExplanationEl.textContent = items.length > 0 ? items.join(" | ") : "Resume blockiert.";
}

function renderResumeValidationError(error) {
  if (els.resumeValidationPreviewEl) {
    els.resumeValidationPreviewEl.textContent = "Validation konnte nicht geladen werden.";
  }
  if (els.resumeBlockedExplanationEl) {
    els.resumeBlockedExplanationEl.textContent = `Validation error: ${String(error?.message || error || "unknown")}`;
  }
  if (els.resumeRunBtn) {
    els.resumeRunBtn.disabled = true;
  }
}

async function refreshResumeValidationPreview(detail) {
  const runId = String(detail?.run_id || "");
  if (!runId) return;
  const token = ++pendingResumeValidationToken;
  try {
    const validation = await fetchResumeValidation(runId);
    if (token !== pendingResumeValidationToken) return;
    renderResumeValidation(validation);
    renderResumeBlockedExplanation(validation);
    if (els.resumeRunBtn) {
      els.resumeRunBtn.disabled = !validation.allowed;
    }
  } catch (error) {
    if (token !== pendingResumeValidationToken) return;
    renderResumeValidationError(error);
  }
}

function renderRunMetrics(detail) {
  if (!els.runMetricsSummaryEl) return;
  const metrics = detail && typeof detail.metrics === "object" ? detail.metrics : {};
  const rows = [
    ["Duration", formatDuration(metrics.duration_ms)],
    ["Files changed", metrics.files_changed_count ?? "0"],
    ["Added lines", metrics.added_lines ?? "0"],
    ["Removed lines", metrics.removed_lines ?? "0"],
    ["Hunks", metrics.hunks_count ?? "0"],
    ["Risk", metrics.risk_level_summary || "unknown"],
    ["Approvals", `${metrics.approvals_applied ?? 0}/${metrics.approvals_requested ?? 0}`],
    ["Patches applied", metrics.patches_applied ?? "0"],
    ["Policy warnings", metrics.policy_warnings_count ?? "0"],
    ["Policy violations", metrics.policy_violations_count ?? "0"],
    ["Blocked actions", metrics.blocked_actions_count ?? "0"],
    ["Constraint evals", metrics.constraint_evaluations ?? "0"],
    ["Approval triggers", metrics.approval_triggers ?? "0"],
    ["Runtime limit hits", metrics.runtime_limit_hits ?? "0"],
    ["Checkpoints", metrics.checkpoints_created ?? "0"],
    ["Resume candidates", metrics.resume_candidates ?? "0"],
    ["Approval waitpoints", metrics.approval_waitpoints ?? "0"],
    ["Resume phase attempts", metrics.resume_phase_attempts ?? "0"],
    ["Resume phase failures", metrics.resume_phase_failures ?? "0"],
    ["Resume transition rejects", metrics.resume_transition_rejections ?? "0"],
    ["Retry limit hits", metrics.retry_limit_hits ?? "0"],
    ["Status", metrics.final_status || detail?.status || "unknown"],
    ["Profile", metrics.profile || detail?.profile || "custom"],
    ["Resume state", detail?.resume_state?.state || "unknown"],
  ];
  els.runMetricsSummaryEl.innerHTML = "";
  for (const [key, value] of rows) {
    const k = document.createElement("span");
    k.className = "run-metric-key";
    k.textContent = `${key}:`;
    const v = document.createElement("span");
    v.className = "run-metric-value";
    v.textContent = String(value ?? "-");
    els.runMetricsSummaryEl.appendChild(k);
    els.runMetricsSummaryEl.appendChild(v);
  }
}

function formatEventTime(ts) {
  if (!ts) return "--:--:--";
  const date = new Date(String(ts));
  if (Number.isNaN(date.getTime())) return "--:--:--";
  return date.toLocaleTimeString([], { hour12: false });
}

function renderReplayNavigation(events, detail) {
  if (!els.replayNavSummaryEl) return;
  const nav = buildReplayNavigation(events || []);
  const replay = detail && typeof detail.replay === "object" ? detail.replay : {};
  const rows = [
    ["Events", nav.totalEvents ?? 0],
    ["First seq", nav.firstSequence ?? 0],
    ["Last seq", nav.lastSequence ?? 0],
    ["Sections", Array.isArray(nav.sections) ? nav.sections.length : 0],
    ["Checkpoints", Array.isArray(replay.checkpoints) ? replay.checkpoints.length : 0],
    ["Resume", detail?.resume_state?.state || "unknown"],
  ];
  els.replayNavSummaryEl.innerHTML = "";
  for (const [k, v] of rows) {
    const keyEl = document.createElement("span");
    keyEl.className = "run-metric-key";
    keyEl.textContent = `${k}:`;
    const valEl = document.createElement("span");
    valEl.className = "run-metric-value";
    valEl.textContent = String(v);
    els.replayNavSummaryEl.appendChild(keyEl);
    els.replayNavSummaryEl.appendChild(valEl);
  }
}

function renderReplayViewer(events, detail) {
  if (!els.runReplayViewerEl) return;
  els.runReplayViewerEl.innerHTML = "";
  const sections = groupReplaySections(events || []);
  if (!Array.isArray(sections) || sections.length === 0) {
    const empty = document.createElement("div");
    empty.className = "event-group-empty";
    empty.textContent = "Keine Replay-Schritte verfügbar.";
    els.runReplayViewerEl.appendChild(empty);
    return;
  }
  const replay = detail && typeof detail.replay === "object" ? detail.replay : {};
  const checkpointList = Array.isArray(replay.checkpoints) ? replay.checkpoints : [];
  for (const section of sections) {
    const details = document.createElement("details");
    details.className = "event-group";
    details.open = true;
    const summary = document.createElement("summary");
    summary.className = "event-group-summary";
    summary.textContent = `${section.phase} · seq ${section.startSequence}-${section.endSequence} (${section.events.length})`;
    details.appendChild(summary);
    const list = document.createElement("div");
    list.className = "event-group-items";
    for (const event of section.events || []) {
      const row = document.createElement("div");
      row.className = "event-group-item";
      const explanation = event.decision_explanation || buildDecisionExplanation(event);
      const title = `[${formatEventTime(event.ts)}] #${event.sequence} ${event.event_type} · ${String(explanation.severity || "info")}`;
      const reasonText = Array.isArray(explanation.reasons) && explanation.reasons.length > 0 ? `\nreasons: ${explanation.reasons.join(", ")}` : "";
      const snapshot = event.metrics_snapshot && typeof event.metrics_snapshot === "object"
        ? `\nmetrics: files=${event.metrics_snapshot.files_changed_count ?? 0} +${event.metrics_snapshot.added_lines ?? 0}/-${event.metrics_snapshot.removed_lines ?? 0}`
        : "";
      const cps = checkpointList.filter((cp) => Number(cp.sequence || 0) === Number(event.sequence || -1));
      const cpText = cps.length > 0 ? `\ncheckpoint: ${String(cps[0].checkpoint_id || "").slice(0, 8)} reason=${cps[0].reason || "-"}` : "";
      row.textContent = `${title}\n${event.title || ""}${reasonText}${snapshot}${cpText}`.trim();
      list.appendChild(row);
    }
    details.appendChild(list);
    els.runReplayViewerEl.appendChild(details);
  }
}

function renderAuditTrail(events) {
  if (!els.runAuditTrailEl) return;
  els.runAuditTrailEl.innerHTML = "";
  const normalized = normalizeReplayEvents(events || []);
  const relevant = normalized.filter((e) =>
    ["policy_warning", "policy_block", "policy_approval_required", "approval_required", "approval_applied"].includes(String(e.event_type || ""))
  );
  if (relevant.length === 0) {
    const empty = document.createElement("div");
    empty.className = "event-group-empty";
    empty.textContent = "Keine Audit-Entscheidungen verfügbar.";
    els.runAuditTrailEl.appendChild(empty);
    return;
  }
  for (const event of relevant) {
    const card = document.createElement("div");
    card.className = "event-group-single";
    const ex = event.decision_explanation || buildDecisionExplanation(event);
    const reasons = Array.isArray(ex.reasons) && ex.reasons.length > 0 ? ex.reasons.join(", ") : "none";
    const data = event.data && typeof event.data === "object" ? event.data : {};
    const resumeRef = data.resume_sequence ? ` | resume_seq: ${data.resume_sequence}` : "";
    const cpRef = data.checkpoint_before_approval ? ` | checkpoint: ${String(data.checkpoint_before_approval).slice(0, 8)}` : "";
    card.textContent = `#${event.sequence} ${ex.title} [${ex.severity}] | reasons: ${reasons}${resumeRef}${cpRef}`;
    els.runAuditTrailEl.appendChild(card);
  }
}

function renderReplay(detail) {
  const lines = [];
  lines.push(`Run: ${detail.run_id}`);
  lines.push(`Task: ${detail.task}`);
  lines.push(`Status: ${detail.status}`);
  lines.push(`Phase: ${derivePhase(detail)}`);
  lines.push(`Summary: ${detail.summary || "-"}`);
  if (detail.estimated_total_cost_usd !== undefined) {
    lines.push(`Estimated total cost: $${detail.estimated_total_cost_usd}`);
  }
  lines.push("Events:");
  for (const event of detail.events || []) {
    for (const row of formatTimelineEvent(event)) lines.push(row);
  }
  els.runReplayContentEl.textContent = lines.join("\n");
  const normalizedEvents = normalizeReplayEvents(detail.events || []);
  renderRunMetrics(detail);
  renderCurrentAction(detail);
  renderResumePanel(detail);
  renderReplayNavigation(normalizedEvents, detail);
  renderReplayViewer(normalizedEvents, detail);
  renderAuditTrail(normalizedEvents);
  renderDiffViewer(normalizedEvents);
  renderEventGroups(normalizedEvents);
}

async function resumeRun() {
  if (!state.selectedRunId) return;
  await apiPost(`/task/resume/${encodeURIComponent(state.selectedRunId)}`, {
    checkpoint_id: selectedResumeCheckpointId || null,
    target_phase: selectedResumeTargetPhase || null,
  });
  const detail = await apiGet(`/task/runs/${encodeURIComponent(state.selectedRunId)}`);
  renderWorkflowCard(detail);
  renderToolDecision(detail.events || []);
  renderApprovalActions(detail.events || []);
  renderReplay(detail);
}

function parseEventTimestampMs(event, fallbackIndex) {
  const sources = [event?.created_at, event?.timestamp, event?.time, event?.ts];
  for (const value of sources) {
    if (!value) continue;
    const ms = Date.parse(String(value));
    if (!Number.isNaN(ms)) return ms;
  }
  return fallbackIndex * GROUP_WINDOW_MS;
}

function toGroupLabel(eventType) {
  return GROUP_LABELS[eventType] || `${String(eventType || "unknown").replaceAll("_", " ")} events`;
}

function groupTimelineEvents(events) {
  const groups = [];
  for (let i = 0; i < events.length; i += 1) {
    const ev = events[i];
    const eventType = String(ev?.event_type || "unknown");
    const ts = parseEventTimestampMs(ev, i);
    const last = groups[groups.length - 1];
    if (last && last.eventType === eventType && ts - last.lastTs <= GROUP_WINDOW_MS) {
      last.events.push(ev);
      last.lastTs = ts;
    } else {
      groups.push({ eventType, firstTs: ts, lastTs: ts, events: [ev] });
    }
  }
  return groups;
}

function renderEventGroupDetails(container, group) {
  const list = document.createElement("div");
  list.className = "event-group-items";
  for (const event of group.events) {
    const item = document.createElement("pre");
    item.className = "event-group-item";
    item.textContent = formatTimelineEvent(event).join("\n");
    list.appendChild(item);
  }
  container.appendChild(list);
}

function renderEventGroups(events) {
  if (!els.runEventGroupsEl) return;
  els.runEventGroupsEl.innerHTML = "";
  if (!Array.isArray(events) || events.length === 0) {
    const empty = document.createElement("div");
    empty.className = "event-group-empty";
    empty.textContent = "No events";
    els.runEventGroupsEl.appendChild(empty);
    return;
  }
  const groups = groupTimelineEvents(events);
  for (const group of groups) {
    if (group.events.length === 1) {
      const single = document.createElement("pre");
      single.className = "event-group-item event-group-single";
      single.textContent = formatTimelineEvent(group.events[0]).join("\n");
      els.runEventGroupsEl.appendChild(single);
      continue;
    }

    const details = document.createElement("details");
    details.className = "event-group";
    const summary = document.createElement("summary");
    summary.className = "event-group-summary";
    summary.textContent = `${group.events.length} ${toGroupLabel(group.eventType)}`;
    details.appendChild(summary);
    renderEventGroupDetails(details, group);
    els.runEventGroupsEl.appendChild(details);
  }
}

async function openRun(runId) {
  state.selectedRunId = runId;
  const detail = await apiGet(`/task/runs/${encodeURIComponent(runId)}`);
  renderWorkflowCard(detail);
  renderToolDecision(detail.events || []);
  renderApprovalActions(detail.events || []);
  renderReplay(detail);
  if (els.resumeCheckpointSelectEl) {
    els.resumeCheckpointSelectEl.onchange = async () => {
      selectedResumeCheckpointId = String(els.resumeCheckpointSelectEl.value || "");
      await refreshResumeValidationPreview(detail);
    };
  }
  if (els.resumeTargetPhaseSelectEl) {
    els.resumeTargetPhaseSelectEl.onchange = async () => {
      selectedResumeTargetPhase = String(els.resumeTargetPhaseSelectEl.value || "");
      await refreshResumeValidationPreview(detail);
    };
  }
  if (els.resumeRunBtn) {
    els.resumeRunBtn.onclick = async () => {
      await resumeRun();
    };
  }
}

async function applyApprovedPatch(eventId) {
  if (!state.selectedRunId) return;
  await apiPost(`/task/runs/${encodeURIComponent(state.selectedRunId)}/approve-patch/${encodeURIComponent(eventId)}`, {});
  const detail = await apiGet(`/task/runs/${encodeURIComponent(state.selectedRunId)}`);
  renderWorkflowCard(detail);
  renderToolDecision(detail.events || []);
  renderApprovalActions(detail.events || []);
  renderReplay(detail);
}

function renderApprovalActions(events) {
  if (!els.approvalActionsEl) return;
  els.approvalActionsEl.innerHTML = "";
  const actions = extractApprovalActions(events);
  for (const action of actions) {
    const row = document.createElement("div");
    row.className = "approval-row";

    const labelWrap = document.createElement("div");
    labelWrap.className = "approval-meta";
    const line1 = document.createElement("div");
    line1.textContent = `${action.file} | risk=${action.riskLevel} | status=${action.fileStatus || "unknown"}`;
    const line2 = document.createElement("div");
    line2.className = "approval-meta-sub";
    line2.textContent = `files=${action.filesChangedCount} hunks=${action.hunksCount} +${action.addedLines}/-${action.removedLines} approval=${action.approvalRequired ? "required" : "not-required"}`;
    const line3 = document.createElement("div");
    line3.className = "approval-meta-sub";
    line3.textContent = `affected: ${(action.affectedFiles || [action.file]).join(", ")}`;
    labelWrap.appendChild(line1);
    labelWrap.appendChild(line2);
    labelWrap.appendChild(line3);

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "run-item";
    btn.textContent = action.buttonLabel || "Approve and apply";
    if (action.alreadyApplied) {
      btn.disabled = true;
    }
    btn.addEventListener("click", async () => {
      if (action.alreadyApplied) return;
      await applyApprovedPatch(action.eventId);
    });

    row.appendChild(labelWrap);
    row.appendChild(btn);
    els.approvalActionsEl.appendChild(row);
  }
}

function computeVisibleRange() {
  const total = allRuns.length;
  const viewport = els.runsListEl?.clientHeight || 180;
  const scrollTop = els.runsListEl?.scrollTop || 0;
  const visibleCount = Math.max(1, Math.ceil(viewport / RUN_ROW_HEIGHT));
  const start = Math.max(0, Math.floor(scrollTop / RUN_ROW_HEIGHT) - RUN_BUFFER);
  const end = Math.min(total, start + visibleCount + RUN_BUFFER * 2);
  return { start, end };
}

function buildRunButton(run) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "run-item";
  const task = String(run.task || "").trim();
  btn.textContent = `${run.status} · ${(task || "Task").slice(0, 40)}`;
  btn.addEventListener("click", async () => {
    writePrefs({ session: { lastRunId: run.run_id } });
    await openRun(run.run_id);
  });
  return btn;
}

function renderRunsWindow() {
  if (!els.runsListEl) return;
  const { start, end } = computeVisibleRange();
  if (start === visibleRange.start && end === visibleRange.end && els.runsListEl.childElementCount > 0) {
    return;
  }
  visibleRange = { start, end };

  const fragment = document.createDocumentFragment();
  const top = document.createElement("div");
  top.className = "run-spacer";
  top.style.height = `${start * RUN_ROW_HEIGHT}px`;
  fragment.appendChild(top);

  for (const run of allRuns.slice(start, end)) {
    fragment.appendChild(buildRunButton(run));
  }

  const bottom = document.createElement("div");
  bottom.className = "run-spacer";
  bottom.style.height = `${Math.max(0, (allRuns.length - end) * RUN_ROW_HEIGHT)}px`;
  fragment.appendChild(bottom);

  els.runsListEl.innerHTML = "";
  els.runsListEl.appendChild(fragment);
}

function scheduleVirtualRender() {
  if (pendingVirtualFrame) return;
  pendingVirtualFrame = requestAnimationFrame(() => {
    pendingVirtualFrame = 0;
    renderRunsWindow();
  });
}

function ensureVirtualScrollBinding() {
  if (!els.runsListEl || els.runsListEl.dataset.virtualBound === "1") return;
  els.runsListEl.dataset.virtualBound = "1";
  els.runsListEl.addEventListener("scroll", scheduleVirtualRender, { passive: true });
}

export function renderRuns(runs) {
  const signature = JSON.stringify((runs || []).slice(0, 60).map((r) => [r.run_id, r.status, r.task]));
  if (signature === lastRenderedRunIds && els.runsListEl.childElementCount > 0) return;
  lastRenderedRunIds = signature;
  allRuns = Array.isArray(runs) ? runs.slice(0, 500) : [];
  visibleRange = { start: -1, end: -1 };
  ensureVirtualScrollBinding();
  const firstRun = Array.isArray(runs) && runs.length > 0 ? runs[0] : null;
  renderWorkflowCard(firstRun ? { run_id: firstRun.run_id, status: firstRun.status, task: firstRun.task, events: [] } : null);
  renderRunsWindow();
}

export function renderRollbacks(items) {
  els.rollbackListEl.innerHTML = "";
  for (const item of items.slice(0, 20)) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "run-item";
    btn.textContent = `${item.file_path} • ${item.created_at}`;
    btn.addEventListener("click", async () => {
      const detail = await apiGet(`/rollback/${encodeURIComponent(item.rollback_id)}`);
      state.selectedRollbackId = detail.rollback_id;
      els.rollbackDetailEl.textContent = [
        `Rollback: ${detail.rollback_id}`,
        `File: ${detail.file_path}`,
        `Time: ${detail.created_at}`,
        "Diff:",
        detail.diff || "-",
      ].join("\n");
    });
    els.rollbackListEl.appendChild(btn);
  }
}

export async function refreshRuns() {
  const data = await apiGet("/task/runs");
  renderRuns(data.runs || []);
  const desired = readPrefs().session?.lastRunId || "";
  if (desired && !state.selectedRunId && (data.runs || []).some((r) => r.run_id === desired)) {
    await openRun(desired);
  }
  return data.runs || [];
}

export async function refreshRollbacks() {
  const data = await apiGet("/rollback");
  renderRollbacks(data.rollbacks || []);
}
