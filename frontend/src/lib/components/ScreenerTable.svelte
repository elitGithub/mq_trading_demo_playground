<script lang="ts">
  import { goto } from '$app/navigation';
  import { screenerResults, screenerLoading } from '$lib/stores/screener';
  import { selectedSymbol } from '$lib/stores/market';

  function selectSymbol(symbol: string) {
    $selectedSymbol = symbol;
    goto('/trade');
  }
</script>

<div class="card p-5 animate-fade-in">
  <h3 class="text-[11px] font-semibold text-text-secondary uppercase tracking-[0.15em] mb-4">Results
    {#if $screenerResults.length > 0}
      <span class="text-text-tertiary font-normal ml-1">({$screenerResults.length})</span>
    {/if}
  </h3>

  <div class="overflow-x-auto">
    <table class="w-full text-xs">
      <thead>
        <tr class="text-text-tertiary text-[10px] uppercase tracking-wider">
          <th class="pb-3 text-left font-medium">Symbol</th>
          <th class="pb-3 text-right font-medium">Last Price</th>
          <th class="pb-3 text-right font-medium">Avg Volume</th>
          <th class="pb-3 text-right font-medium">Avg Daily Range</th>
        </tr>
      </thead>
      <tbody>
        {#each $screenerResults as row, i}
          <tr class="border-t border-border hover:bg-surface-2/50 transition-colors cursor-pointer"
              style="animation: fade-in 300ms ease-out {i * 40}ms both"
              on:click={() => selectSymbol(row.symbol)}>
            <td class="py-3 text-text font-medium">{row.symbol}</td>
            <td class="py-3 text-right text-text font-mono tabular-nums">{row.last_price.toFixed(5)}</td>
            <td class="py-3 text-right text-text-secondary font-mono tabular-nums">{row.avg_volume.toLocaleString()}</td>
            <td class="py-3 text-right text-text-secondary font-mono tabular-nums">{row.avg_daily_range.toFixed(5)}</td>
          </tr>
        {/each}
        {#if $screenerResults.length === 0 && !$screenerLoading}
          <tr>
            <td colspan="4" class="py-10 text-center">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="mx-auto text-text-tertiary mb-2 opacity-50">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
              </svg>
              <p class="text-xs text-text-tertiary">No results — adjust filters and scan</p>
            </td>
          </tr>
        {/if}
        {#if $screenerLoading}
          <tr>
            <td colspan="4" class="py-10 text-center">
              <span class="inline-flex items-center gap-2 text-xs text-text-tertiary">
                <span class="w-4 h-4 border-2 border-accent/30 border-t-accent rounded-full animate-spin"></span>
                Scanning symbols...
              </span>
            </td>
          </tr>
        {/if}
      </tbody>
    </table>
  </div>
</div>
