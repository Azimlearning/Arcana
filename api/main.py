"""FastAPI app factory + uvicorn entry point.

`uvicorn api.main:app` boots the slice. At startup (lifespan):
  1. `configure_logging()` once - structlog JSON.
  2. Build the orchestrator dependency chain from `Settings`. Real
     Anthropic / OpenAI / Pinecone clients are constructed here; the
     slice can't boot without the three required keys.
  3. Wire the orchestrator into the chat route via `dependency_overrides`.

Auth, CORS, and Firebase Admin SDK init are intentionally absent for the
slice (P1 §1.8).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import ValidationError

from api.core.errors import ArcanaError, arcana_error_handler
from api.core.logging import configure_logging, get_logger
from api.routes.chat import get_orchestrator
from api.routes.chat import router as chat_router

logger = get_logger(__name__)


def build_orchestrator():
    """Construct the production orchestrator from `Settings`.

    Imports are local to keep `from api.main import create_app` cheap
    in test code that builds a minimal app without real providers."""
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
    from api.core.settings import get_settings
    from api.embeddings.service import EmbeddingService
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

    vector_retriever = VectorRetriever(vector_store=vector_store, embedder=embedder)
    bm25_retriever = BM25Retriever(chunk_store=chunk_store)
    graph_retriever = GraphRetriever(
        graph_store=graph_store,
        chunk_store=chunk_store,
        llm=llm,
    )

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
    memory_store = InMemoryMemoryStore()
    memory_agent = MemoryAgent(store=memory_store)

    tier2_agents = [
        LearningAgent(llm_service=llm, **_retriever_kwargs),
        SocraticAgent(llm_service=llm, **_retriever_kwargs),
        DiscoveryAgent(llm_service=llm, **_retriever_kwargs),
        WritingAgent(llm_service=llm, **_retriever_kwargs),
        # Slice 7: dormant-UIBlock activators + supporting trio (FR-AGT-06)
        GraphAgent(llm_service=llm, graph_store=graph_store),
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
        orchestrator = build_orchestrator()
    except ValidationError as e:
        # Missing required env vars - surface a structured log so operators
        # see WHICH keys are missing instead of a raw stack trace.
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
    yield
    logger.info("arcana.shutdown")


def create_app() -> FastAPI:
    """Standard FastAPI app for `uvicorn api.main:app`. Use only in
    production / dev runs - tests build a leaner app that skips the
    real provider chain."""
    app = FastAPI(title="Arcana", lifespan=lifespan)
    app.add_exception_handler(ArcanaError, arcana_error_handler)
    app.include_router(chat_router)
    return app


app = create_app()
