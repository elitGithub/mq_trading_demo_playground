<script lang="ts">
  import type { TradePlanSummary } from '$lib/types';
  import { activatePlan, deactivatePlan, cancelPlan, resetPlan, deletePlan } from '$lib/api/client';

  export let plans: TradePlanSummary[];
  export let onEdit: (planId: string) => void;
  export let onRefresh: () => void;

  let loading: Record<string, boolean> = {};

  async function doAction(planId: string, action: () => Promise<any>) {
    loading[planId] = true;
    loading = loading;
    try {
      await action();
      onRefresh();
    } catch (e: any) {
      console.error(e);
    } finally {
      loading[planId] = false;
      loading = loading;
    }
  }

  function stateColor(state: string): string {
    if (state === 'active') return 'bg-long/20 text-long border-long/30';
    if (state === 'executed') return 'bg-accent/20 text-accent border-accent/30';
    return 'bg-surface-2 text-text-tertiary border-border';
  }
</script>

<div class="space-y-3">
  {#each plans as plan}
    {@const busy = loading[plan.plan_id]}
    <div class="card p-4">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <div class="flex items-center gap-2">
            <div class="w-2 h-2 rounded-full {plan.enabled ? 'bg-long animate-pulse-soft' : 'bg-text-tertiary'}"></div>
            <span class="text-sm font-semibold text-text font-mono">{plan.plan_id}</span>
          </div>
          <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-surface-2 text-text-secondary border border-border">
            {plan.symbol}
          </span>
          <span class="text-[10px] text-text-tertiary font-mono">magic: {plan.magic}</span>
        </div>

        <div class="flex items-center gap-1.5">
          {#if plan.enabled}
            <button
              on:click={() => doAction(plan.plan_id, () => deactivatePlan(plan.plan_id))}
              disabled={busy}
              class="text-[10px] px-2.5 py-1 rounded-md bg-surface-2 text-warning border border-warning/20 hover:border-warning/40 transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed">
              Deactivate
            </button>
          {:else}
            <button
              on:click={() => doAction(plan.plan_id, () => activatePlan(plan.plan_id))}
              disabled={busy}
              class="text-[10px] px-2.5 py-1 rounded-md bg-surface-2 text-long border border-long/20 hover:border-long/40 transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed">
              Activate
            </button>
          {/if}
          <button
            on:click={() => doAction(plan.plan_id, () => resetPlan(plan.plan_id))}
            disabled={busy}
            class="text-[10px] px-2.5 py-1 rounded-md bg-surface-2 text-info border border-info/20 hover:border-info/40 transition-colors
              disabled:opacity-50 disabled:cursor-not-allowed">
            Reset
          </button>
          <button
            on:click={() => doAction(plan.plan_id, () => cancelPlan(plan.plan_id))}
            disabled={busy}
            class="text-[10px] px-2.5 py-1 rounded-md bg-surface-2 text-short border border-short/20 hover:border-short/40 transition-colors
              disabled:opacity-50 disabled:cursor-not-allowed">
            Cancel
          </button>
          <button
            on:click={() => onEdit(plan.plan_id)}
            class="text-[10px] px-2.5 py-1 rounded-md bg-surface-2 text-text-secondary border border-border hover:border-border-hover transition-colors">
            Edit
          </button>
          <button
            on:click={() => { if (confirm(`Delete plan "${plan.plan_id}"? This will cancel all orders and remove it.`)) doAction(plan.plan_id, () => deletePlan(plan.plan_id)); }}
            disabled={busy}
            class="text-[10px] px-2.5 py-1 rounded-md bg-short/10 text-short border border-short/20 hover:border-short/40 transition-colors
              disabled:opacity-50 disabled:cursor-not-allowed">
            Delete
          </button>
        </div>
      </div>

      <!-- Rule state pills -->
      <div class="flex flex-wrap gap-1.5">
        {#each Object.entries(plan.rule_states) as [ruleId, state]}
          <span class="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded border {stateColor(state)}">
            {ruleId}
            <span class="opacity-60">{state}</span>
          </span>
        {/each}
      </div>

      <!-- Ticket counts -->
      {#if plan.position_count > 0 || plan.order_count > 0}
        <div class="flex gap-3 mt-2 text-[10px] text-text-tertiary">
          {#if plan.position_count > 0}
            <span>{plan.position_count} position{plan.position_count !== 1 ? 's' : ''}</span>
          {/if}
          {#if plan.order_count > 0}
            <span>{plan.order_count} order{plan.order_count !== 1 ? 's' : ''}</span>
          {/if}
        </div>
      {/if}
    </div>
  {/each}

  {#if plans.length === 0}
    <div class="card p-8 text-center">
      <p class="text-sm text-text-tertiary mb-1">No trade plans configured</p>
      <p class="text-xs text-text-tertiary">Create a plan to get started</p>
    </div>
  {/if}
</div>
