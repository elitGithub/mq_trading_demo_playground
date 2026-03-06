const BASE_URL = '/api';

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// Account
export async function getAccountInfo() {
  return fetchJson<{ account: any; connected: boolean }>('/account/info');
}

// Market Data
export async function getBars(symbol: string, timeframe = 'H1', count = 200) {
  return fetchJson<{ bars: any[] }>(`/market/bars/${symbol}?timeframe=${timeframe}&count=${count}`);
}

export async function getTick(symbol: string) {
  return fetchJson<{ symbol: string; price: any }>(`/market/tick/${symbol}`);
}

export async function getTradeableSymbols(options?: { tradeable?: boolean; visible_only?: boolean }) {
  const params = new URLSearchParams();
  if (options?.tradeable !== undefined) params.set('tradeable', String(options.tradeable));
  if (options?.visible_only !== undefined) params.set('visible_only', String(options.visible_only));
  const qs = params.toString();
  return fetchJson<{ symbols: string[]; connected: boolean }>(`/market/symbols${qs ? `?${qs}` : ''}`);
}

export async function getSymbolInfo(symbol: string) {
  return fetchJson<{
    symbol: string; found: boolean;
    volume_min: number; volume_max: number; volume_step: number;
    trade_contract_size: number; digits: number; point: number;
  }>(`/market/symbol_info/${symbol}`);
}

// Trading
export async function getPositions(symbol?: string) {
  const qs = symbol ? `?symbol=${symbol}` : '';
  return fetchJson<{ positions: any[] }>(`/trading/positions${qs}`);
}

export async function getOrders(symbol?: string) {
  const qs = symbol ? `?symbol=${symbol}` : '';
  return fetchJson<{ orders: any[] }>(`/trading/orders${qs}`);
}

export async function placeOrder(order: {
  symbol: string; side: string; volume: number;
  price?: number; stop_loss?: number; take_profit?: number;
}) {
  return fetchJson('/trading/order', { method: 'POST', body: JSON.stringify(order) });
}

export async function closePosition(ticket: number) {
  return fetchJson(`/trading/position/${ticket}`, { method: 'DELETE' });
}

// Trade History
export async function getTradeHistory(days = 7) {
  return fetchJson<{ trades: any[]; connected: boolean }>(`/trading/history?days=${days}`);
}

// Price Levels
export async function getPriceLevels(symbol: string) {
  return fetchJson<{ levels: any[] }>(`/levels/${symbol}`);
}

// Config
export async function getConfig(name: string) {
  return fetchJson<{ name: string; data: Record<string, unknown> }>(`/strategy/config/${name}`);
}

export async function updateConfig(name: string, data: Record<string, unknown>) {
  return fetchJson(`/strategy/config/${name}`, {
    method: 'PUT',
    body: JSON.stringify({ data })
  });
}

export async function getConfigHistory(name: string) {
  return fetchJson<{ history: any[] }>(`/strategy/config/${name}/history`);
}

// Trade Plans
export async function getTradePlans() {
  return fetchJson<{ plans: import('$lib/types').TradePlanSummary[] }>('/trading/plans');
}

export async function getTradePlan(planId: string) {
  return fetchJson<import('$lib/types').TradePlanDetail>(`/trading/plans/${planId}`);
}

export async function activatePlan(planId: string) {
  return fetchJson<{ success: boolean }>(`/trading/plans/${planId}/activate`, { method: 'POST' });
}

export async function deactivatePlan(planId: string) {
  return fetchJson<{ success: boolean }>(`/trading/plans/${planId}/deactivate`, { method: 'POST' });
}

export async function cancelPlan(planId: string) {
  return fetchJson<{ success: boolean }>(`/trading/plans/${planId}/cancel`, { method: 'POST' });
}

export async function resetPlan(planId: string) {
  return fetchJson<{ success: boolean }>(`/trading/plans/${planId}/reset`, { method: 'POST' });
}

export async function deletePlan(planId: string) {
  return fetchJson<{ success: boolean }>(`/trading/plans/${planId}`, { method: 'DELETE' });
}

// Screener
export async function scanScreener(filters?: {
  price_min?: number; price_max?: number; volume_min?: number;
  range_min?: number; range_max?: number; lookback_days?: number;
}) {
  const params = new URLSearchParams();
  if (filters) {
    for (const [k, v] of Object.entries(filters)) {
      if (v !== undefined && v !== null) params.set(k, String(v));
    }
  }
  const qs = params.toString();
  return fetchJson<{ results: import('$lib/types').ScreenerResult[]; count: number }>(
    `/screener/scan${qs ? `?${qs}` : ''}`
  );
}

/**
 * Stream scan progress via SSE. Hits the backend directly (not through SvelteKit proxy)
 * because the proxy buffers responses and breaks SSE streaming.
 */
export function scanScreenerStream(
  filters?: Record<string, number | undefined>,
  onProgress?: (e: { batch: number; total_batches: number; scanned_so_far: number; total_symbols: number; matched_so_far: number }) => void,
  onDone?: (e: { results: import('$lib/types').ScreenerResult[]; count: number; scanned: number; errors: number }) => void,
  onError?: (err: string) => void,
): () => void {
  const params = new URLSearchParams();
  if (filters) {
    for (const [k, v] of Object.entries(filters)) {
      if (v !== undefined && v !== null) params.set(k, String(v));
    }
  }
  const qs = params.toString();

  // Use the backend directly — same pattern as WebSocket connections
  const backendPort = (window as any).__BACKEND_PORT || location.port;
  const streamUrl = `${location.protocol}//${location.hostname}:${backendPort}/api/screener/scan/stream${qs ? `?${qs}` : ''}`;

  let aborted = false;
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(streamUrl, { signal: controller.signal });
      if (!res.ok || !res.body) {
        onError?.(`Scan failed: ${res.status}`);
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Parse SSE lines
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          if (aborted) return;
          let eventType = 'message';
          let data = '';
          for (const line of part.split('\n')) {
            if (line.startsWith('event: ')) eventType = line.slice(7);
            else if (line.startsWith('data: ')) data = line.slice(6);
          }
          if (!data) continue;
          const parsed = JSON.parse(data);
          if (eventType === 'progress') onProgress?.(parsed);
          else if (eventType === 'done') onDone?.(parsed);
        }
      }
    } catch (e: any) {
      if (!aborted) onError?.(e.message || 'Scan stream failed');
    }
  })();

  return () => {
    aborted = true;
    controller.abort();
  };
}

export async function getScreenerDefaults() {
  return fetchJson<import('$lib/types').ScreenerDefaults>('/screener/defaults');
}

// Health
export async function getHealth() {
  return fetchJson<any>('/health');
}

// Strategy Status
export async function getStrategyStatus() {
  return fetchJson<{ enabled: boolean; symbols: string[] }>('/strategy/status');
}
