#!/usr/bin/env python3
"""
Migration: Create market flow data tables for fund flow analysis

This migration creates three tables for comprehensive market flow data collection:
1. market_trades_aggregated - 15-second aggregated trade data (CVD, Taker Volume)
2. market_orderbook_snapshots - Order book snapshots (Depth Ratio, Liquidity)
3. market_asset_metrics - Asset metrics snapshots (OI, Funding Rate, Premium)

All tables support 30-day data retention with automatic cleanup.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from connection import SessionLocal


def upgrade():
    """Apply the migration - creates all three market flow tables"""
    print("Starting migration: create_market_flow_tables")

    db = SessionLocal()
    try:
        # Table 1: market_trades_aggregated
        print("Creating market_trades_aggregated table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS market_trades_aggregated (
                id SERIAL PRIMARY KEY,
                exchange VARCHAR(20) NOT NULL DEFAULT 'hyperliquid',
                symbol VARCHAR(20) NOT NULL,
                timestamp BIGINT NOT NULL,
                taker_buy_volume DECIMAL(24, 8) NOT NULL DEFAULT 0,
                taker_sell_volume DECIMAL(24, 8) NOT NULL DEFAULT 0,
                taker_buy_count INTEGER NOT NULL DEFAULT 0,
                taker_sell_count INTEGER NOT NULL DEFAULT 0,
                taker_buy_notional DECIMAL(24, 6) NOT NULL DEFAULT 0,
                taker_sell_notional DECIMAL(24, 6) NOT NULL DEFAULT 0,
                vwap DECIMAL(18, 6),
                high_price DECIMAL(18, 6),
                low_price DECIMAL(18, 6),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create unique constraint if not exists
        db.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'market_trades_aggregated_exchange_symbol_timestamp_key'
                ) THEN
                    ALTER TABLE market_trades_aggregated
                    ADD CONSTRAINT market_trades_aggregated_exchange_symbol_timestamp_key
                    UNIQUE (exchange, symbol, timestamp);
                END IF;
            END $$;
        """))

        # Create indexes for market_trades_aggregated
        print("Creating indexes for market_trades_aggregated...")
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_mta_exchange ON market_trades_aggregated(exchange)
        """))
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_mta_symbol ON market_trades_aggregated(symbol)
        """))
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_mta_timestamp ON market_trades_aggregated(timestamp)
        """))
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_mta_exchange_symbol_timestamp
            ON market_trades_aggregated(exchange, symbol, timestamp)
        """))

        # Table 2: market_orderbook_snapshots
        print("Creating market_orderbook_snapshots table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS market_orderbook_snapshots (
                id SERIAL PRIMARY KEY,
                exchange VARCHAR(20) NOT NULL DEFAULT 'hyperliquid',
                symbol VARCHAR(20) NOT NULL,
                timestamp BIGINT NOT NULL,
                best_bid DECIMAL(18, 6),
                best_ask DECIMAL(18, 6),
                spread DECIMAL(18, 6),
                bid_depth_5 DECIMAL(24, 8) NOT NULL DEFAULT 0,
                ask_depth_5 DECIMAL(24, 8) NOT NULL DEFAULT 0,
                bid_depth_10 DECIMAL(24, 8) NOT NULL DEFAULT 0,
                ask_depth_10 DECIMAL(24, 8) NOT NULL DEFAULT 0,
                bid_orders_count INTEGER NOT NULL DEFAULT 0,
                ask_orders_count INTEGER NOT NULL DEFAULT 0,
                raw_levels JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create unique constraint if not exists
        db.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'market_orderbook_snapshots_exchange_symbol_timestamp_key'
                ) THEN
                    ALTER TABLE market_orderbook_snapshots
                    ADD CONSTRAINT market_orderbook_snapshots_exchange_symbol_timestamp_key
                    UNIQUE (exchange, symbol, timestamp);
                END IF;
            END $$;
        """))

        # Create indexes for market_orderbook_snapshots
        print("Creating indexes for market_orderbook_snapshots...")
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_mos_exchange ON market_orderbook_snapshots(exchange)
        """))
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_mos_symbol ON market_orderbook_snapshots(symbol)
        """))
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_mos_timestamp ON market_orderbook_snapshots(timestamp)
        """))
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_mos_exchange_symbol_timestamp
            ON market_orderbook_snapshots(exchange, symbol, timestamp)
        """))

        # Table 3: market_asset_metrics
        print("Creating market_asset_metrics table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS market_asset_metrics (
                id SERIAL PRIMARY KEY,
                exchange VARCHAR(20) NOT NULL DEFAULT 'hyperliquid',
                symbol VARCHAR(20) NOT NULL,
                timestamp BIGINT NOT NULL,
                open_interest DECIMAL(24, 8),
                funding_rate DECIMAL(18, 8),
                mark_price DECIMAL(18, 6),
                oracle_price DECIMAL(18, 6),
                mid_price DECIMAL(18, 6),
                premium DECIMAL(18, 8),
                day_notional_volume DECIMAL(24, 6),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create unique constraint if not exists
        db.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'market_asset_metrics_exchange_symbol_timestamp_key'
                ) THEN
                    ALTER TABLE market_asset_metrics
                    ADD CONSTRAINT market_asset_metrics_exchange_symbol_timestamp_key
                    UNIQUE (exchange, symbol, timestamp);
                END IF;
            END $$;
        """))

        # Create indexes for market_asset_metrics
        print("Creating indexes for market_asset_metrics...")
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_mam_exchange ON market_asset_metrics(exchange)
        """))
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_mam_symbol ON market_asset_metrics(symbol)
        """))
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_mam_timestamp ON market_asset_metrics(timestamp)
        """))
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_mam_exchange_symbol_timestamp
            ON market_asset_metrics(exchange, symbol, timestamp)
        """))

        db.commit()
        print("Migration completed successfully!")
        print("Created tables: market_trades_aggregated, market_orderbook_snapshots, market_asset_metrics")

    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        db.close()


def downgrade():
    """Rollback the migration - drops all three tables"""
    print("Starting rollback: create_market_flow_tables")

    db = SessionLocal()
    try:
        print("Dropping market_trades_aggregated table...")
        db.execute(text("DROP TABLE IF EXISTS market_trades_aggregated CASCADE"))

        print("Dropping market_orderbook_snapshots table...")
        db.execute(text("DROP TABLE IF EXISTS market_orderbook_snapshots CASCADE"))

        print("Dropping market_asset_metrics table...")
        db.execute(text("DROP TABLE IF EXISTS market_asset_metrics CASCADE"))

        db.commit()
        print("Rollback completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Rollback failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Market Flow Tables Migration')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()

    if args.rollback:
        downgrade()
    else:
        upgrade()
