"""WebSearchAgent — Tier 4. Academic paper discovery (FR-AGT, §12).

Scope is deliberately narrow (PRD §12 non-goal: NOT general web search):
given a query it returns a ranked list of *scholarly* papers — title,
link, year — via the free Semantic Scholar Graph API (arXiv ids surfaced
where present), shaped as a SourceList block so the user can pull
promising sources into their corpus.

Network is isolated behind `_search_semantic_scholar` so the agent is
unit-testable without hitting the live API, and a fetch failure degrades
to an empty, `partial`-status result rather than crashing the turn.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger

logger = get_logger(__name__)

_SS_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_SS_FIELDS = "title,url,year,authors,externalIds"
_REQUEST_TIMEOUT = 15.0
_DEFAULT_LIMIT = 8
_MAX_LIMIT = 20


class WebSearchAgent(BaseAgent):
    """Tier-4 academic discovery agent. Emits a SourceList of papers."""

    name = "web_search"
    tier = 4

    def __init__(self, *, limit: int = _DEFAULT_LIMIT) -> None:
        self._limit = limit

    async def run(self, query: str, state: AgentState) -> AgentResult:
        try:
            papers = await _search_semantic_scholar(query, limit=self._limit)
        except Exception as exc:  # degrade, never crash the turn (NFR-REL-01)
            logger.warning("web_search.failed", error=str(exc), query=query[:80])
            papers = []

        documents = [_paper_to_source_document(p) for p in papers]
        return AgentResult(
            agent_name=self.name,
            payload={
                "block_type": "SourceList",
                "data": {
                    "notebookId": state.notebook_id or "",
                    "documents": documents,
                    "totalCount": len(documents),
                },
            },
            status="ok" if documents else "partial",
            error=None if documents else "No academic results found for this query.",
        )


# ---- Network seam (monkeypatched in tests) ----------------------------------


async def _search_semantic_scholar(query: str, *, limit: int) -> list[dict]:
    """Query the Semantic Scholar Graph API. Returns the raw `data` list."""
    params = {
        "query": query,
        "limit": max(1, min(limit, _MAX_LIMIT)),
        "fields": _SS_FIELDS,
    }
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        resp = await client.get(_SS_SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    return list(data.get("data", []))


def _paper_to_source_document(paper: dict) -> dict:
    """Map a Semantic Scholar paper record to a SourceDocument payload dict."""
    ext = paper.get("externalIds") or {}
    arxiv = ext.get("ArXiv")
    paper_id = paper.get("paperId") or (f"arxiv_{arxiv}" if arxiv else "unknown")
    url = paper.get("url") or (f"https://arxiv.org/abs/{arxiv}" if arxiv else "")
    return {
        "docId": f"ss_{paper_id}",
        "title": str(paper.get("title") or "Untitled")[:300],
        "sourceUri": url,
        # External discovery results aren't ingested; mark ready so the
        # SourceList renderer shows them as actionable links.
        "status": "ready",
        "sizeBytes": 0,
        "chunkCount": 0,
        "createdAt": datetime.now(UTC).isoformat(),
        "error": None,
    }
