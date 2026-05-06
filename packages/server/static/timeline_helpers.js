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
    const filesChangedCount = Number(data.files_changed_count || 1) || 1;
    const addedLines = Number(data.added_lines || data?.stats?.additions || 0) || 0;
    const removedLines = Number(data.removed_lines || data?.stats?.deletions || 0) || 0;
    const hunksCount = Number(data.hunks_count || 0) || 0;
    const fileStatus = String(data.file_status || "unknown");
    const approvalRequired = data.approval_required !== false;
    const affectedFiles = Array.isArray(data.files) && data.files.length > 0
      ? data.files.map((x) => String(x))
      : [String(data.file)];
    out.push({
      eventId: event.event_id,
      file: String(data.file),
      riskLevel: String(data.risk_level || "high"),
      preview: String(data.patch_preview || ""),
      patch: data.patch,
      filesChangedCount,
      addedLines,
      removedLines,
      hunksCount,
      fileStatus,
      approvalRequired,
      affectedFiles,
      buttonLabel: alreadyApplied
        ? "Already applied"
        : approvalRequired
          ? "Approve and apply"
          : "Apply this patch",
      alreadyApplied,
    });
  }
  return out;
}

function parseFileHeader(line, prefix) {
  if (!line.startsWith(prefix)) return "";
  const raw = line.slice(prefix.length).trim();
  if (raw.startsWith("a/") || raw.startsWith("b/")) return raw.slice(2);
  return raw;
}

export function parseUnifiedDiff(diffText) {
  const text = String(diffText || "");
  if (!text.trim()) return [];

  const lines = text.split("\n");
  const hunks = [];
  let current = null;

  for (const line of lines) {
    if (line.startsWith("@@")) {
      if (current) hunks.push(current);
      current = { header: line, lines: [] };
      continue;
    }
    if (!current) continue;
    const type = line.startsWith("+")
      ? "added"
      : line.startsWith("-")
        ? "removed"
        : line.startsWith(" ")
          ? "context"
          : line.startsWith("\\")
            ? "meta"
            : "context";
    current.lines.push({ type, text: line });
  }
  if (current) hunks.push(current);
  return hunks;
}

function inferFileStatusFromHunks(hunks) {
  let added = 0;
  let removed = 0;
  for (const hunk of hunks) {
    for (const line of hunk.lines || []) {
      if (line.type === "added") added += 1;
      if (line.type === "removed") removed += 1;
    }
  }
  if (added > 0 && removed === 0) return "added";
  if (removed > 0 && added === 0) return "deleted";
  return "modified";
}

export function collectDiffFilesFromEvents(events) {
  const fileMap = new Map();
  const list = Array.isArray(events) ? events : [];

  for (const event of list) {
    if (!event || !event.event_type) continue;
    const data = event.data && typeof event.data === "object" ? event.data : {};
    if (event.event_type !== "diff" && event.event_type !== "approval_required" && event.event_type !== "approval_applied") {
      continue;
    }

    let filePath = String(data.file || "");
    let diffText = String(data.diff || "");
    let status = String(data.file_status || "unknown");

    const patch = data.patch && typeof data.patch === "object" ? data.patch : null;
    if (patch) {
      filePath = filePath || String(patch.file_path || "");
      diffText = diffText || String(patch.unified_diff || "");
    }

    const diffLines = diffText.split("\n");
    const parsedOld = parseFileHeader(String(diffLines[0] || ""), "--- ");
    const parsedNew = parseFileHeader(String(diffLines[1] || ""), "+++ ");
    const parsedPath = parsedNew || parsedOld;
    if (!filePath && parsedPath) filePath = parsedPath;
    if (!filePath) continue;

    const hunks = parseUnifiedDiff(diffText);
    if ((status === "unknown" || !status) && hunks.length > 0) {
      status = inferFileStatusFromHunks(hunks);
    }
    if ((status === "unknown" || !status) && data.stats && typeof data.stats === "object" && data.stats.is_new_file === true) {
      status = "added";
    }
    const addedLines = Number(data.added_lines || 0) || 0;
    const removedLines = Number(data.removed_lines || 0) || 0;
    const hunksCount = Number(data.hunks_count || hunks.length || 0) || 0;

    const existing = fileMap.get(filePath);
    const merged = {
      file: filePath,
      status: existing?.status === "added" ? "added" : (status || "unknown"),
      hunks: hunks.length > 0 ? hunks : (existing?.hunks || []),
      diffText: diffText || existing?.diffText || "",
      lastEventType: event.event_type,
      sourceEventId: event.event_id || existing?.sourceEventId || "",
      riskLevel: String(data.risk_level || existing?.riskLevel || ""),
      addedLines: addedLines || existing?.addedLines || 0,
      removedLines: removedLines || existing?.removedLines || 0,
      hunksCount: hunksCount || existing?.hunksCount || 0,
      approvalRequired: data.approval_required === true || existing?.approvalRequired === true,
      filesChangedCount: Number(data.files_changed_count || existing?.filesChangedCount || 1) || 1,
    };
    fileMap.set(filePath, merged);
  }

  return Array.from(fileMap.values()).sort((a, b) => a.file.localeCompare(b.file));
}
