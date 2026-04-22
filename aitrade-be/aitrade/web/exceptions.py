from __future__ import annotations

from http import HTTPStatus
from typing import Optional


class ApiError(Exception):
    def __init__(self, message: str, http_code: int = HTTPStatus.BAD_REQUEST, trace: str = ''):
        super().__init__(message)
        self.message = message
        self.http_code = int(http_code)
        self.trace = trace


class UnauthorizedError(ApiError):
    def __init__(self, message: str = '未授权'):
        super().__init__(message, HTTPStatus.UNAUTHORIZED)


class ForbiddenError(ApiError):
    def __init__(self, message: str = '无权限访问'):
        super().__init__(message, HTTPStatus.FORBIDDEN)


class NotFoundError(ApiError):
    def __init__(self, message: str = '资源不存在'):
        super().__init__(message, HTTPStatus.NOT_FOUND)


class ValidationError(ApiError):
    def __init__(self, message: str = '请求参数不合法', trace: Optional[str] = None):
        super().__init__(message, HTTPStatus.BAD_REQUEST, trace or '')
