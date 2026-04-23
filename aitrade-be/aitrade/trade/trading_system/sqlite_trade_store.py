import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class SQLiteTradeStore:
    """SQLite 交易持久化存储。"""

    def __init__(self, db_path: str):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._initialize()

    def close(self) -> None:
        self.conn.close()

    def insert_trade_record(self, record: Dict[str, Any]) -> int:
        payload = {
            'created_at': record.get('created_at') or self._utc_now(),
            'symbol': record.get('symbol'),
            'strategy': record.get('strategy', 'unknown'),
            'trigger_source': record.get('trigger_source', 'strategy_signal'),
            'side': record.get('side', 'unknown'),
            'signal_confidence': record.get('signal_confidence'),
            'signal_reason': record.get('signal_reason'),
            'market_price': record.get('market_price'),
            'requested_amount': record.get('requested_amount'),
            'stop_loss_price': record.get('stop_loss_price'),
            'trailing_stop_price': record.get('trailing_stop_price'),
            'risk_per_trade': record.get('risk_per_trade'),
            'exchange_type': record.get('exchange_type', 'unknown'),
            'sandbox': 1 if record.get('sandbox') else 0,
            'result': record.get('result', 'unknown'),
            'result_reason': record.get('result_reason'),
            'order_id': record.get('order_id'),
            'order_status': record.get('order_status'),
            'order_type': record.get('order_type'),
            'order_price': record.get('order_price'),
            'order_amount': record.get('order_amount'),
            'order_cost': record.get('order_cost'),
            'error_message': record.get('error_message'),
            'signal_meta_json': self._json_text(record.get('signal_meta')),
            'risk_snapshot_json': self._json_text(record.get('risk_snapshot')),
            'position_before_json': self._json_text(record.get('position_before')),
            'position_after_json': self._json_text(record.get('position_after')),
            'order_raw_json': self._json_text(record.get('order_raw')),
        }
        columns = ', '.join(payload.keys())
        placeholders = ', '.join(f':{key}' for key in payload.keys())
        cursor = self.conn.execute(
            f'INSERT INTO trade_records ({columns}) VALUES ({placeholders})',
            payload,
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def upsert_position_state(self, symbol: str, position: Dict[str, Any], source_trade_id: Optional[int] = None) -> None:
        payload = {
            'symbol': symbol,
            'strategy': position.get('strategy'),
            'entry_time': position.get('entry_time'),
            'entry_price': position.get('entry_price'),
            'amount': position.get('amount'),
            'stop_loss': position.get('stop_loss'),
            'initial_stop_loss': position.get('initial_stop_loss'),
            'trailing_stop_price': position.get('trailing_stop_price'),
            'highest_price': position.get('highest_price'),
            'highest_close': position.get('highest_close'),
            'meta_json': self._json_text(position.get('meta', {})),
            'source_trade_id': source_trade_id,
            'updated_at': self._utc_now(),
        }
        self.conn.execute(
            '''
            INSERT INTO position_state (
                symbol,
                strategy,
                entry_time,
                entry_price,
                amount,
                stop_loss,
                initial_stop_loss,
                trailing_stop_price,
                highest_price,
                highest_close,
                meta_json,
                source_trade_id,
                updated_at
            ) VALUES (
                :symbol,
                :strategy,
                :entry_time,
                :entry_price,
                :amount,
                :stop_loss,
                :initial_stop_loss,
                :trailing_stop_price,
                :highest_price,
                :highest_close,
                :meta_json,
                :source_trade_id,
                :updated_at
            )
            ON CONFLICT(symbol) DO UPDATE SET
                strategy=excluded.strategy,
                entry_time=excluded.entry_time,
                entry_price=excluded.entry_price,
                amount=excluded.amount,
                stop_loss=excluded.stop_loss,
                initial_stop_loss=excluded.initial_stop_loss,
                trailing_stop_price=excluded.trailing_stop_price,
                highest_price=excluded.highest_price,
                highest_close=excluded.highest_close,
                meta_json=excluded.meta_json,
                source_trade_id=excluded.source_trade_id,
                updated_at=excluded.updated_at
            ''',
            payload,
        )
        self.conn.commit()

    def delete_position_state(self, symbol: str) -> None:
        self.conn.execute('DELETE FROM position_state WHERE symbol = ?', (symbol,))
        self.conn.commit()

    def get_position_state(self, symbol: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            'SELECT * FROM position_state WHERE symbol = ?',
            (symbol,),
        ).fetchone()
        if row is None:
            return None
        return {
            'symbol': row['symbol'],
            'strategy': row['strategy'],
            'entry_time': row['entry_time'],
            'entry_price': row['entry_price'],
            'amount': row['amount'],
            'stop_loss': row['stop_loss'],
            'initial_stop_loss': row['initial_stop_loss'],
            'trailing_stop_price': row['trailing_stop_price'],
            'highest_price': row['highest_price'],
            'highest_close': row['highest_close'],
            'meta': self._json_value(row['meta_json'], {}),
            'source_trade_id': row['source_trade_id'],
            'updated_at': row['updated_at'],
        }

    def query_trade_records(self, limit: int = 20, strategy: Optional[str] = None, side: Optional[str] = None, result: Optional[str] = None) -> List[Dict[str, Any]]:
        where = []
        params: List[Any] = []
        if strategy:
            where.append('strategy = ?')
            params.append(strategy)
        if side:
            where.append('side = ?')
            params.append(side)
        if result:
            where.append('result = ?')
            params.append(result)

        sql = 'SELECT * FROM trade_records'
        if where:
            sql += ' WHERE ' + ' AND '.join(where)
        sql += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_trade_record(row) for row in rows]

    def list_trade_symbols(self) -> List[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT symbol FROM trade_records WHERE symbol IS NOT NULL AND symbol != '' ORDER BY symbol ASC"
        ).fetchall()
        return [str(row['symbol']) for row in rows]

    def _initialize(self) -> None:
        self.conn.executescript(
            '''
            CREATE TABLE IF NOT EXISTS trade_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                symbol TEXT NOT NULL,
                strategy TEXT NOT NULL,
                trigger_source TEXT NOT NULL,
                side TEXT NOT NULL,
                signal_confidence REAL,
                signal_reason TEXT,
                market_price REAL,
                requested_amount REAL,
                stop_loss_price REAL,
                trailing_stop_price REAL,
                risk_per_trade REAL,
                exchange_type TEXT NOT NULL,
                sandbox INTEGER NOT NULL,
                result TEXT NOT NULL,
                result_reason TEXT,
                order_id TEXT,
                order_status TEXT,
                order_type TEXT,
                order_price REAL,
                order_amount REAL,
                order_cost REAL,
                error_message TEXT,
                signal_meta_json TEXT,
                risk_snapshot_json TEXT,
                position_before_json TEXT,
                position_after_json TEXT,
                order_raw_json TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_trade_records_created_at ON trade_records(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_trade_records_strategy_created_at ON trade_records(strategy, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_trade_records_symbol_created_at ON trade_records(symbol, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_trade_records_result_created_at ON trade_records(result, created_at DESC);

            CREATE TABLE IF NOT EXISTS position_state (
                symbol TEXT PRIMARY KEY,
                strategy TEXT,
                entry_time TEXT,
                entry_price REAL,
                amount REAL,
                stop_loss REAL,
                initial_stop_loss REAL,
                trailing_stop_price REAL,
                highest_price REAL,
                highest_close REAL,
                meta_json TEXT,
                source_trade_id INTEGER,
                updated_at TEXT NOT NULL
            );
            '''
        )
        self.conn.commit()

    def _row_to_trade_record(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            'id': row['id'],
            'created_at': row['created_at'],
            'symbol': row['symbol'],
            'strategy': row['strategy'],
            'trigger_source': row['trigger_source'],
            'side': row['side'],
            'signal_confidence': row['signal_confidence'],
            'signal_reason': row['signal_reason'],
            'market_price': row['market_price'],
            'requested_amount': row['requested_amount'],
            'stop_loss_price': row['stop_loss_price'],
            'trailing_stop_price': row['trailing_stop_price'],
            'risk_per_trade': row['risk_per_trade'],
            'exchange_type': row['exchange_type'],
            'sandbox': bool(row['sandbox']),
            'result': row['result'],
            'result_reason': row['result_reason'],
            'order_id': row['order_id'],
            'order_status': row['order_status'],
            'order_type': row['order_type'],
            'order_price': row['order_price'],
            'order_amount': row['order_amount'],
            'order_cost': row['order_cost'],
            'error_message': row['error_message'],
            'signal_meta': self._json_value(row['signal_meta_json'], {}),
            'risk_snapshot': self._json_value(row['risk_snapshot_json'], {}),
            'position_before': self._json_value(row['position_before_json']),
            'position_after': self._json_value(row['position_after_json']),
            'order_raw': self._json_value(row['order_raw_json'], {}),
        }

    @staticmethod
    def _json_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _json_value(value: Optional[str], default: Any = None) -> Any:
        if value is None:
            return default
        return json.loads(value)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
