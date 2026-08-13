import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("APP_ROOT", str(ROOT))
temporary_directory = tempfile.TemporaryDirectory()
os.environ.setdefault(
    "DATABASE_PATH", str(Path(temporary_directory.name) / "monitoring.db")
)

from feeds.database import initialize  # noqa: E402
from feeds.collection import _is_recent, _score, _source_tags  # noqa: E402
from rag.indexing import index_status, metadata_key, sync_index  # noqa: E402
import rag.retrieve as retrieve_module  # noqa: E402
from rag.retrieve import QueryPlan, chroma_filter  # noqa: E402


class RagMetadataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        initialize()

    def test_metadata_keys_are_stable_and_chroma_safe(self) -> None:
        self.assertEqual(metadata_key("IA Agentique"), "key_ia_agentique")
        self.assertEqual(metadata_key("Cybersécurité"), "key_cybersecurite")

    def test_feed_age_filter_keeps_recent_and_undated_entries(self) -> None:
        from datetime import datetime, timedelta, timezone

        recent = (datetime.now(timezone.utc) - timedelta(days=13)).isoformat()
        old = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        self.assertTrue(_is_recent(recent, 14))
        self.assertFalse(_is_recent(old, 14))
        self.assertTrue(_is_recent("", 14))

    def test_score_combines_relevance_priority_and_freshness(self) -> None:
        now = datetime(2026, 8, 11, tzinfo=timezone.utc)
        recent = now.isoformat()
        old = (now - timedelta(days=14)).isoformat()
        taxonomy = {"Agents": ["agent", "agentic"], "RAG": ["RAG"]}
        p1, tags = _score("Agent RAG", "", taxonomy, 1, recent, recent, 14, now)
        p3, _ = _score("Agent RAG", "", taxonomy, 3, recent, recent, 14, now)
        stale, _ = _score("Agent RAG", "", taxonomy, 1, old, old, 14, now)
        self.assertEqual(["Agents", "RAG"], tags)
        self.assertEqual(70, p1)
        self.assertEqual(45, p3)
        self.assertEqual(59, stale)

    def test_tag_aliases_are_normalized_and_respect_word_boundaries(self) -> None:
        now = datetime(2026, 8, 11, tzinfo=timezone.utc)
        taxonomy = {"Agents": ["agent", "agentic", "multi-agent"]}
        _score_value, tags = _score(
            "An agentic multi-agent framework",
            "",
            taxonomy,
            3,
            now.isoformat(),
            now.isoformat(),
            14,
            now,
        )
        _score_value, false_positive = _score(
            "A reagent release",
            "",
            taxonomy,
            3,
            now.isoformat(),
            now.isoformat(),
            14,
            now,
        )
        self.assertEqual(["Agents"], tags)
        self.assertEqual([], false_positive)

    def test_release_sources_force_the_releases_tag(self) -> None:
        self.assertEqual(
            ["agents", "deploiement", "releases"],
            _source_tags(
                {
                    "name": "LangChain Releases",
                    "keys": ["IA Agentique", "Orchestration"],
                }
            ),
        )
        self.assertEqual(
            ["agents"],
            _source_tags({"name": "LangChain Blog", "keys": ["IA Agentique"]}),
        )
        score, tags = _score(
            "v1.2.0",
            "Corrections diverses",
            {"releases": ["release"]},
            3,
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat(),
            14,
            forced_tags=["releases"],
        )
        self.assertEqual(["releases"], tags)
        self.assertGreaterEqual(score, 20)

    def test_query_plan_becomes_an_explicit_chroma_filter(self) -> None:
        plan = QueryPlan(
            query="agents autonomes",
            categories=["Frameworks"],
            priorities=[1, 2],
            keys=["IA Agentique"],
            min_score=55,
        )
        self.assertEqual(
            chroma_filter(plan),
            {
                "$and": [
                    {"category": {"$in": ["Frameworks"]}},
                    {"priority": {"$in": [1, 2]}},
                    {"key_ia_agentique": True},
                    {"score": {"$gte": 55}},
                ]
            },
        )

    def test_assistant_retrieval_uses_its_own_candidate_limit(self) -> None:
        store = unittest.mock.Mock()
        store.similarity_search_with_relevance_scores.return_value = []
        report_config = {"candidate_k": 10, "final_k": 4, "query_model": "report"}
        assistant_config = {
            "candidate_k": 30,
            "final_k": 8,
            "query_model": "assistant",
            "session_message_limit": 12,
        }
        with (
            patch.object(retrieve_module, "rag_config", return_value=report_config),
            patch.object(
                retrieve_module,
                "load_ai_config",
                return_value={"assistant": {"rag": assistant_config}},
            ),
            patch.object(
                retrieve_module,
                "_query_plan",
                return_value=QueryPlan(query="agents"),
            ) as query_plan,
            patch.object(retrieve_module, "vector_store", return_value=store),
        ):
            self.assertEqual(
                [], retrieve_module.retrieve("agents", profile="assistant")
            )
        query_plan.assert_called_once_with(
            "agents", {**report_config, **assistant_config}
        )
        self.assertEqual(
            30,
            store.similarity_search_with_relevance_scores.call_args.kwargs["k"],
        )

    def test_failed_indexing_stays_pending_until_the_next_success(self) -> None:
        with patch("rag.indexing._sync_index", side_effect=RuntimeError("Nyx down")):
            with self.assertRaisesRegex(RuntimeError, "Nyx down"):
                sync_index()
        failed = index_status()
        self.assertTrue(failed["pending"])
        self.assertEqual("Nyx down", failed["last_error"])

        expected = {"indexed": 2, "unchanged": 3, "deleted_chunks": 0}
        with patch("rag.indexing._sync_index", return_value=expected):
            self.assertEqual(expected, sync_index())
        recovered = index_status()
        self.assertFalse(recovered["pending"])
        self.assertIsNone(recovered["last_error"])
        self.assertIsNotNone(recovered["last_success_at"])


if __name__ == "__main__":
    unittest.main()
