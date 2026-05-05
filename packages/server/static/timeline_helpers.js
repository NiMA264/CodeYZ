export function extractApprovalActions(events) {
  const applied = new Set();
  for (const event of events || []) {
    if (!event || event.event_type !== "approval_applied") continue;
    const data = event.data || {};
    if (data.source_event_id) {
      applied.add(String(data.source_event_id));
    }
  }

  const out = [];
  for (const event of events || []) {
    if (!event || event.event_type !== "approval_required") continue;
    const data = event.data || {};
    if (!event.event_id) continue;
    if (!data || !data.patch || !data.file) continue;
    const alreadyApplied = applied.has(String(event.event_id));
    out.push({
      eventId: event.event_id,
      file: String(data.file),
      riskLevel: String(data.risk_level || "high"),
      preview: String(data.patch_preview || ""),
      alreadyApplied,
    });
  }
  return out;
}
