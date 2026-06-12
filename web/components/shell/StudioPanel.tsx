'use client';

import { useEffect, useRef, useState } from 'react';

import type { KnowledgeGraphView as KGVBlock, GraphViewResponse, UIBlock } from '@arcana/schema';

import { renderBlock } from '@/components/genui/registry';
import { KnowledgeGraphView } from '@/components/genui/KnowledgeGraphView';
import { EmptyState, LoadingState } from '@/components/genui/BlockStates';
import { useBlockStore } from '@/store/blockStore';
import { useUIStore } from '@/store/uiStore';

// ── Tier accent classes — uiux_plan.md §2.1 ──────────────────────────────────
const TIER_STYLE: Record<1 | 2 | 3 | 4, string> = {
  1: 'border-accent/40 bg-accent/10 text-accent',
  2: 'border-green/40 bg-green-bg/40 text-green',
  3: 'border-violet/40 bg-violet-bg/40 text-violet',
  4: 'border-amber/40 bg-amber-bg/40 text-amber',
};

const BLOCK_AGENT: Record<string, { agent: string; tier: 1 | 2 | 3 | 4 }> = {
  CitedSummary:       { agent: 'ResearchAgent',      tier: 2 },
  LiteratureMatrix:   { agent: 'LiteratureAgent',    tier: 2 },
  ContradictionAlert: { agent: 'ContradictionAgent', tier: 2 },
  KnowledgeGraphView: { agent: 'GraphAgent',         tier: 2 },
  GapAnalysis:        { agent: 'AnnotationAgent',    tier: 2 },
  InsightCard:        { agent: 'CrossDocAgent',      tier: 2 },
  FlashcardDeck:      { agent: 'LearningAgent',      tier: 2 },
  QuizCard:           { agent: 'LearningAgent',      tier: 2 },
  SocraticDialog:     { agent: 'SocraticAgent',      tier: 2 },
  FeynmanExplainer:   { agent: 'LearningAgent',      tier: 2 },
  DraftEditor:        { agent: 'WritingAgent',       tier: 2 },
  StudyPlanner:       { agent: 'StudyPlannerAgent',  tier: 4 },
  BlurtingPrompt:     { agent: 'LearningAgent',      tier: 2 },
  CornellNotes:       { agent: 'LearningAgent',      tier: 2 },
  BibliographyExport: { agent: 'CitationAgent',      tier: 3 },
  CitationPreview:    { agent: 'CitationAgent',      tier: 3 },
  Timeline:           { agent: 'TimelineAgent',      tier: 2 },
  ComparisonChart:    { agent: 'ComparatorAgent',    tier: 2 },
  DataTable:          { agent: 'ResearchAgent',      tier: 2 },
  ConceptMap:         { agent: 'GraphAgent',         tier: 2 },
  ProgressDashboard:  { agent: 'StudyPlannerAgent',  tier: 4 },
};

// ── Trace ─────────────────────────────────────────────────────────────────────

interface TraceInfo {
  agents: { name: string; tier: 1 | 2 | 3 | 4 }[];
  blockCount: number;
  elapsedMs: number;
}

function buildTrace(blockTypes: string[], elapsedMs: number): TraceInfo {
  const seen = new Set<string>();
  const agents: TraceInfo['agents'] = [{ name: 'Orchestrator', tier: 1 }];
  for (const type of blockTypes) {
    const info = BLOCK_AGENT[type];
    if (info && !seen.has(info.agent)) {
      seen.add(info.agent);
      agents.push({ name: info.agent, tier: info.tier });
    }
  }
  agents.push({ name: 'UIAgent', tier: 3 });
  return { agents, blockCount: blockTypes.length, elapsedMs };
}

function TraceBar({ trace, onDismiss }: { trace: TraceInfo; onDismiss: () => void }) {
  const secs = (trace.elapsedMs / 1000).toFixed(1);
  return (
    <div className="flex items-center gap-1.5 px-4 py-2 border-b border-line bg-card text-xs flex-wrap shrink-0">
      <span className="font-mono text-ink-softer shrink-0 mr-1">Turn</span>
      {trace.agents.map((a, i) => (
        <span key={i} className="flex items-center gap-1">
          {i > 0 && <span className="text-ink-softer">→</span>}
          <span className={`px-1.5 py-0.5 rounded border font-mono ${TIER_STYLE[a.tier]}`}>
            {a.name}
          </span>
        </span>
      ))}
      <span className="font-mono text-ink-softer ml-auto shrink-0">
        {trace.blockCount} block{trace.blockCount !== 1 ? 's' : ''} · {secs}s
      </span>
      <button
        onClick={onDismiss}
        className="text-ink-softer hover:text-ink ml-2 shrink-0 leading-none"
        aria-label="Dismiss trace"
      >
        ×
      </button>
    </div>
  );
}

// ── Graph API ─────────────────────────────────────────────────────────────────

const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
).replace(/\/$/, '');

async function fetchGraph(): Promise<GraphViewResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/graph`);
    if (!res.ok) return null;
    return res.json() as Promise<GraphViewResponse>;
  } catch {
    return null;
  }
}

function toKGVBlock(data: GraphViewResponse): KGVBlock {
  return {
    type: 'KnowledgeGraphView',
    id: 'ambient-graph',
    meta: { panel: 'studio', order: 0, status: 'ready' },
    data: {
      nodes: data.nodes.map((n) => ({ id: n.id, label: n.label, nodeType: n.nodeType, community: n.community, pagerank: n.pagerank })),
      edges: data.edges.map((e) => ({ source: e.src, target: e.dst, relation: e.edgeType })),
    },
  };
}

// ── Generators ────────────────────────────────────────────────────────────────

interface GeneratorDef {
  id: string;
  name: string;
  icon: string;
  color: string;
  native: boolean;
  query: string;
}

const GENERATORS: GeneratorDef[] = [
  { id: 'flashcards',    name: 'Flashcards',       icon: '▤', color: '#3d7a52', native: false, query: 'Generate a flashcard deck from my corpus' },
  { id: 'quiz',          name: 'Quiz',              icon: '?',  color: '#3d7a52', native: false, query: 'Create a quiz based on my documents' },
  { id: 'report',        name: 'Report',            icon: '≣', color: '#3d7a52', native: false, query: 'Write a detailed research report on my corpus' },
  { id: 'lit-matrix',    name: 'Literature Matrix', icon: '⊞', color: '#2f5fa8', native: true,  query: 'Build a literature comparison matrix across my documents' },
  { id: 'concept-map',   name: 'Concept Map',       icon: '⊛', color: '#6a4ea8', native: true,  query: 'Generate a concept map from my corpus' },
  { id: 'kg-snapshot',   name: 'KG Snapshot',       icon: '◐', color: '#2f5fa8', native: true,  query: 'Show me a knowledge graph snapshot of my corpus' },
  { id: 'cornell',       name: 'Cornell Notes',     icon: '❘',  color: '#3d7a52', native: true,  query: 'Create Cornell notes from my documents' },
  { id: 'draft',         name: 'Draft',             icon: '✎',  color: '#23211c', native: true,  query: 'Draft a literature review section from my corpus' },
  { id: 'study-plan',    name: 'Study Planner',     icon: '◈', color: '#9a6b18', native: false, query: 'Create a study plan for my corpus' },
  { id: 'gap-analysis',  name: 'Gap Analysis',      icon: '△', color: '#6a4ea8', native: true,  query: 'Identify research gaps in my corpus' },
  { id: 'timeline',      name: 'Timeline',          icon: '→',  color: '#3d7a52', native: false, query: 'Build a timeline of key developments from my documents' },
  { id: 'data-table',    name: 'Data Table',        icon: '☷', color: '#23211c', native: false, query: 'Extract key data into a comparison table from my corpus' },
  { id: 'feynman',       name: 'Feynman',           icon: '◎', color: '#2f5fa8', native: false, query: 'Explain the main concept from my corpus in simple language' },
  { id: 'cited-summary', name: 'Cited Summary',     icon: '§',  color: '#3d7a52', native: true,  query: 'Summarise my corpus with inline citations' },
  { id: 'contradiction', name: 'Contradictions',    icon: '!',  color: '#a8423a', native: true,  query: 'Find contradictions or disagreements across my documents' },
];

// UIBlock type → generator id for library display
const BLOCK_TO_GEN: Record<string, string> = {
  FlashcardDeck:      'flashcards',
  QuizCard:           'quiz',
  CitedSummary:       'cited-summary',
  LiteratureMatrix:   'lit-matrix',
  ConceptMap:         'concept-map',
  KnowledgeGraphView: 'kg-snapshot',
  CornellNotes:       'cornell',
  DraftEditor:        'draft',
  StudyPlanner:       'study-plan',
  GapAnalysis:        'gap-analysis',
  Timeline:           'timeline',
  DataTable:          'data-table',
  FeynmanExplainer:   'feynman',
  ContradictionAlert: 'contradiction',
};

// ── Generator tile ─────────────────────────────────────────────────────────────

function GeneratorTile({ gen, onQuery }: { gen: GeneratorDef; onQuery: (q: string) => void }) {
  return (
    <button
      onClick={() => onQuery(gen.query)}
      title={gen.query}
      className="group relative flex flex-col gap-1.5 rounded-[9px] border border-line bg-card p-2.5 text-left transition-all hover:-translate-y-px hover:shadow-sm active:translate-y-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      style={{ minHeight: '62px' }}
    >
      <div
        className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-[5px] text-[11px] leading-none text-white"
        style={{ background: gen.color }}
      >
        {gen.icon}
      </div>
      <span className="text-[11.5px] font-medium text-ink leading-tight">{gen.name}</span>
      {gen.native && (
        <span className="absolute bottom-1.5 right-1.5 font-display text-[8.5px] font-semibold text-accent/60">
          A
        </span>
      )}
    </button>
  );
}

// ── Library item ───────────────────────────────────────────────────────────────

function LibraryItem({ block }: { block: UIBlock }) {
  const [expanded, setExpanded] = useState(true);
  const gen = GENERATORS.find((g) => g.id === BLOCK_TO_GEN[block.type]);

  return (
    <div className="rounded-lg border border-line overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 bg-card hover:bg-paper transition-colors"
      >
        <div
          className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-[5px] text-[10px] leading-none text-white"
          style={{ background: gen?.color ?? '#888' }}
        >
          {gen?.icon ?? '◇'}
        </div>
        <span className="flex-1 min-w-0 text-left text-[12.5px] font-medium text-ink truncate">
          {gen?.name ?? block.type}
        </span>
        <span className="font-mono text-[10px] text-ink-softer shrink-0">just now</span>
        <span className="text-[10px] text-ink-softer ml-1 shrink-0">{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <div className="border-t border-line">
          {renderBlock(block)}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function StudioPanel() {
  const allBlocks = useBlockStore((s) => s.blocks);
  const streaming = useBlockStore((s) => s.streaming);
  const setQueryDraft = useUIStore((s) => s.setQueryDraft);

  const [graphData, setGraphData] = useState<GraphViewResponse | null>(null);
  const [graphLoading, setGraphLoading] = useState(true);
  const [trace, setTrace] = useState<TraceInfo | null>(null);
  const [traceDismissed, setTraceDismissed] = useState(false);

  const prevStreamingRef = useRef(false);
  const turnStartRef = useRef<number | null>(null);

  // Fetch the ambient knowledge graph once on mount.
  useEffect(() => {
    fetchGraph().then((data) => {
      setGraphData(data);
      setGraphLoading(false);
    });
  }, []);

  // Detect turn start/end: build trace, refresh ambient graph.
  useEffect(() => {
    if (streaming && !prevStreamingRef.current) {
      turnStartRef.current = Date.now();
      setTrace(null);
      setTraceDismissed(false);
    } else if (!streaming && prevStreamingRef.current) {
      if (turnStartRef.current !== null) {
        const elapsed = Date.now() - turnStartRef.current;
        const types = useBlockStore
          .getState()
          .blocks.filter((b) => b.meta?.status !== 'loading')
          .map((b) => b.type);
        if (types.length > 0) setTrace(buildTrace(types, elapsed));
        turnStartRef.current = null;
      }
      fetchGraph().then((data) => { if (data) setGraphData(data); });
    }
    prevStreamingRef.current = streaming;
  }, [streaming]);

  const studioBlocks = allBlocks.filter((b) => b.meta?.panel === 'studio');
  const showTrace = trace !== null && !traceDismissed;

  return (
    <aside className="h-full flex flex-col border-l border-line bg-paper">

      {/* ── Knowledge Graph (top ~42%) ──────────────────────────── */}
      <div className="flex flex-col border-b border-line" style={{ flex: '0 0 42%', minHeight: 0 }}>
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-line bg-card shrink-0">
          <span className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-ink-soft">
            Knowledge Graph
          </span>
          {graphData && graphData.nodeCount > 0 && (
            <span className="text-[9.5px] bg-paper text-ink-soft px-1.5 py-0.5 rounded-full border border-line">
              {graphData.nodeCount} nodes · {graphData.edgeCount} edges
            </span>
          )}
        </div>
        <div className="flex-1 overflow-hidden min-h-0" style={{ padding: '6px 8px' }}>
          {graphLoading ? (
            <LoadingState caption="Loading knowledge graph…" rows={4} />
          ) : !graphData || graphData.nodeCount === 0 ? (
            <EmptyState
              title="Knowledge graph"
              hint="Ingest documents to build your knowledge graph. Entities and relationships extracted from your PDFs appear here."
            />
          ) : (
            <KnowledgeGraphView block={toKGVBlock(graphData)} />
          )}
        </div>
      </div>

      {/* ── Studio (bottom, remainder) ──────────────────────────── */}
      <div className="flex flex-col min-h-0" style={{ flex: '1 1 0' }}>
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-line bg-card shrink-0">
          <span className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-ink-soft">
            Studio
          </span>
          <span className="text-[9.5px] bg-paper text-ink-soft px-1.5 py-0.5 rounded-full border border-line">
            {GENERATORS.length} generators{studioBlocks.length > 0 ? ` · ${studioBlocks.length} saved` : ''}
          </span>
          <button
            className="ml-auto h-6 w-6 flex items-center justify-center rounded text-ink-softer hover:text-ink hover:bg-paper transition-colors text-base leading-none"
            title="Add note"
            aria-label="Add note"
          >
            +
          </button>
        </div>

        {showTrace && (
          <TraceBar trace={trace!} onDismiss={() => setTraceDismissed(true)} />
        )}

        <div className="flex-1 overflow-y-auto min-h-0 p-3">
          {/* Generate section */}
          <p className="text-[9.5px] font-semibold uppercase tracking-[0.08em] text-ink-softer pb-2">
            Generate
          </p>
          <div className="grid grid-cols-3 gap-[7px] mb-4">
            {GENERATORS.map((g) => (
              <GeneratorTile key={g.id} gen={g} onQuery={setQueryDraft} />
            ))}
          </div>

          {/* Library section */}
          <div className="flex items-center gap-2 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-softer mb-2">
            Library{studioBlocks.length > 0 ? ` · ${studioBlocks.length} saved` : ''}
            <div className="flex-1 h-px bg-line" />
          </div>

          {studioBlocks.length === 0 ? (
            <p className="text-[12px] text-ink-soft font-serif italic leading-relaxed px-1 py-1">
              Generated artefacts will be saved here — tap any generator above to begin.
            </p>
          ) : (
            <div className="space-y-2">
              {studioBlocks.map((block) => (
                <LibraryItem key={block.id} block={block} />
              ))}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
