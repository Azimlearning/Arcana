"""Notebook CRUD routes — FR-USR-03, FR-USR-06.

Endpoints:
  POST   /notebooks           — create a new notebook
  GET    /notebooks           — list notebooks for the current user
  GET    /notebooks/{id}      — get a single notebook
  DELETE /notebooks/{id}      — delete a notebook

All routes require authentication (get_current_user dependency).
Per-user isolation is enforced by the NotebookStore — each operation
is keyed on current_user.uid.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from api.core.auth import CurrentUser, get_current_user
from api.core.logging import get_logger
from api.stores.notebook_store import NotebookStore

logger = get_logger(__name__)

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


# ── Request / response schemas ────────────────────────────────────────────────


class NotebookCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class NotebookOut(BaseModel):
    id: str
    userId: str
    title: str
    createdAt: str
    updatedAt: str
    docCount: int


class NotebookListOut(BaseModel):
    notebooks: list[NotebookOut]


class NotebookDeleteOut(BaseModel):
    deleted: str


# ── Helpers ───────────────────────────────────────────────────────────────────


def _store(request: Request) -> NotebookStore:
    try:
        return request.app.state.shared["notebook_store"]
    except (AttributeError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Notebook store not initialised.",
        ) from exc


def _nb_out(nb) -> NotebookOut:
    return NotebookOut(
        id=nb.id,
        userId=nb.user_id,
        title=nb.title,
        createdAt=nb.created_at,
        updatedAt=nb.updated_at,
        docCount=nb.doc_count,
    )


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post("", response_model=NotebookOut, status_code=201)
async def create_notebook(
    body: NotebookCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> NotebookOut:
    store = _store(request)
    nb = await store.create(user_id=current_user.uid, title=body.title)
    logger.info("notebook.created", user=current_user.uid, notebook_id=nb.id, title=nb.title)
    return _nb_out(nb)


@router.get("", response_model=NotebookListOut)
async def list_notebooks(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> NotebookListOut:
    store = _store(request)
    notebooks = await store.list(current_user.uid)
    return NotebookListOut(notebooks=[_nb_out(nb) for nb in notebooks])


@router.get("/{notebook_id}", response_model=NotebookOut)
async def get_notebook(
    notebook_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> NotebookOut:
    store = _store(request)
    nb = await store.get(user_id=current_user.uid, notebook_id=notebook_id)
    if nb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found.",
        )
    return _nb_out(nb)


@router.delete("/{notebook_id}", response_model=NotebookDeleteOut)
async def delete_notebook(
    notebook_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> NotebookDeleteOut:
    store = _store(request)
    deleted = await store.delete(user_id=current_user.uid, notebook_id=notebook_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found.",
        )
    logger.info("notebook.deleted", user=current_user.uid, notebook_id=notebook_id)
    return NotebookDeleteOut(deleted=notebook_id)
