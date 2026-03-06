<script lang="ts">
  import ScreenerFilters from '$lib/components/ScreenerFilters.svelte';
  import ScreenerTable from '$lib/components/ScreenerTable.svelte';
</script>

<div class="space-y-5">
  <!-- Header -->
  <div class="flex items-end justify-between">
    <div>
      <h1 class="text-xl font-semibold text-text tracking-tight">Screener</h1>
      <p class="text-xs text-text-tertiary mt-1">Scan MT5 symbols against price, volume, and range filters</p>
    </div>
  </div>

  <ScreenerFilters />
  <ScreenerTable />
</div>
