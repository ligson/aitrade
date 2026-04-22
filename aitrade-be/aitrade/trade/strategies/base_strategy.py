from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseStrategy(ABC):
    name = 'base'

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def get_required_history(self) -> int:
        return 0

    @abstractmethod
    def generate_signal(self, market_data: Dict[str, Any], position: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        pass
