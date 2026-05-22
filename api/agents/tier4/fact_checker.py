"""Fact Checker - Tier 4. FR-AGT-09.

Verifies that each citation in a Research payload actually supports the
claim it's attached to. Asks the LLM, per citation, "does this quote
support its claim in the summary?" - returns a verdict per id.

The Fact Checker is intentionally NON-MUTATING: it produces a verdict
in its own `agent_results["fact_checker"]` entry and the UI Agent
applies the filter when building the final block. This keeps the graph's
reducer model honest (only one node ever writes to a given
`agent_results` key) and makes the verdict auditable post-hoc.

Fail-safe on LLM outage: if the verification call raises, all citations
are treated as supported (innocent until proven guilty) so a transient
provider hiccup doesn't quietly delete legitimate work. The slice
benchmark (FR-AGT-09 ≥90%) will pin a stricter policy once measured.
"""

from __future__ import annotations

import json
import re
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.llm.service import LLMService
from api.llm.types import Message

logger = get_logger(__name__)

# R-02 reproducibility: bump on every prompt edit so benchmark results
# can be partitioned by prompt version. FR-AGT-09 (>=90% citation
# accuracy) is staked on this prompt's behaviour.
FACT_CHECK_PROMPT_VERSION = "v1"

_FACT_CHECK_SYSTEM = """You are a strict but fair fact-checker for an academic
research assistant. For each citation, decide whether the supplied quote
SUPPORTS the corresponding claim from the summary.

A quote SUPPORTS a claim if it contains explicit evidence for the claim.
Mere topical overlap does NOT count as support; the quote must speak to
the specific assertion.

Respond with ONLY a valid JSON array, one object per citation:
[{"id": "c1", "supported": true}, {"id": "c2", "supported": false}, ...]

No prose, no markdown fences. First character `[`, last character `]`.
"""


class FactChecker(BaseAgent):
    name = "fact_checker"
    tier = 4

    def __init__(self, *, llm: LLMService) -> None:
        self._llm = llm

    async def run(self, query: str, state: AgentState) -> AgentResult:
        research = state.agent_results.get("research")
        if research is None or research.status == "failed":
            # Nothing to verify - emit a no-op verdict so downstream
            # consumers see we ran.
            return AgentResult(
                agent_name=self.name,
                payload={"checked": 0, "verified": 0, "dropped_ids": []},
                status="ok",
            )

        citations = research.payload.get("citations", []) or []
        if not citations:
            return AgentResult(
                agent_name=self.name,
                payload={"checked": 0, "verified": 0, "dropped_ids": []},
                status="ok",
            )

        verdicts = await self._verify(
            summary=research.payload.get("summary", ""),
            citations=citations,
        )

        verified = sum(1 for ok in verdicts.values() if ok)
        dropped_ids = [
            c["id"] for c in citations if not verdicts.get(c["id"], True)
        ]

        logger.info(
            "fact_checker.done",
            checked=len(citations),
            verified=verified,
            dropped=len(dropped_ids),
        )

        return AgentResult(
            agent_name=self.name,
            payload={
                "checked": len(citations),
                "verified": verified,
                "dropped_ids": dropped_ids,
            },
            status="ok",
        )

    async def _verify(
        self,
        *,
        summary: str,
        citations: list[dict[str, Any]],
    ) -> dict[str, bool]:
        """One LLM call covering all citations. Returns id -> supported.

        Fail-safe: any failure (network, malformed JSON, missing id) maps
        unknown citations to `True` so the slice doesn't silently shed
        legitimate citations from a transient outage."""
        lines = [f"SUMMARY:\n{summary.strip()}\n", "CITATIONS:"]
        for c in citations:
            cid = str(c.get("id", ""))
            quote = str(c.get("quote", ""))[:280]
            lines.append(f"  [{cid}] {quote}")
        user_prompt = "\n".join(lines)

        try:
            completion = await self._llm.complete(
                messages=[Message(role="user", content=user_prompt)],
                system=_FACT_CHECK_SYSTEM,
                max_tokens=512,
            )
        except Exception as e:
            logger.warning(
                "fact_checker.llm_failed",
                error=str(e),
                citation_count=len(citations),
            )
            return {str(c.get("id", "")): True for c in citations}

        verdicts = _parse_verdicts(completion.text)
        # Default unknown ids to supported (don't drop legitimate work).
        return {str(c.get("id", "")): verdicts.get(str(c.get("id", "")), True)
                for c in citations}


def _parse_verdicts(raw: str) -> dict[str, bool]:
    """Defensive parse of the LLM's verdict array. Returns empty dict on
    any parse failure (which the caller treats as "everything supported")."""
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    first = s.find("[")
    last = s.rfind("]")
    if first == -1 or last == -1 or last <= first:
        logger.warning("fact_checker.unparseable_verdict", raw=raw[:200])
        return {}
    try:
        parsed = json.loads(s[first : last + 1])
    except json.JSONDecodeError:
        logger.warning("fact_checker.malformed_json", raw=raw[:200])
        return {}
    if not isinstance(parsed, list):
        return {}
    out: dict[str, bool] = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        cid = item.get("id")
        supported = item.get("supported")
        if isinstance(cid, str) and isinstance(supported, bool):
            out[cid] = supported
    return out
