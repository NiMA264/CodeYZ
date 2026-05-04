import { apiGet, apiPost } from "./api.js";
import { els } from "./state.js";

export function renderPlugins(items, onPluginMessage, getAccessLevel) {
  els.pluginsListEl.innerHTML = "";
  for (const item of items || []) {
    const row = document.createElement("div");
    row.className = "pinned-row";

    const info = document.createElement("span");
    const perms = Array.isArray(item.permissions) ? item.permissions.join(", ") : "-";
    info.textContent = `${item.name} (${item.enabled ? "on" : "off"}) [${perms}]`;

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.textContent = item.enabled ? "Disable" : "Enable";
    toggle.addEventListener("click", async () => {
      await apiPost(item.enabled ? "/plugins/disable" : "/plugins/enable", { name: item.name });
      await refreshPlugins(onPluginMessage, getAccessLevel);
    });

    const runBtn = document.createElement("button");
    runBtn.type = "button";
    runBtn.textContent = "Run";
    runBtn.addEventListener("click", async () => {
      try {
        const data = await apiPost("/plugins/run", {
          name: item.name,
          input_data: { name: "ui" },
          access_level: getAccessLevel(),
        });
        onPluginMessage(`Plugin ${item.name}: ${JSON.stringify(data.result)}`);
      } catch (err) {
        onPluginMessage(`Plugin-Fehler: ${err.message}`);
      }
    });

    row.appendChild(info);
    row.appendChild(toggle);
    row.appendChild(runBtn);
    els.pluginsListEl.appendChild(row);
  }
}

export async function refreshPlugins(onPluginMessage, getAccessLevel) {
  const data = await apiGet("/plugins");
  renderPlugins(data.plugins || [], onPluginMessage, getAccessLevel);
}
