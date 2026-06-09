'use client';

import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { postSurvey } from '@/lib/feedback';

const SUS_QUESTIONS = [
  'I think that I would like to use this system frequently.',
  'I found the system unnecessarily complex.',
  'I thought the system was easy to use.',
  'I think that I would need the support of a technical person to be able to use this system.',
  'I found the various functions in this system were well integrated.',
  'I thought there was too much inconsistency in this system.',
  'I would imagine that most people would learn to use this system very quickly.',
  'I found the system very cumbersome to use.',
  'I felt very confident using the system.',
  'I needed to learn a lot of things before I could get going with this system.',
];

interface Props {
  sessionId: string;
  onDismiss: () => void;
}

export function SUSModal({ sessionId, onDismiss }: Props) {
  const [responses, setResponses] = useState<(number | null)[]>(
    Array(10).fill(null),
  );
  const [submitted, setSubmitted] = useState(false);
  const [susScore, setSusScore] = useState<number | null>(null);

  const allAnswered = responses.every((r) => r !== null);

  function setResponse(idx: number, val: number) {
    setResponses((prev) => {
      const next = [...prev];
      next[idx] = val;
      return next;
    });
  }

  async function submit() {
    if (!allAnswered) return;
    try {
      const result = await postSurvey({
        sessionId,
        responses: responses as number[],
        taskDescription: 'Arcana P1 user study',
      });
      setSusScore(result.susScore);
      setSubmitted(true);
    } catch {
      // on error just dismiss
      onDismiss();
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-card border border-line rounded-ctl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {submitted ? (
            <div className="text-center py-4">
              <p className="font-display text-xl text-ink mb-2">Thank you!</p>
              <p className="text-ink-softer text-sm">
                Your SUS score: <span className="font-mono text-accent">{susScore?.toFixed(1)}</span>
              </p>
              <Button className="mt-4" onClick={onDismiss}>
                Close
              </Button>
            </div>
          ) : (
            <>
              <h2 className="font-display text-lg text-ink mb-1">
                Quick usability survey
              </h2>
              <p className="text-xs text-ink-softer mb-4">
                Rate each statement 1 (Strongly Disagree) → 5 (Strongly Agree)
              </p>

              <div className="space-y-4">
                {SUS_QUESTIONS.map((q, i) => (
                  <div key={i}>
                    <p className="text-sm text-ink mb-1">
                      <span className="text-ink-softer mr-1">{i + 1}.</span>
                      {q}
                    </p>
                    <div className="flex gap-2">
                      {[1, 2, 3, 4, 5].map((val) => (
                        <button
                          key={val}
                          onClick={() => setResponse(i, val)}
                          className={`w-8 h-8 rounded text-sm font-mono transition-colors ${
                            responses[i] === val
                              ? 'bg-accent text-white'
                              : 'bg-paper border border-line text-ink hover:border-accent'
                          }`}
                        >
                          {val}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex gap-2 mt-6 justify-end">
                <button
                  onClick={onDismiss}
                  className="text-sm text-ink-softer hover:text-ink px-3 py-2"
                >
                  Skip
                </button>
                <Button onClick={submit} disabled={!allAnswered}>
                  Submit
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
