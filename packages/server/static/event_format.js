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
      `- [approval_required] (${role}) ${title || "High-risk patch requires approval"}`,
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
      `- [approval_applied] (${role}) ${title || "Approved patch applied"}`,
      `  file=${file} source_event_id=${source} rollback_id=${rollbackId}`,
    ];
  }

  const lines = [`- [${eventType}] (${role}) ${title}`];
  if (data) lines.push(`  ${JSON.stringify(data, null, 2)}`);
  return lines;
}
