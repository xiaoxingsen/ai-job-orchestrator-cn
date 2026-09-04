import { ChromeCommandStorage, PersistentCommandExecutor } from "./commands/persistent";


const API_ROOT = "http://127.0.0.1:8765";
const WS_ROOT = "ws://127.0.0.1:8765/ws/extension";
const storage = new ChromeCommandStorage();
const executor = new PersistentCommandExecutor(storage);
let socket: WebSocket | undefined;
let reconnectAttempts = 0;
let keepAlive: ReturnType<typeof setInterval> | undefined;


async function pair(token: string): Promise<{ ok: boolean; error?: string }> {
  const response = await fetch(`${API_ROOT}/api/pairing/consume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
    cache: "no-store",
    credentials: "omit",
  });
  if (!response.ok) return { ok: false, error: await response.text() };
  const payload = (await response.json()) as { session_token: string };
  await chrome.storage.local.set({ pairingSession: payload.session_token });
  connect(payload.session_token);
  return { ok: true };
}


function connect(sessionToken: string): void {
  socket?.close();
  socket = new WebSocket(`${WS_ROOT}?session_token=${encodeURIComponent(sessionToken)}`);
  socket.addEventListener("open", () => {
    reconnectAttempts = 0;
    if (keepAlive) clearInterval(keepAlive);
    keepAlive = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "heartbeat" }));
    }, 20_000);
  });
  socket.addEventListener("message", (event) => void handleSocketMessage(event.data));
  socket.addEventListener("close", () => {
    if (keepAlive) clearInterval(keepAlive);
    keepAlive = undefined;
    if (reconnectAttempts >= 5) return;
    const delay = Math.min(30_000, 1_000 * 2 ** reconnectAttempts);
    reconnectAttempts += 1;
    setTimeout(() => connect(sessionToken), delay);
  });
}


async function activeRecruitingTab(): Promise<chrome.tabs.Tab | undefined> {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs.find((tab) =>
    /https?:\/\/[^/]*(?:zhipin\.com|liepin\.com|zhaopin\.com)\//.test(tab.url ?? ""),
  );
}


async function dispatchToContent(message: unknown): Promise<unknown> {
  const tab = await activeRecruitingTab();
  if (!tab?.id) return { status: "requires_user_action", reason: "open_supported_job_page" };
  return chrome.tabs.sendMessage(tab.id, message);
}


async function handleSocketMessage(raw: unknown): Promise<void> {
  if (typeof raw !== "string") return;
  let message: Record<string, unknown>;
  try {
    message = JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return;
  }
  const commandId = message.command_id;
  if (typeof commandId !== "string" || !commandId) return;
  const result = await executor.execute(commandId, () => dispatchToContent(message));
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ command_id: commandId, result }));
  }
}


chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "pair" && typeof message.token === "string") {
    void pair(message.token).then(sendResponse, (error: unknown) =>
      sendResponse({ ok: false, error: String(error) }),
    );
    return true;
  }
  if (message?.type === "riskDetected") {
    void chrome.storage.local.set({ lastRiskStop: message.payload });
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ event: "risk_stopped", payload: message.payload }));
    }
  }
  return false;
});


void chrome.storage.local.get("pairingSession").then((values) => {
  if (typeof values.pairingSession === "string") connect(values.pairingSession);
});

