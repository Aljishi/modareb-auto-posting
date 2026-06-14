#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — Central Research Database
يبني قاعدة SQLite مركزية لكل الإشارات والأداء والقطاعات والمحفظة.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_FILE = DATA_DIR / "rased_research.db"
SIGNALS_FILE = DATA_DIR / "signals.json"
VALIDATED_FILE = DATA_DIR / "validated_signals.json"
GOLDEN_FILE = DATA_DIR / "golden_signals.json"
PERFORMANCE_FILE = DATA_DIR / "signal_performance.csv"
PUBLISHED_FILE = DATA_DIR / "published_signals.csv"
SECTOR_ROTATION_FILE = DATA_DIR / "sector_rotation.json"
PORTFOLIO_FILE = DATA_DIR / "portfolio_allocation.json"


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        if isinstance(x, str):
            x = x.replace(",", "").replace("%", "").strip()
        return float(x)
    except Exception:
        return default


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def extract_signals(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("validated_signals") or data.get("golden_signals") or data.get("signals") or []
    return []


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS signals (
            signal_id TEXT PRIMARY KEY,
            generated_at TEXT,
            source TEXT,
            symbol TEXT,
            name TEXT,
            sector TEXT,
            tier TEXT,
            entry REAL,
            target1 REAL,
            target2 REAL,
            stop_loss REAL,
            rr REAL,
            score REAL,
            rased_score REAL,
            risk_level TEXT,
            backtest_win_rate REAL,
            sector_strength_grade TEXT,
            payload TEXT
        );

        CREATE TABLE IF NOT EXISTS performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loaded_at TEXT,
            symbol TEXT,
            signal_id TEXT,
            status TEXT,
            pnl_pct REAL,
            raw TEXT
        );

        CREATE TABLE IF NOT EXISTS sectors (
            sector TEXT PRIMARY KEY,
            generated_at TEXT,
            rotation_score REAL,
            grade TEXT,
            avg_change_pct REAL,
            advancing_ratio REAL,
            total_value REAL,
            signals_count INTEGER,
            raw TEXT
        );

        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at TEXT,
            symbol TEXT,
            name TEXT,
            sector TEXT,
            tier TEXT,
            weight_pct REAL,
            amount_sar REAL,
            entry REAL,
            stop_loss REAL,
            raw TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
        CREATE INDEX IF NOT EXISTS idx_signals_generated_at ON signals(generated_at);
        CREATE INDEX IF NOT EXISTS idx_performance_symbol ON performance(symbol);
        """
    )
    conn.commit()


def upsert_signals(conn: sqlite3.Connection, source: str, signals: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for sig in signals:
        symbol = str(sig.get("symbol") or sig.get("stock_symbol") or "").strip()
        if not symbol:
            continue
        signal_id = str(sig.get("signal_id") or f"{source}-{symbol}-{sig.get('generated_at', '')}")
        conn.execute(
            """
            INSERT OR REPLACE INTO signals
            (signal_id, generated_at, source, symbol, name, sector, tier, entry, target1, target2, stop_loss, rr, score, rased_score, risk_level, backtest_win_rate, sector_strength_grade, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_id,
                str(sig.get("generated_at") or ""),
                source,
                symbol,
                str(sig.get("name") or sig.get("stock_name") or symbol),
                str(sig.get("sector") or ""),
                str(sig.get("tier") or ""),
                fnum(sig.get("entry") or sig.get("entry_point")),
                fnum(sig.get("target1")),
                fnum(sig.get("target2")),
                fnum(sig.get("stop_loss")),
                fnum(sig.get("rr") or sig.get("rr_ratio")),
                fnum(sig.get("score")),
                fnum(sig.get("rased_score") or sig.get("score")),
                str(sig.get("risk_level") or sig.get("risk_level_ar") or ""),
                fnum(sig.get("backtest_win_rate")),
                str(sig.get("sector_strength_grade") or ""),
                json.dumps(sig, ensure_ascii=False),
            ),
        )
        count += 1
    conn.commit()
    return count


def load_performance(conn: sqlite3.Connection) -> int:
    rows = read_csv(PERFORMANCE_FILE)
    conn.execute("DELETE FROM performance")
    loaded_at = datetime.now().isoformat(timespec="seconds")
    for row in rows:
        conn.execute(
            "INSERT INTO performance (loaded_at, symbol, signal_id, status, pnl_pct, raw) VALUES (?, ?, ?, ?, ?, ?)",
            (
                loaded_at,
                str(row.get("symbol") or row.get("stock_symbol") or ""),
                str(row.get("signal_id") or ""),
                str(row.get("status") or row.get("outcome") or row.get("result") or ""),
                fnum(row.get("pnl_pct") or row.get("return_pct") or row.get("performance_pct")),
                json.dumps(row, ensure_ascii=False),
            ),
        )
    conn.commit()
    return len(rows)


def load_sectors(conn: sqlite3.Connection) -> int:
    data = load_json(SECTOR_ROTATION_FILE, {})
    sectors = data.get("all_sectors", []) if isinstance(data, dict) else []
    generated_at = str(data.get("generated_at") or datetime.now().isoformat(timespec="seconds"))
    for item in sectors:
        conn.execute(
            """
            INSERT OR REPLACE INTO sectors
            (sector, generated_at, rotation_score, grade, avg_change_pct, advancing_ratio, total_value, signals_count, raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(item.get("sector") or ""),
                generated_at,
                fnum(item.get("rotation_score")),
                str(item.get("grade") or ""),
                fnum(item.get("avg_change_pct")),
                fnum(item.get("advancing_ratio")),
                fnum(item.get("total_value")),
                int(fnum(item.get("signals_count"), 0)),
                json.dumps(item, ensure_ascii=False),
            ),
        )
    conn.commit()
    return len(sectors)


def load_portfolio(conn: sqlite3.Connection) -> int:
    data = load_json(PORTFOLIO_FILE, {})
    positions = data.get("positions", []) if isinstance(data, dict) else []
    generated_at = str(data.get("generated_at") or datetime.now().isoformat(timespec="seconds"))
    conn.execute("DELETE FROM portfolio")
    for p in positions:
        conn.execute(
            """
            INSERT INTO portfolio
            (generated_at, symbol, name, sector, tier, weight_pct, amount_sar, entry, stop_loss, raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generated_at,
                str(p.get("symbol") or ""),
                str(p.get("name") or ""),
                str(p.get("sector") or ""),
                str(p.get("tier") or ""),
                fnum(p.get("weight_pct")),
                fnum(p.get("amount_sar")),
                fnum(p.get("entry")),
                fnum(p.get("stop_loss")),
                json.dumps(p, ensure_ascii=False),
            ),
        )
    conn.commit()
    return len(positions)


def build_database() -> Dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    try:
        init_db(conn)
        counts = {
            "signals": upsert_signals(conn, "signals", extract_signals(load_json(SIGNALS_FILE, {}))),
            "validated_signals": upsert_signals(conn, "validated_signals", extract_signals(load_json(VALIDATED_FILE, {}))),
            "golden_signals": upsert_signals(conn, "golden_signals", extract_signals(load_json(GOLDEN_FILE, {}))),
            "performance": load_performance(conn),
            "sectors": load_sectors(conn),
            "portfolio": load_portfolio(conn),
        }
    finally:
        conn.close()
    meta = {"generated_at": datetime.now().isoformat(timespec="seconds"), "database": str(DB_FILE), "counts": counts}
    (DATA_DIR / "rased_database_summary.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def main() -> int:
    meta = build_database()
    print(f"✅ Central database updated: {meta['database']}")
    print(f"📊 {meta['counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
