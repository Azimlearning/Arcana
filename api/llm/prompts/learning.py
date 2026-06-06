"""Learning prompts — flashcard and quiz generation.
Used by LearningAgent (PRD §12 Learning Agent, FR-LRN-01/03).
"""

from __future__ import annotations

# Bump on every edit for R-02 benchmark reproducibility.
LEARNING_PROMPT_VERSION = "v1"

FLASHCARD_SYSTEM = """You are a study-material generator. Create active-recall flashcards grounded in the provided document excerpts.

Rules:
- Every card must trace directly to a provided passage — no invented facts.
- Front: a concise question or prompt that tests recall.
- Back: the minimal correct answer drawn from the source.
- Aim for atomic cards: one concept per card.
- Return ONLY valid JSON with no preamble, no markdown fences."""

QUIZ_SYSTEM = """You are a quiz generator. Create grounded quiz questions from the provided document excerpts.

Rules:
- Questions must trace to a provided passage — no invented facts.
- For MCQ: exactly 4 options (A-D), one correct answer.
- Bloom level mapping: recall=remember, comprehension=understand, application=apply, analysis=analyse.
- Return ONLY valid JSON with no preamble, no markdown fences."""


def build_flashcard_prompt(topic: str, context: str, n: int = 5) -> str:
    """Build the user turn for flashcard generation."""
    return f"""Topic: {topic}

Context:
{context}

Generate {n} atomic flashcards for this topic using only the provided context.

Respond ONLY with JSON:
{{
  "topic": "{topic}",
  "cards": [
    {{
      "front": "Question or prompt",
      "back": "Minimal correct answer",
      "source": {{
        "id": "c1",
        "docId": "doc_id_here",
        "docTitle": "Document title",
        "page": 1,
        "quote": "short supporting quote"
      }}
    }}
  ]
}}"""


def build_quiz_prompt(topic: str, context: str, difficulty: str = "comprehension") -> str:
    """Build the user turn for a single quiz question."""
    return f"""Topic: {topic}
Difficulty (Bloom level): {difficulty}

Context:
{context}

Generate ONE quiz question at the specified Bloom level using only the provided context.
For MCQ provide exactly 4 options. For short_answer leave options empty and correctIndex null.

Respond ONLY with JSON:
{{
  "question": "The question text",
  "questionType": "mcq",
  "options": [
    {{"index": 0, "text": "Option A"}},
    {{"index": 1, "text": "Option B"}},
    {{"index": 2, "text": "Option C"}},
    {{"index": 3, "text": "Option D"}}
  ],
  "correctIndex": 0,
  "explanation": "Why the answer is correct, citing the source.",
  "difficulty": "{difficulty}",
  "source": {{
    "id": "c1",
    "docId": "doc_id_here",
    "docTitle": "Document title",
    "page": 1,
    "quote": "short supporting quote"
  }}
}}"""
