<script lang="ts">
  import type { RuleCondition, RuleAction, RuleOnFill } from '$lib/types';
  import { updateConfig, getConfig, resetPlan, getSymbolInfo } from '$lib/api/client';
  import RuleRow from './RuleRow.svelte';

  export let planId: string = '';
  export let initialData: {
    enabled: boolean;
    symbol: string;
    magic: number;
    rules: Record<string, { active: boolean; conditions: RuleCondition[]; actions: RuleAction[]; on_fill: RuleOnFill }>;
  } | null = null;
  export let onSave: () => void;
  export let onCancel: () => void;
  export let symbols: string[] = [];

  let symbol = initialData?.symbol ?? '';
  let magic = initialData?.magic ?? 234200;
  let enabled = initialData?.enabled ?? true;
  let editPlanId = planId || '';
  let saving = false;
  let error = '';
  let showAdvanced = false;
  let ruleCounter = 0;

  let volumeMin = 0.01;
  let volumeMax = 100.0;
  let volumeStep = 0.01;
  let contractSize = 100000;

  async function loadSymbolInfo(sym: string) {
    if (!sym) return;
    try {
      const info = await getSymbolInfo(sym);
      if (info.found) {
        volumeMin = info.volume_min;
        volumeMax = info.volume_max;
        volumeStep = info.volume_step;
        contractSize = info.trade_contract_size;
      }
    } catch { /* non-critical */ }
  }

  // Fetch symbol info on init and when symbol changes
  $: if (symbol) loadSymbolInfo(symbol);

  interface EditorRule {
    active: boolean;
    conditions: RuleCondition[];
    actions: RuleAction[];
    onFill: RuleOnFill;
  }

  let rules: Record<string, EditorRule> = {};

  // Initialize from existing data
  if (initialData?.rules) {
    for (const [id, r] of Object.entries(initialData.rules)) {
      rules[id] = {
        active: r.active,
        conditions: [...r.conditions],
        actions: [...r.actions],
        onFill: { activate: [...r.on_fill.activate], deactivate: [...r.on_fill.deactivate] },
      };
      ruleCounter++;
    }
  }

  // For new plans, auto-create a default entry rule
  if (!planId && Object.keys(rules).length === 0) {
    rules['entry'] = {
      active: true,
      conditions: [{ field: 'bid', op: '>=', value: 0 }, { field: 'bid', op: '<=', value: 0 }],
      actions: [{ type: 'market_buy' }],
      onFill: { activate: [], deactivate: [] },
    };
    ruleCounter = 1;
  }

  $: allRuleIds = Object.keys(rules);

  // Auto-generate plan ID from symbol when creating new
  $: if (!planId && symbol) {
    const base = symbol.toLowerCase().replace(/[^a-z0-9]/g, '_');
    editPlanId = `${base}_plan`;
  }

  function addRule() {
    ruleCounter++;
    const id = `rule_${ruleCounter}`;
    rules[id] = {
      active: false,
      conditions: [{ field: 'bid', op: '<=', value: 0 }],
      actions: [{ type: 'market_buy' }],
      onFill: { activate: [], deactivate: [] },
    };
    rules = rules;
  }

  function updateRule(ruleId: string, data: { conditions: RuleCondition[]; actions: RuleAction[]; onFill: RuleOnFill }) {
    rules[ruleId] = { ...rules[ruleId], ...data };
    rules = rules;
  }

  function removeRule(ruleId: string) {
    const { [ruleId]: _, ...rest } = rules;
    rules = rest;
    for (const r of Object.values(rules)) {
      r.onFill.activate = r.onFill.activate.filter(x => x !== ruleId);
      r.onFill.deactivate = r.onFill.deactivate.filter(x => x !== ruleId);
    }
    rules = rules;
  }

  function toggleRuleActive(ruleId: string) {
    rules[ruleId].active = !rules[ruleId].active;
    rules = rules;
  }

  async function save() {
    if (!editPlanId.trim() || !symbol.trim()) {
      error = 'Symbol is required';
      return;
    }
    saving = true;
    error = '';

    const planRules: Record<string, any> = {};
    for (const [id, r] of Object.entries(rules)) {
      planRules[id] = {
        active: r.active,
        conditions: r.conditions.map(c => ({ field: c.field, op: c.op, value: c.value })),
        actions: r.actions.map(a => {
          const obj: Record<string, any> = { type: a.type };
          if (a.volume != null) obj.volume = a.volume;
          if (a.price != null) obj.price = a.price;
          if (a.sl != null) obj.sl = a.sl;
          if (a.tp != null) obj.tp = a.tp;
          if (a.comment) obj.comment = a.comment;
          return obj;
        }),
        on_fill: {
          activate: r.onFill.activate,
          deactivate: r.onFill.deactivate,
        },
      };
    }

    const payload = {
      trade_plans: {
        [editPlanId]: {
          enabled,
          symbol: symbol.trim(),
          magic,
          rules: planRules,
        },
      },
    };

    try {
      const existing = await getConfig('trade_plans');
      const merged = { ...existing.data, ...payload };
      if (existing.data?.trade_plans) {
        merged.trade_plans = { ...existing.data.trade_plans, ...payload.trade_plans };
      }
      await updateConfig('trade_plans', merged);
      // Reset Redis state so YAML defaults (active flags) take effect
      try { await resetPlan(editPlanId); } catch { /* plan may not be loaded yet */ }
      onSave();
    } catch (e: any) {
      error = e.message || 'Save failed';
    } finally {
      saving = false;
    }
  }
</script>

<div class="card p-5 max-w-3xl">
  <div class="flex items-center justify-between mb-4">
    <h3 class="text-sm font-semibold text-text">
      {planId ? `Edit Plan: ${planId}` : 'New Trade Plan'}
    </h3>
    <button on:click={onCancel} class="text-xs text-text-tertiary hover:text-text-secondary transition-colors">Cancel</button>
  </div>

  {#if error}
    <div class="mb-3 px-3 py-2 rounded-lg bg-short/10 border border-short/20 text-short text-xs">{error}</div>
  {/if}

  <!-- Plan metadata -->
  <div class="flex items-center gap-3 mb-4">
    <div class="flex-1">
      <label class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider block mb-1">Symbol</label>
      {#if symbols.length > 0}
        <select bind:value={symbol}
          class="w-full bg-surface-0 text-text text-xs font-mono rounded-lg px-3 py-2 border border-border focus:border-accent focus:outline-none">
          <option value="" disabled>Select symbol</option>
          {#each symbols as sym}
            <option value={sym}>{sym}</option>
          {/each}
        </select>
      {:else}
        <input type="text" bind:value={symbol} placeholder="e.g. EURUSD"
          class="w-full bg-surface-0 text-text text-xs font-mono rounded-lg px-3 py-2 border border-border focus:border-accent focus:outline-none" />
      {/if}
    </div>
    <div class="pt-4">
      <label class="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" bind:checked={enabled}
          class="rounded border-border bg-surface-0 text-accent focus:ring-accent/30 w-3.5 h-3.5" />
        <span class="text-xs text-text-secondary">Enabled</span>
      </label>
    </div>
  </div>

  <!-- Advanced: Plan ID + Magic (collapsed by default) -->
  <details class="mb-4" bind:open={showAdvanced}>
    <summary class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider cursor-pointer hover:text-text-secondary transition-colors">
      Advanced
    </summary>
    <div class="grid grid-cols-2 gap-3 mt-2">
      <div>
        <label class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider block mb-1">Plan ID</label>
        <input type="text" bind:value={editPlanId} disabled={!!planId}
          class="w-full bg-surface-0 text-text text-xs font-mono rounded-lg px-3 py-2 border border-border focus:border-accent focus:outline-none
            disabled:opacity-50 disabled:cursor-not-allowed" />
        <p class="text-[9px] text-text-tertiary mt-1">Auto-generated from symbol. Change if needed.</p>
      </div>
      <div>
        <label class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider block mb-1">Magic Number</label>
        <input type="number" bind:value={magic}
          class="w-full bg-surface-0 text-text text-xs font-mono rounded-lg px-3 py-2 border border-border focus:border-accent focus:outline-none tabular-nums" />
        <p class="text-[9px] text-text-tertiary mt-1">MT5 order identifier. Leave default unless needed.</p>
      </div>
    </div>
  </details>

  <!-- Rules -->
  <div class="mb-4">
    <div class="flex items-center justify-between mb-2">
      <span class="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">Rules</span>
    </div>

    <div class="space-y-2 mb-3">
      {#each Object.entries(rules) as [id, rule]}
        <div>
          <div class="flex items-center gap-2 mb-1">
            <label class="flex items-center gap-1.5 cursor-pointer">
              <input type="checkbox" checked={rule.active} on:change={() => toggleRuleActive(id)}
                class="rounded border-border bg-surface-0 text-accent focus:ring-accent/30 w-3 h-3" />
              <span class="text-[10px] text-text-secondary">Active</span>
            </label>
          </div>
          <RuleRow
            ruleId={id}
            conditions={rule.conditions}
            actions={rule.actions}
            onFill={rule.onFill}
            {allRuleIds}
            {volumeMin}
            {volumeMax}
            {volumeStep}
            {contractSize}
            onUpdate={updateRule}
            onRemove={removeRule}
          />
        </div>
      {/each}
    </div>

    <button on:click={addRule}
      class="text-xs px-3 py-1.5 rounded-lg bg-surface-2 text-text-secondary hover:text-text border border-border hover:border-border-hover transition-colors">
      + Add Rule
    </button>
  </div>

  <!-- Save -->
  <div class="flex justify-end gap-2">
    <button on:click={onCancel}
      class="text-xs px-4 py-2 rounded-lg bg-surface-2 text-text-secondary hover:text-text border border-border hover:border-border-hover transition-colors">
      Cancel
    </button>
    <button on:click={save} disabled={saving}
      class="text-xs px-4 py-2 rounded-lg bg-accent text-white font-medium hover:bg-accent-hover transition-colors
        disabled:opacity-50 disabled:cursor-not-allowed">
      {saving ? 'Saving...' : 'Save Plan'}
    </button>
  </div>
</div>
