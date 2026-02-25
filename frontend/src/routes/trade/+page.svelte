<script lang="ts">
  import Chart from '$lib/components/Chart.svelte';
  import OrderPanel from '$lib/components/OrderPanel.svelte';
  import PositionTable from '$lib/components/PositionTable.svelte';
  import PriceLevelOverlay from '$lib/components/PriceLevelOverlay.svelte';
  import { selectedSymbol, selectedTimeframe, chartBars, tradeableSymbols, symbolsLoading, currentPrices } from '$lib/stores/market';
  import { subscribeTopic, unsubscribeTopic, wsConnected } from '$lib/stores/websocket';
  import { wsLastMessage } from '$lib/stores/websocket';
  import { getBars, getTradeableSymbols } from '$lib/api/client';
  import { onMount, onDestroy, tick } from 'svelte';

  const timeframes = ['M1', 'M5', 'M15', 'H1', 'H4', 'D1'];

  let currentSymbol = '';
  let currentTf = '';
  let symbolsConnected = true;
  let symbolOpen = false;
  let symbolQuery = '';
  let symbolMenuEl: HTMLDivElement | null = null;
  let symbolSearchEl: HTMLInputElement | null = null;
  let filteredSymbols: string[] = [];
  const hasWindow = typeof window !== 'undefined';

  function timeframeSeconds(tf: string): number {
    switch (tf) {
      case 'M1': return 60;
      case 'M5': return 300;
      case 'M15': return 900;
      case 'M30': return 1800;
      case 'H1': return 3600;
      case 'H4': return 14400;
      case 'D1': return 86400;
      default: return 60;
    }
  }

  function updateBarsWithTick(bars: any[], barTime: number, price: number) {
    if (!Array.isArray(bars) || bars.length === 0) return bars;
    const last = bars[bars.length - 1];
    if (!last || typeof last.time !== 'number') return bars;
    if (barTime < last.time) return bars;

    if (barTime === last.time) {
      const updated = {
        ...last,
        close: price,
        high: Math.max(last.high, price),
        low: Math.min(last.low, price),
        tick_volume: (last.tick_volume ?? 0) + 1,
      };
      return [...bars.slice(0, -1), updated];
    }

    const open = last.close ?? price;
    const next = {
      time: barTime,
      open,
      high: price,
      low: price,
      close: price,
      tick_volume: 1,
    };
    const combined = [...bars, next];
    return combined.length > 300 ? combined.slice(combined.length - 300) : combined;
  }

  async function loadChart(symbol: string, tf: string) {
    try {
      const res = await getBars(symbol, tf, 300);
      $chartBars = res.bars;
    } catch { /* retry */ }
  }

  async function loadSymbols() {
    $symbolsLoading = true;
    try {
      const res = await getTradeableSymbols({ tradeable: false, visible_only: true });
      symbolsConnected = res.connected;
      const list = Array.isArray(res.symbols) ? res.symbols : [];
      $tradeableSymbols = list;
      if (list.length && !list.includes($selectedSymbol)) {
        $selectedSymbol = list[0];
      }
    } catch {
      symbolsConnected = false;
      $tradeableSymbols = [];
    } finally {
      $symbolsLoading = false;
    }
  }

  const unsubSymbols = tradeableSymbols.subscribe((list) => {
    if (!Array.isArray(list) || list.length === 0) return;
    if (!list.includes($selectedSymbol)) {
      $selectedSymbol = list[0];
    }
  });

  const unsub1 = selectedSymbol.subscribe(sym => {
    if (currentSymbol) unsubscribeTopic(currentSymbol);
    currentSymbol = sym;
    subscribeTopic(sym);
    loadChart(sym, currentTf || 'H1');
  });

  const unsub2 = selectedTimeframe.subscribe(tf => {
    currentTf = tf;
    if (currentSymbol) loadChart(currentSymbol, tf);
  });

  const unsubWsConnected = wsConnected.subscribe((connected) => {
    if (connected && currentSymbol) {
      subscribeTopic(currentSymbol);
    }
  });

  const unsubWs = wsLastMessage.subscribe((msg) => {
    if (!msg || msg.type !== 'tick') return;
    if (!currentSymbol || msg.symbol !== currentSymbol) return;

    const bid = Number(msg.bid);
    const ask = Number(msg.ask);
    if (!Number.isFinite(bid) || !Number.isFinite(ask)) return;

    $currentPrices = {
      ...$currentPrices,
      [msg.symbol]: { bid, ask },
    };

    const price = (bid + ask) / 2;
    const tfSec = timeframeSeconds(currentTf || 'H1');
    const tickTime = msg.time ? Math.floor(Date.parse(msg.time) / 1000) : Math.floor(Date.now() / 1000);
    const barTime = Math.floor(tickTime / tfSec) * tfSec;
    $chartBars = updateBarsWithTick($chartBars, barTime, price);
  });

  function openSymbolMenu() {
    symbolOpen = true;
    symbolQuery = '';
    tick().then(() => symbolSearchEl?.focus());
  }

  function closeSymbolMenu() {
    symbolOpen = false;
  }

  function selectSymbol(sym: string) {
    $selectedSymbol = sym;
    closeSymbolMenu();
  }

  function handleOutsideClick(event: MouseEvent) {
    if (!symbolOpen) return;
    if (symbolMenuEl && !symbolMenuEl.contains(event.target as Node)) {
      closeSymbolMenu();
    }
  }

  $: filteredSymbols = $tradeableSymbols.filter((s) =>
    s.toLowerCase().includes(symbolQuery.trim().toLowerCase())
  );

  onMount(() => {
    loadSymbols();
    loadChart(currentSymbol || 'EURUSD', currentTf || 'H1');
    const refresh = setInterval(loadSymbols, 30000);
    if (hasWindow) window.addEventListener('mousedown', handleOutsideClick);
    return () => clearInterval(refresh);
  });

  onDestroy(() => {
    unsub1();
    unsub2();
    unsubSymbols();
    unsubWsConnected();
    unsubWs();
    if (hasWindow) window.removeEventListener('mousedown', handleOutsideClick);
    if (currentSymbol) unsubscribeTopic(currentSymbol);
  });
</script>

<div class="flex gap-4 h-[calc(100vh-48px)] animate-fade-in">
  <!-- Chart area -->
  <div class="flex-1 min-w-0 flex flex-col">
    <!-- Symbol bar -->
    <div class="flex items-center gap-2 mb-3">
      <div class="relative" bind:this={symbolMenuEl}>
        <button
          type="button"
          on:click={() => symbolOpen ? closeSymbolMenu() : openSymbolMenu()}
          disabled={$symbolsLoading || $tradeableSymbols.length === 0}
          class="min-w-[140px] bg-surface-1 text-text rounded-lg px-3 py-2 text-xs font-semibold
            border border-border focus:border-accent focus:outline-none
            cursor-pointer transition-colors disabled:opacity-60 disabled:cursor-not-allowed
            inline-flex items-center gap-2 justify-between">
          <span class="font-mono tabular-nums">{$selectedSymbol}</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            class="text-text-tertiary transition-transform {symbolOpen ? 'rotate-180' : ''}">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>

        {#if symbolOpen}
          <div class="absolute left-0 top-full mt-2 w-64 rounded-xl border border-border bg-surface-2 shadow-xl shadow-black/40 z-50">
            <div class="p-2 border-b border-border">
              <input
                bind:this={symbolSearchEl}
                bind:value={symbolQuery}
                type="text"
                placeholder="Search symbols..."
                class="w-full bg-surface-0 text-text text-xs rounded-lg px-3 py-2 border border-border focus:border-accent/60 focus:outline-none"
              />
            </div>
            <div class="max-h-64 overflow-y-auto">
              {#if $symbolsLoading}
                <div class="px-3 py-2 text-xs text-text-tertiary">Loading symbols...</div>
              {:else if $tradeableSymbols.length === 0}
                <div class="px-3 py-2 text-xs text-text-tertiary">{symbolsConnected ? 'No tradeable symbols' : 'MT5 offline'}</div>
              {:else if filteredSymbols.length === 0}
                <div class="px-3 py-2 text-xs text-text-tertiary">No matches</div>
              {:else}
                {#each filteredSymbols as sym}
                  <button
                    type="button"
                    on:click={() => selectSymbol(sym)}
                    class="w-full text-left px-3 py-2 text-xs font-mono tabular-nums
                      hover:bg-surface-3 transition-colors
                      {sym === $selectedSymbol ? 'bg-surface-3 text-text' : 'text-text-secondary'}">
                    {sym}
                  </button>
                {/each}
              {/if}
            </div>
          </div>
        {/if}
      </div>

      <div class="flex gap-0.5 p-0.5 rounded-lg bg-surface-0">
        {#each timeframes as tf}
          <button
            on:click={() => $selectedTimeframe = tf}
            class="px-2.5 py-1.5 rounded-md text-[10px] font-semibold tracking-wider transition-all duration-150
              {$selectedTimeframe === tf
                ? 'bg-surface-2 text-text shadow-sm'
                : 'text-text-tertiary hover:text-text-secondary'}">
            {tf}
          </button>
        {/each}
      </div>

      <div class="ml-auto flex items-center gap-2">
        <span class="text-[10px] font-mono text-text-tertiary tabular-nums">
          {currentSymbol || 'EURUSD'} / {currentTf || 'H1'}
        </span>
      </div>
    </div>

    <!-- Chart -->
    <div class="flex-1 min-h-0">
      <Chart />
    </div>

    <!-- Positions below chart -->
    <div class="mt-4 flex-shrink-0">
      <PositionTable />
    </div>
  </div>

  <!-- Right sidebar -->
  <div class="w-72 flex-shrink-0 flex flex-col gap-4 overflow-y-auto">
    <OrderPanel />
    <PriceLevelOverlay />
  </div>
</div>
