import { writable } from 'svelte/store';
import type { ConfigName } from '$lib/types';

export const activeConfigTab = writable<ConfigName>('strategy');
export const configData = writable<Record<string, unknown>>({});
export const configDirty = writable(false);
export const activeStrategyId = writable<string>('');
