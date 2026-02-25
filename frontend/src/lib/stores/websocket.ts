import { writable } from 'svelte/store';

export const wsConnected = writable(false);
export const wsLastMessage = writable<Record<string, any>>({});

let ws: WebSocket | null = null;
let reconnectTimeout: ReturnType<typeof setTimeout>;
let reconnectDelay = 1000;
let savedBackendPort = '';

function buildWsUrl(): string {
  const explicitBase = import.meta.env.VITE_WS_BASE as string | undefined;
  if (explicitBase) {
    const trimmed = explicitBase.endsWith('/') ? explicitBase.slice(0, -1) : explicitBase;
    return `${trimmed}/api/market/ws/prices`;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

  // If a separate backend port is configured, connect directly to the backend
  // (SvelteKit can't proxy WebSocket upgrades through hooks.server.ts)
  if (savedBackendPort) {
    return `${protocol}//${window.location.hostname}:${savedBackendPort}/api/market/ws/prices`;
  }

  // Fallback: same origin (works behind a reverse proxy or Vite dev server)
  return `${protocol}//${window.location.host}/api/market/ws/prices`;
}

export function connectWs(backendPort?: string): void {
  if (typeof window === 'undefined') return;
  if (backendPort) savedBackendPort = backendPort;
  const url = buildWsUrl();

  ws = new WebSocket(url);

  ws.onopen = () => {
    wsConnected.set(true);
    reconnectDelay = 1000;
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      wsLastMessage.set(data);
    } catch { /* ignore */ }
  };

  ws.onclose = () => {
    wsConnected.set(false);
    reconnectTimeout = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
      connectWs();
    }, reconnectDelay);
  };

  ws.onerror = () => ws?.close();
}

export function subscribeTopic(symbol: string): void {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action: 'subscribe', symbol }));
  }
}

export function unsubscribeTopic(symbol: string): void {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action: 'unsubscribe', symbol }));
  }
}

export function disconnectWs(): void {
  clearTimeout(reconnectTimeout);
  ws?.close();
}
