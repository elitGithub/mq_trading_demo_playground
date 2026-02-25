import { writable } from 'svelte/store';
import type { Position, Order } from '$lib/types';

export const openPositions = writable<Position[]>([]);
export const pendingOrders = writable<Order[]>([]);
