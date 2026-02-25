export interface Tick {
  time: number;
  bid: number;
  ask: number;
  last: number;
  volume: number;
}

export interface Bar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  tick_volume: number;
}

export interface Position {
  ticket: number;
  time: string;
  type: number;
  volume: number;
  price_open: number;
  sl: number;
  tp: number;
  price_current: number;
  profit: number;
  symbol: string;
  comment: string;
}

export interface Order {
  ticket: number;
  type: number;
  volume_current: number;
  price_open: number;
  sl: number;
  tp: number;
  symbol: string;
  comment: string;
}

export interface AccountInfo {
  login: number;
  balance: number;
  equity: number;
  margin: number;
  margin_free: number;
  margin_level: number;
  profit: number;
  currency: string;
  leverage: number;
  server: string;
  name: string;
  company: string;
}

export interface PriceLevel {
  price: number;
  zone_upper: number;
  zone_lower: number;
  level_type: 'support' | 'resistance';
  method: string;
  strength: number;
  touch_count: number;
  is_active: boolean;
}

export interface HealthStatus {
  status: string;
  mt5_connected: boolean;
  strategy_enabled: boolean;
  ws_connections: number;
}

export type ConfigName = 'strategy' | 'price_levels' | 'risk' | 'symbols' | 'notifications' | 'trade_plans';

// Trade Plans

export interface RuleCondition {
  field: 'bid' | 'ask' | 'last';
  op: '>=' | '<=' | '>' | '<' | '==';
  value: number;
}

export interface RuleAction {
  type: string;
  volume?: number;
  price?: number;
  sl?: number;
  tp?: number;
  comment?: string;
}

export interface RuleOnFill {
  activate: string[];
  deactivate: string[];
}

export interface RuleState {
  active: boolean;
  executed: boolean;
  conditions: RuleCondition[];
  actions: RuleAction[];
  on_fill: RuleOnFill;
}

export interface TradePlanDetail {
  plan_id: string;
  enabled: boolean;
  symbol: string;
  magic: number;
  rules: Record<string, RuleState>;
  position_tickets: number[];
  order_tickets: number[];
}

export interface TradePlanSummary {
  plan_id: string;
  enabled: boolean;
  symbol: string;
  magic: number;
  rule_states: Record<string, 'active' | 'inactive' | 'executed'>;
  position_count: number;
  order_count: number;
}
