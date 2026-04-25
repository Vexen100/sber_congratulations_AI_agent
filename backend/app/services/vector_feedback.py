from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimilarExample:
    comment: str
    text: str
    rating: int
    holiday: str
    greeting_id: int


class _NoopFeedbackVectorDB:
    def save_feedback_vector(self, **_kwargs: Any) -> str:  # noqa: ANN401
        return ""

    def find_similar(self, **_kwargs: Any) -> list[dict]:  # noqa: ANN401
        return []

    def get_statistics(self) -> dict:
        return {"total": 0, "avg_rating": 0}


class FeedbackVectorDB:
    """Vector DB wrapper for manager-approved examples.

    Important constraints:
    - Must not import heavy deps at module import time.
    - Must be safe to run in CI/offline mode (feature-flagged).
    """

    def __init__(self, *, persist_directory: str) -> None:
        # Lazy imports: only when the feature is actually enabled.
        import chromadb  # type: ignore
        from sentence_transformers import SentenceTransformer  # type: ignore

        directory = (Path(__file__).resolve().parents[2] / persist_directory).resolve()
        directory.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(directory))
        self._encoder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        self._collection = self._client.get_or_create_collection(
            name="manager_feedback",
            metadata={"hnsw:space": "cosine"},
        )

    def _get_embedding(self, text: str) -> list[float]:
        return self._encoder.encode(text).tolist()

    def save_feedback_vector(
        self,
        *,
        greeting_id: int,
        greeting_text: str,
        client_profession: str,
        holiday_title: str,
        rating: int,
        comment: str = "",
    ) -> str:
        profession = (client_profession or "").strip() or "Неизвестно"
        title = (holiday_title or "").strip()
        text_for_embedding = "\n".join(
            [
                f"Профессия клиента: {profession}",
                f"Праздник: {title}",
                "Текст:",
                greeting_text,
                f"Комментарий: {comment}",
            ]
        )

        doc_id = f"greeting_{greeting_id}_{dt.datetime.now(dt.timezone.utc).timestamp()}"
        self._collection.add(
            ids=[doc_id],
            embeddings=[self._get_embedding(text_for_embedding)],
            metadatas=[
                {
                    "greeting_id": greeting_id,
                    "client_profession": profession,
                    "holiday_title": title,
                    "rating": int(rating),
                    "comment": comment,
                }
            ],
            documents=[greeting_text],
        )
        return doc_id

    def find_similar(
        self,
        *,
        client_profession: str,
        holiday_title: str,
        limit: int = 3,
        min_rating: int = 4,
    ) -> list[dict]:
        if self._collection.count() == 0:
            return []

        profession = (client_profession or "").strip()
        title = (holiday_title or "").strip()
        if not profession or not title:
            return []

        query_text = f"Профессия клиента: {profession}\nПраздник: {title}\n"
        try:
            results = self._collection.query(
                query_embeddings=[self._get_embedding(query_text)],
                n_results=min(int(limit), self._collection.count()),
                where={
                    "$and": [
                        {"client_profession": profession},
                        {"holiday_title": title},
                        {"rating": {"$gte": int(min_rating)}},
                    ]
                },
            )
        except Exception as e:
            log.warning("vector db query failed: %s", e)
            return []

        examples: list[dict] = []
        ids = (results or {}).get("ids") or []
        if not ids:
            return []
        for i, _doc_id in enumerate(ids[0]):
            doc_text = ((results or {}).get("documents") or [[""]])[0][i] or ""
            meta = ((results or {}).get("metadatas") or [[{}]])[0][i] or {}
            examples.append(
                {
                    "comment": meta.get("comment", "") or "",
                    "text": doc_text,
                    "rating": int(meta.get("rating", 0) or 0),
                    "holiday": meta.get("holiday_title", "") or "",
                    "greeting_id": int(meta.get("greeting_id", 0) or 0),
                }
            )
        return examples

    def get_statistics(self) -> dict:
        try:
            all_data = self._collection.get()
            metas = (all_data or {}).get("metadatas") or []
            ratings = [int(m.get("rating", 0) or 0) for m in metas if m]
            return {
                "total": len(ratings),
                "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
            }
        except Exception as e:
            log.warning("vector db stats failed: %s", e)
            return {"total": 0, "avg_rating": 0}


_db: FeedbackVectorDB | _NoopFeedbackVectorDB | None = None


def _get_db() -> FeedbackVectorDB | _NoopFeedbackVectorDB:
    global _db  # noqa: PLW0603
    if _db is not None:
        return _db
    if not bool(getattr(settings, "vector_feedback_enabled", False)):
        _db = _NoopFeedbackVectorDB()
        return _db
    try:
        _db = FeedbackVectorDB(persist_directory=str(getattr(settings, "vector_db_path", "")))
    except Exception as e:
        log.warning("vector db init failed; disabling: %s", e)
        _db = _NoopFeedbackVectorDB()
    return _db


class _VectorDBFacade:
    def save_feedback_vector(self, **kwargs: Any) -> str:  # noqa: ANN401
        return _get_db().save_feedback_vector(**kwargs)

    def find_similar(self, **kwargs: Any) -> list[dict]:  # noqa: ANN401
        return _get_db().find_similar(**kwargs)

    def get_statistics(self) -> dict:
        return _get_db().get_statistics()


feedback_db = _VectorDBFacade()
