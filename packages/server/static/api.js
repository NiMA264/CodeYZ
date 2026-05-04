import { TOKEN_KEY } from "./state.js";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setStored(key, value) {
  localStorage.setItem(key, value);
}

export function getStored(key, fallbackValue) {
  return localStorage.getItem(key) || fallbackValue;
}

function buildHeaders() {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) {
    headers["x-api-key"] = token;
  }
  return headers;
}

async function buildApiError(resp) {
  const fallbackText = await resp.text();
  try {
    const data = JSON.parse(fallbackText);
    const err = new Error(data.message || `HTTP ${resp.status}`);
    err.status = resp.status;
    err.code = data.code || `http_${resp.status}`;
    err.hint = data.hint || "";
    err.api = data;
    return err;
  } catch {
    const err = new Error(`HTTP ${resp.status}: ${fallbackText}`);
    err.status = resp.status;
    err.code = `http_${resp.status}`;
    err.hint = "";
    return err;
  }
}

export async function apiGet(url) {
  let resp;
  try {
    resp = await fetch(url, { headers: buildHeaders() });
  } catch {
    throw new Error("Server nicht erreichbar. Lösung: 'codeyz server' starten und URL prüfen.");
  }
  if (!resp.ok) {
    throw await buildApiError(resp);
  }
  return resp.json();
}

export async function apiPost(url, body) {
  const resp = await fetch(url, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    throw await buildApiError(resp);
  }
  return resp.json();
}

export async function apiDelete(url) {
  const resp = await fetch(url, {
    method: "DELETE",
    headers: buildHeaders(),
  });
  if (!resp.ok) {
    throw await buildApiError(resp);
  }
  return resp.json();
}
