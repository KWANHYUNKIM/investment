"""Minimal, idempotent logging setup.

Called once at app startup. Kept deliberately light — a single stream handler on
the ``app`` logger — so it configures structured-ish output without fighting
uvicorn's own handlers or duplicating lines on reload.
"""
from __future__ import annotations

import logging

_CONFIGURED = False


def setup(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logger = logging.getLogger("app")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    logger.propagate = False
    _CONFIGURED = True
