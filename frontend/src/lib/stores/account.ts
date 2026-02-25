import { writable } from 'svelte/store';
import type { AccountInfo } from '$lib/types';

export const accountInfo = writable<AccountInfo | null>(null);
export const accountConnected = writable(false);
