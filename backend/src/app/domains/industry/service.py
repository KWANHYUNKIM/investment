"""Business logic for the industry domain.

Pure delegation to the same ``app.data`` modules the legacy endpoints called
(``app.data.intel.industry``, ``app.data.intel.industry_research`` and the
background ``industry_scheduler``) — behavior is intentionally identical.
The "unknown industry" case is signalled by returning ``None`` (the router
turns it into the same 404 the legacy handler raised). No store access, so
there is no repository dependency (see ``repository.py``). Never depends on
FastAPI.
"""
from __future__ import annotations

from app.data.intel import industry, industry_research
from app.data.schedulers import industry_scheduler


class IndustryService:
    def industries(self, full: bool) -> dict:
        if full:
            return {"industries": industry.industries()}
        return {
            "industries": industry.industry_names(),
            "scheduler": industry_scheduler.status(),
        }

    def industry_detail(self, name: str) -> dict | None:
        grp = industry.get_industry(name)
        if grp is None:
            return None
        research = industry_research.research_industry(name)
        return {"group": grp, "research": research}

    def scheduler_status(self) -> dict:
        return industry_scheduler.status()

    def refresh(self, snapshot: bool) -> dict:
        n = industry.refresh_profiles()
        out: dict = {"profiles": n}
        if snapshot:
            out["snapshot"] = industry_research.snapshot(force=True)
        return out
