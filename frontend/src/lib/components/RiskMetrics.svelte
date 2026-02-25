<script lang="ts">
  import { accountInfo } from '$lib/stores/account';
  import { openPositions } from '$lib/stores/positions';

  let posCount = 0;
  let totalExposure = 0;
  let unrealizedPnl = 0;
  let drawdownPct = 0;

  const unsub = openPositions.subscribe(positions => {
    posCount = positions.length;
    totalExposure = positions.reduce((sum, p) => sum + Math.abs(p.volume), 0);
    unrealizedPnl = positions.reduce((sum, p) => sum + p.profit, 0);
  });

  const unsub2 = accountInfo.subscribe(info => {
    if (info && info.balance > 0) {
      drawdownPct = ((info.balance - info.equity) / info.balance) * 100;
    }
  });

  import { onDestroy } from 'svelte';
  onDestroy(() => { unsub(); unsub2(); });

  function getDrawdownColor(pct: number): string {
    if (pct > 5) return 'text-short';
    if (pct > 2) return 'text-warning';
    return 'text-text';
  }
</script>

<div class="card p-5 animate-fade-in delay-1">
  <h3 class="text-[11px] font-semibold text-text-secondary uppercase tracking-[0.15em] mb-4">Risk</h3>

  <div class="space-y-3">
    <div class="flex justify-between items-center">
      <span class="text-xs text-text-tertiary">Open Positions</span>
      <span class="text-xs text-text font-mono font-medium tabular-nums">{posCount}</span>
    </div>

    <div class="h-px bg-border"></div>

    <div class="flex justify-between items-center">
      <span class="text-xs text-text-tertiary">Total Exposure</span>
      <span class="text-xs text-text font-mono tabular-nums">{totalExposure.toFixed(2)} <span class="text-text-tertiary">lots</span></span>
    </div>

    <div class="h-px bg-border"></div>

    <div class="flex justify-between items-center">
      <span class="text-xs text-text-tertiary">Unrealized P&L</span>
      <span class="text-xs font-mono font-semibold tabular-nums
        {unrealizedPnl >= 0 ? 'text-long' : 'text-short'}">
        {unrealizedPnl >= 0 ? '+' : ''}{unrealizedPnl.toFixed(2)}
      </span>
    </div>

    <div class="h-px bg-border"></div>

    <div class="flex justify-between items-center">
      <span class="text-xs text-text-tertiary">Drawdown</span>
      <span class="text-xs font-mono font-semibold tabular-nums {getDrawdownColor(drawdownPct)}">
        {drawdownPct.toFixed(1)}%
      </span>
    </div>

    {#if $accountInfo}
      <div class="h-px bg-border"></div>
      <div class="flex justify-between items-center">
        <span class="text-xs text-text-tertiary">Margin Level</span>
        <span class="text-xs text-text font-mono tabular-nums">
          {$accountInfo.margin_level > 0 ? $accountInfo.margin_level.toFixed(0) + '%' : '—'}
        </span>
      </div>
    {/if}
  </div>
</div>
