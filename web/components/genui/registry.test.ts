import { describe, expect, it } from 'vitest';

import { _registeredTypes } from './registry';

describe('GenUI registry', () => {
  it('covers all 14 UIBlock variants', () => {
    const types = new Set(_registeredTypes());
    expect(types.size).toBe(14);
  });

  it('includes every expected block type', () => {
    const types = new Set(_registeredTypes());
    const expected = [
      'CitedSummary',
      'LiteratureMatrix',
      'ContradictionAlert',
      'GapAnalysis',
      'InsightCard',
      'KnowledgeGraphView',
      'FlashcardDeck',
      'QuizCard',
      'SocraticDialog',
      'FeynmanExplainer',
      'DraftEditor',
      'StudyPlanner',
      'BlurtingPrompt',
      'CornellNotes',
    ] as const;
    for (const t of expected) {
      expect(types.has(t), `missing: ${t}`).toBe(true);
    }
  });
});
