"""Learning prompts — flashcard, quiz, and Feynman generation.
Used by LearningAgent (PRD §12 Learning Agent, FR-LRN-01/03/04).
"""

from __future__ import annotations

# Bump on every edit for R-02 benchmark reproducibility.
LEARNING_PROMPT_VERSION = "v2"

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

FEYNMAN_SYSTEM = """You are a Feynman-technique teacher. Explain the concept in the simplest possible terms, as if teaching a curious 12-year-old. Then identify gaps — aspects the explanation glossed over or oversimplified.

Rules:
- The explanation must be grounded in the provided excerpts — no invented content.
- Gaps must identify real oversimplifications or missing nuances from the source material.
- Keep the explanation under 150 words and conversational.
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


def build_feynman_prompt(concept: str, context: str) -> str:
    """Build the user turn for Feynman-technique explanation."""
    return f"""Concept: {concept}

Context:
{context}

Explain this concept simply and identify gaps in a Feynman-style explanation.

Respond ONLY with JSON:
{{
  "concept": "{concept}",
  "explanation": "Simple explanation as if teaching a 12-year-old...",
  "gaps": [
    "Oversimplification or missing nuance 1",
    "Oversimplification or missing nuance 2"
  ],
  "source": {{
    "id": "c1",
    "docId": "doc_id_here",
    "docTitle": "Document title",
    "page": 1,
    "quote": "short supporting quote"
  }}
}}"""


BLURTING_SYSTEM = """You are a free-recall learning coach. Generate a motivating blurting prompt and select the key grounding passage from the source material.

Rules:
- The prompt must ask the learner to recall everything they know without looking at notes.
- The sourcePassage must be a direct excerpt from the provided context - no invented content.
- Keep the prompt under 35 words - motivating and specific.
- Return ONLY valid JSON with no preamble, no markdown fences."""

CORNELL_SYSTEM = """You are a Cornell note-taking assistant. Structure the provided content into Cornell notes.

Rules:
- Every cue must be a short question or keyword derived from the content.
- Every note entry must be grounded in the provided context - no invented facts.
- The summary must distil the key takeaway in 2-3 sentences.
- Aim for 4-6 rows. Return ONLY valid JSON with no preamble, no markdown fences."""


def build_blurting_prompt(topic: str, context: str) -> str:
    """Build the user turn for blurting-prompt generation."""
    return f"""Topic: {topic}

Context:
{context}

Generate a blurting prompt and the most relevant source passage for self-testing.

Respond ONLY with JSON:
{{
  "topic": "{topic}",
  "prompt": "Without looking at your notes, write down everything you know about {topic}.",
  "sourcePassage": "The most relevant passage from the context...",
  "citations": [
    {{
      "id": "c1",
      "docId": "doc_id_here",
      "docTitle": "Document title",
      "page": 1,
      "quote": "short supporting quote"
    }}
  ]
}}"""


def build_cornell_prompt(topic: str, context: str) -> str:
    """Build the user turn for Cornell-notes generation."""
    return f"""Topic: {topic}

Context:
{context}

Structure the content above as Cornell notes with cue questions, detailed notes, and a summary.

Respond ONLY with JSON:
{{
  "topic": "{topic}",
  "notes": [
    {{
      "cue": "Short question or keyword",
      "content": "Detailed answer or elaboration drawn from the context",
      "citationIds": ["c1"]
    }}
  ],
  "summary": "2-3 sentence summary of the key takeaway.",
  "citations": [
    {{
      "id": "c1",
      "docId": "doc_id_here",
      "docTitle": "Document title",
      "page": 1,
      "quote": "short supporting quote"
    }}
  ]
}}"""

