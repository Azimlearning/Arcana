"""FastAPI app factory + uvicorn entry point.

`uvicorn api.main:app` boots the slice. At startup (lifespan):
  1. `configure_logging()` once - structlog JSON.
  2. Build the shared infrastructure (stores, embedder, llm) from `Settings`.
  3. Build the orchestrator from shared infra.
  4. Wire both the orchestrator and the ingest context via dependency_overrides
     so the chat route and the ingest route share the SAME store instances —
     a freshly ingested document is visible to the next chat turn without a
     server restart.

Slice 9: auth (api/core/auth.py) and notebooks/review routes added.
Slice 10: analytics event store + feedback/sus/export routes added.
Slice 14: UserGraphRegistry replaces the single shared graph_store (FR-KG-02).
CORS is open to localhost:3000 for local dev; tighten for deployment.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from api.core.errors import ArcanaError, arcana_error_handler
from api.core.logging import configure_logging, get_logger
from api.routes.analytics import router as analytics_router
from api.routes.chat import get_orchestrator
from api.routes.chat import router as chat_router
from api.routes.feedback import router as feedback_router
from api.routes.graph import router as graph_router
from api.routes.ingest import IngestContext, get_ingest_context
from api.routes.ingest import router as ingest_router
from api.routes.notebooks import router as notebooks_router
from api.routes.review import router as review_router

logger = get_logger(__name__)


def _build_shared_resources():
    """Build infrastructure shared between the orchestrator and the ingest route.

    Returns a dict with everything needed so lifespan can wire both
    dependency overrides from a single construction pass — no duplicate
    Pinecone connections, no duplicate in-memory graph objects.
    """
    from api.core.settings import get_settings
    from api.embeddings.service import EmbeddingService
    from api.ingestion.stores_bundle import Stores
    from api.llm.service import LLMService
    from api.retrieval.bm25 import BM25Retriever
    from api.retrieval.graph import GraphRetriever
    from api.retrieval.vector import VectorRetriever
    from api.stores.filesystem_doc_store import FilesystemDocStore
    from api.stores.in_memory_store import InMemoryMemoryStore
    from api.stores.jsonl_chunk_store import JsonlChunkStore
    from api.stores.networkx_store import NetworkXGraphStore
    from api.stores.pinecone_store import PineconeVectorStore
    from api.stores.user_graph_registry import UserGraphRegistry

    settings = get_settings()

    # Three model tiers — each falls back to sonnet-4.6 on outage.
    # Heavy (Opus 4.8): research, writing, literature, contradiction.
    # Standard (Sonnet 4.6): most analysis agents, general default.
    # Light (Haiku 4.5): extraction, fact-check, flashcards, memory.
    llm = LLMService(settings=settings)  # standard: sonnet-4.6
    llm_heavy = LLMService.for_model(
        settings.llm_heavy,
        settings=settings,
        fallback_model=settings.llm_fallback,
    )
    llm_light = LLMService.for_model(
        settings.llm_light,
        settings=settings,
        fallback_model=settings.llm_fallback,
    )
    embedder = EmbeddingService(settings=settings)

    vector_store = PineconeVectorStore(
        api_key=settings.pinecone_api_key.get_secret_value(),
        index_name=settings.pinecone_index,
    )

    # FR-KG-02: per-user graph registry. Each user's graph persists at
    # {local_storage_path}/graphs/{uid}.json. The shared_graph is a fallback
    # used by the GraphRetriever (which reads the graph of the "anon" user
    # in local dev and the shared corpus in single-tenant deployments).
    graph_registry = UserGraphRegistry(root=settings.local_storage_path / "graphs")
    shared_graph = NetworkXGraphStore(
        persist_path=settings.local_storage_path / "graphs" / "shared.json",
    )

    doc_store = FilesystemDocStore(root=settings.local_storage_path)
    chunk_store = JsonlChunkStore(root=settings.local_storage_path)

    stores = Stores(
        doc=doc_store,
        vector=vector_store,
        graph=shared_graph,
        chunks=chunk_store,
    )

    vector_retriever = VectorRetriever(vector_store=vector_store, embedder=embedder)
    bm25_retriever = BM25Retriever(chunk_store=chunk_store)
    graph_retriever = GraphRetriever(
        graph_store=shared_graph,
        chunk_store=chunk_store,
        llm=llm,
    )
    memory_store = InMemoryMemoryStore()

    from api.stores.notebook_store import JsonlNotebookStore
    notebook_store = JsonlNotebookStore(root=settings.local_storage_path / "notebooks")

    from api.analytics.event_store import JsonlEventStore
    event_store = JsonlEventStore(root=settings.local_storage_path / "events")

    return {
        "settings": settings,
        "llm": llm,
        "llm_heavy": llm_heavy,
        "llm_light": llm_light,
        "embedder": embedder,
        "stores": stores,
        "doc_store": doc_store,
        "vector_retriever": vector_retriever,
        "bm25_retriever": bm25_retriever,
        "graph_retriever": graph_retriever,
        "memory_store": memory_store,
        "notebook_store": notebook_store,
        "event_store": event_store,
        "graph_registry": graph_registry,
    }


def build_orchestrator(shared: dict):
    """Construct the orchestrator from pre-built shared resources.

    Accepts the dict returned by _build_shared_resources() so tests can
    inject stubs without touching the real provider chain."""
    from api.agents.orchestrator import Orchestrator
    from api.agents.tier2.annotation import AnnotationAgent
    from api.agents.tier2.comparator import ComparatorAgent
    from api.agents.tier2.contradiction import ContradictionAgent
    from api.agents.tier2.cross_doc import CrossDocAgent
    from api.agents.tier2.discovery import DiscoveryAgent
    from api.agents.tier2.graph_agent import GraphAgent
    from api.agents.tier2.learning import LearningAgent
    from api.agents.tier2.literature import LiteratureAgent
    from api.agents.tier2.research import ResearchAgent
    from api.agents.tier2.socratic import SocraticAgent
    from api.agents.tier2.timeline_agent import TimelineAgent
    from api.agents.tier2.writing import WritingAgent
    from api.agents.tier3.ui_agent import UIAgent
    from api.agents.tier4.fact_checker import FactChecker
    from api.agents.tier4.memory import MemoryAgent
    from api.agents.tier4.study_planner import StudyPlannerAgent

    llm = shared["llm"]              # sonnet-4.6: standard
    llm_heavy = shared["llm_heavy"]  # opus-4.8 → sonnet fallback
    llm_light = shared["llm_light"]  # haiku-4.5 → sonnet fallback
    embedder = shared["embedder"]
    doc_store = shared["doc_store"]
    vector_retriever = shared["vector_retriever"]
    bm25_retriever = shared["bm25_retriever"]
    graph_retriever = shared["graph_retriever"]
    memory_store = shared["memory_store"]
    graph_registry = shared["graph_registry"]

    _retriever_kwargs = dict(
        vector_retriever=vector_retriever,
        bm25_retriever=bm25_retriever,
        graph_retriever=graph_retriever,
    )

    # Heavy: primary research synthesis — quality matters most here.
    research = ResearchAgent(
        llm_service=llm_heavy,
        embedder=embedder,
        doc_store=doc_store,
        **_retriever_kwargs,
    )
    memory_agent = MemoryAgent(store=memory_store)

    tier2_agents = [
        # Light: structured output, repetitive generation
        LearningAgent(llm_service=llm_light, **_retriever_kwargs),
        AnnotationAgent(llm_service=llm_light, **_retriever_kwargs),
        # FR-KG-02: GraphAgent uses the per-user registry so KnowledgeGraphView
        # reflects the calling user's own graph, not a shared corpus.
        GraphAgent(llm_service=llm_light, graph_registry=graph_registry),
        # Standard: analysis and dialogue
        SocraticAgent(llm_service=llm, **_retriever_kwargs),
        DiscoveryAgent(llm_service=llm, **_retriever_kwargs),
        ComparatorAgent(llm_service=llm, **_retriever_kwargs),
        TimelineAgent(llm_service=llm, **_retriever_kwargs),
        # Heavy: deep cross-document reasoning and long-form writing
        WritingAgent(llm_service=llm_heavy, **_retriever_kwargs),
        LiteratureAgent(llm_service=llm_heavy, **_retriever_kwargs),
        ContradictionAgent(llm_service=llm_heavy, **_retriever_kwargs),
        CrossDocAgent(llm_service=llm_heavy, **_retriever_kwargs),
    ]

    study_planner = StudyPlannerAgent(llm_service=llm_light)

    return Orchestrator(
        research=research,
        ui_agent=UIAgent(),
        fact_checker=FactChecker(llm=llm_light),
        memory_agent=memory_agent,
        memory_store=memory_store,
        extra_agents=[*tier2_agents, study_planner],
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    logger.info("arcana.startup")
    try:
        shared = _build_shared_resources()
        orchestrator = build_orchestrator(shared)
    except ValidationError as e:
        missing = [".".join(str(p) for p in err.get("loc", ())) for err in e.errors()]
        logger.error(
            "arcana.startup.missing_env",
            missing_fields=missing,
            error_count=e.error_count(),
        )
        raise
    except Exception as e:
        logger.error(
            "arcana.startup.failed",
            error=str(e),
            exc_type=type(e).__name__,
        )
        raise

    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_ingest_context] = lambda: IngestContext(
        stores=shared["stores"],
        embedder=shared["embedder"],
        llm=shared["llm"],
        graph_registry=shared["graph_registry"],
    )
    # Expose shared resources on app.state so routes can resolve them.
    app.state.shared = shared
    yield
    # Flush all per-user graphs on shutdown.
    await shared["graph_registry"].save_all()
    logger.info("arcana.shutdown")


def create_app() -> FastAPI:
    """Standard FastAPI app for `uvicorn api.main:app`."""
    app = FastAPI(title="Arcana", lifespan=lifespan)
    app.add_exception_handler(ArcanaError, arcana_error_handler)
    # CORS: allow the Next.js dev server. Tighten `allow_origins` for prod.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(chat_router)
    app.include_router(ingest_router)
    app.include_router(review_router)
    app.include_router(notebooks_router)
    app.include_router(feedback_router)
    app.include_router(analytics_router)
    app.include_router(graph_router)
    return app


app = create_app()
