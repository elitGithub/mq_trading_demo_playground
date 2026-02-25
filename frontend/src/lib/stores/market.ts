import { writable } from 'svelte/store';
import type { Bar } from '$lib/types';

export const currentPrices = writable<Record<string, { bid: number; ask: number }>>({});
export const chartBars = writable<Bar[]>([]);
export const selectedSymbol = writable<string>('EURUSD');
export const selectedTimeframe = writable<string>('H1');
export const tradeableSymbols = writable<string[]>([]);
export const symbolsLoading = writable(true);
