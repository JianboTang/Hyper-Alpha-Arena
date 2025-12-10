"""
Signal Detection Service

Detects signal triggers based on market flow data.
Uses edge-triggered logic: only triggers when condition changes from False to True.
"""

import logging
import time
from typing import Dict, List, Optional, Any
from decimal import Decimal
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SignalState:
    """Track the active state of a signal for edge detection"""
    signal_id: int
    symbol: str
    is_active: bool = False
    last_value: Optional[float] = None
    last_check_time: float = 0


class SignalDetectionService:
    """
    Service for detecting signal triggers based on market flow data.
    Implements edge-triggered logic to avoid repeated triggers.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Signal states for edge detection: {(signal_id, symbol): SignalState}
        self.signal_states: Dict[tuple, SignalState] = {}

        # Cache of enabled signal pools and their signals
        self._signal_pools_cache: List[dict] = []
        self._signals_cache: Dict[int, dict] = {}
        self._cache_time: float = 0
        self._cache_ttl: float = 60  # Refresh cache every 60 seconds

        logger.info("SignalDetectionService initialized")

    def detect_signals(self, symbol: str, market_data: Dict[str, Any]) -> List[dict]:
        """
        Detect triggered signals for a symbol based on current market data.
        Returns list of triggered signals (edge-triggered).
        """
        triggered_signals = []

        try:
            # Refresh cache if needed
            self._refresh_cache_if_needed()

            # Get all enabled signal pools that monitor this symbol
            relevant_pools = [
                pool for pool in self._signal_pools_cache
                if pool.get("enabled") and symbol in pool.get("symbols", [])
            ]

            if not relevant_pools:
                return []

            # Get all signal IDs from relevant pools
            signal_ids = set()
            for pool in relevant_pools:
                signal_ids.update(pool.get("signal_ids", []))

            # Check each signal
            for signal_id in signal_ids:
                signal_def = self._signals_cache.get(signal_id)
                if not signal_def or not signal_def.get("enabled"):
                    continue

                trigger_result = self._check_signal_trigger(
                    signal_id, signal_def, symbol, market_data
                )
                if trigger_result:
                    triggered_signals.append(trigger_result)

        except Exception as e:
            logger.error(f"Error detecting signals for {symbol}: {e}", exc_info=True)

        return triggered_signals

    def _refresh_cache_if_needed(self):
        """Refresh signal pools and signals cache if TTL expired"""
        now = time.time()
        if now - self._cache_time < self._cache_ttl:
            return

        try:
            from database.connection import SessionLocal
            from sqlalchemy import text
            db = SessionLocal()
            try:
                # Load enabled signal pools
                result = db.execute(
                    text("SELECT id, pool_name, signal_ids, symbols, enabled FROM signal_pools WHERE enabled = true")
                )
                self._signal_pools_cache = [
                    {
                        "id": row[0],
                        "pool_name": row[1],
                        "signal_ids": row[2] or [],
                        "symbols": row[3] or [],
                        "enabled": row[4]
                    }
                    for row in result.fetchall()
                ]

                # Load all enabled signals
                result = db.execute(
                    text("SELECT id, signal_name, description, trigger_condition, enabled FROM signal_definitions WHERE enabled = true")
                )
                self._signals_cache = {
                    row[0]: {
                        "id": row[0],
                        "signal_name": row[1],
                        "description": row[2],
                        "trigger_condition": row[3],
                        "enabled": row[4]
                    }
                    for row in result.fetchall()
                }

                self._cache_time = now
                logger.debug(f"Signal cache refreshed: {len(self._signal_pools_cache)} pools, {len(self._signals_cache)} signals")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to refresh signal cache: {e}")

    def _check_signal_trigger(
        self, signal_id: int, signal_def: dict, symbol: str, market_data: Dict[str, Any]
    ) -> Optional[dict]:
        """
        Check if a signal should trigger based on current market data.
        Implements edge-triggered logic.
        """
        condition = signal_def.get("trigger_condition", {})
        metric = condition.get("metric")
        operator = condition.get("operator")
        threshold = condition.get("threshold")
        time_window = condition.get("time_window", 60)  # Default 60 seconds

        if not all([metric, operator, threshold is not None]):
            return None

        # Get current metric value
        current_value = self._get_metric_value(metric, symbol, market_data, time_window)
        if current_value is None:
            return None

        # Check condition
        condition_met = self._evaluate_condition(current_value, operator, threshold)

        # Get or create signal state
        state_key = (signal_id, symbol)
        if state_key not in self.signal_states:
            self.signal_states[state_key] = SignalState(
                signal_id=signal_id, symbol=symbol
            )
        state = self.signal_states[state_key]

        # Edge detection: only trigger when condition changes from False to True
        should_trigger = condition_met and not state.is_active

        # Update state
        state.is_active = condition_met
        state.last_value = current_value
        state.last_check_time = time.time()

        if should_trigger:
            trigger_result = {
                "signal_id": signal_id,
                "signal_name": signal_def.get("signal_name"),
                "symbol": symbol,
                "trigger_value": current_value,
                "threshold": threshold,
                "operator": operator,
                "metric": metric,
                "trigger_time": time.time(),
                "description": signal_def.get("description"),
            }
            self._log_trigger(trigger_result)
            return trigger_result

        return None

    def _get_metric_value(
        self, metric: str, symbol: str, market_data: Dict[str, Any], time_window: int
    ) -> Optional[float]:
        """
        Get the current value of a metric from market data or indicators.

        Uses get_indicator_value() from market_flow_indicators for DB-based metrics.
        This ensures proper separation of concerns - signal detection doesn't depend
        on prompt-specific data structures.
        """
        try:
            # Direct metrics from market_data (no DB query needed)
            if metric == "oi":
                return self._get_oi(symbol, market_data)
            elif metric == "funding_rate":
                return self._get_funding_rate(symbol, market_data)

            # Metrics that need DB query via market_flow_indicators
            from database.connection import SessionLocal
            from services.market_flow_indicators import get_indicator_value

            # Convert time_window to period string
            period = self._time_window_to_period(time_window)

            # Map signal metric names to indicator types
            indicator_map = {
                "oi_delta_percent": "OI_DELTA",
                "cvd": "CVD",
                "depth_ratio": "DEPTH",
                "order_imbalance": "IMBALANCE",
                "taker_buy_ratio": "TAKER",
            }

            if metric not in indicator_map:
                logger.warning(f"Unknown metric: {metric}")
                return None

            indicator_type = indicator_map[metric]

            db = SessionLocal()
            try:
                return get_indicator_value(db, symbol, indicator_type, period)
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error getting metric {metric} for {symbol}: {e}")
            return None

    def _time_window_to_period(self, time_window: int) -> str:
        """Convert time window (seconds or string) to period string"""
        if isinstance(time_window, str):
            return time_window
        # time_window in seconds
        if time_window <= 60:
            return "1m"
        elif time_window <= 180:
            return "3m"
        elif time_window <= 300:
            return "5m"
        elif time_window <= 900:
            return "15m"
        elif time_window <= 1800:
            return "30m"
        elif time_window <= 3600:
            return "1h"
        elif time_window <= 7200:
            return "2h"
        else:
            return "4h"

    def _get_oi(self, symbol: str, market_data: Dict[str, Any]) -> Optional[float]:
        """Get open interest from market data"""
        asset_ctx = market_data.get("asset_ctx", {})
        oi = asset_ctx.get("openInterest")
        return float(oi) if oi else None

    def _get_funding_rate(self, symbol: str, market_data: Dict[str, Any]) -> Optional[float]:
        """Get funding rate from market data"""
        asset_ctx = market_data.get("asset_ctx", {})
        funding = asset_ctx.get("funding")
        return float(funding) if funding else None

    def _evaluate_condition(self, value: float, operator: str, threshold: float) -> bool:
        """Evaluate if a condition is met"""
        if operator == ">":
            return value > threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<":
            return value < threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return abs(value - threshold) < 1e-9
        elif operator == "!=":
            return abs(value - threshold) >= 1e-9
        elif operator == "abs_greater_than" or operator == "abs_gt":
            return abs(value) > threshold
        elif operator == "abs_less_than" or operator == "abs_lt":
            return abs(value) < threshold
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False

    def _log_trigger(self, trigger_result: dict):
        """Log signal trigger to database"""
        try:
            from database.connection import SessionLocal
            from sqlalchemy import text

            db = SessionLocal()
            try:
                db.execute(
                    text("""
                        INSERT INTO signal_trigger_logs
                        (signal_id, symbol, trigger_value, threshold, triggered_at)
                        VALUES (:signal_id, :symbol, :trigger_value, :threshold, NOW())
                    """),
                    {
                        "signal_id": trigger_result["signal_id"],
                        "symbol": trigger_result["symbol"],
                        "trigger_value": trigger_result["trigger_value"],
                        "threshold": trigger_result["threshold"],
                    }
                )
                db.commit()
                logger.info(
                    f"Signal triggered: {trigger_result['signal_name']} on {trigger_result['symbol']} "
                    f"(value={trigger_result['trigger_value']:.4f}, threshold={trigger_result['threshold']})"
                )
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to log signal trigger: {e}")

    def get_signal_states(self) -> Dict[str, Any]:
        """Get current signal states for debugging/monitoring"""
        return {
            f"{state.signal_id}:{state.symbol}": {
                "is_active": state.is_active,
                "last_value": state.last_value,
                "last_check_time": state.last_check_time,
            }
            for state_key, state in self.signal_states.items()
        }

    def reset_state(self, signal_id: int = None, symbol: str = None):
        """Reset signal states (useful for testing)"""
        if signal_id is None and symbol is None:
            self.signal_states.clear()
        else:
            keys_to_remove = [
                k for k in self.signal_states.keys()
                if (signal_id is None or k[0] == signal_id) and
                   (symbol is None or k[1] == symbol)
            ]
            for k in keys_to_remove:
                del self.signal_states[k]


# Singleton instance
signal_detection_service = SignalDetectionService()
