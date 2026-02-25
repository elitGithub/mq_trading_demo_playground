<script lang="ts">
  import StrategyConfig from '$lib/components/StrategyConfig.svelte';
</script>

<div class="space-y-5">
  <div>
    <h1 class="text-xl font-semibold text-text tracking-tight">Strategy Configuration</h1>
    <p class="text-xs text-text-tertiary mt-1">
      Adjust strategy, risk, symbols, and notifications. Changes are hot-reloaded on save — no restart needed.
    </p>
  </div>

  <StrategyConfig />
</div>
