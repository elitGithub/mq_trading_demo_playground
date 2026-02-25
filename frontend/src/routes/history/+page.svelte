<script lang="ts">
  import TradeHistory from '$lib/components/TradeHistory.svelte';
</script>

<div class="space-y-5">
  <div>
    <h1 class="text-xl font-semibold text-text tracking-tight">Trade History</h1>
    <p class="text-xs text-text-tertiary mt-1">Closed positions and performance log</p>
  </div>

  <TradeHistory />
</div>
