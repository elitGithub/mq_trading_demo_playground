<script lang="ts">
  import { openPositions } from '$lib/stores/positions';
  import { closePosition } from '$lib/api/client';

  let closingTicket: number | null = null;

  async function handleClose(ticket: number) {
    if (confirm(`Close position #${ticket}?`)) {
      closingTicket = ticket;
      try {
        await closePosition(ticket);
      } catch (e: any) {
        alert(`Failed to close: ${e.message}`);
      } finally {
        closingTicket = null;
      }
    }
  }
</script>

<div class="card p-5 animate-fade-in delay-3">
  <h3 class="text-[11px] font-semibold text-text-secondary uppercase tracking-[0.15em] mb-4">Open Positions</h3>

  <div class="overflow-x-auto">
    <table class="w-full text-xs">
      <thead>
        <tr class="text-text-tertiary text-[10px] uppercase tracking-wider">
          <th class="pb-3 text-left font-medium">Symbol</th>
          <th class="pb-3 text-left font-medium">Side</th>
          <th class="pb-3 text-right font-medium">Volume</th>
          <th class="pb-3 text-right font-medium">Entry</th>
          <th class="pb-3 text-right font-medium">Current</th>
          <th class="pb-3 text-right font-medium">P&L</th>
          <th class="pb-3 text-right font-medium">SL</th>
          <th class="pb-3 text-right font-medium">TP</th>
          <th class="pb-3 w-16"></th>
        </tr>
      </thead>
      <tbody>
        {#each $openPositions as pos, i}
          <tr class="border-t border-border hover:bg-surface-2/50 transition-colors"
              style="animation: fade-in 300ms ease-out {i * 40}ms both">
            <td class="py-3 text-text font-medium">{pos.symbol}</td>
            <td class="py-3">
              <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold tracking-wider
                {pos.type === 0 ? 'bg-long-dim text-long' : 'bg-short-dim text-short'}">
                {pos.type === 0 ? 'LONG' : 'SHORT'}
              </span>
            </td>
            <td class="py-3 text-right text-text font-mono tabular-nums">{pos.volume}</td>
            <td class="py-3 text-right text-text-secondary font-mono tabular-nums">{pos.price_open.toFixed(5)}</td>
            <td class="py-3 text-right text-text font-mono tabular-nums">{pos.price_current.toFixed(5)}</td>
            <td class="py-3 text-right font-mono font-semibold tabular-nums
              {pos.profit >= 0 ? 'text-long' : 'text-short'}">
              {pos.profit >= 0 ? '+' : ''}{pos.profit.toFixed(2)}
            </td>
            <td class="py-3 text-right text-text-tertiary font-mono tabular-nums">{pos.sl || '—'}</td>
            <td class="py-3 text-right text-text-tertiary font-mono tabular-nums">{pos.tp || '—'}</td>
            <td class="py-3 text-right">
              <button
                on:click={() => handleClose(pos.ticket)}
                disabled={closingTicket === pos.ticket}
                class="px-2.5 py-1 rounded-md text-[10px] font-semibold tracking-wide uppercase
                  text-short bg-short-dim hover:bg-short/20 transition-colors disabled:opacity-40">
                {closingTicket === pos.ticket ? '...' : 'Close'}
              </button>
            </td>
          </tr>
        {/each}
        {#if $openPositions.length === 0}
          <tr>
            <td colspan="9" class="py-10 text-center">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="mx-auto text-text-tertiary mb-2 opacity-50">
                <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/>
              </svg>
              <p class="text-xs text-text-tertiary">No open positions</p>
            </td>
          </tr>
        {/if}
      </tbody>
    </table>
  </div>
</div>
