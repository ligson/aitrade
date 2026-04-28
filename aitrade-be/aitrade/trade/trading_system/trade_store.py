from typing import Any, Dict, List, Optional, Protocol, Sequence



class TradeStore(Protocol):
    database_url: str
    backend: str

    def close(self) -> None: ...

    def insert_trade_record(self, record: Dict[str, Any]) -> int: ...

    def upsert_position_state(
        self,
        symbol: str,
        position: Dict[str, Any],
        source_trade_id: Optional[int] = None,
    ) -> None: ...

    def delete_position_state(self, symbol: str) -> None: ...

    def get_position_state(self, symbol: str) -> Optional[Dict[str, Any]]: ...

    def query_trade_records(
        self,
        limit: int = 20,
        strategy: Optional[str] = None,
        side: Optional[str] = None,
        result: Optional[str] = None,
        results: Optional[Sequence[str]] = None,
        offset: int = 0,
        symbol: Optional[str] = None,
        run_id: Optional[int] = None,
        created_from: Optional[str] = None,
        created_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]: ...

    def count_trade_records(
        self,
        strategy: Optional[str] = None,
        side: Optional[str] = None,
        result: Optional[str] = None,
        results: Optional[Sequence[str]] = None,
        symbol: Optional[str] = None,
        run_id: Optional[int] = None,
        created_from: Optional[str] = None,
        created_to: Optional[str] = None,
    ) -> int: ...

    def query_position_states(self) -> List[Dict[str, Any]]: ...

    def get_daily_loss_summary(self, run_id: int, created_from: str, created_to: str) -> Dict[str, Any]: ...

    def list_trade_symbols(self) -> List[str]: ...
