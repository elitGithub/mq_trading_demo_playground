<script lang="ts">
  import { placeOrder } from '$lib/api/client';
  import { selectedSymbol } from '$lib/stores/market';
  import { onDestroy } from 'svelte';

  let side: 'BUY' | 'SELL' = 'BUY';
  let volume = 0.01;
  let stopLoss: number | undefined = undefined;
  let takeProfit: number | undefined = undefined;
  let submitting = false;
  let message = '';
  let messageType: 'success' | 'error' = 'success';

  let currentSymbol = '';
  const unsub = selectedSymbol.subscribe(v => currentSymbol = v);
  onDestroy(() => unsub());

  async function submit() {
    submitting = true;
    message = '';
    try {
      const result: any = await placeOrder({
        symbol: currentSymbol,
        side,
        volume,
        stop_loss: stopLoss,
        take_profit: takeProfit
      });
      if (result.success) {
        message = `Filled #${result.ticket}`;
        messageType = 'success';
      } else {
        message = result.comment || 'Order rejected';
        messageType = 'error';
      }
    } catch (e: any) {
      message = e.message;
      messageType = 'error';
    } finally {
      submitting = false;
    }
  }
</script>

<div class="card p-5">
  <h3 class="text-[11px] font-semibold text-text-secondary uppercase tracking-[0.15em] mb-4">Place Order</h3>

  <!-- Buy / Sell toggle -->
  <div class="flex gap-1.5 mb-5 p-1 rounded-lg bg-surface-0">
    <button
      class="flex-1 py-2 rounded-md font-semibold text-xs tracking-wide transition-all duration-200
        {side === 'BUY'
          ? 'bg-long text-base shadow-md shadow-long/20'
          : 'text-text-tertiary hover:text-text-secondary'}"
      on:click={() => side = 'BUY'}>
      LONG
    </button>
    <button
      class="flex-1 py-2 rounded-md font-semibold text-xs tracking-wide transition-all duration-200
        {side === 'SELL'
          ? 'bg-short text-base shadow-md shadow-short/20'
          : 'text-text-tertiary hover:text-text-secondary'}"
      on:click={() => side = 'SELL'}>
      SHORT
    </button>
  </div>

  <!-- Volume -->
  <label class="block text-[10px] font-medium text-text-tertiary uppercase tracking-wider mb-1.5">Volume (lots)</label>
  <input type="number" bind:value={volume} step="0.01" min="0.01"
    class="w-full bg-surface-0 text-text rounded-lg px-3 py-2.5 mb-4 text-sm border border-border
      focus:border-accent focus:outline-none font-mono tabular-nums placeholder:text-text-tertiary
      transition-colors" />

  <!-- Stop Loss -->
  <label class="block text-[10px] font-medium text-text-tertiary uppercase tracking-wider mb-1.5">Stop Loss</label>
  <input type="number" bind:value={stopLoss} step="0.00001" placeholder="Optional"
    class="w-full bg-surface-0 text-text rounded-lg px-3 py-2.5 mb-4 text-sm border border-border
      focus:border-accent focus:outline-none font-mono tabular-nums placeholder:text-text-tertiary
      transition-colors" />

  <!-- Take Profit -->
  <label class="block text-[10px] font-medium text-text-tertiary uppercase tracking-wider mb-1.5">Take Profit</label>
  <input type="number" bind:value={takeProfit} step="0.00001" placeholder="Optional"
    class="w-full bg-surface-0 text-text rounded-lg px-3 py-2.5 mb-5 text-sm border border-border
      focus:border-accent focus:outline-none font-mono tabular-nums placeholder:text-text-tertiary
      transition-colors" />

  <!-- Submit -->
  <button on:click={submit} disabled={submitting}
    class="w-full py-3 rounded-lg font-bold text-sm tracking-wide text-white transition-all duration-200
      disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed
      {side === 'BUY'
        ? 'bg-long hover:shadow-lg hover:shadow-long/25 active:scale-[0.98]'
        : 'bg-short hover:shadow-lg hover:shadow-short/25 active:scale-[0.98]'}">
    {#if submitting}
      <span class="inline-flex items-center gap-2">
        <span class="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
        Sending
      </span>
    {:else}
      {side} {currentSymbol}
    {/if}
  </button>

  <!-- Feedback message -->
  {#if message}
    <div class="mt-3 px-3 py-2 rounded-md text-xs font-medium text-center
      {messageType === 'success' ? 'bg-long-dim text-long' : 'bg-short-dim text-short'}">
      {message}
    </div>
  {/if}
</div>
