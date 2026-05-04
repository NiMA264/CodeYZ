import { apiGet } from "./api.js";
import { els, state } from "./state.js";

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

export function renderRuns(runs) {
  els.runsListEl.innerHTML = "";
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
      els.runReplayContentEl.textContent = lines.join("\n");
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
}

export async function refreshRollbacks() {
  const data = await apiGet("/rollback");
  renderRollbacks(data.rollbacks || []);
}
