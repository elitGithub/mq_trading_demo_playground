<script lang="ts">
  import { accountInfo, accountConnected } from '$lib/stores/account';
</script>

<div class="card p-5 animate-fade-in">
  <div class="flex items-center justify-between mb-4">
    <h3 class="text-[11px] font-semibold text-text-secondary uppercase tracking-[0.15em]">Account</h3>
    <div class="flex items-center gap-2">
      <div class="w-1.5 h-1.5 rounded-full {$accountConnected ? 'bg-long animate-pulse-soft' : 'bg-short'}"></div>
      <span class="text-[10px] font-medium {$accountConnected ? 'text-long' : 'text-short'}">
        {$accountConnected ? 'Live' : 'Offline'}
      </span>
    </div>
  </div>

  {#if $accountInfo}
    <div class="grid grid-cols-2 gap-x-6 gap-y-4">
      <div>
        <span class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">Balance</span>
        <p class="text-text font-mono text-xl font-semibold tabular-nums mt-0.5">
          {$accountInfo.balance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
      </div>
      <div>
        <span class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">Equity</span>
        <p class="text-text font-mono text-xl font-semibold tabular-nums mt-0.5">
          {$accountInfo.equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
      </div>
      <div>
        <span class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">Margin</span>
        <p class="text-text font-mono text-sm tabular-nums mt-0.5">{$accountInfo.margin.toFixed(2)}</p>
      </div>
      <div>
        <span class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">Free Margin</span>
        <p class="text-text font-mono text-sm tabular-nums mt-0.5">{$accountInfo.margin_free.toFixed(2)}</p>
      </div>
      <div>
        <span class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">P&L</span>
        <p class="font-mono text-sm font-semibold tabular-nums mt-0.5
          {$accountInfo.profit >= 0 ? 'text-long' : 'text-short'}">
          {$accountInfo.profit >= 0 ? '+' : ''}{$accountInfo.profit.toFixed(2)}
        </p>
      </div>
      <div>
        <span class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">Leverage</span>
        <p class="text-text font-mono text-sm tabular-nums mt-0.5">1:{$accountInfo.leverage}</p>
      </div>
    </div>
  {:else}
    <div class="flex items-center gap-2 py-4">
      <div class="w-4 h-4 border-2 border-text-tertiary border-t-accent rounded-full animate-spin"></div>
      <p class="text-xs text-text-tertiary">
        {$accountConnected ? 'Loading account...' : 'Waiting for MT5 connection'}
      </p>
    </div>
  {/if}
</div>
