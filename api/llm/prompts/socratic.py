"""Socratic prompts — guided questioning that withholds answers.
Used by SocraticAgent (PRD §12 Socratic Tutor, FR-LRN-08).
"""

from __future__ import annotations

# Bump on every edit for R-02 benchmark reproducibility.
SOCRATIC_PROMPT_VERSION = "v1"

SOCRATIC_SYSTEM = """You are a Socratic tutor. Your ONLY job is to ask questions that guide the learner to the answer — you NEVER give the answer directly.

Rules (non-negotiable):
1. nextQuestion MUST be a question, not a statement or explanation.
2. nextQuestion MUST NOT contain the answer or reveal it implicitly.
3. Each question moves the learner one step forward in their reasoning.
4. Target the Bloom level specified in the prompt.
5. If you detect a misconception, ask a question that targets it — do NOT correct it directly.
6. Return ONLY valid JSON with no preamble, no markdown fences."""


def build_socratic_prompt(
    concept: str,
    context: str,
    turns: list[dict[str, str]],
    bloom_level: str = "comprehension",
) -> str:
    """Build the user turn for a Socratic probing question."""
    turn_text = ""
    if turns:
        turn_text = "\n\nConversation so far:\n" + "\n".join(
            f"{t['role'].upper()}: {t['text']}" for t in turns[-6:]  # last 3 exchanges
        )

    return f"""Concept: {concept}
Bloom level target: {bloom_level}

Grounding context:
{context}{turn_text}

Generate the next Socratic probing question. Do NOT give the answer.

Respond ONLY with JSON:
{{
  "nextQuestion": "Your probing question here (must end with '?')",
  "bloomLevel": "{bloom_level}",
  "reasoning": "Why this question moves the learner forward (internal, not shown)"
}}"""
