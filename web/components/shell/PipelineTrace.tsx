'use client';

import { useUIStore } from '@/store/uiStore';

// Tier accent styles — per uiux_plan.md §2.1:
// Tier 1 Orchestration → blue  · Tier 2 Core Intelligence → green
// Tier 3 Output → violet       · Tier 4 Quality/Meta → amber
const TIER_PILL: Record<number, string> = {
  1: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800',
  2: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800',
  3: 'bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-950 dark:text-violet-300 dark:border-violet-800',
  4: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800',
};

// Human-readable display names for agent registry keys.
const AGENT_LABEL: Record<string, string> = {
  orchestrator: 'Orchestrator',
  research: 'Research',
  comparator: 'Comparator',
  graph_agent: 'Graph',
  literature: 'Literature',
  contradiction: 'Contradiction',
  cross_doc: 'Cross-Doc',
  discovery: 'Discovery',
  learning: 'Learning',
  socratic: 'Socratic',
  writing: 'Writing',
  timeline: 'Timeline',
  annotate: 'Annotate',
  ui_agent: 'UI Agent',
  fact_checker: 'Fact Check',
  memory: 'Memory',
  study_planner: 'Study Planner',
};

/**
 * Compact strip showing the agent pipeline that ran on the last turn.
 * Renders tier-coloured pills, A2A hop arrows, and a hop count badge.
 * Dismissible by the user. Per uiux_plan.md §8.
 */
export function PipelineTrace() {
  const trace = useUIStore((s) => s.trace);
  const clearTrace = useUIStore((s) => s.clearTrace);

  if (!trace || trace.agents.length === 0) return null;

  return (
    <div
      role="status"
      aria-label="Agent pipeline trace"
      className="mx-4 mb-3 px-3 py-2 rounded-ctl border border-line bg-card flex items-center gap-1 flex-wrap text-xs"
    >
      <span className="text-ink-soft font-medium mr-1 shrink-0 select-none">
        Pipeline
      </span>

      {trace.agents.map((agent, i) => (
        <span key={`${agent.name}-${i}`} className="flex items-center gap-0.5">
          {i > 0 && (
            <span
              className={`mx-0.5 select-none ${
                agent.is_hop ? 'text-emerald-500 font-bold' : 'text-ink-softer'
              }`}
              title={agent.is_hop ? 'A2A hop via route_to_agent' : undefined}
            >
              {agent.is_hop ? '↗' : '→'}
            </span>
          )}
          <span
            className={`px-1.5 py-0.5 rounded border font-mono leading-none ${
              TIER_PILL[agent.tier] ?? TIER_PILL[2]
            } ${agent.status === 'failed' ? 'opacity-50 line-through' : ''}`}
            title={`Tier ${agent.tier} · ${agent.status}`}
          >
            {AGENT_LABEL[agent.name] ?? agent.name}
          </span>
        </span>
      ))}

      {trace.hops_used > 0 && (
        <span className="ml-2 px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono shrink-0">
          {trace.hops_used} {trace.hops_used === 1 ? 'hop' : 'hops'}
        </span>
      )}

      <button
        onClick={clearTrace}
        className="ml-auto text-ink-softer hover:text-ink shrink-0 leading-none p-0.5 rounded"
        aria-label="Dismiss pipeline trace"
        type="button"
      >
        ✕
      </button>
    </div>
  );
}
