"""业务异常与稳定错误码：前端 / 日志 / 告警统一识别。"""

from __future__ import annotations


class FlareError(Exception):
    """业务异常基类。"""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(FlareError):
    code = "NOT_FOUND"
    status_code = 404


class ValidationError(FlareError):
    code = "VALIDATION_ERROR"
    status_code = 422


class RateLimitError(FlareError):
    code = "RATE_LIMITED"
    status_code = 429
