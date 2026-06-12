// KnowledgeGraphView - text-based node/edge summary of the knowledge graph.
// uiux_plan.md §4 catalog entry; PRD §16 payload KnowledgeGraphViewData.
// Interactive D3 graph deferred to P2; this renders a text node/edge summary
// with all four states (invariant #2 compliant).
// FR-KG-04: community id drives node colour. FR-KG-05: pagerank drives font weight.

import type { KnowledgeGraphView as KnowledgeGraphViewBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

// 8 distinct community colours cycling from the design token palette.
const COMMUNITY_COLORS: string[] = [
  'border-accent/60 bg-accent/8 text-accent',
  'border-green/60 bg-green-bg/30 text-green',
  'border-violet/60 bg-violet-bg/30 text-violet',
  'border-amber/60 bg-amber-bg/30 text-amber',
  'border-red/40 bg-red-bg/20 text-red',
  'border-blue-400/60 bg-blue-50/30 text-blue-700',
  'border-teal-400/60 bg-teal-50/30 text-teal-700',
  'border-line bg-card text-ink-soft',
];

function nodeClass(community?: number | null, pagerank?: number | null): string {
  const colorClass = community != null
    ? (COMMUNITY_COLORS[community % COMMUNITY_COLORS.length] ?? COMMUNITY_COLORS[0])
    : 'border-line/50 bg-card text-ink-soft';
  // PageRank > 0.1 → bold; > 0.05 → medium; otherwise normal
  const weightClass = (pagerank ?? 0) > 0.1 ? 'font-bold' : (pagerank ?? 0) > 0.05 ? 'font-medium' : 'font-normal';
  return `px-2 py-0.5 text-xs font-mono rounded border ${colorClass} ${weightClass}`;
}

interface Props {
  block: KnowledgeGraphViewBlock;
}

export function KnowledgeGraphView({ block }: Props) {
  const { meta, data } = block;

  if (data.nodes.length === 0 && meta.status === 'ready') {
    return <EmptyState title="Empty graph" hint="Ingest documents to populate the knowledge graph." />;
  }

  if (meta.status === 'loading') {
    return <LoadingState caption="Loading knowledge graph..." rows={4} />;
  }

  if (meta.status === 'error') {
    return <ErrorState message="Could not load the knowledge graph." />;
  }

  const body = <Body block={block} />;

  if (meta.status === 'partial') {
    return <PartialState>{body}</PartialState>;
  }

  return <Card>{body}</Card>;
}

function Body({ block }: { block: KnowledgeGraphViewBlock }) {
  const { data } = block;

  const focusNode = data.focusNodeId
    ? data.nodes.find((n) => n.id === data.focusNodeId)
    : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">
          Knowledge Graph
        </div>
        <div className="text-xs font-mono text-ink-softer">
          {data.nodes.length} nodes &middot; {data.edges.length} edges
        </div>
      </div>

      {focusNode && (
        <div className="px-3 py-2 bg-surface-2 rounded border border-line/50">
          <div className="text-xs font-mono text-ink-softer">Focus</div>
          <div className="text-sm font-medium text-ink">{focusNode.label}</div>
          <div className="text-xs text-ink-softer font-mono">{focusNode.nodeType}</div>
        </div>
      )}

      <div className="space-y-1">
        <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">Nodes</div>
        <div className="flex flex-wrap gap-1.5">
          {data.nodes.map((node) => (
            <span
              key={node.id}
              title={node.pagerank != null ? `PageRank: ${node.pagerank.toFixed(3)}` : undefined}
              className={node.id === data.focusNodeId
                ? 'px-2 py-0.5 text-xs font-mono rounded border text-green border-green/60 bg-green-bg/20 font-bold'
                : nodeClass(node.community, node.pagerank)}
            >
              {node.label}
            </span>
          ))}
        </div>
      </div>

      {data.edges.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">
            Relationships
          </div>
          <ul className="space-y-1">
            {data.edges.slice(0, 10).map((edge, i) => (
              <li key={i} className="text-xs text-ink-soft font-mono flex gap-1.5 items-center">
                <span className="text-ink">{edge.source}</span>
                <span className="text-ink-softer">&rarr; {edge.relation} &rarr;</span>
                <span className="text-ink">{edge.target}</span>
              </li>
            ))}
            {data.edges.length > 10 && (
              <li className="text-xs text-ink-softer font-mono">
                &hellip; {data.edges.length - 10} more
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
