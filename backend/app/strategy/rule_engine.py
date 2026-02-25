"""Rule-based trade execution engine.

Evaluates user-defined price rules from trade_plans.yaml and executes
actions via mt5_client. State is persisted in Redis to survive restarts.
"""

import operator
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.config.loader import config_loader
from app.data.redis_client import get_redis
from app.events.bus import event_bus
from app.events.events import Event, EventType
from app.mt5.client import mt5_client
from app.mt5.models import OrderType, Tick, TradeRequest
from app.risk.manager import risk_manager

logger = structlog.get_logger()

VALID_FIELDS = {"bid", "ask", "last"}
VALID_OPS = {">=", "<=", ">", "<", "=="}
VALID_ACTION_TYPES = {
    "market_buy", "market_sell",
    "buy_limit", "sell_limit", "buy_stop", "sell_stop",
    "partial_close", "close_all",
    "modify_sl", "cancel_orders",
}

OP_MAP = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
}


@dataclass
class Condition:
    field: str
    op: str
    value: float


@dataclass
class Action:
    type: str
    volume: float | None = None
    price: float | None = None
    sl: float | None = None
    tp: float | None = None
    comment: str | None = None


@dataclass
class OnFill:
    activate: list[str] = field(default_factory=list)
    deactivate: list[str] = field(default_factory=list)


@dataclass
class Rule:
    id: str
    active: bool
    executed: bool
    conditions: list[Condition]
    actions: list[Action]
    on_fill: OnFill


@dataclass
class TradePlan:
    plan_id: str
    enabled: bool
    symbol: str
    magic: int
    rules: dict[str, Rule]
    position_tickets: set[int] = field(default_factory=set)
    order_tickets: set[int] = field(default_factory=set)


class RuleEngine:
    """Evaluates trade plans and executes rule-based actions."""

    MAX_CONSECUTIVE_FAILURES = 3

    def __init__(self):
        self._plans: dict[str, TradePlan] = {}
        self._loaded = False
        self._fail_counts: dict[tuple[str, str], int] = {}  # (plan_id, rule_id) -> count
        self._cycle_failed: set[tuple[str, str]] = set()  # already counted this cycle

    @property
    def plans(self) -> dict[str, TradePlan]:
        return self._plans

    async def load_plans(self) -> None:
        """Parse trade_plans.yaml into TradePlan objects, then reconcile with Redis state."""
        raw = config_loader.get("trade_plans")
        plans_cfg = raw.get("trade_plans", {})
        if not isinstance(plans_cfg, dict):
            logger.warning("rule_engine.invalid_config", detail="trade_plans not a dict")
            return

        new_plans: dict[str, TradePlan] = {}
        for plan_id, plan_cfg in plans_cfg.items():
            plan = self._parse_plan(plan_id, plan_cfg)
            if plan is not None:
                new_plans[plan_id] = plan

        self._plans = new_plans
        await self._restore_state()
        await self._reconcile_tickets()
        self._loaded = True
        logger.info("rule_engine.plans_loaded", count=len(self._plans))

    def _parse_plan(self, plan_id: str, cfg: dict[str, Any]) -> TradePlan | None:
        """Parse a single plan from config dict."""
        if not isinstance(cfg, dict):
            logger.warning("rule_engine.skip_plan", plan_id=plan_id, reason="not a dict")
            return None

        symbol = cfg.get("symbol")
        if not symbol:
            logger.warning("rule_engine.skip_plan", plan_id=plan_id, reason="no symbol")
            return None

        rules: dict[str, Rule] = {}
        rules_cfg = cfg.get("rules", {})
        for rule_id, rule_cfg in rules_cfg.items():
            rule = self._parse_rule(plan_id, rule_id, rule_cfg)
            if rule is not None:
                rules[rule_id] = rule

        # Validate on_fill references
        all_rule_ids = set(rules.keys())
        for rule in rules.values():
            for ref in rule.on_fill.activate + rule.on_fill.deactivate:
                if ref not in all_rule_ids:
                    logger.warning(
                        "rule_engine.bad_ref",
                        plan_id=plan_id, rule_id=rule.id, ref=ref,
                    )

        return TradePlan(
            plan_id=plan_id,
            enabled=cfg.get("enabled", True),
            symbol=symbol,
            magic=cfg.get("magic", 234200),
            rules=rules,
        )

    def _parse_rule(self, plan_id: str, rule_id: str, cfg: dict) -> Rule | None:
        """Parse a single rule from config dict."""
        conditions = []
        for cond_cfg in cfg.get("conditions", []):
            f = cond_cfg.get("field")
            op = cond_cfg.get("op")
            val = cond_cfg.get("value")
            if f not in VALID_FIELDS:
                logger.warning("rule_engine.bad_field", plan_id=plan_id, rule_id=rule_id, field=f)
                return None
            if op not in VALID_OPS:
                logger.warning("rule_engine.bad_op", plan_id=plan_id, rule_id=rule_id, op=op)
                return None
            conditions.append(Condition(field=f, op=op, value=float(val)))

        actions = []
        for act_cfg in cfg.get("actions", []):
            act_type = act_cfg.get("type")
            if act_type not in VALID_ACTION_TYPES:
                logger.warning("rule_engine.bad_action", plan_id=plan_id, rule_id=rule_id, type=act_type)
                return None
            actions.append(Action(
                type=act_type,
                volume=act_cfg.get("volume"),
                price=act_cfg.get("price"),
                sl=act_cfg.get("sl"),
                tp=act_cfg.get("tp"),
                comment=act_cfg.get("comment"),
            ))

        on_fill_cfg = cfg.get("on_fill", {})
        on_fill = OnFill(
            activate=on_fill_cfg.get("activate", []),
            deactivate=on_fill_cfg.get("deactivate", []),
        )

        return Rule(
            id=rule_id,
            active=cfg.get("active", False),
            executed=False,
            conditions=conditions,
            actions=actions,
            on_fill=on_fill,
        )

    def begin_cycle(self) -> None:
        """Mark the start of a new poll cycle. Failure counting is per-cycle, not per-tick."""
        self._cycle_failed.clear()

    async def evaluate(self, symbol: str, tick: Tick) -> None:
        """Evaluate all active plans matching this symbol against the current tick."""
        if risk_manager._halted:
            return

        for plan in self._plans.values():
            if not plan.enabled or plan.symbol != symbol:
                continue
            for rule in plan.rules.values():
                if not rule.active or rule.executed:
                    continue
                if self._check_conditions(rule, tick):
                    key = (plan.plan_id, rule.id)
                    # Skip re-attempting actions that already failed this cycle
                    if key in self._cycle_failed:
                        continue
                    success = await self._execute_actions(plan, rule, tick)
                    if success:
                        self._fail_counts.pop(key, None)
                        self._cycle_failed.discard(key)
                        rule.executed = True
                        self._apply_transitions(plan, rule)
                        await self._publish_rule_event(plan, rule)
                        await self.save_state(plan.plan_id)

                        # Check if plan is complete (all rules executed or inactive)
                        if self._is_plan_complete(plan):
                            await event_bus.publish(Event(
                                type=EventType.PLAN_COMPLETE,
                                data={"plan_id": plan.plan_id, "symbol": plan.symbol},
                                source="rule_engine",
                            ))
                    else:
                        # Only count one failure per rule per poll cycle
                        self._cycle_failed.add(key)
                        count = self._fail_counts.get(key, 0) + 1
                        self._fail_counts[key] = count
                        if count >= self.MAX_CONSECUTIVE_FAILURES:
                            rule.active = False
                            self._fail_counts.pop(key, None)
                            await self.save_state(plan.plan_id)
                            logger.error(
                                "rule_engine.rule_disabled_after_failures",
                                plan_id=plan.plan_id, rule_id=rule.id,
                                failures=count,
                            )

    def _check_conditions(self, rule: Rule, tick: Tick) -> bool:
        """All conditions must pass (AND logic)."""
        for cond in rule.conditions:
            tick_value = getattr(tick, cond.field, None)
            if tick_value is None:
                return False
            op_fn = OP_MAP.get(cond.op)
            if op_fn is None:
                return False
            if not op_fn(tick_value, cond.value):
                return False
        return True

    async def _execute_actions(self, plan: TradePlan, rule: Rule, tick: Tick) -> bool:
        """Execute all actions for a triggered rule. Returns True if all succeed."""
        symbol = plan.symbol
        magic = plan.magic

        for action in rule.actions:
            try:
                result = await self._dispatch_action(plan, action, tick)
                if result is not None and not result:
                    logger.error(
                        "rule_engine.action_failed",
                        plan_id=plan.plan_id, rule_id=rule.id, action=action.type,
                        symbol=plan.symbol,
                    )
                    return False
            except Exception:
                logger.exception(
                    "rule_engine.action_error",
                    plan_id=plan.plan_id, rule_id=rule.id, action=action.type,
                )
                return False

        logger.info(
            "rule_engine.rule_fired",
            plan_id=plan.plan_id, rule_id=rule.id,
            actions=[a.type for a in rule.actions],
        )
        return True

    async def _dispatch_action(self, plan: TradePlan, action: Action, tick: Tick) -> bool | None:
        """Dispatch a single action to mt5_client. Returns True on success, False on failure."""
        symbol = plan.symbol
        magic = plan.magic
        comment = action.comment or f"ATS|{plan.plan_id}|{action.type}"

        if action.type == "market_buy":
            result = await mt5_client.place_order(TradeRequest(
                symbol=symbol, side="BUY",
                volume=action.volume if action.volume is not None else 0.01,
                stop_loss=action.sl, take_profit=action.tp,
                comment=comment, magic=magic,
            ))
            if result.success and result.ticket:
                plan.position_tickets.add(result.ticket)
            elif not result.success:
                logger.warning(
                    "rule_engine.order_rejected",
                    action=action.type, symbol=symbol, plan_id=plan.plan_id,
                    retcode=result.retcode, mt5_comment=result.comment,
                )
            return result.success

        if action.type == "market_sell":
            result = await mt5_client.place_order(TradeRequest(
                symbol=symbol, side="SELL",
                volume=action.volume if action.volume is not None else 0.01,
                stop_loss=action.sl, take_profit=action.tp,
                comment=comment, magic=magic,
            ))
            if result.success and result.ticket:
                plan.position_tickets.add(result.ticket)
            elif not result.success:
                logger.warning(
                    "rule_engine.order_rejected",
                    action=action.type, symbol=symbol, plan_id=plan.plan_id,
                    retcode=result.retcode, mt5_comment=result.comment,
                )
            return result.success

        if action.type == "buy_limit":
            result = await mt5_client.place_limit_order(
                symbol=symbol, order_type=OrderType.BUY_LIMIT,
                price=action.price if action.price is not None else tick.ask,
                volume=action.volume if action.volume is not None else 0.01,
                sl=action.sl if action.sl is not None else 0.0,
                magic=magic, comment=comment,
            )
            if result.success and result.ticket:
                plan.order_tickets.add(result.ticket)
            elif not result.success:
                logger.warning(
                    "rule_engine.order_rejected",
                    action=action.type, symbol=symbol, plan_id=plan.plan_id,
                    retcode=result.retcode, mt5_comment=result.comment,
                )
            return result.success

        if action.type == "sell_limit":
            result = await mt5_client.place_limit_order(
                symbol=symbol, order_type=OrderType.SELL_LIMIT,
                price=action.price if action.price is not None else tick.bid,
                volume=action.volume if action.volume is not None else 0.01,
                sl=action.sl if action.sl is not None else 0.0,
                magic=magic, comment=comment,
            )
            if result.success and result.ticket:
                plan.order_tickets.add(result.ticket)
            elif not result.success:
                logger.warning(
                    "rule_engine.order_rejected",
                    action=action.type, symbol=symbol, plan_id=plan.plan_id,
                    retcode=result.retcode, mt5_comment=result.comment,
                )
            return result.success

        if action.type == "buy_stop":
            result = await mt5_client.place_limit_order(
                symbol=symbol, order_type=OrderType.BUY_STOP,
                price=action.price if action.price is not None else tick.ask,
                volume=action.volume if action.volume is not None else 0.01,
                sl=action.sl if action.sl is not None else 0.0,
                magic=magic, comment=comment,
            )
            if result.success and result.ticket:
                plan.order_tickets.add(result.ticket)
            return result.success

        if action.type == "sell_stop":
            result = await mt5_client.place_limit_order(
                symbol=symbol, order_type=OrderType.SELL_STOP,
                price=action.price if action.price is not None else tick.bid,
                volume=action.volume if action.volume is not None else 0.01,
                sl=action.sl if action.sl is not None else 0.0,
                magic=magic, comment=comment,
            )
            if result.success and result.ticket:
                plan.order_tickets.add(result.ticket)
            return result.success

        if action.type == "partial_close":
            positions = await mt5_client.get_positions(symbol)
            our = [p for p in positions if p.magic == magic]
            if not our:
                logger.warning("rule_engine.no_positions_to_close", plan_id=plan.plan_id)
                return True  # Not a failure, just nothing to close
            vol_remaining = action.volume or our[0].volume
            for pos in our:
                if vol_remaining <= 0:
                    break
                close_vol = min(vol_remaining, pos.volume)
                if close_vol >= pos.volume:
                    result = await mt5_client.close_position(pos.ticket)
                else:
                    result = await mt5_client.partial_close(pos.ticket, symbol, close_vol)
                if result.success:
                    vol_remaining -= close_vol
                else:
                    return False
            return True

        if action.type == "close_all":
            positions = await mt5_client.get_positions(symbol)
            our = [p for p in positions if p.magic == magic]
            for pos in our:
                result = await mt5_client.close_position(pos.ticket)
                if not result.success:
                    logger.error("rule_engine.close_failed", ticket=pos.ticket)
            plan.position_tickets.clear()
            return True

        if action.type == "modify_sl":
            if action.sl is None:
                logger.warning("rule_engine.modify_sl_no_value", plan_id=plan.plan_id)
                return True
            positions = await mt5_client.get_positions(symbol)
            our = [p for p in positions if p.magic == magic]
            for pos in our:
                await mt5_client.modify_position_sl(pos.ticket, symbol, action.sl)
            return True

        if action.type == "cancel_orders":
            orders = await mt5_client.get_orders(symbol)
            for order in orders:
                if order.ticket in plan.order_tickets:
                    await mt5_client.cancel_order(order.ticket)
            plan.order_tickets.clear()
            return True

        logger.warning("rule_engine.unknown_action", action=action.type)
        return False

    def _apply_transitions(self, plan: TradePlan, rule: Rule) -> None:
        """Activate/deactivate rules per on_fill config."""
        for ref in rule.on_fill.activate:
            target = plan.rules.get(ref)
            if target and not target.executed:
                target.active = True
        for ref in rule.on_fill.deactivate:
            target = plan.rules.get(ref)
            if target:
                target.active = False

    def _is_plan_complete(self, plan: TradePlan) -> bool:
        """A plan is complete when no rules are active and unexecuted."""
        return not any(r.active and not r.executed for r in plan.rules.values())

    async def _publish_rule_event(self, plan: TradePlan, rule: Rule) -> None:
        await event_bus.publish(Event(
            type=EventType.RULE_TRIGGERED,
            data={
                "plan_id": plan.plan_id,
                "rule_id": rule.id,
                "symbol": plan.symbol,
                "actions": [a.type for a in rule.actions],
            },
            source="rule_engine",
        ))

    # --- State persistence ---

    async def save_state(self, plan_id: str) -> None:
        """Persist rule states and ticket sets to Redis."""
        plan = self._plans.get(plan_id)
        if plan is None:
            return

        r = await get_redis()
        prefix = f"ats:plans:{plan_id}"

        # Rule states
        state_map = {}
        for rule_id, rule in plan.rules.items():
            if rule.executed:
                state_map[rule_id] = "executed"
            elif rule.active:
                state_map[rule_id] = "active"
            else:
                state_map[rule_id] = "inactive"

        pipe = r.pipeline()
        pipe.delete(f"{prefix}:rule_states")
        if state_map:
            pipe.hset(f"{prefix}:rule_states", mapping=state_map)

        pipe.delete(f"{prefix}:positions")
        if plan.position_tickets:
            pipe.sadd(f"{prefix}:positions", *[str(t) for t in plan.position_tickets])

        pipe.delete(f"{prefix}:orders")
        if plan.order_tickets:
            pipe.sadd(f"{prefix}:orders", *[str(t) for t in plan.order_tickets])

        await pipe.execute()

    async def _restore_state(self) -> None:
        """Load persisted rule states from Redis. Falls back to YAML defaults."""
        r = await get_redis()

        for plan_id, plan in self._plans.items():
            prefix = f"ats:plans:{plan_id}"

            states = await r.hgetall(f"{prefix}:rule_states")
            if states:
                for rule_id, state in states.items():
                    rule = plan.rules.get(rule_id)
                    if rule is None:
                        continue
                    if state == "executed":
                        rule.active = False
                        rule.executed = True
                    elif state == "active":
                        rule.active = True
                        rule.executed = False
                    else:  # inactive
                        rule.active = False
                        rule.executed = False

            pos_tickets = await r.smembers(f"{prefix}:positions")
            if pos_tickets:
                plan.position_tickets = {int(t) for t in pos_tickets}

            ord_tickets = await r.smembers(f"{prefix}:orders")
            if ord_tickets:
                plan.order_tickets = {int(t) for t in ord_tickets}

    async def _reconcile_tickets(self) -> None:
        """Verify tracked tickets still exist in MT5. Remove stale ones."""
        if not mt5_client.connected:
            return

        for plan in self._plans.values():
            # Reconcile positions
            if plan.position_tickets:
                positions = await mt5_client.get_positions(plan.symbol)
                live_tickets = {p.ticket for p in positions}
                stale = plan.position_tickets - live_tickets
                if stale:
                    logger.info(
                        "rule_engine.stale_positions_removed",
                        plan_id=plan.plan_id, tickets=list(stale),
                    )
                    plan.position_tickets -= stale

            # Reconcile orders
            if plan.order_tickets:
                orders = await mt5_client.get_orders(plan.symbol)
                live_orders = {o.ticket for o in orders}
                stale = plan.order_tickets - live_orders
                if stale:
                    logger.info(
                        "rule_engine.stale_orders_removed",
                        plan_id=plan.plan_id, tickets=list(stale),
                    )
                    plan.order_tickets -= stale

    async def save_all_state(self) -> None:
        """Save state for all plans."""
        for plan_id in self._plans:
            await self.save_state(plan_id)

    async def reset_plan(self, plan_id: str) -> bool:
        """Reset all rule states to YAML defaults."""
        raw = config_loader.get("trade_plans")
        plans_cfg = raw.get("trade_plans", {})
        plan_cfg = plans_cfg.get(plan_id)
        if plan_cfg is None:
            return False

        plan = self._parse_plan(plan_id, plan_cfg)
        if plan is None:
            return False

        self._plans[plan_id] = plan

        # Clear fail counts and cycle state for this plan
        stale_keys = [k for k in self._fail_counts if k[0] == plan_id]
        for k in stale_keys:
            del self._fail_counts[k]
        stale_cycle = [k for k in self._cycle_failed if k[0] == plan_id]
        for k in stale_cycle:
            self._cycle_failed.discard(k)

        # Clear Redis state
        r = await get_redis()
        prefix = f"ats:plans:{plan_id}"
        await r.delete(f"{prefix}:rule_states", f"{prefix}:positions", f"{prefix}:orders")

        logger.info("rule_engine.plan_reset", plan_id=plan_id)
        return True

    def get_plan_state(self, plan_id: str) -> dict | None:
        """Get current state of a plan for API response."""
        plan = self._plans.get(plan_id)
        if plan is None:
            return None

        return {
            "plan_id": plan.plan_id,
            "enabled": plan.enabled,
            "symbol": plan.symbol,
            "magic": plan.magic,
            "rules": {
                rule_id: {
                    "active": rule.active,
                    "executed": rule.executed,
                    "conditions": [
                        {"field": c.field, "op": c.op, "value": c.value}
                        for c in rule.conditions
                    ],
                    "actions": [
                        {"type": a.type, "volume": a.volume, "price": a.price,
                         "sl": a.sl, "tp": a.tp, "comment": a.comment}
                        for a in rule.actions
                    ],
                    "on_fill": {
                        "activate": rule.on_fill.activate,
                        "deactivate": rule.on_fill.deactivate,
                    },
                }
                for rule_id, rule in plan.rules.items()
            },
            "position_tickets": list(plan.position_tickets),
            "order_tickets": list(plan.order_tickets),
        }

    def list_plans(self) -> list[dict]:
        """List all plans with summary state for API response."""
        result = []
        for plan_id, plan in self._plans.items():
            rule_states = {}
            for rule_id, rule in plan.rules.items():
                if rule.executed:
                    rule_states[rule_id] = "executed"
                elif rule.active:
                    rule_states[rule_id] = "active"
                else:
                    rule_states[rule_id] = "inactive"

            result.append({
                "plan_id": plan.plan_id,
                "enabled": plan.enabled,
                "symbol": plan.symbol,
                "magic": plan.magic,
                "rule_states": rule_states,
                "position_count": len(plan.position_tickets),
                "order_count": len(plan.order_tickets),
            })
        return result

    def set_plan_enabled(self, plan_id: str, enabled: bool) -> bool:
        """Enable or disable a plan."""
        plan = self._plans.get(plan_id)
        if plan is None:
            return False
        plan.enabled = enabled
        logger.info("rule_engine.plan_toggled", plan_id=plan_id, enabled=enabled)
        return True

    async def cancel_plan(self, plan_id: str) -> bool:
        """Disable plan, close its positions, cancel its orders."""
        plan = self._plans.get(plan_id)
        if plan is None:
            return False

        plan.enabled = False

        # Close positions
        if plan.position_tickets:
            positions = await mt5_client.get_positions(plan.symbol)
            for pos in positions:
                if pos.magic == plan.magic:
                    await mt5_client.close_position(pos.ticket)
            plan.position_tickets.clear()

        # Cancel orders
        if plan.order_tickets:
            orders = await mt5_client.get_orders(plan.symbol)
            for order in orders:
                if order.ticket in plan.order_tickets:
                    await mt5_client.cancel_order(order.ticket)
            plan.order_tickets.clear()

        await self.save_state(plan_id)
        logger.info("rule_engine.plan_cancelled", plan_id=plan_id)
        return True


# Global instance
rule_engine = RuleEngine()
