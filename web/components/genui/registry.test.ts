// Registry test - confirms every UIBlock variant has a renderer.
// If a future schema change adds a variant without registering it,
// the `RendererMap` type fails to compile - this test backstops the
// type-check by also asserting at runtime that the registered set
// matches the slice's known set.

import { describe, expect, it } from 'vitest';

import { _registeredTypes } from './registry';

describe('GenUI registry', () => {
  it('registers exactly the slice-supported variants', () => {
    // Slice 2 scope: CitedSummary + 5 new catalog variants.
    expect(new Set(_registeredTypes())).toEqual(
      new Set([
        'CitedSummary',
        'LiteratureMatrix',
        'ContradictionAlert',
        'GapAnalysis',
        'InsightCard',
        'KnowledgeGraphView',
      ])
    );
  });
});
