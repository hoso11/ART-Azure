from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    def __init__(self, detail: str, code: str, status_code: int = 400):
        self.detail = detail
        self.code = code
        self.status_code = status_code


class NotFoundException(AppException):
    def __init__(self, detail: str = "Resource not found", code: str = "not_found"):
        super().__init__(detail=detail, code=code, status_code=404)


class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Not authenticated", code: str = "unauthorized"):
        super().__init__(detail=detail, code=code, status_code=401)


class ForbiddenException(AppException):
    def __init__(self, detail: str = "Access denied", code: str = "forbidden"):
        super().__init__(detail=detail, code=code, status_code=403)


class ConflictException(AppException):
    def __init__(self, detail: str = "Resource already exists", code: str = "conflict"):
        super().__init__(detail=detail, code=code, status_code=409)


class ValidationException(AppException):
    def __init__(self, detail: str = "Validation error", code: str = "validation_error"):
        super().__init__(detail=detail, code=code, status_code=422)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )
