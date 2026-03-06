<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { getScreenerDefaults, scanScreenerStream } from '$lib/api/client';
  import { screenerResults, screenerLoading, screenerError, screenerProgress } from '$lib/stores/screener';

  let priceMin: number | undefined;
  let priceMax: number | undefined;
  let volumeMin: number | undefined;
  let rangeMin: number | undefined;
  let rangeMax: number | undefined;
  let lookbackDays: number | undefined;
  let closeStream: (() => void) | null = null;

  onMount(async () => {
    try {
      const defaults = await getScreenerDefaults();
      priceMin = defaults.price_min;
      priceMax = defaults.price_max;
      volumeMin = defaults.volume_min;
      rangeMin = defaults.range_min;
      rangeMax = defaults.range_max;
      lookbackDays = defaults.lookback_days;
    } catch { /* use empty fields */ }
  });

  onDestroy(() => {
    closeStream?.();
  });

  function handleScan() {
    closeStream?.();
    $screenerLoading = true;
    $screenerError = '';
    $screenerProgress = null;
    $screenerResults = [];

    closeStream = scanScreenerStream(
      {
        price_min: priceMin,
        price_max: priceMax,
        volume_min: volumeMin,
        range_min: rangeMin,
        range_max: rangeMax,
        lookback_days: lookbackDays,
      },
      (progress) => {
        $screenerProgress = {
          batch: progress.batch,
          totalBatches: progress.total_batches,
          scannedSoFar: progress.scanned_so_far,
          totalSymbols: progress.total_symbols,
          matchedSoFar: progress.matched_so_far,
        };
      },
      (done) => {
        $screenerResults = done.results;
        $screenerLoading = false;
        $screenerProgress = null;
        closeStream = null;
      },
      (err) => {
        $screenerError = err;
        $screenerLoading = false;
        $screenerProgress = null;
        closeStream = null;
      },
    );
  }

  $: progressPct = $screenerProgress
    ? Math.round(($screenerProgress.scannedSoFar / $screenerProgress.totalSymbols) * 100)
    : 0;
</script>

<div class="card p-5">
  <h3 class="text-[11px] font-semibold text-text-secondary uppercase tracking-[0.15em] mb-4">Screener Filters</h3>

  <div class="grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-3">
    <!-- Price Min -->
    <div>
      <label class="block text-[10px] font-medium text-text-tertiary uppercase tracking-wider mb-1.5">Price Min</label>
      <input type="number" bind:value={priceMin} step="0.01"
        class="w-full bg-surface-0 text-text rounded-lg px-3 py-2 text-xs border border-border
          focus:border-accent focus:outline-none font-mono tabular-nums placeholder:text-text-tertiary transition-colors" />
    </div>

    <!-- Price Max -->
    <div>
      <label class="block text-[10px] font-medium text-text-tertiary uppercase tracking-wider mb-1.5">Price Max</label>
      <input type="number" bind:value={priceMax} step="0.01"
        class="w-full bg-surface-0 text-text rounded-lg px-3 py-2 text-xs border border-border
          focus:border-accent focus:outline-none font-mono tabular-nums placeholder:text-text-tertiary transition-colors" />
    </div>

    <!-- Volume Min -->
    <div>
      <label class="block text-[10px] font-medium text-text-tertiary uppercase tracking-wider mb-1.5">Volume Min</label>
      <input type="number" bind:value={volumeMin} step="1000"
        class="w-full bg-surface-0 text-text rounded-lg px-3 py-2 text-xs border border-border
          focus:border-accent focus:outline-none font-mono tabular-nums placeholder:text-text-tertiary transition-colors" />
    </div>

    <!-- Range Min -->
    <div>
      <label class="block text-[10px] font-medium text-text-tertiary uppercase tracking-wider mb-1.5">Range Min</label>
      <input type="number" bind:value={rangeMin} step="0.01"
        class="w-full bg-surface-0 text-text rounded-lg px-3 py-2 text-xs border border-border
          focus:border-accent focus:outline-none font-mono tabular-nums placeholder:text-text-tertiary transition-colors" />
    </div>

    <!-- Range Max -->
    <div>
      <label class="block text-[10px] font-medium text-text-tertiary uppercase tracking-wider mb-1.5">Range Max</label>
      <input type="number" bind:value={rangeMax} step="0.01"
        class="w-full bg-surface-0 text-text rounded-lg px-3 py-2 text-xs border border-border
          focus:border-accent focus:outline-none font-mono tabular-nums placeholder:text-text-tertiary transition-colors" />
    </div>

    <!-- Lookback Days -->
    <div>
      <label class="block text-[10px] font-medium text-text-tertiary uppercase tracking-wider mb-1.5">Lookback Days</label>
      <input type="number" bind:value={lookbackDays} step="1" min="1"
        class="w-full bg-surface-0 text-text rounded-lg px-3 py-2 text-xs border border-border
          focus:border-accent focus:outline-none font-mono tabular-nums placeholder:text-text-tertiary transition-colors" />
    </div>
  </div>

  <!-- Scan button -->
  <button on:click={handleScan} disabled={$screenerLoading}
    class="mt-4 w-full py-2.5 rounded-lg font-semibold text-xs tracking-wide text-white
      bg-accent hover:shadow-lg hover:shadow-accent/25 active:scale-[0.98] transition-all duration-200
      disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer">
    {#if $screenerLoading}
      <span class="inline-flex items-center gap-2">
        <span class="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
        Scanning
      </span>
    {:else}
      Scan
    {/if}
  </button>

  <!-- Progress bar -->
  {#if $screenerProgress}
    <div class="mt-3 space-y-1.5">
      <div class="flex items-center justify-between text-[10px] font-medium text-text-tertiary">
        <span>Batch {$screenerProgress.batch}/{$screenerProgress.totalBatches}</span>
        <span>{$screenerProgress.scannedSoFar}/{$screenerProgress.totalSymbols} symbols &middot; {$screenerProgress.matchedSoFar} matched</span>
      </div>
      <div class="w-full h-1.5 rounded-full bg-surface-0 overflow-hidden">
        <div
          class="h-full rounded-full bg-accent transition-all duration-300 ease-out"
          style="width: {progressPct}%"
        ></div>
      </div>
    </div>
  {/if}

  {#if $screenerError}
    <div class="mt-3 px-3 py-2 rounded-md text-xs font-medium text-center bg-short-dim text-short">
      {$screenerError}
    </div>
  {/if}
</div>
