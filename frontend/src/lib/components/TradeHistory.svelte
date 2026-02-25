<script lang="ts">
  import { onMount } from 'svelte';
  import { getTradeHistory } from '$lib/api/client';

  interface Trade {
    close_time: string;
    close_time_ts: number;
    symbol: string;
    side: 'BUY' | 'SELL';
    volume: number;
    entry_price: number | null;
    exit_price: number;
    pnl: number;
    magic: number;
    comment: string;
    entry_time: string | null;
    duration_s: number | null;
  }

  let trades: Trade[] = [];
  let loading = true;
  let error = '';
  let days = 7;

  async function load() {
    loading = true;
    error = '';
    try {
      const res = await getTradeHistory(days);
      trades = res.trades;
    } catch (e: any) {
      error = e.message || 'Failed to load';
    } finally {
      loading = false;
    }
  }

  onMount(load);

  function formatTime(iso: string | null): string {
    if (!iso) return '--';
    const d = new Date(iso);
    return d.toLocaleString('en-GB', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    });
  }

  function formatDuration(s: number | null): string {
    if (s === null) return '--';
    if (s < 60) return `${s}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${h}h ${m}m`;
  }

  $: totalPnl = trades.reduce((sum, t) => sum + t.pnl, 0);
  $: winners = trades.filter(t => t.pnl > 0).length;
  $: losers = trades.filter(t => t.pnl < 0).length;
</script>

<div class="space-y-4 animate-fade-in">
  <!-- Summary + Controls -->
  <div class="card p-4 flex items-center justify-between">
    <div class="flex items-center gap-6">
      <div>
        <span class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider block">Total P&L</span>
        <span class="text-lg font-semibold font-mono tabular-nums {totalPnl >= 0 ? 'text-long' : 'text-short'}">
          {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(2)}
        </span>
      </div>
      <div>
        <span class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider block">Trades</span>
        <span class="text-sm font-mono tabular-nums text-text">{trades.length}</span>
      </div>
      <div>
        <span class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider block">Win/Loss</span>
        <span class="text-sm font-mono tabular-nums">
          <span class="text-long">{winners}</span>
          <span class="text-text-tertiary">/</span>
          <span class="text-short">{losers}</span>
        </span>
      </div>
    </div>
    <div class="flex items-center gap-2">
      {#each [1, 7, 30] as d}
        <button on:click={() => { days = d; load(); }}
          class="text-[10px] px-2.5 py-1 rounded-md border transition-colors
            {days === d
              ? 'bg-accent/10 text-accent border-accent/30'
              : 'bg-surface-2 text-text-tertiary border-border hover:text-text-secondary hover:border-border-hover'}">
          {d === 1 ? 'Today' : `${d}d`}
        </button>
      {/each}
      <button on:click={load}
        class="text-[10px] px-2.5 py-1 rounded-md bg-surface-2 text-text-tertiary border border-border hover:text-text-secondary hover:border-border-hover transition-colors">
        Refresh
      </button>
    </div>
  </div>

  {#if error}
    <div class="px-3 py-2 rounded-lg bg-short/10 border border-short/20 text-short text-xs">{error}</div>
  {/if}

  <!-- Trade Table -->
  <div class="card p-5">
    <div class="overflow-x-auto">
      <table class="w-full text-xs">
        <thead>
          <tr class="text-text-tertiary text-[10px] uppercase tracking-wider">
            <th class="pb-3 text-left font-medium">Closed</th>
            <th class="pb-3 text-left font-medium">Symbol</th>
            <th class="pb-3 text-left font-medium">Side</th>
            <th class="pb-3 text-right font-medium">Volume</th>
            <th class="pb-3 text-right font-medium">Entry</th>
            <th class="pb-3 text-right font-medium">Exit</th>
            <th class="pb-3 text-right font-medium">Duration</th>
            <th class="pb-3 text-right font-medium">P&L</th>
          </tr>
        </thead>
        <tbody>
          {#each trades as t, i}
            <tr class="border-t border-border hover:bg-surface-2/50 transition-colors"
                style="animation: fade-in 300ms ease-out {i * 40}ms both">
              <td class="py-3 text-text-tertiary font-mono tabular-nums">{formatTime(t.close_time)}</td>
              <td class="py-3 text-text font-medium font-mono">{t.symbol}</td>
              <td class="py-3">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold tracking-wider
                  {t.side === 'BUY' ? 'bg-long/10 text-long' : 'bg-short/10 text-short'}">
                  {t.side === 'BUY' ? 'LONG' : 'SHORT'}
                </span>
              </td>
              <td class="py-3 text-right text-text font-mono tabular-nums">{t.volume}</td>
              <td class="py-3 text-right text-text-secondary font-mono tabular-nums">{t.entry_price ?? '--'}</td>
              <td class="py-3 text-right text-text-secondary font-mono tabular-nums">{t.exit_price}</td>
              <td class="py-3 text-right text-text-tertiary font-mono tabular-nums">{formatDuration(t.duration_s)}</td>
              <td class="py-3 text-right font-mono font-semibold tabular-nums
                {t.pnl >= 0 ? 'text-long' : 'text-short'}">
                {t.pnl >= 0 ? '+' : ''}{t.pnl.toFixed(2)}
              </td>
            </tr>
          {/each}
          {#if trades.length === 0}
            <tr>
              <td colspan="8" class="py-12 text-center">
                {#if loading}
                  <div class="flex items-center justify-center gap-2">
                    <span class="w-4 h-4 border-2 border-text-tertiary border-t-accent rounded-full animate-spin"></span>
                    <span class="text-xs text-text-tertiary">Loading trades...</span>
                  </div>
                {:else}
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="mx-auto text-text-tertiary mb-2 opacity-50">
                    <circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 15"/>
                  </svg>
                  <p class="text-xs text-text-tertiary">No closed trades in this period</p>
                {/if}
              </td>
            </tr>
          {/if}
        </tbody>
      </table>
    </div>
  </div>
</div>
