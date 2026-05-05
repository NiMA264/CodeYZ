import { apiGet, apiPost } from "./api.js";
import { formatTimelineEvent } from "./event_format.js";
import { els, state } from "./state.js";
import { extractApprovalActions } from "./timeline_helpers.js";

const PHASE_KEYS = ["task", "plan", "patch", "tests", "diff", "approval"];
const PHASE_EVENT_MAP = {
  plan: ["plan"],
  patch: ["diff", "approval_required", "approval_applied"],
  tests: ["test"],
  diff: ["diff"],
};

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

function renderReplay(detail) {
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
    for (const row of formatTimelineEvent(event)) lines.push(row);
  }
  els.runReplayContentEl.textContent = lines.join("\n");
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

    const label = document.createElement("span");
    label.textContent = action.alreadyApplied
      ? `${action.file} (${action.riskLevel}) - applied`
      : `${action.file} (${action.riskLevel})`;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "run-item";
    btn.textContent = "Apply approved patch";
    if (action.alreadyApplied) {
      btn.disabled = true;
      btn.textContent = "Already applied";
    }
    btn.addEventListener("click", async () => {
      if (action.alreadyApplied) return;
      await applyApprovedPatch(action.eventId);
    });

    row.appendChild(label);
    row.appendChild(btn);
    els.approvalActionsEl.appendChild(row);
  }
}

export function renderRuns(runs) {
  els.runsListEl.innerHTML = "";
  const firstRun = Array.isArray(runs) && runs.length > 0 ? runs[0] : null;
  renderWorkflowCard(firstRun ? { run_id: firstRun.run_id, status: firstRun.status, task: firstRun.task, events: [] } : null);

  for (const run of runs.slice(0, 12)) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "run-item";
    const task = String(run.task || "").trim();
    btn.textContent = `${run.status} · ${(task || "Task").slice(0, 40)}`;
    btn.addEventListener("click", async () => {
      state.selectedRunId = run.run_id;
      const detail = await apiGet(`/task/runs/${encodeURIComponent(run.run_id)}`);
      renderWorkflowCard(detail);
      renderToolDecision(detail.events || []);
      renderApprovalActions(detail.events || []);
      renderReplay(detail);
    });
    els.runsListEl.appendChild(btn);
  }
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
