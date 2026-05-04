export function extractApprovalActions(events) {
  const out = [];
  for (const event of events || []) {
    if (!event || event.event_type !== "approval_required") continue;
    const data = event.data || {};
    if (!event.event_id) continue;
    if (!data || !data.patch || !data.file) continue;
    out.push({
      eventId: event.event_id,
      file: String(data.file),
      riskLevel: String(data.risk_level || "high"),
      preview: String(data.patch_preview || ""),
    });
  }
  return out;
}
