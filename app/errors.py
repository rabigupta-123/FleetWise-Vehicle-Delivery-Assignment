import logging
import os
import secrets
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("fleetwise")


class AppError(Exception):
    """Domain error with standardized status_code, error code, and human-readable message."""

    def __init__(self, status_code: int, error: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or f"req_{secrets.token_hex(6)}"
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error, "message": exc.message, "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or f"req_{secrets.token_hex(6)}"
        parts = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", []) if x != "body")
            msg = err.get("msg", "Invalid value")
            parts.append(f"{loc}: {msg}" if loc else msg)
        message = "; ".join(parts) if parts else "Request validation failed."
        return JSONResponse(
            status_code=400,
            content={"error": "VALIDATION_ERROR", "message": message, "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or f"req_{secrets.token_hex(6)}"
        code_map = {
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            409: "CONFLICT",
            415: "UNSUPPORTED_MEDIA_TYPE",
            429: "TOO_MANY_REQUESTS",
            500: "internal_error",
        }
        err_code = code_map.get(exc.status_code, "HTTP_ERROR")
        detail_msg = exc.detail if exc.detail else "An HTTP error occurred."
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": err_code, "message": detail_msg, "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or f"req_{secrets.token_hex(6)}"
        tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        logger.error("Unhandled Exception [request_id=%s]: %s\n%s", request_id, exc, tb_str)
        print(f"[ERROR] Unhandled Exception [{request_id}]: {exc}\n{tb_str}", flush=True)

        is_debug = os.environ.get("APP_DEBUG", "").lower() in ("1", "true", "yes")
        content: dict[str, str] = {
            "error": "internal_error",
            "message": "An unexpected error occurred.",
            "request_id": request_id,
        }
        if is_debug:
            content["detail"] = str(exc)

        return JSONResponse(
            status_code=500,
            content=content,
            headers={"X-Request-ID": request_id},
        )

