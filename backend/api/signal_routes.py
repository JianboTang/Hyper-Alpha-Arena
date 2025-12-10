"""Signal system API routes"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.connection import SessionLocal
from schemas.signal import (
    SignalDefinitionCreate,
    SignalDefinitionUpdate,
    SignalDefinitionResponse,
    SignalPoolCreate,
    SignalPoolUpdate,
    SignalPoolResponse,
    SignalListResponse,
    SignalTriggerLogResponse,
    SignalTriggerLogsResponse,
)

router = APIRouter(prefix="/api/signals", tags=["Signal System"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============ Signal Definitions ============

@router.get("", response_model=SignalListResponse)
@router.get("/", response_model=SignalListResponse)
def list_signals(db: Session = Depends(get_db)) -> SignalListResponse:
    """List all signal definitions and pools"""
    signals_result = db.execute(text("""
        SELECT id, signal_name, description, trigger_condition, enabled, created_at, updated_at
        FROM signal_definitions ORDER BY id
    """))
    signals = []
    for row in signals_result:
        signals.append(SignalDefinitionResponse(
            id=row[0], signal_name=row[1], description=row[2],
            trigger_condition=row[3], enabled=row[4],
            created_at=row[5], updated_at=row[6]
        ))

    pools_result = db.execute(text("""
        SELECT id, pool_name, signal_ids, symbols, enabled, created_at
        FROM signal_pools ORDER BY id
    """))
    pools = []
    for row in pools_result:
        pools.append(SignalPoolResponse(
            id=row[0], pool_name=row[1], signal_ids=row[2] or [],
            symbols=row[3] or [], enabled=row[4], created_at=row[5]
        ))

    return SignalListResponse(signals=signals, pools=pools)


@router.post("/definitions", response_model=SignalDefinitionResponse)
def create_signal(payload: SignalDefinitionCreate, db: Session = Depends(get_db)):
    """Create a new signal definition"""
    import json
    result = db.execute(text("""
        INSERT INTO signal_definitions (signal_name, description, trigger_condition, enabled)
        VALUES (:name, :desc, :condition, :enabled)
        RETURNING id, signal_name, description, trigger_condition, enabled, created_at, updated_at
    """), {
        "name": payload.signal_name,
        "desc": payload.description,
        "condition": json.dumps(payload.trigger_condition),
        "enabled": payload.enabled
    })
    db.commit()
    row = result.fetchone()
    return SignalDefinitionResponse(
        id=row[0], signal_name=row[1], description=row[2],
        trigger_condition=row[3], enabled=row[4],
        created_at=row[5], updated_at=row[6]
    )


@router.get("/definitions/{signal_id}", response_model=SignalDefinitionResponse)
def get_signal(signal_id: int, db: Session = Depends(get_db)):
    """Get a signal definition by ID"""
    result = db.execute(text("""
        SELECT id, signal_name, description, trigger_condition, enabled, created_at, updated_at
        FROM signal_definitions WHERE id = :id
    """), {"id": signal_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")
    return SignalDefinitionResponse(
        id=row[0], signal_name=row[1], description=row[2],
        trigger_condition=row[3], enabled=row[4],
        created_at=row[5], updated_at=row[6]
    )


@router.put("/definitions/{signal_id}", response_model=SignalDefinitionResponse)
def update_signal(signal_id: int, payload: SignalDefinitionUpdate, db: Session = Depends(get_db)):
    """Update a signal definition"""
    import json
    # Build dynamic update query
    updates = []
    params = {"id": signal_id}
    if payload.signal_name is not None:
        updates.append("signal_name = :name")
        params["name"] = payload.signal_name
    if payload.description is not None:
        updates.append("description = :desc")
        params["desc"] = payload.description
    if payload.trigger_condition is not None:
        updates.append("trigger_condition = :condition")
        params["condition"] = json.dumps(payload.trigger_condition)
    if payload.enabled is not None:
        updates.append("enabled = :enabled")
        params["enabled"] = payload.enabled

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = CURRENT_TIMESTAMP")
    query = f"UPDATE signal_definitions SET {', '.join(updates)} WHERE id = :id RETURNING *"
    result = db.execute(text(query), params)
    db.commit()
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")
    return SignalDefinitionResponse(
        id=row[0], signal_name=row[1], description=row[2],
        trigger_condition=row[3], enabled=row[4],
        created_at=row[5], updated_at=row[6]
    )


@router.delete("/definitions/{signal_id}")
def delete_signal(signal_id: int, db: Session = Depends(get_db)):
    """Delete a signal definition"""
    result = db.execute(text("DELETE FROM signal_definitions WHERE id = :id"), {"id": signal_id})
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Signal not found")
    return {"message": "Signal deleted successfully"}


# ============ Signal Pools ============

@router.post("/pools", response_model=SignalPoolResponse)
def create_pool(payload: SignalPoolCreate, db: Session = Depends(get_db)):
    """Create a new signal pool"""
    import json
    result = db.execute(text("""
        INSERT INTO signal_pools (pool_name, signal_ids, symbols, enabled)
        VALUES (:name, :signal_ids, :symbols, :enabled)
        RETURNING id, pool_name, signal_ids, symbols, enabled, created_at
    """), {
        "name": payload.pool_name,
        "signal_ids": json.dumps(payload.signal_ids),
        "symbols": json.dumps(payload.symbols),
        "enabled": payload.enabled
    })
    db.commit()
    row = result.fetchone()
    return SignalPoolResponse(
        id=row[0], pool_name=row[1], signal_ids=row[2] or [],
        symbols=row[3] or [], enabled=row[4], created_at=row[5]
    )


@router.get("/pools/{pool_id}", response_model=SignalPoolResponse)
def get_pool(pool_id: int, db: Session = Depends(get_db)):
    """Get a signal pool by ID"""
    result = db.execute(text("""
        SELECT id, pool_name, signal_ids, symbols, enabled, created_at
        FROM signal_pools WHERE id = :id
    """), {"id": pool_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Pool not found")
    return SignalPoolResponse(
        id=row[0], pool_name=row[1], signal_ids=row[2] or [],
        symbols=row[3] or [], enabled=row[4], created_at=row[5]
    )


@router.put("/pools/{pool_id}", response_model=SignalPoolResponse)
def update_pool(pool_id: int, payload: SignalPoolUpdate, db: Session = Depends(get_db)):
    """Update a signal pool"""
    import json
    updates = []
    params = {"id": pool_id}
    if payload.pool_name is not None:
        updates.append("pool_name = :name")
        params["name"] = payload.pool_name
    if payload.signal_ids is not None:
        updates.append("signal_ids = :signal_ids")
        params["signal_ids"] = json.dumps(payload.signal_ids)
    if payload.symbols is not None:
        updates.append("symbols = :symbols")
        params["symbols"] = json.dumps(payload.symbols)
    if payload.enabled is not None:
        updates.append("enabled = :enabled")
        params["enabled"] = payload.enabled

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    query = f"UPDATE signal_pools SET {', '.join(updates)} WHERE id = :id RETURNING *"
    result = db.execute(text(query), params)
    db.commit()
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Pool not found")
    return SignalPoolResponse(
        id=row[0], pool_name=row[1], signal_ids=row[2] or [],
        symbols=row[3] or [], enabled=row[4], created_at=row[5]
    )


@router.delete("/pools/{pool_id}")
def delete_pool(pool_id: int, db: Session = Depends(get_db)):
    """Delete a signal pool"""
    result = db.execute(text("DELETE FROM signal_pools WHERE id = :id"), {"id": pool_id})
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Pool not found")
    return {"message": "Pool deleted successfully"}


# ============ Trigger Logs ============

@router.get("/logs", response_model=SignalTriggerLogsResponse)
def get_trigger_logs(
    pool_id: Optional[int] = Query(None),
    signal_id: Optional[int] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db)
):
    """Get signal trigger logs with optional filters"""
    conditions = []
    params = {"limit": limit}

    if pool_id is not None:
        conditions.append("pool_id = :pool_id")
        params["pool_id"] = pool_id
    if signal_id is not None:
        conditions.append("signal_id = :signal_id")
        params["signal_id"] = signal_id
    if symbol is not None:
        conditions.append("symbol = :symbol")
        params["symbol"] = symbol

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT id, signal_id, pool_id, symbol, trigger_value, triggered_at
        FROM signal_trigger_logs {where_clause}
        ORDER BY triggered_at DESC LIMIT :limit
    """
    result = db.execute(text(query), params)
    logs = []
    for row in result:
        logs.append(SignalTriggerLogResponse(
            id=row[0], signal_id=row[1], pool_id=row[2],
            symbol=row[3], trigger_value=row[4], triggered_at=row[5]
        ))

    # Get total count
    count_query = f"SELECT COUNT(*) FROM signal_trigger_logs {where_clause}"
    count_params = {k: v for k, v in params.items() if k != "limit"}
    total = db.execute(text(count_query), count_params).scalar()

    return SignalTriggerLogsResponse(logs=logs, total=total)


# ============ Signal Testing & Monitoring ============

@router.get("/test/{signal_id}")
def test_signal(
    signal_id: int,
    symbol: str = Query(..., description="Symbol to test against"),
    db: Session = Depends(get_db)
):
    """
    Test a signal against current market data.
    Returns the current metric value and whether the condition is met.
    """
    from services.signal_detection_service import signal_detection_service
    from services.market_flow_collector import market_flow_collector

    # Get signal definition
    result = db.execute(text("""
        SELECT id, signal_name, description, trigger_condition, enabled
        FROM signal_definitions WHERE id = :id
    """), {"id": signal_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")

    signal_def = {
        "id": row[0],
        "signal_name": row[1],
        "description": row[2],
        "trigger_condition": row[3],
        "enabled": row[4]
    }

    # Get current market data from collector
    market_data = {
        "asset_ctx": market_flow_collector.latest_asset_ctx.get(symbol, {}),
        "orderbook": market_flow_collector.latest_orderbook.get(symbol, {}),
    }

    condition = signal_def.get("trigger_condition", {})
    metric = condition.get("metric")
    operator = condition.get("operator")
    threshold = condition.get("threshold")
    time_window = condition.get("time_window", 60)

    # Get current metric value
    current_value = signal_detection_service._get_metric_value(
        metric, symbol, market_data, time_window
    )

    # Evaluate condition
    condition_met = False
    if current_value is not None:
        condition_met = signal_detection_service._evaluate_condition(
            current_value, operator, threshold
        )

    # Get signal state
    state_key = (signal_id, symbol)
    state = signal_detection_service.signal_states.get(state_key)

    return {
        "signal_id": signal_id,
        "signal_name": signal_def["signal_name"],
        "symbol": symbol,
        "metric": metric,
        "operator": operator,
        "threshold": threshold,
        "time_window": time_window,
        "current_value": current_value,
        "condition_met": condition_met,
        "is_active": state.is_active if state else False,
        "would_trigger": condition_met and (not state or not state.is_active),
        "market_data_available": bool(market_data.get("asset_ctx")),
    }


@router.get("/states")
def get_signal_states():
    """Get current signal states for monitoring"""
    from services.signal_detection_service import signal_detection_service
    return {
        "states": signal_detection_service.get_signal_states(),
        "cache_info": {
            "pools_count": len(signal_detection_service._signal_pools_cache),
            "signals_count": len(signal_detection_service._signals_cache),
        }
    }


@router.post("/states/reset")
def reset_signal_states(
    signal_id: Optional[int] = Query(None),
    symbol: Optional[str] = Query(None)
):
    """Reset signal states (useful for testing)"""
    from services.signal_detection_service import signal_detection_service
    signal_detection_service.reset_state(signal_id, symbol)
    return {"message": "Signal states reset successfully"}
