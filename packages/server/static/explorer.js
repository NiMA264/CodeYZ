import { apiGet } from "./api.js";
import { els, state } from "./state.js";

export function toRelative(absolutePath) {
  if (!absolutePath || !state.currentProject) return absolutePath || "";
  const base = state.currentProject.toLowerCase();
  const path = absolutePath.toLowerCase();
  if (path.startsWith(base)) {
    const rel = absolutePath.slice(state.currentProject.length).replace(/^[/\\]+/, "");
    return rel || absolutePath;
  }
  return absolutePath;
}

export function setSelectedFile(path) {
  state.selectedFile = path || "";
  els.selectedFileEl.textContent = state.selectedFile || "-";
  els.contextSelectedFileEl.textContent = `Selected: ${state.selectedFile || "-"}`;
}

function matchesFilter(node, filter) {
  if (!filter) return true;
  const name = (node.name || "").toLowerCase();
  if (name.includes(filter)) return true;
  return (node.children || []).some((c) => matchesFilter(c, filter));
}

function renderNode(node, level, filter, onFileClick) {
  if (!matchesFilter(node, filter)) return;

  const row = document.createElement("div");
  row.className = "tree-item";
  row.style.paddingLeft = `${level * 12}px`;

  const isDir = node.type === "directory";
  const rel = toRelative(node.path);
  const collapsed = isDir && state.collapsedDirs.has(node.path);
  const isPinned = state.pinnedFiles.includes(rel);

  const label = document.createElement("span");
  label.className = isDir ? "dir" : "file";
  if (!isDir && rel === state.selectedFile) label.classList.add("active");
  if (!isDir && isPinned) label.classList.add("pinned");
  label.textContent = `${isDir ? (collapsed ? "▸" : "▾") : (isPinned ? "📌" : "•")} ${node.name}`;
  row.appendChild(label);

  if (isDir) {
    label.addEventListener("click", () => {
      if (state.collapsedDirs.has(node.path)) state.collapsedDirs.delete(node.path);
      else state.collapsedDirs.add(node.path);
      renderExplorer(onFileClick);
    });
  } else {
    label.addEventListener("click", () => onFileClick(rel));
  }

  els.explorerEl.appendChild(row);

  if (isDir && !collapsed) {
    for (const child of (node.children || [])) renderNode(child, level + 1, filter, onFileClick);
  }
}

export function renderExplorer(onFileClick) {
  els.explorerEl.innerHTML = "";
  if (!state.treeData) {
    els.explorerEl.textContent = "-";
    return;
  }
  const filter = els.filterEl.value.trim().toLowerCase();
  renderNode(state.treeData, 0, filter, onFileClick);
}

export async function loadFilePreview(relPath) {
  try {
    const data = await apiGet(`/files/read?path=${encodeURIComponent(relPath)}`);
    els.previewEl.textContent = data.content || "-";
  } catch {
    els.previewEl.textContent = "Vorschau nicht verfügbar.";
  }
}

export function renderSearchResults(results, onResultClick) {
  els.searchResultsEl.innerHTML = "";
  for (const item of results || []) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "run-item";
    const preview = String(item.content || "").slice(0, 90).replace(/\s+/g, " ");
    btn.textContent = `${item.path} (${item.score || 0}) :: ${preview}`;
    btn.addEventListener("click", () => onResultClick(item.path || ""));
    els.searchResultsEl.appendChild(btn);
  }
}
