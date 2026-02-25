<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { getTradePlans, getTradePlan, getConfig } from '$lib/api/client';
  import type { TradePlanSummary, TradePlanDetail } from '$lib/types';
  import TradePlanList from '$lib/components/TradePlanList.svelte';
  import TradePlanEditor from '$lib/components/TradePlanEditor.svelte';

  let plans: TradePlanSummary[] = [];
  let pollInterval: ReturnType<typeof setInterval>;
  let view: 'list' | 'edit' | 'new' = 'list';
  let editPlanId = '';
  let editData: TradePlanDetail | null = null;
  let loading = true;
  let configuredSymbols: string[] = [];

  async function loadPlans() {
    try {
      const res = await getTradePlans();
      plans = res.plans;
    } catch (e) {
      console.error('Failed to load plans', e);
    } finally {
      loading = false;
    }
  }

  async function startEdit(planId: string) {
    try {
      editData = await getTradePlan(planId);
      editPlanId = planId;
      view = 'edit';
    } catch (e) {
      console.error('Failed to load plan', e);
    }
  }

  function startNew() {
    editData = null;
    editPlanId = '';
    view = 'new';
  }

  function onSave() {
    view = 'list';
    editData = null;
    editPlanId = '';
    loadPlans();
  }

  function onCancel() {
    view = 'list';
    editData = null;
    editPlanId = '';
  }

  onMount(async () => {
    loadPlans();
    pollInterval = setInterval(loadPlans, 2000);
    try {
      const symRes = await getConfig('symbols');
      configuredSymbols = Object.keys(symRes.data?.symbols?.instruments ?? {}).sort();
    } catch { /* fallback to empty */ }
  });

  onDestroy(() => {
    clearInterval(pollInterval);
  });
</script>

<div class="animate-fade-in">
  {#if view === 'list'}
    <div class="flex items-center justify-between mb-5">
      <div>
        <h1 class="text-lg font-semibold text-text">Trade Plans</h1>
        <p class="text-xs text-text-tertiary mt-0.5">Rule-based trade execution engine</p>
      </div>
      <button on:click={startNew}
        class="text-xs px-4 py-2 rounded-lg bg-accent text-white font-medium hover:bg-accent-hover transition-colors">
        New Plan
      </button>
    </div>

    {#if loading}
      <div class="card p-8 text-center">
        <p class="text-sm text-text-tertiary">Loading plans...</p>
      </div>
    {:else}
      <TradePlanList {plans} onEdit={startEdit} onRefresh={loadPlans} />
    {/if}

  {:else if view === 'edit' && editData}
    <TradePlanEditor
      planId={editPlanId}
      initialData={{
        enabled: editData.enabled,
        symbol: editData.symbol,
        magic: editData.magic,
        rules: editData.rules,
      }}
      symbols={configuredSymbols}
      {onSave}
      {onCancel}
    />

  {:else if view === 'new'}
    <TradePlanEditor
      planId=""
      initialData={null}
      symbols={configuredSymbols}
      {onSave}
      {onCancel}
    />
  {/if}
</div>
