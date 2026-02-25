<script lang="ts">
  import { getConfig, getTradeableSymbols, updateConfig } from '$lib/api/client';
  import { activeConfigTab, activeStrategyId, configDirty } from '$lib/stores/config';
  import { tradeableSymbols, symbolsLoading } from '$lib/stores/market';
  import { onDestroy, onMount } from 'svelte';
  import type { ConfigName } from '$lib/types';

  const tabs: ConfigName[] = ['strategy', 'price_levels', 'risk', 'symbols', 'notifications'];

  const tabIcons: Record<ConfigName, string> = {
    strategy: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 16l4-8 4 4 5-9"/></svg>`,
    price_levels: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h18"/><path d="M3 6h18"/><path d="M3 18h18"/></svg>`,
    risk: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>`,
    symbols: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v12"/><path d="M15.5 9.5c-.2-1.1-1.5-2-3.5-2s-3.3.9-3.5 2c-.2 1.2.9 2.5 3.5 2.5s3.7 1.3 3.5 2.5c-.2 1.1-1.5 2-3.5 2s-3.3-.9-3.5-2"/></svg>`,
    notifications: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>`,
  };

  const timeframes = ['D1', 'H4', 'H1', 'M30', 'M15', 'M5', 'M1'];
  const categories = ['forex_major', 'forex_minor', 'forex_cross', 'commodity', 'index', 'crypto', 'equity'];
  const sizingMethods = ['fixed_percentage', 'fixed_lot', 'volatility_adjusted'];
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  let knownStrategyIds: string[] = ['default'];
  let config: any = normalizeStrategy({});
  let activeTab: ConfigName = 'strategy';
  let symbolOrder: string[] = [];
  let saving = false;
  let message = '';
  let messageType: 'success' | 'error' = 'success';
  let showAdvanced = false;
  let rawJson = '';
  let symbolsConnected = true;
  let newSymbol = '';
  let availableSymbols: string[] = [];
  let showNewStrategyForm = false;
  let newStrategyName = '';
  let levelScope = 'global';  // 'global' or a symbol name
  let configuredSymbols: string[] = [];

  const inputBase = 'w-full bg-surface-0 text-text text-xs rounded-lg px-3 py-2 border border-border focus:border-accent/60 focus:outline-none';
  const labelBase = 'text-[10px] font-medium text-text-tertiary uppercase tracking-wider';

  function defaultStrategyEntry(name: string) {
    return {
      name: name,
      enabled: false,
      timeframes: {
        analysis: ['H4', 'H1', 'M15'],
        entry: 'M5',
      },
      entry: {
        proximity_atr_multiplier: 1.5,
        confirmation_candles: 2,
        min_rejection_pips: 10,
        require_volume_spike: false,
        volume_spike_multiplier: 1.5,
      },
      exit: {
        take_profit_atr_multiplier: 2.0,
        stop_loss_atr_multiplier: 1.0,
        trailing_stop: {
          enabled: true,
          activation_atr: 1.5,
          trail_atr: 0.75,
        },
        break_even: {
          enabled: true,
          trigger_atr: 1.0,
          offset_pips: 2,
        },
      },
      atr: {
        period: 14,
        timeframe: 'H1',
      },
    };
  }

  function normalizeStrategyEntry(s: any): any {
    const clean = { ...(s ?? {}) };
    delete clean.poll_interval_ms;
    return {
      name: clean.name ?? 'Unnamed Strategy',
      enabled: clean.enabled ?? false,
      timeframes: {
        analysis: Array.isArray(clean.timeframes?.analysis) ? clean.timeframes.analysis : ['H4', 'H1', 'M15'],
        entry: clean.timeframes?.entry ?? 'M5',
      },
      entry: {
        proximity_atr_multiplier: clean.entry?.proximity_atr_multiplier ?? 1.5,
        confirmation_candles: clean.entry?.confirmation_candles ?? 2,
        min_rejection_pips: clean.entry?.min_rejection_pips ?? 10,
        require_volume_spike: clean.entry?.require_volume_spike ?? false,
        volume_spike_multiplier: clean.entry?.volume_spike_multiplier ?? 1.5,
      },
      exit: {
        take_profit_atr_multiplier: clean.exit?.take_profit_atr_multiplier ?? 2.0,
        stop_loss_atr_multiplier: clean.exit?.stop_loss_atr_multiplier ?? 1.0,
        trailing_stop: {
          enabled: clean.exit?.trailing_stop?.enabled ?? true,
          activation_atr: clean.exit?.trailing_stop?.activation_atr ?? 1.5,
          trail_atr: clean.exit?.trailing_stop?.trail_atr ?? 0.75,
        },
        break_even: {
          enabled: clean.exit?.break_even?.enabled ?? true,
          trigger_atr: clean.exit?.break_even?.trigger_atr ?? 1.0,
          offset_pips: clean.exit?.break_even?.offset_pips ?? 2,
        },
      },
      atr: {
        period: clean.atr?.period ?? 14,
        timeframe: clean.atr?.timeframe ?? 'H1',
      },
    };
  }

  function normalizeStrategy(data: any) {
    const legacyStrategy = data?.strategy ?? null;
    const strategies = data?.strategies
      ?? (legacyStrategy && typeof legacyStrategy === 'object' ? { default: legacyStrategy } : {});
    const normalized: Record<string, any> = {};
    for (const [id, cfg] of Object.entries(strategies)) {
      normalized[id] = normalizeStrategyEntry(cfg);
    }
    // If empty, provide a default
    if (Object.keys(normalized).length === 0) {
      normalized['default'] = defaultStrategyEntry('PriceLevel Reactor');
    }
    // Update known IDs for use in symbols tab dropdowns
    const ids = Object.keys(normalized);
    knownStrategyIds = ids;
    if (!$activeStrategyId || !normalized[$activeStrategyId]) {
      $activeStrategyId = ids[0];
    }
    return {
      poll_interval_ms: data?.poll_interval_ms ?? legacyStrategy?.poll_interval_ms ?? 500,
      strategies: normalized,
    };
  }

  function normalizePriceLevels(data: any) {
    const p = data?.price_levels ?? {};
    return {
      price_levels: {
        methods: {
          pivot_points: {
            enabled: p.methods?.pivot_points?.enabled ?? true,
            lookback_periods: p.methods?.pivot_points?.lookback_periods ?? 20,
            min_touches: p.methods?.pivot_points?.min_touches ?? 2,
            sensitivity: p.methods?.pivot_points?.sensitivity ?? 3,
          },
          volume_profile: {
            enabled: p.methods?.volume_profile?.enabled ?? true,
            lookback_bars: p.methods?.volume_profile?.lookback_bars ?? 500,
            value_area_pct: p.methods?.volume_profile?.value_area_pct ?? 0.7,
            num_bins: p.methods?.volume_profile?.num_bins ?? 100,
            hvn_threshold: p.methods?.volume_profile?.hvn_threshold ?? 1.5,
          },
          clustering: {
            enabled: p.methods?.clustering?.enabled ?? true,
            bandwidth: p.methods?.clustering?.bandwidth ?? 0.5,
            min_cluster_size: p.methods?.clustering?.min_cluster_size ?? 5,
            merge_distance_atr: p.methods?.clustering?.merge_distance_atr ?? 0.3,
          },
          round_numbers: {
            enabled: p.methods?.round_numbers?.enabled ?? true,
            intervals: {
              forex_major: p.methods?.round_numbers?.intervals?.forex_major ?? 0.01,
              forex_minor: p.methods?.round_numbers?.intervals?.forex_minor ?? 0.005,
              index: p.methods?.round_numbers?.intervals?.index ?? 100,
              gold: p.methods?.round_numbers?.intervals?.gold ?? 10,
              crypto: p.methods?.round_numbers?.intervals?.crypto ?? 1000,
            },
          },
        },
        zones: {
          width_atr_multiplier: p.zones?.width_atr_multiplier ?? 0.5,
          max_active_levels: p.zones?.max_active_levels ?? 10,
          level_expiry_hours: p.zones?.level_expiry_hours ?? 168,
        },
        scoring: {
          touch_weight: p.scoring?.touch_weight ?? 2.0,
          recency_weight: p.scoring?.recency_weight ?? 1.5,
          timeframe_weight: p.scoring?.timeframe_weight ?? 3.0,
          volume_weight: p.scoring?.volume_weight ?? 2.0,
          confluence_bonus: p.scoring?.confluence_bonus ?? 5.0,
        },
        confluence: {
          enabled: p.confluence?.enabled ?? true,
          timeframes: Array.isArray(p.confluence?.timeframes) ? p.confluence.timeframes : ['D1', 'H4', 'H1'],
          min_timeframes: p.confluence?.min_timeframes ?? 2,
        },
        invalidation: {
          max_clean_breaks: p.invalidation?.max_clean_breaks ?? 2,
          break_threshold_atr: p.invalidation?.break_threshold_atr ?? 0.5,
          polarity_flip: p.invalidation?.polarity_flip ?? true,
        },
        symbol_overrides: p.symbol_overrides ?? {},
      },
    };
  }

  function normalizeRisk(data: any) {
    const r = data?.risk ?? {};
    return {
      risk: {
        per_trade: {
          max_risk_pct: r.per_trade?.max_risk_pct ?? 1.0,
          max_volume: r.per_trade?.max_volume ?? 10.0,
        },
        sizing: {
          method: r.sizing?.method ?? 'fixed_percentage',
          fixed_lot_size: r.sizing?.fixed_lot_size ?? 0.01,
          volatility_lookback: r.sizing?.volatility_lookback ?? 14,
        },
        portfolio: {
          max_open_positions: r.portfolio?.max_open_positions ?? 5,
          max_positions_per_symbol: r.portfolio?.max_positions_per_symbol ?? 2,
          max_correlation_positions: r.portfolio?.max_correlation_positions ?? 3,
          max_total_exposure: r.portfolio?.max_total_exposure ?? 30.0,
        },
        daily: {
          max_daily_loss_pct: r.daily?.max_daily_loss_pct ?? 3.0,
          max_daily_trades: r.daily?.max_daily_trades ?? 20,
          reset_hour_utc: r.daily?.reset_hour_utc ?? 0,
        },
        drawdown: {
          max_drawdown_pct: r.drawdown?.max_drawdown_pct ?? 10.0,
          warning_drawdown_pct: r.drawdown?.warning_drawdown_pct ?? 7.0,
          recovery_required: r.drawdown?.recovery_required ?? true,
        },
        kill_switch: {
          enabled: r.kill_switch?.enabled ?? true,
          max_consecutive_losses: r.kill_switch?.max_consecutive_losses ?? 5,
          abnormal_spread_multiplier: r.kill_switch?.abnormal_spread_multiplier ?? 3.0,
          max_slippage_pips: r.kill_switch?.max_slippage_pips ?? 5,
        },
        trading_hours: {
          enabled: r.trading_hours?.enabled ?? false,
          sessions: Array.isArray(r.trading_hours?.sessions) ? r.trading_hours.sessions : [
            { name: 'London', start: '07:00', end: '16:00' },
            { name: 'New York', start: '12:00', end: '21:00' },
          ],
          excluded_days: Array.isArray(r.trading_hours?.excluded_days) ? r.trading_hours.excluded_days : [5, 6],
        },
      },
    };
  }

  function normalizeSymbols(data: any) {
    const s = data?.symbols ?? {};
    const defaults = {
      strategy: s.defaults?.strategy ?? 'default',
      pip_size: s.defaults?.pip_size ?? 0.0001,
      min_volume: s.defaults?.min_volume ?? 0.01,
      volume_step: s.defaults?.volume_step ?? 0.01,
      spread_limit_pips: s.defaults?.spread_limit_pips ?? 5,
      enabled: s.defaults?.enabled ?? true,
    };
    const instruments = s.instruments ?? {};
    const normalizedInstruments: Record<string, any> = {};
    for (const [name, cfg] of Object.entries(instruments)) {
      const row = { ...cfg } as Record<string, any>;
      row.strategy = row.strategy ?? defaults.strategy;
      row.category = row.category ?? 'forex_major';
      row.pip_size = row.pip_size ?? defaults.pip_size;
      row.min_volume = row.min_volume ?? defaults.min_volume;
      row.volume_step = row.volume_step ?? defaults.volume_step;
      row.spread_limit_pips = row.spread_limit_pips ?? defaults.spread_limit_pips;
      row.enabled = row.enabled ?? defaults.enabled;
      normalizedInstruments[name] = row;
    }
    symbolOrder = Object.keys(normalizedInstruments).sort();
    return {
      symbols: {
        defaults,
        instruments: normalizedInstruments,
        correlation_groups: s.correlation_groups ?? {},
      },
    };
  }

  function normalizeNotifications(data: any) {
    const n = data?.notifications ?? {};
    return {
      notifications: {
        enabled: n.enabled ?? false,
        channels: {
          console: {
            enabled: n.channels?.console?.enabled ?? true,
          },
          telegram: {
            enabled: n.channels?.telegram?.enabled ?? false,
            bot_token: n.channels?.telegram?.bot_token ?? '',
            chat_id: n.channels?.telegram?.chat_id ?? '',
          },
          email: {
            enabled: n.channels?.email?.enabled ?? false,
            smtp_host: n.channels?.email?.smtp_host ?? '',
            smtp_port: n.channels?.email?.smtp_port ?? 587,
            username: n.channels?.email?.username ?? '',
            password: n.channels?.email?.password ?? '',
            to_address: n.channels?.email?.to_address ?? '',
          },
        },
        events: {
          trade_opened: n.events?.trade_opened ?? true,
          trade_closed: n.events?.trade_closed ?? true,
          level_detected: n.events?.level_detected ?? false,
          level_hit: n.events?.level_hit ?? true,
          risk_warning: n.events?.risk_warning ?? true,
          kill_switch_triggered: n.events?.kill_switch_triggered ?? true,
          daily_summary: n.events?.daily_summary ?? true,
          error: n.events?.error ?? true,
        },
      },
    };
  }

  function normalizeConfig(name: ConfigName, data: any) {
    if (name === 'strategy') return normalizeStrategy(data);
    if (name === 'price_levels') return normalizePriceLevels(data);
    if (name === 'risk') return normalizeRisk(data);
    if (name === 'symbols') return normalizeSymbols(data);
    return normalizeNotifications(data);
  }

  async function loadConfig(name: ConfigName) {
    config = normalizeConfig(name, {});
    try {
      const res = await getConfig(name);
      config = normalizeConfig(name, res.data);
      $configDirty = false;
      message = '';
      // When loading symbols tab, also fetch strategy IDs for the dropdown
      if (name === 'symbols') {
        try {
          const stratRes = await getConfig('strategy');
          const stratIds = Object.keys(stratRes.data?.strategies ?? {});
          if (stratIds.length > 0) knownStrategyIds = stratIds;
        } catch { /* keep existing knownStrategyIds */ }
      }
      // When loading price_levels tab, fetch the symbol list for per-symbol overrides
      if (name === 'price_levels') {
        try {
          const symRes = await getConfig('symbols');
          const instruments = symRes.data?.symbols?.instruments ?? {};
          configuredSymbols = Object.keys(instruments).sort();
        } catch { /* keep existing */ }
      }
    } catch (e: any) {
      message = `Load error: ${e.message}`;
      messageType = 'error';
    }
  }

  async function loadTradeableSymbols() {
    $symbolsLoading = true;
    try {
      const res = await getTradeableSymbols({ tradeable: false, visible_only: true });
      symbolsConnected = res.connected;
      $tradeableSymbols = Array.isArray(res.symbols) ? res.symbols : [];
    } catch {
      symbolsConnected = false;
      $tradeableSymbols = [];
    } finally {
      $symbolsLoading = false;
    }
  }

  async function saveConfig() {
    saving = true;
    try {
      await updateConfig(activeTab, config);
      $configDirty = false;
      message = 'Saved & hot-reloaded';
      messageType = 'success';
    } catch (e: any) {
      message = `Save error: ${e.message}`;
      messageType = 'error';
    } finally {
      saving = false;
    }
  }

  function markDirty() {
    $configDirty = true;
  }

  // -- Per-symbol price level override helpers --

  function getLevelVal(...keys: string[]): any {
    if (levelScope !== 'global') {
      const ov = config.price_levels.symbol_overrides?.[levelScope];
      if (ov) {
        let v: any = ov;
        for (const k of keys) { v = v?.[k]; }
        if (v !== undefined && v !== null) return v;
      }
    }
    let v: any = config.price_levels;
    for (const k of keys) { v = v?.[k]; }
    return v;
  }

  function setLevelVal(value: any, ...keys: string[]) {
    $configDirty = true;
    if (levelScope === 'global') {
      let obj = config.price_levels;
      for (let i = 0; i < keys.length - 1; i++) {
        if (!obj[keys[i]]) obj[keys[i]] = {};
        obj = obj[keys[i]];
      }
      obj[keys[keys.length - 1]] = value;
    } else {
      if (!config.price_levels.symbol_overrides) config.price_levels.symbol_overrides = {};
      if (!config.price_levels.symbol_overrides[levelScope]) config.price_levels.symbol_overrides[levelScope] = {};
      let obj = config.price_levels.symbol_overrides[levelScope];
      for (let i = 0; i < keys.length - 1; i++) {
        if (!obj[keys[i]]) obj[keys[i]] = {};
        obj = obj[keys[i]];
      }
      obj[keys[keys.length - 1]] = value;
    }
    config = config;  // trigger reactivity
  }

  function clearSymbolOverride(sym: string) {
    if (config.price_levels.symbol_overrides?.[sym]) {
      delete config.price_levels.symbol_overrides[sym];
      config = config;
      $configDirty = true;
    }
  }

  function hasOverride(sym: string): boolean {
    const ov = config.price_levels.symbol_overrides?.[sym];
    return ov !== undefined && ov !== null && Object.keys(ov).length > 0;
  }

  function getConfiguredSymbols(): string[] {
    return configuredSymbols;
  }

  function toggleString(list: string[], value: string) {
    const next = list.includes(value) ? list.filter(v => v !== value) : [...list, value];
    $configDirty = true;
    return next;
  }

  function toggleNumber(list: number[], value: number) {
    const next = list.includes(value) ? list.filter(v => v !== value) : [...list, value];
    $configDirty = true;
    return next;
  }

  function addSession() {
    config.risk.trading_hours.sessions = [
      ...config.risk.trading_hours.sessions,
      { name: 'Session', start: '00:00', end: '00:00' },
    ];
    $configDirty = true;
  }

  function removeSession(index: number) {
    config.risk.trading_hours.sessions = config.risk.trading_hours.sessions.filter((_: any, i: number) => i !== index);
    $configDirty = true;
  }

  function addSymbol(name: string) {
    if (!name) return;
    if (config.symbols.instruments[name]) return;
    const strategyIds = Object.keys(config.strategies ?? {});
    config.symbols.instruments[name] = {
      strategy: config.symbols.defaults.strategy ?? (strategyIds[0] || 'default'),
      category: 'forex_major',
      pip_size: config.symbols.defaults.pip_size,
      min_volume: config.symbols.defaults.min_volume,
      volume_step: config.symbols.defaults.volume_step,
      spread_limit_pips: config.symbols.defaults.spread_limit_pips,
      enabled: config.symbols.defaults.enabled,
    };
    symbolOrder = [...symbolOrder, name];
    newSymbol = '';
    $configDirty = true;
  }

  function removeSymbol(name: string) {
    const { [name]: _, ...rest } = config.symbols.instruments;
    config.symbols.instruments = rest;
    symbolOrder = symbolOrder.filter(s => s !== name);
    $configDirty = true;
  }

  function slugifyId(input: string) {
    const base = input.trim().toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '');
    return base || 'strategy';
  }

  function uniqueStrategyId(base: string, existing: Set<string>) {
    let id = base;
    let i = 2;
    while (existing.has(id)) {
      id = `${base}_${i}`;
      i += 1;
    }
    return id;
  }

  function addStrategy() {
    const name = newStrategyName.trim();
    if (!name) {
      messageType = 'error';
      message = 'Enter a strategy name';
      return;
    }
    const base = slugifyId(name);
    const id = uniqueStrategyId(base, new Set(Object.keys(config.strategies ?? {})));
    config.strategies = { ...config.strategies, [id]: defaultStrategyEntry(name) };
    knownStrategyIds = Array.from(new Set([...knownStrategyIds, id]));
    $activeStrategyId = id;
    showNewStrategyForm = false;
    newStrategyName = '';
    message = '';
    $configDirty = true;
  }

  function deleteStrategy(id: string) {
    if (Object.keys(config.strategies).length <= 1) return;
    const { [id]: _, ...rest } = config.strategies;
    config.strategies = rest;
    knownStrategyIds = knownStrategyIds.filter((sid) => sid !== id);
    const ids = Object.keys(config.strategies);
    if ($activeStrategyId === id) {
      $activeStrategyId = ids[0];
    }
    config = config;
    $configDirty = true;
  }

  const unsub = activeConfigTab.subscribe((tab) => {
    activeTab = tab;
    loadConfig(tab);
  });

  onDestroy(() => unsub());

  onMount(() => {
    loadTradeableSymbols();
  });

  $: strategyIds = config.strategies ? Object.keys(config.strategies) : [];
  $: currentStrategy = config.strategies?.[$activeStrategyId] ?? null;
  $: availableSymbols = $tradeableSymbols.filter((s) => !symbolOrder.includes(s));
  $: if (availableSymbols.length && (!newSymbol || !availableSymbols.includes(newSymbol))) {
    newSymbol = availableSymbols[0];
  }
  $: if (showAdvanced) rawJson = JSON.stringify(config, null, 2);
</script>

<div class="card p-5 animate-fade-in">
  <div class="flex gap-1.5 mb-5 p-1 rounded-lg bg-surface-0 overflow-x-auto">
    {#each tabs as tab}
      <button
        on:click={() => $activeConfigTab = tab}
        class="flex items-center gap-2 px-3.5 py-2 rounded-md text-xs font-medium transition-all duration-200 whitespace-nowrap
          {$activeConfigTab === tab
            ? 'bg-surface-2 text-text shadow-sm'
            : 'text-text-tertiary hover:text-text-secondary hover:bg-surface-2/50'}">
        {@html tabIcons[tab]}
        <span class="capitalize">{tab.replace('_', ' ')}</span>
      </button>
    {/each}
  </div>

  <div class="space-y-6" on:input={markDirty} on:change={markDirty}>
    {#if $activeConfigTab === 'strategy'}
      <!-- Engine Settings (poll interval) -->
      <div class="p-4 rounded-xl bg-surface-0 border border-border">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs font-semibold text-text">Engine Settings</p>
            <p class="text-[10px] text-text-tertiary">Global engine parameters shared across all strategies</p>
          </div>
          <div class="flex items-center gap-3">
            <label class={labelBase}>Poll Interval (ms)</label>
            <input class="w-24 bg-surface-0 text-text text-xs rounded-lg px-3 py-2 border border-border focus:border-accent/60 focus:outline-none"
              type="number" step="50" value={config.poll_interval_ms}
              on:input={(e) => config.poll_interval_ms = e.currentTarget.valueAsNumber} />
          </div>
        </div>
      </div>

      <!-- Strategy Selector -->
      <div class="flex items-center gap-2 flex-wrap">
        {#each strategyIds as sid}
          <button
            type="button"
            on:click={() => $activeStrategyId = sid}
            class="flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium transition-all duration-200
              {$activeStrategyId === sid
                ? 'bg-accent/15 text-accent border border-accent/40 shadow-sm'
                : 'bg-surface-0 text-text-tertiary border border-border hover:border-border-hover hover:text-text-secondary'}">
            <span class="w-1.5 h-1.5 rounded-full {config.strategies[sid]?.enabled ? 'bg-long' : 'bg-text-tertiary/40'}"></span>
            {config.strategies[sid]?.name ?? sid}
          </button>
        {/each}

        {#if showNewStrategyForm}
          <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-0 border border-accent/40">
            <input
              class="w-40 bg-transparent text-text text-xs px-1.5 py-1 border-b border-border focus:border-accent/60 focus:outline-none"
              type="text" placeholder="Strategy Name" bind:value={newStrategyName}
              on:keydown={(e) => { if (e.key === 'Enter') addStrategy(); }} />
            <button type="button" on:click={addStrategy}
              class="px-2.5 py-1 rounded-md text-[10px] font-semibold bg-accent/20 text-accent hover:bg-accent/30">
              Add
            </button>
            <button type="button" on:click={() => { showNewStrategyForm = false; newStrategyName = ''; }}
              class="px-2 py-1 rounded-md text-[10px] font-semibold text-text-tertiary hover:text-text-secondary">
              Cancel
            </button>
          </div>
        {:else}
          <button type="button" on:click={() => showNewStrategyForm = true}
            class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-text-tertiary
              bg-surface-0 border border-dashed border-border hover:border-accent/40 hover:text-accent transition-all">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>
            Add Strategy
          </button>
        {/if}
      </div>

      <!-- Active Strategy Form -->
      {#if currentStrategy}
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div class="lg:col-span-2 space-y-4">
            <div class="p-4 rounded-xl bg-surface-0 border border-border">
              <div class="flex items-center justify-between">
                <div class="flex-1">
                  <p class="text-xs font-semibold text-text">Strategy Switch</p>
                  <p class="text-[10px] text-text-tertiary">Enable or pause this strategy</p>
                </div>
                <div class="flex items-center gap-4">
                  {#if strategyIds.length > 1}
                    <button type="button" on:click={() => deleteStrategy($activeStrategyId)}
                      class="px-2.5 py-1 rounded-md text-[10px] font-semibold text-short hover:bg-short-dim transition-colors">
                      Delete
                    </button>
                  {/if}
                  <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" class="sr-only peer" bind:checked={config.strategies[$activeStrategyId].enabled} />
                    <span class="w-10 h-5 bg-surface-2 border border-border rounded-full peer-checked:bg-accent/30 transition-colors"></span>
                    <span class="absolute left-1 top-1 w-3 h-3 bg-text-tertiary rounded-full transition-transform peer-checked:translate-x-5 peer-checked:bg-accent"></span>
                  </label>
                </div>
              </div>
              <div class="mt-4">
                <label class={labelBase}>Strategy Name</label>
                <input class={inputBase} type="text" bind:value={config.strategies[$activeStrategyId].name} />
              </div>
            </div>

            <div class="p-4 rounded-xl bg-surface-0 border border-border space-y-4">
              <div>
                <p class="text-xs font-semibold text-text">Timeframes</p>
                <p class="text-[10px] text-text-tertiary">Choose analysis and entry granularity</p>
              </div>
              <div>
                <label class={labelBase}>Analysis Timeframes</label>
                <div class="flex flex-wrap gap-2 mt-2">
                  {#each timeframes as tf}
                    <button
                      type="button"
                      on:click={() => config.strategies[$activeStrategyId].timeframes.analysis = toggleString(config.strategies[$activeStrategyId].timeframes.analysis, tf)}
                      class="px-2.5 py-1 rounded-md text-[10px] font-semibold tracking-wide
                        {config.strategies[$activeStrategyId].timeframes.analysis.includes(tf)
                          ? 'bg-accent/20 text-accent border border-accent/40'
                          : 'bg-surface-1 text-text-tertiary border border-border'}">
                      {tf}
                    </button>
                  {/each}
                </div>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class={labelBase}>Entry Timeframe</label>
                  <select class={inputBase} bind:value={config.strategies[$activeStrategyId].timeframes.entry}>
                    {#each timeframes as tf}<option value={tf}>{tf}</option>{/each}
                  </select>
                </div>
                <div>
                  <label class={labelBase}>ATR Timeframe</label>
                  <select class={inputBase} bind:value={config.strategies[$activeStrategyId].atr.timeframe}>
                    {#each timeframes as tf}<option value={tf}>{tf}</option>{/each}
                  </select>
                </div>
              </div>
            </div>

            <div class="p-4 rounded-xl bg-surface-0 border border-border">
              <p class="text-xs font-semibold text-text mb-3">Entry Rules</p>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class={labelBase}>Proximity (ATR)</label>
                  <input class={inputBase} type="number" step="0.1" value={config.strategies[$activeStrategyId].entry.proximity_atr_multiplier}
                    on:input={(e) => config.strategies[$activeStrategyId].entry.proximity_atr_multiplier = e.currentTarget.valueAsNumber} />
                </div>
                <div>
                  <label class={labelBase}>Confirmation Candles</label>
                  <input class={inputBase} type="number" step="1" value={config.strategies[$activeStrategyId].entry.confirmation_candles}
                    on:input={(e) => config.strategies[$activeStrategyId].entry.confirmation_candles = e.currentTarget.valueAsNumber} />
                </div>
                <div>
                  <label class={labelBase}>Min Rejection (pips)</label>
                  <input class={inputBase} type="number" step="1" value={config.strategies[$activeStrategyId].entry.min_rejection_pips}
                    on:input={(e) => config.strategies[$activeStrategyId].entry.min_rejection_pips = e.currentTarget.valueAsNumber} />
                </div>
                <div>
                  <label class={labelBase}>Volume Spike Multiplier</label>
                  <input class={inputBase} type="number" step="0.1" value={config.strategies[$activeStrategyId].entry.volume_spike_multiplier}
                    on:input={(e) => config.strategies[$activeStrategyId].entry.volume_spike_multiplier = e.currentTarget.valueAsNumber} />
                </div>
              </div>
              <label class="flex items-center gap-2 mt-4 text-xs text-text-secondary">
                <input type="checkbox" class="accent-accent" bind:checked={config.strategies[$activeStrategyId].entry.require_volume_spike} />
                Require volume spike confirmation
              </label>
            </div>

            <div class="p-4 rounded-xl bg-surface-0 border border-border space-y-4">
              <p class="text-xs font-semibold text-text">Exit Rules</p>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class={labelBase}>Take Profit (ATR)</label>
                  <input class={inputBase} type="number" step="0.1" value={config.strategies[$activeStrategyId].exit.take_profit_atr_multiplier}
                    on:input={(e) => config.strategies[$activeStrategyId].exit.take_profit_atr_multiplier = e.currentTarget.valueAsNumber} />
                </div>
                <div>
                  <label class={labelBase}>Stop Loss (ATR)</label>
                  <input class={inputBase} type="number" step="0.1" value={config.strategies[$activeStrategyId].exit.stop_loss_atr_multiplier}
                    on:input={(e) => config.strategies[$activeStrategyId].exit.stop_loss_atr_multiplier = e.currentTarget.valueAsNumber} />
                </div>
              </div>

              <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div class="p-3 rounded-lg bg-surface-1 border border-border/70">
                  <div class="flex items-center justify-between">
                    <p class="text-xs font-semibold text-text">Trailing Stop</p>
                    <input type="checkbox" class="accent-accent" bind:checked={config.strategies[$activeStrategyId].exit.trailing_stop.enabled} />
                  </div>
                  <div class="grid grid-cols-2 gap-3 mt-3">
                    <div>
                      <label class={labelBase}>Activation (ATR)</label>
                      <input class={inputBase} type="number" step="0.1" value={config.strategies[$activeStrategyId].exit.trailing_stop.activation_atr}
                        on:input={(e) => config.strategies[$activeStrategyId].exit.trailing_stop.activation_atr = e.currentTarget.valueAsNumber} />
                    </div>
                    <div>
                      <label class={labelBase}>Trail (ATR)</label>
                      <input class={inputBase} type="number" step="0.1" value={config.strategies[$activeStrategyId].exit.trailing_stop.trail_atr}
                        on:input={(e) => config.strategies[$activeStrategyId].exit.trailing_stop.trail_atr = e.currentTarget.valueAsNumber} />
                    </div>
                  </div>
                </div>

                <div class="p-3 rounded-lg bg-surface-1 border border-border/70">
                  <div class="flex items-center justify-between">
                    <p class="text-xs font-semibold text-text">Break Even</p>
                    <input type="checkbox" class="accent-accent" bind:checked={config.strategies[$activeStrategyId].exit.break_even.enabled} />
                  </div>
                  <div class="grid grid-cols-2 gap-3 mt-3">
                    <div>
                      <label class={labelBase}>Trigger (ATR)</label>
                      <input class={inputBase} type="number" step="0.1" value={config.strategies[$activeStrategyId].exit.break_even.trigger_atr}
                        on:input={(e) => config.strategies[$activeStrategyId].exit.break_even.trigger_atr = e.currentTarget.valueAsNumber} />
                    </div>
                    <div>
                      <label class={labelBase}>Offset (pips)</label>
                      <input class={inputBase} type="number" step="0.1" value={config.strategies[$activeStrategyId].exit.break_even.offset_pips}
                        on:input={(e) => config.strategies[$activeStrategyId].exit.break_even.offset_pips = e.currentTarget.valueAsNumber} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="space-y-4">
            <div class="p-4 rounded-xl bg-surface-0 border border-border">
              <p class="text-xs font-semibold text-text mb-3">ATR Settings</p>
              <div>
                <label class={labelBase}>Period</label>
                <input class={inputBase} type="number" step="1" value={config.strategies[$activeStrategyId].atr.period}
                  on:input={(e) => config.strategies[$activeStrategyId].atr.period = e.currentTarget.valueAsNumber} />
              </div>
            </div>

            <div class="p-4 rounded-xl bg-surface-0 border border-border">
              <p class="text-xs font-semibold text-text mb-3">Strategy ID</p>
              <p class="text-xs font-mono text-text-secondary bg-surface-1 rounded-lg px-3 py-2">{$activeStrategyId}</p>
              <p class="text-[10px] text-text-tertiary mt-2">Used in order comments and symbol assignments.</p>
            </div>
          </div>
        </div>
      {/if}
    {/if}

    {#if $activeConfigTab === 'price_levels'}
      <div class="space-y-4">
        <!-- Scope selector: Global vs per-symbol -->
        <div class="p-3 rounded-xl bg-surface-0 border border-border">
          <div class="flex items-center gap-2 mb-2">
            <span class={labelBase}>Scope</span>
            {#if levelScope !== 'global'}
              <button type="button" on:click={() => clearSymbolOverride(levelScope)}
                class="ml-auto text-[10px] text-short hover:text-short/80 transition-colors">
                Clear {levelScope} overrides
              </button>
            {/if}
          </div>
          <div class="flex flex-wrap gap-1.5">
            <button type="button" on:click={() => levelScope = 'global'}
              class="px-3 py-1.5 rounded-lg text-[10px] font-semibold tracking-wide transition-all
                {levelScope === 'global'
                  ? 'bg-accent/20 text-accent border border-accent/40'
                  : 'bg-surface-1 text-text-tertiary border border-border hover:border-border-hover'}">
              Global
            </button>
            {#each configuredSymbols as sym}
              <button type="button" on:click={() => levelScope = sym}
                class="px-3 py-1.5 rounded-lg text-[10px] font-semibold tracking-wide transition-all
                  {levelScope === sym
                    ? 'bg-accent/20 text-accent border border-accent/40'
                    : hasOverride(sym)
                      ? 'bg-warning/10 text-warning border border-warning/30 hover:border-warning/50'
                      : 'bg-surface-1 text-text-tertiary border border-border hover:border-border-hover'}">
                {sym}
              </button>
            {/each}
          </div>
          {#if levelScope !== 'global'}
            <p class="mt-2 text-[10px] text-text-tertiary">
              Editing overrides for <span class="text-accent font-semibold">{levelScope}</span>. Empty fields inherit from Global.
            </p>
          {/if}
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div class="p-4 rounded-xl bg-surface-0 border border-border space-y-3">
            <div class="flex items-center justify-between">
              <p class="text-xs font-semibold text-text">Pivot Points</p>
              <input type="checkbox" class="accent-accent" checked={getLevelVal('methods', 'pivot_points', 'enabled')}
                on:change={(e) => setLevelVal(e.currentTarget.checked, 'methods', 'pivot_points', 'enabled')} />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class={labelBase}>Lookback Periods</label>
                <input class={inputBase} type="number" step="1" value={getLevelVal('methods', 'pivot_points', 'lookback_periods')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'pivot_points', 'lookback_periods')} />
              </div>
              <div>
                <label class={labelBase}>Min Touches</label>
                <input class={inputBase} type="number" step="1" value={getLevelVal('methods', 'pivot_points', 'min_touches')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'pivot_points', 'min_touches')} />
              </div>
              <div>
                <label class={labelBase}>Sensitivity</label>
                <input class={inputBase} type="number" step="1" value={getLevelVal('methods', 'pivot_points', 'sensitivity')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'pivot_points', 'sensitivity')} />
              </div>
            </div>
          </div>

          <div class="p-4 rounded-xl bg-surface-0 border border-border space-y-3">
            <div class="flex items-center justify-between">
              <p class="text-xs font-semibold text-text">Volume Profile</p>
              <input type="checkbox" class="accent-accent" checked={getLevelVal('methods', 'volume_profile', 'enabled')}
                on:change={(e) => setLevelVal(e.currentTarget.checked, 'methods', 'volume_profile', 'enabled')} />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class={labelBase}>Lookback Bars</label>
                <input class={inputBase} type="number" step="10" value={getLevelVal('methods', 'volume_profile', 'lookback_bars')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'volume_profile', 'lookback_bars')} />
              </div>
              <div>
                <label class={labelBase}>Value Area %</label>
                <input class={inputBase} type="number" step="0.01" value={getLevelVal('methods', 'volume_profile', 'value_area_pct')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'volume_profile', 'value_area_pct')} />
              </div>
              <div>
                <label class={labelBase}>Bins</label>
                <input class={inputBase} type="number" step="1" value={getLevelVal('methods', 'volume_profile', 'num_bins')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'volume_profile', 'num_bins')} />
              </div>
              <div>
                <label class={labelBase}>HVN Threshold</label>
                <input class={inputBase} type="number" step="0.1" value={getLevelVal('methods', 'volume_profile', 'hvn_threshold')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'volume_profile', 'hvn_threshold')} />
              </div>
            </div>
          </div>

          <div class="p-4 rounded-xl bg-surface-0 border border-border space-y-3">
            <div class="flex items-center justify-between">
              <p class="text-xs font-semibold text-text">Clustering</p>
              <input type="checkbox" class="accent-accent" checked={getLevelVal('methods', 'clustering', 'enabled')}
                on:change={(e) => setLevelVal(e.currentTarget.checked, 'methods', 'clustering', 'enabled')} />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class={labelBase}>Bandwidth</label>
                <input class={inputBase} type="number" step="0.1" value={getLevelVal('methods', 'clustering', 'bandwidth')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'clustering', 'bandwidth')} />
              </div>
              <div>
                <label class={labelBase}>Min Cluster Size</label>
                <input class={inputBase} type="number" step="1" value={getLevelVal('methods', 'clustering', 'min_cluster_size')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'clustering', 'min_cluster_size')} />
              </div>
              <div>
                <label class={labelBase}>Merge Distance (ATR)</label>
                <input class={inputBase} type="number" step="0.1" value={getLevelVal('methods', 'clustering', 'merge_distance_atr')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'clustering', 'merge_distance_atr')} />
              </div>
            </div>
          </div>

          <div class="p-4 rounded-xl bg-surface-0 border border-border space-y-3">
            <div class="flex items-center justify-between">
              <p class="text-xs font-semibold text-text">Round Numbers</p>
              <input type="checkbox" class="accent-accent" checked={getLevelVal('methods', 'round_numbers', 'enabled')}
                on:change={(e) => setLevelVal(e.currentTarget.checked, 'methods', 'round_numbers', 'enabled')} />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class={labelBase}>Forex Major</label>
                <input class={inputBase} type="number" step="0.001" value={getLevelVal('methods', 'round_numbers', 'intervals', 'forex_major')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'round_numbers', 'intervals', 'forex_major')} />
              </div>
              <div>
                <label class={labelBase}>Forex Minor</label>
                <input class={inputBase} type="number" step="0.001" value={getLevelVal('methods', 'round_numbers', 'intervals', 'forex_minor')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'round_numbers', 'intervals', 'forex_minor')} />
              </div>
              <div>
                <label class={labelBase}>Index</label>
                <input class={inputBase} type="number" step="1" value={getLevelVal('methods', 'round_numbers', 'intervals', 'index')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'round_numbers', 'intervals', 'index')} />
              </div>
              <div>
                <label class={labelBase}>Gold</label>
                <input class={inputBase} type="number" step="1" value={getLevelVal('methods', 'round_numbers', 'intervals', 'gold')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'round_numbers', 'intervals', 'gold')} />
              </div>
              <div>
                <label class={labelBase}>Crypto</label>
                <input class={inputBase} type="number" step="10" value={getLevelVal('methods', 'round_numbers', 'intervals', 'crypto')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'methods', 'round_numbers', 'intervals', 'crypto')} />
              </div>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div class="p-4 rounded-xl bg-surface-0 border border-border">
            <p class="text-xs font-semibold text-text mb-3">Zones</p>
            <div class="space-y-3">
              <div>
                <label class={labelBase}>Width (ATR)</label>
                <input class={inputBase} type="number" step="0.1" value={getLevelVal('zones', 'width_atr_multiplier')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'zones', 'width_atr_multiplier')} />
              </div>
              <div>
                <label class={labelBase}>Max Active Levels</label>
                <input class={inputBase} type="number" step="1" value={getLevelVal('zones', 'max_active_levels')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'zones', 'max_active_levels')} />
              </div>
              <div>
                <label class={labelBase}>Expiry (hours)</label>
                <input class={inputBase} type="number" step="1" value={getLevelVal('zones', 'level_expiry_hours')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'zones', 'level_expiry_hours')} />
              </div>
            </div>
          </div>

          <div class="p-4 rounded-xl bg-surface-0 border border-border">
            <p class="text-xs font-semibold text-text mb-3">Scoring</p>
            <div class="space-y-3">
              <div>
                <label class={labelBase}>Touch Weight</label>
                <input class={inputBase} type="number" step="0.1" value={getLevelVal('scoring', 'touch_weight')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'scoring', 'touch_weight')} />
              </div>
              <div>
                <label class={labelBase}>Recency Weight</label>
                <input class={inputBase} type="number" step="0.1" value={getLevelVal('scoring', 'recency_weight')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'scoring', 'recency_weight')} />
              </div>
              <div>
                <label class={labelBase}>Timeframe Weight</label>
                <input class={inputBase} type="number" step="0.1" value={getLevelVal('scoring', 'timeframe_weight')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'scoring', 'timeframe_weight')} />
              </div>
              <div>
                <label class={labelBase}>Volume Weight</label>
                <input class={inputBase} type="number" step="0.1" value={getLevelVal('scoring', 'volume_weight')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'scoring', 'volume_weight')} />
              </div>
              <div>
                <label class={labelBase}>Confluence Bonus</label>
                <input class={inputBase} type="number" step="0.1" value={getLevelVal('scoring', 'confluence_bonus')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'scoring', 'confluence_bonus')} />
              </div>
            </div>
          </div>

          <div class="p-4 rounded-xl bg-surface-0 border border-border">
            <p class="text-xs font-semibold text-text mb-3">Confluence</p>
            <label class="flex items-center gap-2 text-xs text-text-secondary">
              <input type="checkbox" class="accent-accent" checked={getLevelVal('confluence', 'enabled')}
                on:change={(e) => setLevelVal(e.currentTarget.checked, 'confluence', 'enabled')} />
              Require multi-timeframe match
            </label>
            {#if levelScope === 'global'}
              <div class="mt-3">
                <label class={labelBase}>Timeframes</label>
                <div class="flex flex-wrap gap-2 mt-2">
                  {#each timeframes as tf}
                    <button
                      type="button"
                      on:click={() => config.price_levels.confluence.timeframes = toggleString(config.price_levels.confluence.timeframes, tf)}
                      class="px-2.5 py-1 rounded-md text-[10px] font-semibold tracking-wide
                        {config.price_levels.confluence.timeframes.includes(tf)
                          ? 'bg-accent/20 text-accent border border-accent/40'
                          : 'bg-surface-1 text-text-tertiary border border-border'}">
                      {tf}
                    </button>
                  {/each}
                </div>
              </div>
              <div class="mt-3">
                <label class={labelBase}>Minimum Timeframes</label>
                <input class={inputBase} type="number" step="1" value={getLevelVal('confluence', 'min_timeframes')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'confluence', 'min_timeframes')} />
              </div>
            {:else}
              <div class="mt-3">
                <label class={labelBase}>Minimum Timeframes</label>
                <input class={inputBase} type="number" step="1" value={getLevelVal('confluence', 'min_timeframes')}
                  on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'confluence', 'min_timeframes')} />
              </div>
            {/if}
          </div>
        </div>

        <div class="p-4 rounded-xl bg-surface-0 border border-border">
          <p class="text-xs font-semibold text-text mb-3">Invalidation Rules</p>
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div>
              <label class={labelBase}>Max Clean Breaks</label>
              <input class={inputBase} type="number" step="1" value={getLevelVal('invalidation', 'max_clean_breaks')}
                on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'invalidation', 'max_clean_breaks')} />
            </div>
            <div>
              <label class={labelBase}>Break Threshold (ATR)</label>
              <input class={inputBase} type="number" step="0.1" value={getLevelVal('invalidation', 'break_threshold_atr')}
                on:input={(e) => setLevelVal(e.currentTarget.valueAsNumber, 'invalidation', 'break_threshold_atr')} />
            </div>
            <div class="flex items-center gap-2">
              <input type="checkbox" class="accent-accent" checked={getLevelVal('invalidation', 'polarity_flip')}
                on:change={(e) => setLevelVal(e.currentTarget.checked, 'invalidation', 'polarity_flip')} />
              <span class="text-xs text-text-secondary">Polarity flip after break</span>
            </div>
          </div>
        </div>
      </div>
    {/if}

    {#if $activeConfigTab === 'risk'}
      <div class="space-y-4">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div class="p-4 rounded-xl bg-surface-0 border border-border">
            <p class="text-xs font-semibold text-text mb-3">Per Trade</p>
            <div class="space-y-3">
              <div>
                <label class={labelBase}>Max Risk %</label>
                <input class={inputBase} type="number" step="0.1" value={config.risk.per_trade.max_risk_pct}
                  on:input={(e) => config.risk.per_trade.max_risk_pct = e.currentTarget.valueAsNumber} />
              </div>
              <div>
                <label class={labelBase}>Max Volume</label>
                <input class={inputBase} type="number" step="0.01" value={config.risk.per_trade.max_volume}
                  on:input={(e) => config.risk.per_trade.max_volume = e.currentTarget.valueAsNumber} />
              </div>
            </div>
          </div>

          <div class="p-4 rounded-xl bg-surface-0 border border-border">
            <p class="text-xs font-semibold text-text mb-3">Sizing</p>
            <div class="space-y-3">
              <div>
                <label class={labelBase}>Method</label>
                <select class={inputBase} bind:value={config.risk.sizing.method}>
                  {#each sizingMethods as method}<option value={method}>{method.replace('_', ' ')}</option>{/each}
                </select>
              </div>
              {#if config.risk.sizing.method === 'fixed_lot'}
                <div>
                  <label class={labelBase}>Fixed Lot Size</label>
                  <input class={inputBase} type="number" step="0.01" value={config.risk.sizing.fixed_lot_size}
                    on:input={(e) => config.risk.sizing.fixed_lot_size = e.currentTarget.valueAsNumber} />
                </div>
              {:else}
                <div>
                  <label class={labelBase}>Volatility Lookback</label>
                  <input class={inputBase} type="number" step="1" value={config.risk.sizing.volatility_lookback}
                    on:input={(e) => config.risk.sizing.volatility_lookback = e.currentTarget.valueAsNumber} />
                </div>
              {/if}
            </div>
          </div>

          <div class="p-4 rounded-xl bg-surface-0 border border-border">
            <p class="text-xs font-semibold text-text mb-3">Portfolio</p>
            <div class="space-y-3">
              <div>
                <label class={labelBase}>Max Open Positions</label>
                <input class={inputBase} type="number" step="1" value={config.risk.portfolio.max_open_positions}
                  on:input={(e) => config.risk.portfolio.max_open_positions = e.currentTarget.valueAsNumber} />
              </div>
              <div>
                <label class={labelBase}>Max Positions/Symbol</label>
                <input class={inputBase} type="number" step="1" value={config.risk.portfolio.max_positions_per_symbol}
                  on:input={(e) => config.risk.portfolio.max_positions_per_symbol = e.currentTarget.valueAsNumber} />
              </div>
              <div>
                <label class={labelBase}>Max Correlated Positions</label>
                <input class={inputBase} type="number" step="1" value={config.risk.portfolio.max_correlation_positions}
                  on:input={(e) => config.risk.portfolio.max_correlation_positions = e.currentTarget.valueAsNumber} />
              </div>
              <div>
                <label class={labelBase}>Max Total Exposure</label>
                <input class={inputBase} type="number" step="0.1" value={config.risk.portfolio.max_total_exposure}
                  on:input={(e) => config.risk.portfolio.max_total_exposure = e.currentTarget.valueAsNumber} />
              </div>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div class="p-4 rounded-xl bg-surface-0 border border-border">
            <p class="text-xs font-semibold text-text mb-3">Daily Limits</p>
            <div class="space-y-3">
              <div>
                <label class={labelBase}>Max Daily Loss %</label>
                <input class={inputBase} type="number" step="0.1" value={config.risk.daily.max_daily_loss_pct}
                  on:input={(e) => config.risk.daily.max_daily_loss_pct = e.currentTarget.valueAsNumber} />
              </div>
              <div>
                <label class={labelBase}>Max Daily Trades</label>
                <input class={inputBase} type="number" step="1" value={config.risk.daily.max_daily_trades}
                  on:input={(e) => config.risk.daily.max_daily_trades = e.currentTarget.valueAsNumber} />
              </div>
              <div>
                <label class={labelBase}>Reset Hour (UTC)</label>
                <input class={inputBase} type="number" step="1" value={config.risk.daily.reset_hour_utc}
                  on:input={(e) => config.risk.daily.reset_hour_utc = e.currentTarget.valueAsNumber} />
              </div>
            </div>
          </div>

          <div class="p-4 rounded-xl bg-surface-0 border border-border">
            <p class="text-xs font-semibold text-text mb-3">Drawdown</p>
            <div class="space-y-3">
              <div>
                <label class={labelBase}>Max Drawdown %</label>
                <input class={inputBase} type="number" step="0.1" value={config.risk.drawdown.max_drawdown_pct}
                  on:input={(e) => config.risk.drawdown.max_drawdown_pct = e.currentTarget.valueAsNumber} />
              </div>
              <div>
                <label class={labelBase}>Warning Drawdown %</label>
                <input class={inputBase} type="number" step="0.1" value={config.risk.drawdown.warning_drawdown_pct}
                  on:input={(e) => config.risk.drawdown.warning_drawdown_pct = e.currentTarget.valueAsNumber} />
              </div>
              <label class="flex items-center gap-2 text-xs text-text-secondary">
                <input type="checkbox" class="accent-accent" bind:checked={config.risk.drawdown.recovery_required} />
                Require recovery before resuming
              </label>
            </div>
          </div>

          <div class="p-4 rounded-xl bg-surface-0 border border-border">
            <p class="text-xs font-semibold text-text mb-3">Kill Switch</p>
            <div class="space-y-3">
              <label class="flex items-center gap-2 text-xs text-text-secondary">
                <input type="checkbox" class="accent-accent" bind:checked={config.risk.kill_switch.enabled} />
                Enabled
              </label>
              <div>
                <label class={labelBase}>Max Consecutive Losses</label>
                <input class={inputBase} type="number" step="1" value={config.risk.kill_switch.max_consecutive_losses}
                  on:input={(e) => config.risk.kill_switch.max_consecutive_losses = e.currentTarget.valueAsNumber} />
              </div>
              <div>
                <label class={labelBase}>Abnormal Spread Multiplier</label>
                <input class={inputBase} type="number" step="0.1" value={config.risk.kill_switch.abnormal_spread_multiplier}
                  on:input={(e) => config.risk.kill_switch.abnormal_spread_multiplier = e.currentTarget.valueAsNumber} />
              </div>
              <div>
                <label class={labelBase}>Max Slippage (pips)</label>
                <input class={inputBase} type="number" step="1" value={config.risk.kill_switch.max_slippage_pips}
                  on:input={(e) => config.risk.kill_switch.max_slippage_pips = e.currentTarget.valueAsNumber} />
              </div>
            </div>
          </div>
        </div>

        <div class="p-4 rounded-xl bg-surface-0 border border-border space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-xs font-semibold text-text">Trading Hours</p>
              <p class="text-[10px] text-text-tertiary">Restrict when the strategy is allowed to trade</p>
            </div>
            <label class="flex items-center gap-2 text-xs text-text-secondary">
              <input type="checkbox" class="accent-accent" bind:checked={config.risk.trading_hours.enabled} />
              Enabled
            </label>
          </div>

          <div class="space-y-3">
            {#each config.risk.trading_hours.sessions as session, i}
              <div class="grid grid-cols-1 lg:grid-cols-4 gap-3 items-end">
                <div>
                  <label class={labelBase}>Session</label>
                  <input class={inputBase} type="text" bind:value={session.name} />
                </div>
                <div>
                  <label class={labelBase}>Start (UTC)</label>
                  <input class={inputBase} type="time" bind:value={session.start} />
                </div>
                <div>
                  <label class={labelBase}>End (UTC)</label>
                  <input class={inputBase} type="time" bind:value={session.end} />
                </div>
                <button type="button" on:click={() => removeSession(i)}
                  class="px-3 py-2 rounded-lg text-[10px] font-semibold tracking-wider text-short bg-short-dim hover:bg-short/20 transition-colors">
                  Remove
                </button>
              </div>
            {/each}
          </div>

          <button type="button" on:click={addSession}
            class="px-3 py-2 rounded-lg text-[10px] font-semibold tracking-wider text-text bg-surface-1 border border-border hover:border-border-hover">
            Add Session
          </button>

          <div>
            <label class={labelBase}>Excluded Days</label>
            <div class="flex flex-wrap gap-2 mt-2">
              {#each days as day, idx}
                <button
                  type="button"
                  on:click={() => config.risk.trading_hours.excluded_days = toggleNumber(config.risk.trading_hours.excluded_days, idx)}
                  class="px-2.5 py-1 rounded-md text-[10px] font-semibold tracking-wide
                    {config.risk.trading_hours.excluded_days.includes(idx)
                      ? 'bg-short-dim text-short border border-short/40'
                      : 'bg-surface-1 text-text-tertiary border border-border'}">
                  {day}
                </button>
              {/each}
            </div>
          </div>
        </div>
      </div>
    {/if}

    {#if $activeConfigTab === 'symbols'}
      <div class="space-y-4">
        <div class="p-4 rounded-xl bg-surface-0 border border-border">
          <p class="text-xs font-semibold text-text mb-3">Defaults</p>
          <div class="grid grid-cols-1 lg:grid-cols-6 gap-4">
            <div>
              <label class={labelBase}>Default Strategy</label>
              <select class={inputBase} bind:value={config.symbols.defaults.strategy}>
                {#each knownStrategyIds as sid}<option value={sid}>{sid}</option>{/each}
              </select>
            </div>
            <div>
              <label class={labelBase}>Pip Size</label>
              <input class={inputBase} type="number" step="0.0001" value={config.symbols.defaults.pip_size}
                on:input={(e) => config.symbols.defaults.pip_size = e.currentTarget.valueAsNumber} />
            </div>
            <div>
              <label class={labelBase}>Min Volume</label>
              <input class={inputBase} type="number" step="0.01" value={config.symbols.defaults.min_volume}
                on:input={(e) => config.symbols.defaults.min_volume = e.currentTarget.valueAsNumber} />
            </div>
            <div>
              <label class={labelBase}>Volume Step</label>
              <input class={inputBase} type="number" step="0.01" value={config.symbols.defaults.volume_step}
                on:input={(e) => config.symbols.defaults.volume_step = e.currentTarget.valueAsNumber} />
            </div>
            <div>
              <label class={labelBase}>Spread Limit (pips)</label>
              <input class={inputBase} type="number" step="0.1" value={config.symbols.defaults.spread_limit_pips}
                on:input={(e) => config.symbols.defaults.spread_limit_pips = e.currentTarget.valueAsNumber} />
            </div>
            <div class="flex items-end">
              <label class="flex items-center gap-2 text-xs text-text-secondary">
                <input type="checkbox" class="accent-accent" bind:checked={config.symbols.defaults.enabled} />
                Default Enabled
              </label>
            </div>
          </div>
        </div>

        <div class="p-4 rounded-xl bg-surface-0 border border-border">
          <div class="flex items-center justify-between mb-3 gap-3">
            <p class="text-xs font-semibold text-text">Instruments</p>
            <div class="flex items-center gap-2">
              <select
                class="bg-surface-0 text-text text-[10px] rounded-lg px-2.5 py-2 border border-border focus:border-accent/60 focus:outline-none"
                bind:value={newSymbol}
                disabled={$symbolsLoading || availableSymbols.length === 0}
              >
                {#if $symbolsLoading}
                  <option value="" disabled>Loading symbols...</option>
                {:else if !symbolsConnected}
                  <option value="" disabled>MT5 offline</option>
                {:else if availableSymbols.length === 0}
                  <option value="" disabled>All symbols added</option>
                {:else}
                  {#each availableSymbols as sym}
                    <option value={sym}>{sym}</option>
                  {/each}
                {/if}
              </select>
              <button
                type="button"
                on:click={() => addSymbol(newSymbol)}
                disabled={$symbolsLoading || !newSymbol || availableSymbols.length === 0}
                class="px-3 py-2 rounded-lg text-[10px] font-semibold tracking-wider text-text bg-surface-1 border border-border hover:border-border-hover disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Add Symbol
              </button>
            </div>
          </div>
          <div class="grid grid-cols-8 gap-3 text-[10px] font-semibold text-text-tertiary uppercase tracking-wider">
            <span>Symbol</span>
            <span>Enabled</span>
            <span>Strategy</span>
            <span>Category</span>
            <span>Pip Size</span>
            <span>Min Vol</span>
            <span>Step</span>
            <span>Spread</span>
          </div>
          <div class="mt-2 space-y-2">
            {#each symbolOrder as sym}
              <div class="grid grid-cols-8 gap-3 items-center py-2 border-t border-border/60">
                <div class="flex items-center gap-2">
                  <span class="text-xs font-mono text-text">{sym}</span>
                  <button type="button" on:click={() => removeSymbol(sym)}
                    class="text-[10px] text-short hover:text-short/80">Remove</button>
                </div>
                <label class="flex items-center gap-2 text-xs text-text-secondary">
                  <input
                    type="checkbox"
                    class="accent-accent"
                    checked={config.symbols.instruments[sym].enabled}
                    on:change={(e) => config.symbols.instruments[sym].enabled = e.currentTarget.checked}
                  />
                  On
                </label>
                <select class={inputBase}
                  value={config.symbols.instruments[sym].strategy}
                  on:change={(e) => config.symbols.instruments[sym].strategy = e.currentTarget.value}>
                  {#each knownStrategyIds as sid}<option value={sid}>{sid}</option>{/each}
                </select>
                <select
                  class={inputBase}
                  value={config.symbols.instruments[sym].category}
                  on:change={(e) => config.symbols.instruments[sym].category = e.currentTarget.value}
                >
                  {#each categories as c}<option value={c}>{c}</option>{/each}
                </select>
                <input class={inputBase} type="number" step="0.0001" value={config.symbols.instruments[sym].pip_size}
                  on:input={(e) => config.symbols.instruments[sym].pip_size = e.currentTarget.valueAsNumber} />
                <input class={inputBase} type="number" step="0.01" value={config.symbols.instruments[sym].min_volume}
                  on:input={(e) => config.symbols.instruments[sym].min_volume = e.currentTarget.valueAsNumber} />
                <input class={inputBase} type="number" step="0.01" value={config.symbols.instruments[sym].volume_step}
                  on:input={(e) => config.symbols.instruments[sym].volume_step = e.currentTarget.valueAsNumber} />
                <input class={inputBase} type="number" step="0.1" value={config.symbols.instruments[sym].spread_limit_pips}
                  on:input={(e) => config.symbols.instruments[sym].spread_limit_pips = e.currentTarget.valueAsNumber} />
              </div>
            {/each}
          </div>
        </div>
      </div>
    {/if}

    {#if $activeConfigTab === 'notifications'}
      <div class="space-y-4">
        <div class="p-4 rounded-xl bg-surface-0 border border-border flex items-center justify-between">
          <div>
            <p class="text-xs font-semibold text-text">Notifications</p>
            <p class="text-[10px] text-text-tertiary">Control alerting channels and events</p>
          </div>
          <label class="flex items-center gap-2 text-xs text-text-secondary">
            <input type="checkbox" class="accent-accent" bind:checked={config.notifications.enabled} />
            Enabled
          </label>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div class="p-4 rounded-xl bg-surface-0 border border-border space-y-3">
            <div class="flex items-center justify-between">
              <p class="text-xs font-semibold text-text">Console</p>
              <input type="checkbox" class="accent-accent" bind:checked={config.notifications.channels.console.enabled} />
            </div>
            <p class="text-[10px] text-text-tertiary">Always logs to server output.</p>
          </div>

          <div class="p-4 rounded-xl bg-surface-0 border border-border space-y-3">
            <div class="flex items-center justify-between">
              <p class="text-xs font-semibold text-text">Telegram</p>
              <input type="checkbox" class="accent-accent" bind:checked={config.notifications.channels.telegram.enabled} />
            </div>
            <div>
              <label class={labelBase}>Bot Token</label>
              <input class={inputBase} type="password" bind:value={config.notifications.channels.telegram.bot_token} />
            </div>
            <div>
              <label class={labelBase}>Chat ID</label>
              <input class={inputBase} type="text" bind:value={config.notifications.channels.telegram.chat_id} />
            </div>
          </div>

          <div class="p-4 rounded-xl bg-surface-0 border border-border space-y-3">
            <div class="flex items-center justify-between">
              <p class="text-xs font-semibold text-text">Email</p>
              <input type="checkbox" class="accent-accent" bind:checked={config.notifications.channels.email.enabled} />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class={labelBase}>SMTP Host</label>
                <input class={inputBase} type="text" bind:value={config.notifications.channels.email.smtp_host} />
              </div>
              <div>
                <label class={labelBase}>SMTP Port</label>
                <input class={inputBase} type="number" step="1" value={config.notifications.channels.email.smtp_port}
                  on:input={(e) => config.notifications.channels.email.smtp_port = e.currentTarget.valueAsNumber} />
              </div>
              <div>
                <label class={labelBase}>Username</label>
                <input class={inputBase} type="text" bind:value={config.notifications.channels.email.username} />
              </div>
              <div>
                <label class={labelBase}>Password</label>
                <input class={inputBase} type="password" bind:value={config.notifications.channels.email.password} />
              </div>
              <div class="lg:col-span-2">
                <label class={labelBase}>Recipient</label>
                <input class={inputBase} type="email" bind:value={config.notifications.channels.email.to_address} />
              </div>
            </div>
          </div>
        </div>

        <div class="p-4 rounded-xl bg-surface-0 border border-border">
          <p class="text-xs font-semibold text-text mb-3">Event Triggers</p>
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {#each Object.entries(config.notifications.events) as [key, value]}
              <label class="flex items-center gap-2 text-xs text-text-secondary">
                <input type="checkbox" class="accent-accent" bind:checked={config.notifications.events[key]} />
                {key.replace(/_/g, ' ')}
              </label>
            {/each}
          </div>
        </div>
      </div>
    {/if}
  </div>

  <details class="mt-6 bg-surface-0 border border-border rounded-xl p-4" bind:open={showAdvanced}>
    <summary class="text-xs font-semibold text-text cursor-pointer">Advanced JSON</summary>
    <textarea
      bind:value={rawJson}
      rows="16"
      class="mt-3 w-full bg-surface-0 text-text font-mono text-xs rounded-xl p-4
        border border-border resize-y focus:border-accent/50 focus:outline-none"
      spellcheck="false"
      placeholder="JSON snapshot (read-only)"
      readonly
    ></textarea>
  </details>

  <div class="flex justify-between items-center mt-4">
    <div class="flex items-center gap-2">
      {#if message}
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium
          {messageType === 'success' ? 'bg-long-dim text-long' : 'bg-short-dim text-short'}">
          {#if messageType === 'success'}
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
          {:else}
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>
          {/if}
          {message}
        </span>
      {/if}
    </div>

    <div class="flex items-center gap-3">
      {#if $configDirty}
        <span class="flex items-center gap-1.5 text-xs text-warning">
          <span class="w-1.5 h-1.5 rounded-full bg-warning"></span>
          Unsaved
        </span>
      {/if}
      <button
        on:click={saveConfig}
        disabled={!$configDirty || saving}
        class="px-5 py-2.5 rounded-lg text-xs font-semibold bg-accent text-white
          disabled:opacity-30 hover:bg-accent-hover transition-all duration-200
          hover:shadow-lg hover:shadow-accent/20 active:scale-[0.98]
          disabled:hover:shadow-none disabled:cursor-not-allowed">
        {#if saving}
          <span class="inline-flex items-center gap-2">
            <span class="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
            Saving
          </span>
        {:else}
          Save & Apply
        {/if}
      </button>
    </div>
  </div>
</div>
