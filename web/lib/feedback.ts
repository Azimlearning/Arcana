/** Feedback API client — FR-ANL-03, R-03. */

const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
).replace(/\/$/, '');

export async function postRating(payload: {
  sessionId: string;
  blockId: string;
  rating: 'up' | 'down';
  blockType: string;
}): Promise<void> {
  await fetch(`${API_BASE}/feedback/rating`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function postSurvey(payload: {
  sessionId: string;
  responses: number[];
  taskDescription: string;
}): Promise<{ susScore: number }> {
  const res = await fetch(`${API_BASE}/feedback/sus`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return res.json();
}
