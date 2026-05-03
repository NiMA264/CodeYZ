import * as vscode from "vscode";

export function activate(context: vscode.ExtensionContext) {
  const provider = new CodeyzViewProvider(context.extensionUri);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider("codeyz.chatView", provider)
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codeyz.openChat", async () => {
      await vscode.commands.executeCommand("workbench.view.extension.codeyz");
    })
  );
}

export function deactivate() {}

class CodeyzViewProvider implements vscode.WebviewViewProvider {
  private view?: vscode.WebviewView;
  private sessionId: string | null = null;

  constructor(private readonly extensionUri: vscode.Uri) {}

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    const { webview } = webviewView;
    webview.options = { enableScripts: true };
    webview.html = this.getHtml(webview);

    webview.onDidReceiveMessage(async (msg) => {
      try {
        if (msg.type === "newChat") {
          this.sessionId = null;
          this.post({ type: "assistant", text: "New chat started." });
          return;
        }

        if (msg.type === "sendText") {
          await this.sendChat(msg.text);
          return;
        }

        if (msg.type === "sendCurrentFile") {
          const editor = vscode.window.activeTextEditor;
          if (!editor) {
            this.post({ type: "assistant", text: "No active file." });
            return;
          }
          const text = editor.document.getText();
          const payload = `Explain this file:\n\nPath: ${editor.document.fileName}\n\n${text.slice(0, 12000)}`;
          await this.sendChat(payload);
          return;
        }

        if (msg.type === "sendSelection") {
          const editor = vscode.window.activeTextEditor;
          if (!editor) {
            this.post({ type: "assistant", text: "No active editor." });
            return;
          }
          const selection = editor.document.getText(editor.selection).trim();
          if (!selection) {
            this.post({ type: "assistant", text: "No selection." });
            return;
          }
          const payload = `Explain this selection:\n\nPath: ${editor.document.fileName}\n\n${selection.slice(0, 12000)}`;
          await this.sendChat(payload);
          return;
        }

        if (msg.type === "gitStatus") {
          const res = await this.apiGet("/git/status");
          this.post({ type: "assistant", text: `Git status:\n${res.status || ""}` });
          return;
        }

        if (msg.type === "gitDiff") {
          const res = await this.apiGet("/git/diff");
          this.post({ type: "assistant", text: `Git diff:\n${res.diff || ""}` });
        }
      } catch {
        this.post({ type: "assistant", text: "Request failed. Check server/token config." });
      }
    });
  }

  private async sendChat(text: string) {
    this.post({ type: "user", text });
    const res = await this.apiPost("/chat", { message: text, session_id: this.sessionId });
    this.sessionId = res.session_id || this.sessionId;
    this.post({ type: "assistant", text: res.response || "No response." });
  }

  private getConfig() {
    const cfg = vscode.workspace.getConfiguration("codeyz");
    const serverUrl = (cfg.get<string>("serverUrl") || "http://127.0.0.1:8765").replace(/\/$/, "");
    const token = cfg.get<string>("localToken") || "";
    return { serverUrl, token };
  }

  private async apiGet(path: string): Promise<any> {
    const { serverUrl, token } = this.getConfig();
    const headers: Record<string, string> = {};
    if (token) headers["x-api-key"] = token;
    const resp = await fetch(`${serverUrl}${path}`, { headers });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  }

  private async apiPost(path: string, body: unknown): Promise<any> {
    const { serverUrl, token } = this.getConfig();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["x-api-key"] = token;
    const resp = await fetch(`${serverUrl}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  }

  private post(message: { type: "user" | "assistant"; text: string }) {
    this.view?.webview.postMessage(message);
  }

  private getHtml(webview: vscode.Webview): string {
    const nonce = getNonce();
    const csp = `default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';`;

    return `<!doctype html>
<html>
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="${csp}">
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style nonce="${nonce}">
    body { font-family: sans-serif; margin: 0; padding: 10px; color: var(--vscode-foreground); background: var(--vscode-editor-background); }
    .row { display: flex; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
    button { border: 1px solid var(--vscode-button-border, #666); background: var(--vscode-button-background); color: var(--vscode-button-foreground); padding: 6px 8px; cursor: pointer; }
    input { width: 100%; box-sizing: border-box; padding: 8px; margin-bottom: 8px; color: var(--vscode-input-foreground); background: var(--vscode-input-background); border: 1px solid var(--vscode-input-border, #555); }
    #messages { border: 1px solid var(--vscode-panel-border, #555); min-height: 280px; max-height: 50vh; overflow: auto; padding: 8px; margin-bottom: 8px; }
    .msg { white-space: pre-wrap; margin: 6px 0; padding: 6px 8px; border-radius: 6px; }
    .user { background: rgba(30,140,90,.3); }
    .assistant { background: rgba(80,80,90,.35); }
  </style>
</head>
<body>
  <div class="row">
    <button id="newChat">New Chat</button>
    <button id="sendFile">Send Current File</button>
    <button id="sendSel">Send Selection</button>
    <button id="gitStatus">Git Status</button>
    <button id="gitDiff">Git Diff</button>
  </div>
  <div id="messages"></div>
  <input id="input" placeholder="Message CodeYZ..." />
  <button id="send">Send</button>

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const messages = document.getElementById('messages');
    const input = document.getElementById('input');

    function add(type, text) {
      const el = document.createElement('div');
      el.className = 'msg ' + type;
      el.textContent = text;
      messages.appendChild(el);
      messages.scrollTop = messages.scrollHeight;
    }

    document.getElementById('send').addEventListener('click', () => {
      const text = input.value.trim();
      if (!text) return;
      input.value = '';
      vscode.postMessage({ type: 'sendText', text });
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') document.getElementById('send').click();
    });

    document.getElementById('newChat').addEventListener('click', () => vscode.postMessage({ type: 'newChat' }));
    document.getElementById('sendFile').addEventListener('click', () => vscode.postMessage({ type: 'sendCurrentFile' }));
    document.getElementById('sendSel').addEventListener('click', () => vscode.postMessage({ type: 'sendSelection' }));
    document.getElementById('gitStatus').addEventListener('click', () => vscode.postMessage({ type: 'gitStatus' }));
    document.getElementById('gitDiff').addEventListener('click', () => vscode.postMessage({ type: 'gitDiff' }));

    window.addEventListener('message', (event) => {
      const msg = event.data;
      if (!msg || !msg.type) return;
      add(msg.type, msg.text || '');
    });

    add('assistant', 'CodeYZ sidebar ready.');
  </script>
</body>
</html>`;
  }
}

function getNonce(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let out = "";
  for (let i = 0; i < 24; i += 1) {
    out += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return out;
}
