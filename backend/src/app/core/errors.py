"""Application error types + FastAPI exception handlers.

Domains raise semantic errors (``NotFoundError`` …) instead of importing
``fastapi.HTTPException`` into the service/repository layers. ``install()`` maps
them to HTTP responses at the edge, so business code stays framework-agnostic.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("app")


class AppError(Exception):
    """Base for expected, client-facing errors. ``status`` drives the response."""

    status: int = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(AppError):
    status = 404


class BadRequestError(AppError):
    status = 400


class UpstreamError(AppError):
    """A dependency we don't control (data source, external API) was unreachable."""

    status = 503


def install(app: FastAPI) -> None:
    """Register handlers that turn ``AppError``s into clean JSON responses."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail})
