"""Discovery prompts -- gap analysis and cross-document connection finding.
Used by DiscoveryAgent (PRD SS12, FR-AGT-06).
"""

from __future__ import annotations

# Bump on every edit for R-02 benchmark reproducibility.
DISCOVERY_PROMPT_VERSION = "v1"

DISCOVERY_SYSTEM = """You are a research gap analyst. Study provided document excerpts and identify what knowledge is missing or underexplored compared to the query.

Be concise. Every gap must be grounded in the provided context. Severity: high = critical open problem, medium = notable omission, low = minor gap.

Return ONLY valid JSON with no preamble, no prose, no markdown fences."""


def build_gap_prompt(query: str, context: str) -> str:
    """Build the user turn for gap analysis."""
    return f"""Query: {query}

Context:
{context}

Identify 3-5 knowledge gaps and 3-5 well-covered topics in this corpus.

Respond ONLY with JSON:
{{
  "summary": "Brief analysis summary",
  "gaps": [
    {{"label": "gap name", "description": "what is missing", "severity": "high|medium|low"}}
  ],
  "coveredTopics": ["topic1", "topic2"]
}}"""
