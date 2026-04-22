from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any


@dataclass
class ApiPayload:
    success: bool
    message: str
    trace: str
    httpCode: int
    data: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'trace': self.trace,
            'httpCode': self.httpCode,
            'data': self.data,
        }


def success_response(data: Any = None, message: str = '', http_code: int = HTTPStatus.OK) -> dict[str, Any]:
    return ApiPayload(True, message, '', int(http_code), {} if data is None else data).to_dict()


def page_response(total: int, size: int, offset: int, rows: list[Any], message: str = '') -> dict[str, Any]:
    return success_response(
        data={
            'total': total,
            'size': size,
            'offset': offset,
            'data': rows,
        },
        message=message,
    )
