const EVENT_LABELS = {
  analyze: "Task analysieren",
  plan: "Plan erstellen",
  diff: "Patch anwenden",
  build: "Build ausführen",
  test: "Tests ausführen",
  tool_decision: "Tools auswählen",
  approval_required: "Approval prüfen",
  approval_applied: "Approval angewendet",
  error: "Fehler",
};

function eventLabel(eventType, title) {
  const pretty = EVENT_LABELS[eventType] || eventType.replaceAll("_", " ");
  const safeTitle = title && title.trim() ? title.trim() : "";
  if (!safeTitle) return pretty;
  return `${pretty}: ${safeTitle}`;
}

export function formatTimelineEvent(event) {
  const eventType = event && event.event_type ? event.event_type : "unknown";
  const role = event && event.agent_role ? event.agent_role : "-";
  const title = event && event.title ? event.title : "";
  const data = event && event.data ? event.data : null;

  if (eventType === "approval_required") {
    const file = data && data.file ? data.file : "-";
    const risk = data && data.risk_level ? data.risk_level : "high";
    const reasons = Array.isArray(data && data.reasons) ? data.reasons.join(", ") : "-";
    const stats = data && data.stats ? JSON.stringify(data.stats) : "{}";
    const previewRaw = data && data.patch_preview ? String(data.patch_preview) : "";
    const preview = previewRaw.length > 300 ? `${previewRaw.slice(0, 300)}...` : previewRaw;
    return [
      `- [${eventType}] ${eventLabel(eventType, title || "High-risk patch requires approval")} (${role})`,
      `  file=${file} risk=${risk} reasons=${reasons}`,
      `  stats=${stats}`,
      `  preview=${preview}`,
    ];
  }

  if (eventType === "approval_applied") {
    const file = data && data.file ? data.file : "-";
    const source = data && data.source_event_id ? data.source_event_id : "-";
    const rollbackId = data && data.rollback_id ? data.rollback_id : "-";
    return [
      `- [${eventType}] ${eventLabel(eventType, title || "Approved patch applied")} (${role})`,
      `  file=${file} source_event_id=${source} rollback_id=${rollbackId}`,
    ];
  }

  const lines = [`- [${eventType}] ${eventLabel(eventType, title)} (${role})`];
  if (data) lines.push(`  ${JSON.stringify(data, null, 2)}`);
  return lines;
}
