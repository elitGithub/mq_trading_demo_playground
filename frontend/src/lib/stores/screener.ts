import { writable } from 'svelte/store';
import type { ScreenerResult } from '$lib/types';

export const screenerResults = writable<ScreenerResult[]>([]);
export const screenerLoading = writable(false);
export const screenerError = writable('');

// Progress tracking
export const screenerProgress = writable<{
  batch: number;
  totalBatches: number;
  scannedSoFar: number;
  totalSymbols: number;
  matchedSoFar: number;
} | null>(null);
