<script lang="ts">
  import AccountSummary from '$lib/components/AccountSummary.svelte';
  import PositionTable from '$lib/components/PositionTable.svelte';
  import RiskMetrics from '$lib/components/RiskMetrics.svelte';
  import PriceLevelOverlay from '$lib/components/PriceLevelOverlay.svelte';
</script>

<div class="space-y-5">
  <!-- Header -->
  <div class="flex items-end justify-between">
    <div>
      <h1 class="text-xl font-semibold text-text tracking-tight">Dashboard</h1>
      <p class="text-xs text-text-tertiary mt-1">Account overview and risk monitoring</p>
    </div>
    <div class="text-[10px] font-mono text-text-tertiary tabular-nums">
      {new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
    </div>
  </div>

  <!-- Metrics grid -->
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
    <AccountSummary />
    <RiskMetrics />
    <PriceLevelOverlay />
  </div>

  <!-- Positions -->
  <PositionTable />
</div>
