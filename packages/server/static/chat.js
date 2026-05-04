import { apiPost } from "./api.js";
import { els, getComposerState, scrollChatToBottom, state } from "./state.js";

export function autoResizeTextarea() {
  els.inputEl.style.height = "auto";
  els.inputEl.style.height = `${Math.min(els.inputEl.scrollHeight, 180)}px`;
}

export function renderAttachments() {
  els.attachmentsEl.innerHTML = "";
  for (const file of state.attachments) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "attachment-chip";
    chip.textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;
    chip.addEventListener("click", () => {
      state.attachments = state.attachments.filter((f) => f !== file);
      renderAttachments();
    });
    els.attachmentsEl.appendChild(chip);
  }
}

export function addMessage(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.textContent = text;
  els.messagesEl.appendChild(el);
  scrollChatToBottom();
}

export function addApiErrorMessage(prefix, err) {
  const wrap = document.createElement("div");
  wrap.className = "msg assistant msg-error";

  const title = document.createElement("div");
  title.className = "error-message";
  title.textContent = prefix ? `${prefix}: ${err.message || "Unbekannter Fehler"}` : (err.message || "Unbekannter Fehler");
  wrap.appendChild(title);

  if (err.hint) {
    const hint = document.createElement("div");
    hint.className = "error-hint";
    hint.textContent = err.hint;
    wrap.appendChild(hint);
  }

  const code = document.createElement("div");
  code.className = "error-code";
  code.textContent = `code: ${err.code || "unknown_error"}`;
  wrap.appendChild(code);

  els.messagesEl.appendChild(wrap);
  scrollChatToBottom();
}

export function setLoading(isLoading) {
  els.statusEl.hidden = !isLoading;
  els.statusEl.textContent = isLoading ? "Lade..." : "";
  els.sendBtn.disabled = isLoading;
  els.autoBtn.disabled = isLoading;
  els.inputEl.disabled = isLoading;
}

export async function sendMessage(message, refreshPanels) {
  setLoading(true);
  try {
    const stateComposer = getComposerState();
    const data = await apiPost("/chat", {
      message,
      session_id: state.sessionId || null,
      selected_file: state.selectedFile || null,
      model: stateComposer.selectedModel,
      mode: stateComposer.selectedMode,
      access_level: stateComposer.accessLevel,
      plan_mode: stateComposer.planMode,
      attachments_metadata: stateComposer.attachments,
    });
    state.sessionId = data.session_id || state.sessionId;
    addMessage("assistant", data.response || "Keine Antwort.");
    scrollChatToBottom();
    await refreshPanels();
  } catch (err) {
    addApiErrorMessage("Fehler", err);
  } finally {
    setLoading(false);
  }
}

export async function runAutonomousTask(task, refreshRuns, refreshRollbacks) {
  setLoading(true);
  addMessage("assistant", "Autonomous task gestartet...");
  try {
    const stateComposer = getComposerState();
    const payload = {
      task,
      model: stateComposer.selectedModel,
      access_level: stateComposer.accessLevel,
      multi_agent: !!els.multiAgentEl.checked,
      max_cost_usd: stateComposer.maxCostUsd,
      role_models: stateComposer.roleModels,
    };
    const data = await apiPost("/task/auto", payload);
    els.contextCostEl.textContent = `Estimated: $${(data.estimated_total_cost_usd || 0).toFixed(6)}`;
    addMessage(
      "assistant",
      data.ok
        ? `Run abgeschlossen (run_id=${data.run_id})`
        : `Run fehlgeschlagen (run_id=${data.run_id}): ${data.error || "unknown"}`
    );
    await refreshRuns();
    await refreshRollbacks();
  } catch (err) {
    addApiErrorMessage("Autonomous Task fehlgeschlagen", err);
  } finally {
    setLoading(false);
  }
}
