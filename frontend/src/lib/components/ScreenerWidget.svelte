<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { scanScreener } from '$lib/api/client';
  import { selectedSymbol } from '$lib/stores/market';
  import type { ScreenerResult } from '$lib/types';

  let results: ScreenerResult[] = [];
  let loading = true;
  let refreshTimer: ReturnType<typeof setInterval>;

  async function refresh() {
    try {
      const res = await scanScreener();
      results = res.results.slice(0, 5);
    } catch { /* silent */ }
    loading = false;
  }

  function selectSymbol(symbol: string) {
    $selectedSymbol = symbol;
    goto('/trade');
  }

  onMount(() => {
    refresh();
    refreshTimer = setInterval(refresh, 60_000);
  });

  onDestroy(() => clearInterval(refreshTimer));
</script>

<div class="card p-5 animate-fade-in">
  <div class="flex items-center justify-between mb-4">
    <h3 class="text-[11px] font-semibold text-text-secondary uppercase tracking-[0.15em]">Screener</h3>
    <a href="/screener" class="text-[10px] font-medium text-accent hover:underline">View All &rarr;</a>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-6">
      <span class="w-4 h-4 border-2 border-accent/30 border-t-accent rounded-full animate-spin"></span>
    </div>
  {:else if results.length === 0}
    <p class="text-xs text-text-tertiary text-center py-4">No matches</p>
  {:else}
    <table class="w-full text-xs">
      <thead>
        <tr class="text-text-tertiary text-[10px] uppercase tracking-wider">
          <th class="pb-2 text-left font-medium">Symbol</th>
          <th class="pb-2 text-right font-medium">Price</th>
          <th class="pb-2 text-right font-medium">Range</th>
        </tr>
      </thead>
      <tbody>
        {#each results as row}
          <tr class="border-t border-border hover:bg-surface-2/50 transition-colors cursor-pointer"
              on:click={() => selectSymbol(row.symbol)}>
            <td class="py-2 text-text font-medium">{row.symbol}</td>
            <td class="py-2 text-right font-mono tabular-nums text-text-secondary">{row.last_price.toFixed(5)}</td>
            <td class="py-2 text-right font-mono tabular-nums text-text-secondary">{row.avg_daily_range.toFixed(5)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>
