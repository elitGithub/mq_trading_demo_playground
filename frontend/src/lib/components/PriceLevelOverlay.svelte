<script lang="ts">
  import type { PriceLevel } from '$lib/types';
  import { getPriceLevels } from '$lib/api/client';
  import { selectedSymbol } from '$lib/stores/market';

  let levels: PriceLevel[] = [];

  async function loadLevels(symbol: string) {
    try {
      const res = await getPriceLevels(symbol);
      levels = res.levels || [];
    } catch {
      levels = [];
    }
  }

  const unsub = selectedSymbol.subscribe((sym) => loadLevels(sym));

  import { onDestroy } from 'svelte';
  onDestroy(() => unsub());
</script>

<div class="card p-5 animate-fade-in delay-2">
  <h3 class="text-[11px] font-semibold text-text-secondary uppercase tracking-[0.15em] mb-4">Price Levels</h3>

  {#if levels.length === 0}
    <div class="py-4 text-center">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="mx-auto text-text-tertiary mb-2">
        <path d="M3 3v18h18" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M7 12h10" stroke-linecap="round" stroke-dasharray="2 3"/>
      </svg>
      <p class="text-xs text-text-tertiary">No active levels detected</p>
    </div>
  {:else}
    <div class="space-y-0.5">
      {#each levels as level, i}
        <div class="flex items-center gap-3 text-xs py-2 px-2 rounded-md hover:bg-surface-2 transition-colors"
             style="animation-delay: {i * 30}ms">
          <span class="w-10 text-center py-0.5 rounded text-[10px] font-bold uppercase tracking-wider
            {level.level_type === 'support'
              ? 'bg-long-dim text-long'
              : 'bg-short-dim text-short'}">
            {level.level_type === 'support' ? 'SUP' : 'RES'}
          </span>
          <span class="flex-1 text-text font-mono font-medium tabular-nums">{level.price.toFixed(5)}</span>
          <span class="text-text-tertiary font-mono tabular-nums" title="Strength">
            {level.strength.toFixed(1)}
          </span>
          <span class="text-text-tertiary font-mono tabular-nums text-[10px]" title="Touches">
            x{level.touch_count}
          </span>
        </div>
      {/each}
    </div>
  {/if}
</div>
