"""Trading API routes - order management and trade plans."""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.mt5.client import mt5_client
from app.mt5.models import TradeRequest
from app.strategy.rule_engine import rule_engine

router = APIRouter(prefix="/trading", tags=["trading"])


class OrderRequest(BaseModel):
    symbol: str
    side: str
    volume: float
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    comment: str = ""


@router.get("/positions")
async def get_positions(symbol: str | None = None):
    """Get open positions."""
    positions = await mt5_client.get_positions(symbol)
    return {
        "positions": [
            {
                "ticket": p.ticket,
                "time": p.time.isoformat(),
                "type": p.type,
                "volume": p.volume,
                "price_open": p.price_open,
                "sl": p.sl,
                "tp": p.tp,
                "price_current": p.price_current,
                "profit": p.profit,
                "symbol": p.symbol,
                "comment": p.comment,
            }
            for p in positions
        ]
    }


@router.get("/orders")
async def get_orders(symbol: str | None = None):
    """Get pending orders."""
    orders = await mt5_client.get_orders(symbol)
    return {
        "orders": [
            {
                "ticket": o.ticket,
                "type": o.type,
                "volume_current": o.volume_current,
                "price_open": o.price_open,
                "sl": o.sl,
                "tp": o.tp,
                "symbol": o.symbol,
                "comment": o.comment,
            }
            for o in orders
        ]
    }


@router.post("/order")
async def place_order(req: OrderRequest):
    """Place a market order."""
    result = await mt5_client.place_order(TradeRequest(
        symbol=req.symbol,
        side=req.side,
        volume=req.volume,
        price=req.price,
        stop_loss=req.stop_loss,
        take_profit=req.take_profit,
        comment=req.comment or "ATS-Manual",
    ))
    return {
        "success": result.success,
        "ticket": result.ticket,
        "retcode": result.retcode,
        "comment": result.comment,
    }


@router.delete("/position/{ticket}")
async def close_position(ticket: int):
    """Close a position by ticket."""
    result = await mt5_client.close_position(ticket)
    return {
        "success": result.success,
        "ticket": result.ticket,
        "comment": result.comment,
    }


@router.get("/history")
async def get_trade_history(days: int = Query(default=7, le=90)):
    """Get closed deal history from MT5, paired into round-trip trades."""
    if not mt5_client.connected:
        return {"trades": [], "connected": False}

    now = datetime.now(timezone.utc)
    # Use a wide range from epoch to avoid RPyC timezone issues
    since = datetime(2020, 1, 1, tzinfo=timezone.utc)
    far_future = datetime(2030, 1, 1, tzinfo=timezone.utc)

    try:
        async with mt5_client._lock:
            deals = await asyncio.to_thread(
                mt5_client._mt5.history_deals_get, since, far_future
            )
    except Exception:
        return {"trades": [], "error": "Failed to fetch history"}

    if deals is None or len(deals) == 0:
        return {"trades": [], "connected": True}

    # Filter to the requested time range
    cutoff = now.timestamp() - (days * 86400)

    # Pair entry deals (entry=0) with their close deals (entry=1)
    entries: dict[int, dict] = {}  # order -> deal info
    trades = []

    for d in deals:
        if d.type == 2:  # balance/deposit/withdrawal
            continue
        if d.time < cutoff:
            continue

        deal = {
            "ticket": int(d.ticket),
            "order": int(d.order),
            "time": datetime.fromtimestamp(d.time, tz=timezone.utc).isoformat(),
            "time_ts": int(d.time),
            "type": int(d.type),  # 0=buy, 1=sell
            "entry": int(d.entry),  # 0=in, 1=out
            "volume": float(d.volume),
            "price": float(d.price),
            "profit": float(d.profit),
            "symbol": str(d.symbol),
            "magic": int(d.magic),
            "comment": str(d.comment),
        }

        if deal["entry"] == 0:
            # Opening deal - store by order number (used in "Close #<order>" comments)
            entries[deal["order"]] = deal
        elif deal["entry"] == 1:
            # Closing deal - find matching entry via "Close #<order>" comment
            entry_order = None
            cmt = deal["comment"]
            if "Close #" in cmt:
                try:
                    entry_order = int(cmt.split("#")[1].split()[0])
                except (ValueError, IndexError):
                    pass

            entry = entries.pop(entry_order, None) if entry_order else None

            trades.append({
                "close_time": deal["time"],
                "close_time_ts": deal["time_ts"],
                "symbol": deal["symbol"],
                "side": "BUY" if deal["type"] == 1 else "SELL",  # close type is opposite
                "volume": deal["volume"],
                "entry_price": entry["price"] if entry else None,
                "exit_price": deal["price"],
                "pnl": deal["profit"],
                "magic": deal["magic"] or (entry["magic"] if entry else 0),
                "comment": entry["comment"] if entry else deal["comment"],
                "entry_time": entry["time"] if entry else None,
                "duration_s": (deal["time_ts"] - entry["time_ts"]) if entry else None,
            })

    # Also add any orphaned entries (opened but not yet closed) as info
    # ... skip for now, those show in positions

    # Sort newest first
    trades.sort(key=lambda t: t["close_time_ts"], reverse=True)

    return {"trades": trades, "connected": True}


# --- Trade Plan endpoints ---

@router.get("/plans")
async def list_trade_plans():
    """List all trade plans with current state."""
    return {"plans": rule_engine.list_plans()}


@router.get("/plans/{plan_id}")
async def get_trade_plan(plan_id: str):
    """Get a single trade plan with full detail and rule states."""
    state = rule_engine.get_plan_state(plan_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    return state


@router.post("/plans/{plan_id}/activate")
async def activate_plan(plan_id: str):
    """Enable a trade plan."""
    if not rule_engine.set_plan_enabled(plan_id, True):
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    return {"success": True, "plan_id": plan_id, "enabled": True}


@router.post("/plans/{plan_id}/deactivate")
async def deactivate_plan(plan_id: str):
    """Disable a trade plan (stops evaluating rules but does not close positions)."""
    if not rule_engine.set_plan_enabled(plan_id, False):
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    return {"success": True, "plan_id": plan_id, "enabled": False}


@router.post("/plans/{plan_id}/cancel")
async def cancel_plan(plan_id: str):
    """Disable plan + close all its positions + cancel its pending orders."""
    if not await rule_engine.cancel_plan(plan_id):
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    return {"success": True, "plan_id": plan_id, "cancelled": True}


@router.post("/plans/{plan_id}/reset")
async def reset_plan(plan_id: str):
    """Reset all rule states to YAML defaults."""
    if not await rule_engine.reset_plan(plan_id):
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    return {"success": True, "plan_id": plan_id, "reset": True}


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str):
    """Delete a trade plan from config and runtime."""
    from app.config.loader import config_loader
    from app.data.redis_client import get_redis

    # Cancel first (close positions, cancel orders)
    await rule_engine.cancel_plan(plan_id)

    # Remove from runtime
    rule_engine._plans.pop(plan_id, None)

    # Remove from config YAML
    raw = config_loader.get("trade_plans")
    plans_cfg = raw.get("trade_plans", {})
    if plan_id not in plans_cfg:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found in config")
    del plans_cfg[plan_id]
    config_loader.update("trade_plans", raw, changed_by="api_delete")

    # Clear Redis state
    r = await get_redis()
    prefix = f"ats:plans:{plan_id}"
    await r.delete(f"{prefix}:rule_states", f"{prefix}:positions", f"{prefix}:orders")

    return {"success": True, "plan_id": plan_id, "deleted": True}
