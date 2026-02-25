<script lang="ts">
  import type { RuleCondition, RuleAction, RuleOnFill } from '$lib/types';

  export let ruleId: string;
  export let conditions: RuleCondition[];
  export let actions: RuleAction[];
  export let onFill: RuleOnFill;
  export let allRuleIds: string[];
  export let volumeMin: number = 0.01;
  export let volumeMax: number = 100.0;
  export let volumeStep: number = 0.01;
  export let contractSize: number = 100000;
  export let onUpdate: (ruleId: string, data: { conditions: RuleCondition[]; actions: RuleAction[]; onFill: RuleOnFill }) => void;
  export let onRemove: (ruleId: string) => void;

  const fields: RuleCondition['field'][] = ['bid', 'ask', 'last'];
  const ops: RuleCondition['op'][] = ['>=', '<=', '>', '<', '=='];
  const actionTypes = [
    'market_buy', 'market_sell', 'buy_limit', 'sell_limit',
    'buy_stop', 'sell_stop', 'partial_close', 'close_all',
    'modify_sl', 'cancel_orders',
  ];

  function emit() {
    onUpdate(ruleId, { conditions, actions, onFill });
  }

  function addCondition() {
    conditions = [...conditions, { field: 'bid', op: '<=', value: 0 }];
    emit();
  }

  function removeCondition(i: number) {
    conditions = conditions.filter((_, idx) => idx !== i);
    emit();
  }

  function addAction() {
    actions = [...actions, { type: 'market_buy' }];
    emit();
  }

  function removeAction(i: number) {
    actions = actions.filter((_, idx) => idx !== i);
    emit();
  }

  function toggleActivate(id: string) {
    if (onFill.activate.includes(id)) {
      onFill = { ...onFill, activate: onFill.activate.filter(x => x !== id) };
    } else {
      onFill = { ...onFill, activate: [...onFill.activate, id] };
    }
    emit();
  }

  function toggleDeactivate(id: string) {
    if (onFill.deactivate.includes(id)) {
      onFill = { ...onFill, deactivate: onFill.deactivate.filter(x => x !== id) };
    } else {
      onFill = { ...onFill, deactivate: [...onFill.deactivate, id] };
    }
    emit();
  }

  $: otherRules = allRuleIds.filter(id => id !== ruleId);
</script>

<div class="rounded-lg border border-border bg-surface-0 p-3">
  <div class="flex items-center justify-between mb-3">
    <span class="text-xs font-semibold text-text font-mono">{ruleId}</span>
    <button
      on:click={() => onRemove(ruleId)}
      class="text-[10px] text-short hover:text-short/80 transition-colors">
      Remove
    </button>
  </div>

  <!-- Conditions -->
  <div class="mb-3">
    <div class="flex items-center justify-between mb-1.5">
      <span class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">Conditions</span>
      <button on:click={addCondition} class="text-[10px] text-accent hover:text-accent-hover transition-colors">+ Add</button>
    </div>
    {#each conditions as cond, i}
      <div class="flex items-center gap-1.5 mb-1">
        <select bind:value={cond.field} on:change={emit}
          class="bg-surface-2 text-text text-[10px] rounded px-1.5 py-1 border border-border focus:border-accent focus:outline-none">
          {#each fields as f}<option value={f}>{f}</option>{/each}
        </select>
        <select bind:value={cond.op} on:change={emit}
          class="bg-surface-2 text-text text-[10px] rounded px-1.5 py-1 border border-border focus:border-accent focus:outline-none">
          {#each ops as o}<option value={o}>{o}</option>{/each}
        </select>
        <input type="number" step="any" bind:value={cond.value} on:change={emit}
          class="w-24 bg-surface-2 text-text text-[10px] font-mono rounded px-1.5 py-1 border border-border focus:border-accent focus:outline-none tabular-nums" />
        <button on:click={() => removeCondition(i)} class="text-text-tertiary hover:text-short text-xs">&times;</button>
      </div>
    {/each}
  </div>

  <!-- Actions -->
  <div class="mb-3">
    <div class="flex items-center justify-between mb-1.5">
      <span class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">Actions</span>
      <button on:click={addAction} class="text-[10px] text-accent hover:text-accent-hover transition-colors">+ Add</button>
    </div>
    {#each actions as act, i}
      <div class="flex items-center gap-1.5 mb-1 flex-wrap">
        <select bind:value={act.type} on:change={emit}
          class="bg-surface-2 text-text text-[10px] rounded px-1.5 py-1 border border-border focus:border-accent focus:outline-none">
          {#each actionTypes as t}<option value={t}>{t}</option>{/each}
        </select>
        {#if !['close_all', 'cancel_orders'].includes(act.type)}
          <div class="flex items-center gap-1">
            <input type="number" step={volumeStep} min={volumeMin} max={volumeMax}
              bind:value={act.volume} on:change={emit} placeholder={String(volumeMin)}
              class="w-20 bg-surface-2 text-text text-[10px] font-mono rounded px-1.5 py-1 border border-border focus:border-accent focus:outline-none tabular-nums" />
            <span class="text-[9px] text-text-tertiary whitespace-nowrap">lots{#if act.volume} = {(act.volume * contractSize).toLocaleString()} units{/if}</span>
          </div>
        {/if}
        {#if ['buy_limit', 'sell_limit', 'buy_stop', 'sell_stop'].includes(act.type)}
          <input type="number" step="any" bind:value={act.price} on:change={emit} placeholder="price"
            class="w-20 bg-surface-2 text-text text-[10px] font-mono rounded px-1.5 py-1 border border-border focus:border-accent focus:outline-none tabular-nums" />
        {/if}
        {#if act.type === 'modify_sl'}
          <input type="number" step="any" bind:value={act.sl} on:change={emit} placeholder="sl"
            class="w-20 bg-surface-2 text-text text-[10px] font-mono rounded px-1.5 py-1 border border-border focus:border-accent focus:outline-none tabular-nums" />
        {/if}
        <button on:click={() => removeAction(i)} class="text-text-tertiary hover:text-short text-xs">&times;</button>
      </div>
    {/each}
  </div>

  <!-- On Fill Transitions -->
  {#if otherRules.length > 0}
    <div>
      <span class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider block mb-1.5">On Fill Transitions</span>
      <div class="flex gap-4">
        <div class="flex-1">
          <span class="text-[10px] text-text-tertiary block mb-1">Activate</span>
          {#each otherRules as id}
            <label class="flex items-center gap-1.5 text-[10px] text-text-secondary cursor-pointer mb-0.5">
              <input type="checkbox" checked={onFill.activate.includes(id)} on:change={() => toggleActivate(id)}
                class="rounded border-border bg-surface-2 text-accent focus:ring-accent/30 w-3 h-3" />
              <span class="font-mono">{id}</span>
            </label>
          {/each}
        </div>
        <div class="flex-1">
          <span class="text-[10px] text-text-tertiary block mb-1">Deactivate</span>
          {#each otherRules as id}
            <label class="flex items-center gap-1.5 text-[10px] text-text-secondary cursor-pointer mb-0.5">
              <input type="checkbox" checked={onFill.deactivate.includes(id)} on:change={() => toggleDeactivate(id)}
                class="rounded border-border bg-surface-2 text-accent focus:ring-accent/30 w-3 h-3" />
              <span class="font-mono">{id}</span>
            </label>
          {/each}
        </div>
      </div>
    </div>
  {/if}
</div>
