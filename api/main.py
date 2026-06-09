"""FastAPI app factory + uvicorn entry point.

`uvicorn api.main:app` boots the slice. At startup (lifespan):
  1. `configure_logging()` once - structlog JSON.
  2. Build the shared infrastructure (stores, embedder, llm) from `Settings`.
  3. Build the orchestrator from shared infra.
  4. Wire both the orchestrator and the ingest context via dependency_overrides
     so the chat route and the ingest route share the SAME store instances —
     a freshly ingested document is visible to the next chat turn without a
     server restart.

Auth, Firebase Admin SDK init are intentionally absent for the slice (P1 §1.8).
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
from api.routes.chat import get_orchestrator
from api.routes.chat import router as chat_router
from api.routes.ingest import IngestContext, get_ingest_context
from api.routes.ingest import router as ingest_router

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

    settings = get_settings()

    llm = LLMService(settings=settings)
    embedder = EmbeddingService(settings=settings)

    vector_store = PineconeVectorStore(
        api_key=settings.pinecone_api_key.get_secret_value(),
        index_name=settings.pinecone_index,
    )
    graph_store = NetworkXGraphStore(
        persist_path=settings.local_storage_path / "graph.json",
    )
    doc_store = FilesystemDocStore(root=settings.local_storage_path)
    chunk_store = JsonlChunkStore(root=settings.local_storage_path)

    stores = Stores(
        doc=doc_store,
        vector=vector_store,
        graph=graph_store,
        chunks=chunk_store,
    )

    vector_retriever = VectorRetriever(vector_store=vector_store, embedder=embedder)
    bm25_retriever = BM25Retriever(chunk_store=chunk_store)
    graph_retriever = GraphRetriever(
        graph_store=graph_store,
        chunk_store=chunk_store,
        llm=llm,
    )
    memory_store = InMemoryMemoryStore()

    return {
        "settings": settings,
        "llm": llm,
        "embedder": embedder,
        "stores": stores,
        "doc_store": doc_store,
        "vector_retriever": vector_retriever,
        "bm25_retriever": bm25_retriever,
        "graph_retriever": graph_retriever,
        "memory_store": memory_store,
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

    llm = shared["llm"]
    embedder = shared["embedder"]
    doc_store = shared["doc_store"]
    stores = shared["stores"]
    vector_retriever = shared["vector_retriever"]
    bm25_retriever = shared["bm25_retriever"]
    graph_retriever = shared["graph_retriever"]
    memory_store = shared["memory_store"]

    _retriever_kwargs = dict(
        vector_retriever=vector_retriever,
        bm25_retriever=bm25_retriever,
        graph_retriever=graph_retriever,
    )

    research = ResearchAgent(
        llm_service=llm,
        embedder=embedder,
        doc_store=doc_store,
        **_retriever_kwargs,
    )
    memory_agent = MemoryAgent(store=memory_store)

    tier2_agents = [
        LearningAgent(llm_service=llm, **_retriever_kwargs),
        SocraticAgent(llm_service=llm, **_retriever_kwargs),
        DiscoveryAgent(llm_service=llm, **_retriever_kwargs),
        WritingAgent(llm_service=llm, **_retriever_kwargs),
        # Slice 7: dormant-UIBlock activators + supporting trio (FR-AGT-06)
        GraphAgent(llm_service=llm, graph_store=stores.graph),
        LiteratureAgent(llm_service=llm, **_retriever_kwargs),
        ContradictionAgent(llm_service=llm, **_retriever_kwargs),
        CrossDocAgent(llm_service=llm, **_retriever_kwargs),
        ComparatorAgent(llm_service=llm, **_retriever_kwargs),
        TimelineAgent(llm_service=llm, **_retriever_kwargs),
        AnnotationAgent(llm_service=llm, **_retriever_kwargs),
    ]

    return Orchestrator(
        research=research,
        ui_agent=UIAgent(),
        fact_checker=FactChecker(llm=llm),
        memory_agent=memory_agent,
        memory_store=memory_store,
        extra_agents=tier2_agents,
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
    )
    yield
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
    return app


app = create_app()
