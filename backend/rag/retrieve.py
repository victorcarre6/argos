from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from rag.indexing import metadata_key, rag_config, vector_store
from rag.models import chat_model
from rag.prompts import load_prompt
from system.settings import SOURCE_KEYS, load_sources_config


class QueryPlan(BaseModel):
    query: str = Field(description="Requête sémantique sans les contraintes de filtre")
    categories: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    keys: list[str] = Field(default_factory=list)
    priorities: list[int] = Field(default_factory=list)
    published_after: str | None = None
    published_before: str | None = None
    min_score: int | None = None


def _query_plan(prompt: str) -> QueryPlan:
    catalog = load_sources_config()
    categories = [category["name"] for category in catalog.get("categories", [])]
    sources = [
        source["name"]
        for category in catalog.get("categories", [])
        for source in category.get("sources", [])
    ]
    instruction = load_prompt(
        "retrieval",
        "query_plan",
        categories=categories,
        sources=sources,
        keys=sorted(SOURCE_KEYS),
        question=prompt,
    )
    planner = chat_model(
        rag_config().get("query_model") or None
    ).with_structured_output(QueryPlan, method="json_schema")
    plan = planner.invoke(instruction)
    plan.query = plan.query.strip() or prompt
    plan.categories = [item for item in plan.categories if item in categories]
    plan.sources = [item for item in plan.sources if item in sources]
    plan.keys = [item for item in plan.keys if item in SOURCE_KEYS]
    plan.priorities = [item for item in plan.priorities if item in {1, 2, 3}]
    return plan


def _date_filter(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return None


def chroma_filter(plan: QueryPlan) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []
    if plan.categories:
        clauses.append({"category": {"$in": plan.categories}})
    if plan.sources:
        clauses.append({"source": {"$in": plan.sources}})
    if plan.priorities:
        clauses.append({"priority": {"$in": plan.priorities}})
    clauses.extend({metadata_key(key): True} for key in plan.keys)
    if plan.min_score is not None:
        clauses.append({"score": {"$gte": max(0, min(100, plan.min_score))}})
    if after := _date_filter(plan.published_after):
        clauses.append({"published_timestamp": {"$gte": after}})
    if before := _date_filter(plan.published_before):
        clauses.append({"published_timestamp": {"$lte": before}})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def retrieve(prompt: str, limit: int | None = None) -> list[dict[str, Any]]:
    config = rag_config()
    final_limit = limit or int(config.get("final_k", 6))
    try:
        plan = _query_plan(prompt)
    except Exception:
        plan = QueryPlan(query=prompt)
    candidates = vector_store().similarity_search_with_relevance_scores(
        plan.query,
        k=int(config.get("candidate_k", 24)),
        filter=chroma_filter(plan),
    )
    results = []
    seen_articles = set()
    for document, score in candidates:
        metadata = document.metadata
        if metadata["article_id"] in seen_articles:
            continue
        seen_articles.add(metadata["article_id"])
        results.append(
            {
                "id": metadata["article_id"],
                "title": metadata["title"],
                "summary": document.page_content,
                "url": metadata["url"],
                "source": metadata["source"],
                "category": metadata["category"],
                "published_at": metadata["published_at"],
                "similarity": float(score),
            }
        )
        if len(results) >= final_limit:
            break
    return results
