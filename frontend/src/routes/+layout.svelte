<script lang="ts">
  import '../app.css';
  import { onMount, onDestroy } from 'svelte';
  import { connectWs, disconnectWs, wsConnected } from '$lib/stores/websocket';
  import { getAccountInfo, getPositions, getHealth } from '$lib/api/client';
  import { accountInfo, accountConnected } from '$lib/stores/account';
  import { openPositions } from '$lib/stores/positions';
  import { page } from '$app/stores';

  export let data;

  let pollInterval: ReturnType<typeof setInterval>;
  let mt5Status = false;
  let strategyEnabled = false;

  const navItems = [
    {
      href: '/',
      label: 'Dashboard',
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>`,
    },
    {
      href: '/trade',
      label: 'Trade',
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 16l4-8 4 4 5-9"/></svg>`,
    },
    {
      href: '/screener',
      label: 'Screener',
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>`,
    },
    {
      href: '/trade-plans',
      label: 'Plans',
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 14l2 2 4-4"/></svg>`,
    },
    {
      href: '/history',
      label: 'History',
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 15"/></svg>`,
    },
    {
      href: '/settings',
      label: 'Settings',
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 00-2 2v.18a2 2 0 01-1 1.73l-.43.25a2 2 0 01-2 0l-.15-.08a2 2 0 00-2.73.73l-.22.38a2 2 0 00.73 2.73l.15.1a2 2 0 011 1.72v.51a2 2 0 01-1 1.74l-.15.09a2 2 0 00-.73 2.73l.22.38a2 2 0 002.73.73l.15-.08a2 2 0 012 0l.43.25a2 2 0 011 1.73V20a2 2 0 002 2h.44a2 2 0 002-2v-.18a2 2 0 011-1.73l.43-.25a2 2 0 012 0l.15.08a2 2 0 002.73-.73l.22-.39a2 2 0 00-.73-2.73l-.15-.08a2 2 0 01-1-1.74v-.5a2 2 0 011-1.74l.15-.09a2 2 0 00.73-2.73l-.22-.38a2 2 0 00-2.73-.73l-.15.08a2 2 0 01-2 0l-.43-.25a2 2 0 01-1-1.73V4a2 2 0 00-2-2z"/><circle cx="12" cy="12" r="3"/></svg>`,
    },
  ];

  function isActive(pagePath: string, itemHref: string): boolean {
    if (itemHref === '/') return pagePath === '/';
    return pagePath === itemHref || pagePath.startsWith(itemHref + '/');
  }

  onMount(() => {
    // Expose backend port for direct API calls (SSE streams, etc.)
    if (data.backendPort) (window as any).__BACKEND_PORT = data.backendPort;
    connectWs(data.backendPort);

    async function poll() {
      try {
        const [accRes, posRes, healthRes] = await Promise.allSettled([
          getAccountInfo(),
          getPositions(),
          getHealth(),
        ]);

        if (accRes.status === 'fulfilled') {
          $accountInfo = accRes.value.account;
          $accountConnected = accRes.value.connected;
        }
        if (posRes.status === 'fulfilled') {
          $openPositions = posRes.value.positions;
        }
        if (healthRes.status === 'fulfilled') {
          mt5Status = healthRes.value.mt5_connected;
          strategyEnabled = healthRes.value.strategy_enabled;
        }
      } catch { /* retry next tick */ }
    }

    poll();
    pollInterval = setInterval(poll, 2000);
  });

  onDestroy(() => {
    disconnectWs();
    clearInterval(pollInterval);
  });
</script>

<div class="flex h-screen bg-base noise-bg">
  <!-- Sidebar -->
  <nav class="relative z-30 w-[68px] flex flex-col items-center py-5 bg-surface-0 border-r border-border overflow-visible">
    <!-- Logo -->
    <div class="mb-8 flex flex-col items-center gap-1">
      <div class="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-accent">
          <path d="M3 3v18h18" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M7 16l4-8 4 4 5-9" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <span class="text-[9px] font-semibold tracking-[0.2em] text-text-tertiary uppercase">ATS</span>
    </div>

    <!-- Nav items -->
    <div class="flex flex-col gap-1.5">
      {#each navItems as item}
        {@const active = isActive($page.url.pathname, item.href)}
        <a
          href={item.href}
          class="group relative w-10 h-10 rounded-lg flex items-center justify-center transition-all duration-200
            {active
              ? 'bg-accent/15 text-accent'
              : 'text-text-tertiary hover:text-text-secondary hover:bg-surface-2'}"
          aria-label={item.label}
        >
          <!-- Active indicator bar -->
          {#if active}
            <div class="absolute left-[-14px] w-[3px] h-5 rounded-r-full bg-accent"></div>
          {/if}
          {@html item.icon}

          <!-- Tooltip -->
          <div class="absolute left-full ml-3 px-2.5 py-1 rounded-md bg-surface-3/95 text-text text-xs font-medium
            opacity-0 pointer-events-none group-hover:opacity-100 transition-all duration-150 whitespace-nowrap
            shadow-lg shadow-black/50 z-[60] border border-border/80 backdrop-blur
            translate-x-1 group-hover:translate-x-0">
            {item.label}
          </div>
        </a>
      {/each}
    </div>

    <!-- Status indicators -->
    <div class="mt-auto flex flex-col items-center gap-3 pb-2">
      <!-- MT5 -->
      <div class="group relative flex flex-col items-center gap-1 cursor-default">
        <div class="w-2 h-2 rounded-full {mt5Status ? 'bg-long animate-pulse-soft' : 'bg-short'}"></div>
        <span class="text-[8px] font-medium tracking-wider text-text-tertiary uppercase">MT5</span>
        <div class="absolute bottom-full mb-2 px-2 py-1 rounded-md bg-surface-3/95 text-[10px] font-medium
          opacity-0 pointer-events-none group-hover:opacity-100 transition-all duration-150 whitespace-nowrap
          shadow-lg shadow-black/40 z-[60] border border-border/80 backdrop-blur
          translate-y-1 group-hover:translate-y-0
          {mt5Status ? 'text-long' : 'text-short'}">
          {mt5Status ? 'Connected' : 'Disconnected'}
        </div>
      </div>
      <!-- WS -->
      <div class="group relative flex flex-col items-center gap-1 cursor-default">
        <div class="w-2 h-2 rounded-full {$wsConnected ? 'bg-long animate-pulse-soft' : 'bg-short'}"></div>
        <span class="text-[8px] font-medium tracking-wider text-text-tertiary uppercase">WS</span>
        <div class="absolute bottom-full mb-2 px-2 py-1 rounded-md bg-surface-3/95 text-[10px] font-medium
          opacity-0 pointer-events-none group-hover:opacity-100 transition-all duration-150 whitespace-nowrap
          shadow-lg shadow-black/40 z-[60] border border-border/80 backdrop-blur
          translate-y-1 group-hover:translate-y-0
          {$wsConnected ? 'text-long' : 'text-short'}">
          {$wsConnected ? 'Connected' : 'Disconnected'}
        </div>
      </div>
      <!-- Strategy -->
      <div class="group relative flex flex-col items-center gap-1 cursor-default">
        <div class="w-2 h-2 rounded-full {strategyEnabled ? 'bg-long animate-pulse-soft' : 'bg-warning'}"></div>
        <span class="text-[8px] font-medium tracking-wider text-text-tertiary uppercase">ALGO</span>
        <div class="absolute bottom-full mb-2 px-2 py-1 rounded-md bg-surface-3/95 text-[10px] font-medium
          opacity-0 pointer-events-none group-hover:opacity-100 transition-all duration-150 whitespace-nowrap
          shadow-lg shadow-black/40 z-[60] border border-border/80 backdrop-blur
          translate-y-1 group-hover:translate-y-0
          {strategyEnabled ? 'text-long' : 'text-warning'}">
          {strategyEnabled ? 'Running' : 'Stopped'}
        </div>
      </div>
    </div>
  </nav>

  <!-- Main content -->
  <main class="relative z-10 flex-1 overflow-auto p-6">
    <slot />
  </main>
</div>
