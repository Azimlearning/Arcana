"""UI Agent - Tier 3. The ONLY agent that picks components (invariant #3).

Routes intent/mode to the most appropriate UIBlock variant (FR-UI-04).
Priority order (since the graph routes ONE intent per turn):
  1. Learning agent result  → FlashcardDeck | QuizCard | FeynmanExplainer
  2. Socratic agent result  → SocraticDialog
  3. Writing agent result   → DraftEditor
  4. Discovery agent result → GapAnalysis | InsightCard
  5. Cross-doc agent result → InsightCard
  6. Graph agent result     → KnowledgeGraphView
  7. Literature agent result → LiteratureMatrix
  8. Contradiction agent result → ContradictionAlert
  9. Comparator → LiteratureMatrix (multi-doc, FR-RET-05) or CitedSummary (single-doc)
 10. Timeline agent result → CitedSummary (timeline framing)
 11. Annotation agent result → GapAnalysis (annotation framing)
 12. Research agent result  → CitedSummary (with Fact Check filter)
 13. Error block            (invariant #6: always terminate with a block)

Slice 1 additions (still in effect):
  - Reads fact_checker result and filters unsupported citations (FR-AGT-09).
  - Downgrades ready -> partial when >50% of citations were dropped.

Slice 11 additions:
  - Priority-0 StudyPlanner routing slot (_build_from_study_planner).
  - BlurtingPrompt and CornellNotes cases added to _build_from_learning.
  - is_llm_error propagation for BlurtingPrompt + CornellNotes (mirrors DraftEditor).

Slice 7 additions:
  - Routing for KnowledgeGraphView (graph_agent), LiteratureMatrix (literature),
    ContradictionAlert (contradiction), InsightCard (cross_doc + discovery).
  - InsightCard routing in DiscoveryAgent result is now live (was deferred in Slice 2).
  - Comparator/Timeline produce CitedSummary; Annotation produces GapAnalysis via
    existing builder paths.

Slice 16 (FR-RET-05):
  - Comparator now returns LiteratureMatrix when ≥2 docs found; UIAgent dispatches
    on block_type to pick _build_from_literature vs _build_cited_summary_from_result.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import ValidationError

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.genui._generated import (
    BlockMeta,
    BlurtingPrompt,
    BlurtingPromptData,
    CitedSummary,
    CitedSummaryData,
    ContradictionAlert,
    ContradictionAlertData,
    CornellNotes,
    CornellNotesData,
    DraftEditor,
    DraftEditorData,
    FeynmanExplainer,
    FeynmanExplainerData,
    FlashcardDeck,
    FlashcardDeckData,
    GapAnalysis,
    GapAnalysisData,
    InsightCard,
    InsightCardData,
    KnowledgeGraphView,
    KnowledgeGraphViewData,
    LiteratureMatrix,
    LiteratureMatrixData,
    QuizCard,
    QuizCardData,
    SocraticDialog,
    SocraticDialogData,
    StudyPlanner,
    StudyPlannerData,
    UIBlock,
)

logger = get_logger(__name__)

# Above this fraction of citations dropped, downgrade ready -> partial.
_PARTIAL_DROP_THRESHOLD = 0.5


class UIAgent(BaseAgent):
    name = "ui_agent"
    tier = 3

    async def run(self, query: str, state: AgentState) -> AgentResult:
        # Multi-block path: comparator with A2A hops emits up to 3 blocks
        # (LiteratureMatrix + KnowledgeGraphView + ContradictionAlert — PRD Listing 12.1).
        comparator = state.agent_results.get("comparator")
        if (comparator is not None and comparator.status == "ok"
                and comparator.payload.get("block_type") == "LiteratureMatrix"):
            blocks = self._route_compare_multi_block(state)
            for b in blocks:
                state.ui_blocks.append(b)
            return AgentResult(
                agent_name=self.name,
                payload={"block_ids": [b.id for b in blocks],
                          "types": [b.type for b in blocks]},
                status="ok",
            )

        block = self._route_to_block(state)
        state.ui_blocks.append(block)
        return AgentResult(
            agent_name=self.name,
            payload={"block_id": block.id, "type": block.type},
            status="ok",
        )

    # -- Routing ---------------------------------------------------------

    def _route_compare_multi_block(self, state: AgentState) -> list[UIBlock]:
        """Emit LiteratureMatrix + KnowledgeGraphView + ContradictionAlert
        when ComparatorAgent ran with A2A sub-hops (PRD Listing 12.1)."""
        blocks: list[UIBlock] = []
        order = len(state.ui_blocks)

        # Block 1 — LiteratureMatrix (always present for multi-doc compare)
        comparator = state.agent_results["comparator"]
        matrix = self._build_from_literature(comparator, order=order)
        if matrix is not None:
            blocks.append(matrix)
            order += 1

        # Block 2 — KnowledgeGraphView from A2A hop 1 (graph_agent)
        graph = state.agent_results.get("graph_agent")
        if graph is not None and graph.status == "ok":
            kg = self._build_from_graph(graph, order=order)
            if kg is not None:
                blocks.append(kg)
                order += 1

        # Block 3 — ContradictionAlert from A2A hop 2 (contradiction)
        contradiction = state.agent_results.get("contradiction")
        if contradiction is not None and contradiction.status == "ok":
            ca = self._build_from_contradiction(contradiction, order=order)
            if ca is not None:
                blocks.append(ca)

        return blocks or [self._error_block("Comparison failed to produce any components.")]

    def _route_to_block(self, state: AgentState) -> UIBlock:
        """Pick the best UIBlock variant given available agent results."""
        order = len(state.ui_blocks)

        # 0. StudyPlanner (StudyPlanner)
        study_planner = state.agent_results.get("study_planner")
        if study_planner is not None and study_planner.status == "ok":
            block = self._build_from_study_planner(study_planner, order=order)
            if block is not None:
                return block

        # 1. Learning (FlashcardDeck | QuizCard | FeynmanExplainer | BlurtingPrompt | CornellNotes)
        learning = state.agent_results.get("learning")
        if learning is not None and learning.status == "ok":
            block = self._build_from_learning(learning, order=order)
            if block is not None:
                return block

        # 2. Socratic (SocraticDialog)
        socratic = state.agent_results.get("socratic")
        if socratic is not None and socratic.status == "ok":
            block = self._build_from_socratic(socratic, order=order)
            if block is not None:
                return block

        # 3. Writing (DraftEditor)
        writing = state.agent_results.get("writing")
        if writing is not None and writing.status == "ok":
            block = self._build_from_writing(writing, order=order)
            if block is not None:
                return block

        # 4. Discovery (GapAnalysis | InsightCard)
        discovery = state.agent_results.get("discovery")
        if discovery is not None and discovery.status == "ok":
            block = self._build_from_discovery(discovery, order=order)
            if block is not None:
                return block

        # 5. Cross-doc (InsightCard)
        cross_doc = state.agent_results.get("cross_doc")
        if cross_doc is not None and cross_doc.status == "ok":
            block = self._build_from_cross_doc(cross_doc, order=order)
            if block is not None:
                return block

        # 6. Graph (KnowledgeGraphView)
        graph = state.agent_results.get("graph_agent")
        if graph is not None and graph.status == "ok":
            block = self._build_from_graph(graph, order=order)
            if block is not None:
                return block

        # 7. Literature (LiteratureMatrix)
        literature = state.agent_results.get("literature")
        if literature is not None and literature.status == "ok":
            block = self._build_from_literature(literature, order=order)
            if block is not None:
                return block

        # 8. Contradiction (ContradictionAlert)
        contradiction = state.agent_results.get("contradiction")
        if contradiction is not None and contradiction.status == "ok":
            block = self._build_from_contradiction(contradiction, order=order)
            if block is not None:
                return block

        # 9. Comparator → LiteratureMatrix (multi-doc, FR-RET-05) or CitedSummary (single-doc)
        comparator = state.agent_results.get("comparator")
        if comparator is not None and comparator.status == "ok":
            if comparator.payload.get("block_type") == "LiteratureMatrix":
                block = self._build_from_literature(comparator, order=order)
            else:
                block = self._build_cited_summary_from_result(comparator, order=order)
            if block is not None:
                return block

        # 10. Timeline → CitedSummary
        timeline = state.agent_results.get("timeline")
        if timeline is not None and timeline.status == "ok":
            block = self._build_cited_summary_from_result(timeline, order=order)
            if block is not None:
                return block

        # 11. Annotation → GapAnalysis
        annotation = state.agent_results.get("annotate")
        if annotation is not None and annotation.status == "ok":
            block = self._build_from_discovery(annotation, order=order)
            if block is not None:
                return block

        # 12. Research (CitedSummary, with Fact Check filter)
        research = state.agent_results.get("research")
        fact_check = state.agent_results.get("fact_checker")

        if research is None:
            # A specialist agent was routed but failed — surface its error.
            for _name in ("study_planner", "discovery", "learning", "socratic", "writing"):
                _result = state.agent_results.get(_name)
                if _result is not None:
                    return self._error_block(
                        _result.error or f"{_name} agent failed to produce a result."
                    )
            return self._error_block("Research agent did not run.")
        if research.status == "failed":
            return self._error_block(research.error or "Research agent failed.")

        payload, status = self._apply_fact_check(
            payload=research.payload,
            research_status=research.status,
            fact_check=fact_check,
        )
        try:
            data = CitedSummaryData.model_validate(payload)
            return self._build_cited_summary(data, status=status, order=order)
        except ValidationError as e:
            logger.warning("ui_agent.payload_invalid", error=str(e))
            return self._error_block(
                f"Research payload failed schema validation: {e.error_count()} field(s)"
            )

    # -- Per-agent block builders -----------------------------------------

    def _build_from_learning(self, result: AgentResult, *, order: int = 0) -> UIBlock | None:
        block_type = result.payload.get("block_type")
        data_dict = result.payload.get("data", {}) or {}
        is_llm_error = bool(result.payload.get("_error"))

        if block_type == "FlashcardDeck":
            try:
                data = FlashcardDeckData.model_validate(data_dict)
                return FlashcardDeck(
                    type="FlashcardDeck",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="chat", order=order, status="ready"),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.learning_flashcard_invalid", error=str(e))
                return None

        if block_type == "QuizCard":
            try:
                data = QuizCardData.model_validate(data_dict)
                return QuizCard(
                    type="QuizCard",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="chat", order=order, status="ready"),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.learning_quiz_invalid", error=str(e))
                return None

        if block_type == "FeynmanExplainer":
            try:
                data = FeynmanExplainerData.model_validate(data_dict)
                return FeynmanExplainer(
                    type="FeynmanExplainer",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="chat", order=order, status="ready"),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.learning_feynman_invalid", error=str(e))
                return None

        if block_type == "BlurtingPrompt":
            try:
                data = BlurtingPromptData.model_validate(data_dict)
                status = "error" if is_llm_error else "ready"
                return BlurtingPrompt(
                    type="BlurtingPrompt",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="chat", order=order, status=status),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.learning_blurting_invalid", error=str(e))
                return None

        if block_type == "CornellNotes":
            try:
                data = CornellNotesData.model_validate(data_dict)
                status = "error" if is_llm_error else "ready"
                return CornellNotes(
                    type="CornellNotes",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="studio", order=order, status=status),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.learning_cornell_invalid", error=str(e))
                return None

        return None

    def _build_from_study_planner(self, result: AgentResult, *, order: int = 0) -> UIBlock | None:
        block_type = result.payload.get("block_type")
        data_dict = result.payload.get("data", {}) or {}

        if block_type == "StudyPlanner":
            try:
                data = StudyPlannerData.model_validate(data_dict)
                return StudyPlanner(
                    type="StudyPlanner",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="studio", order=order, status="ready"),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.study_planner_invalid", error=str(e))
                return None

        return None

    def _build_from_socratic(self, result: AgentResult, *, order: int = 0) -> UIBlock | None:
        block_type = result.payload.get("block_type")
        data_dict = result.payload.get("data", {}) or {}

        if block_type == "SocraticDialog":
            try:
                data = SocraticDialogData.model_validate(data_dict)
                return SocraticDialog(
                    type="SocraticDialog",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="chat", order=order, status="ready"),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.socratic_invalid", error=str(e))
                return None

        return None

    def _build_from_writing(self, result: AgentResult, *, order: int = 0) -> UIBlock | None:
        block_type = result.payload.get("block_type")
        data_dict = result.payload.get("data", {}) or {}
        is_llm_error = bool(result.payload.get("_error"))

        if block_type == "DraftEditor":
            try:
                data = DraftEditorData.model_validate(data_dict)
                status = "error" if is_llm_error else "ready"
                return DraftEditor(
                    type="DraftEditor",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="chat", order=order, status=status),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.writing_draft_invalid", error=str(e))
                return None

        return None

    def _build_from_discovery(self, result: AgentResult, *, order: int = 0) -> UIBlock | None:
        block_type = result.payload.get("block_type")
        data_dict = result.payload.get("data", {}) or {}

        if block_type == "GapAnalysis":
            try:
                data = GapAnalysisData.model_validate(data_dict)
                return GapAnalysis(
                    type="GapAnalysis",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="studio", order=order, status="ready"),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.discovery_gap_invalid", error=str(e))
                return None

        if block_type == "InsightCard":
            try:
                data = InsightCardData.model_validate(data_dict)
                return InsightCard(
                    type="InsightCard",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="chat", order=order, status="ready"),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.discovery_insight_invalid", error=str(e))
                return None

        return None

    def _build_from_cross_doc(self, result: AgentResult, *, order: int = 0) -> UIBlock | None:
        block_type = result.payload.get("block_type")
        data_dict = result.payload.get("data", {}) or {}

        if block_type == "InsightCard":
            try:
                data = InsightCardData.model_validate(data_dict)
                return InsightCard(
                    type="InsightCard",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="chat", order=order, status="ready"),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.cross_doc_insight_invalid", error=str(e))
                return None

        return None

    def _build_from_graph(self, result: AgentResult, *, order: int = 0) -> UIBlock | None:
        block_type = result.payload.get("block_type")
        data_dict = result.payload.get("data", {}) or {}

        if block_type == "KnowledgeGraphView":
            try:
                data = KnowledgeGraphViewData.model_validate(data_dict)
                return KnowledgeGraphView(
                    type="KnowledgeGraphView",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="studio", order=order, status="ready"),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.graph_view_invalid", error=str(e))
                return None

        return None

    def _build_from_literature(self, result: AgentResult, *, order: int = 0) -> UIBlock | None:
        block_type = result.payload.get("block_type")
        data_dict = result.payload.get("data", {}) or {}

        if block_type == "LiteratureMatrix":
            try:
                data = LiteratureMatrixData.model_validate(data_dict)
                return LiteratureMatrix(
                    type="LiteratureMatrix",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="studio", order=order, status="ready"),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.literature_matrix_invalid", error=str(e))
                return None

        return None

    def _build_from_contradiction(self, result: AgentResult, *, order: int = 0) -> UIBlock | None:
        block_type = result.payload.get("block_type")
        data_dict = result.payload.get("data", {}) or {}

        if block_type == "ContradictionAlert":
            try:
                data = ContradictionAlertData.model_validate(data_dict)
                return ContradictionAlert(
                    type="ContradictionAlert",
                    id=_new_block_id(),
                    meta=BlockMeta(panel="chat", order=order, status="ready"),  # type: ignore[arg-type]
                    data=data,
                )
            except ValidationError as e:
                logger.warning("ui_agent.contradiction_alert_invalid", error=str(e))
                return None

        return None

    def _build_cited_summary_from_result(
        self, result: AgentResult, *, order: int = 0
    ) -> UIBlock | None:
        """Build CitedSummary from a comparator/timeline AgentResult payload."""
        try:
            data = CitedSummaryData.model_validate(result.payload)
            status = "ready" if result.status == "ok" else "partial"
            return self._build_cited_summary(data, status=status, order=order)
        except ValidationError as e:
            logger.warning("ui_agent.cited_summary_from_result_invalid", error=str(e))
            return None

    # -- Fact-check filter -----------------------------------------------

    def _apply_fact_check(
        self,
        *,
        payload: dict[str, Any],
        research_status: str,
        fact_check: AgentResult | None,
    ) -> tuple[dict[str, Any], str]:
        base_status = "ready" if research_status == "ok" else "partial"

        if fact_check is None or fact_check.status != "ok":
            return payload, base_status

        dropped = set(fact_check.payload.get("dropped_ids", []) or [])
        checked = int(fact_check.payload.get("checked", 0) or 0)
        if not dropped:
            return payload, base_status

        filtered = dict(payload)
        filtered["citations"] = [
            c for c in payload.get("citations", []) if c.get("id") not in dropped
        ]
        filtered["segments"] = [
            {
                "text": s.get("text", ""),
                "citationIds": [
                    cid for cid in s.get("citationIds", []) if cid not in dropped
                ],
            }
            for s in payload.get("segments", [])
        ]

        if checked > 0 and (len(dropped) / checked) > _PARTIAL_DROP_THRESHOLD:
            return filtered, "partial"
        return filtered, base_status

    # -- Block constructors ----------------------------------------------

    def _build_cited_summary(
        self, data: CitedSummaryData, *, status: str, order: int = 0
    ) -> CitedSummary:
        return CitedSummary(
            type="CitedSummary",
            id=_new_block_id(),
            meta=BlockMeta(panel="chat", order=order, status=status),  # type: ignore[arg-type]
            data=data,
        )

    # Keep the old name as an alias so existing test helpers still work.
    _build_block = _build_cited_summary

    def _error_block(self, message: str) -> CitedSummary:
        return CitedSummary(
            type="CitedSummary",
            id=_new_block_id(),
            meta=BlockMeta(panel="chat", order=0, status="error"),  # type: ignore[arg-type]
            data=CitedSummaryData(
                summary=f"Sorry — {message}",
                segments=[],
                citations=[],
            ),
        )


def _new_block_id() -> str:
    return f"block_{uuid.uuid4().hex[:12]}"
