"""Status domain — background scheduler / crawler progress endpoints.

Layered: router (transport) → service (logic). Pure delegation to the
``app.data`` crawler/scheduler singletons — no store access, so no repository.
Part of the strangler-fig migration of ``app/api/data``.
"""
from .router import router

__all__ = ["router"]
