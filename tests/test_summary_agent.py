import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("APP_ROOT", str(ROOT))
temporary_directory = tempfile.TemporaryDirectory()
os.environ.setdefault(
    "DATABASE_PATH", str(Path(temporary_directory.name) / "monitoring.db")
)

from feeds.collection import _refresh_ai_outputs  # noqa: E402
from feeds.database import connect, initialize  # noqa: E402
from rag.summary_agent import (  # noqa: E402
    _build_graph,
    _new_p1_signals,
    _draft_node,
    _references_markdown,
    _source_block,
)


class SummaryAgentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        initialize()

    def test_context_distinguishes_new_and_related_signals(self) -> None:
        new = [{"title": "Nouveau", "source": "A", "url": "u1", "summary": "s"}]
        related = [{"title": "Ancien", "source": "B", "url": "u2", "summary": "s"}]
        block = _source_block(new, related)
        self.assertIn("[1] [NOUVEAU]", block)
        self.assertIn("[2] [CONTEXTE]", block)
        references = _references_markdown(new, related)
        self.assertIn("[1] [Nouveau](u1)", references)
        self.assertIn("[2] [Ancien](u2)", references)

    def test_selection_keeps_only_the_forty_most_recent_publications(self) -> None:
        with connect() as connection:
            for index in range(41):
                timestamp = (
                    f"2099-08-{index // 24 + 10:02d}T{index % 24:02d}:00:00+00:00"
                )
                connection.execute(
                    """INSERT OR REPLACE INTO articles
                    (id,title,url,source,category,summary,published_at,collected_at,
                    first_seen_at,score,tags,view) VALUES (?,?,?,?,?,?,?,?,?,?,?,1)""",
                    (
                        f"top-{index:02d}",
                        f"Signal {index}",
                        f"https://example.com/{index}",
                        "Source P1",
                        "Test",
                        "",
                        timestamp,
                        timestamp,
                        timestamp,
                        1,
                        "",
                    ),
                )
        config = {
            "collection": {"max_age_days": 7},
            "categories": [
                {"sources": [{"name": "Source P1", "priorité": 1, "enabled": True}]}
            ],
        }
        with (
            patch("rag.summary_agent.load_sources_config", return_value=config),
            patch(
                "rag.summary_agent.load_ai_config",
                return_value={"summary": {"top_n": 40}},
            ),
            patch(
                "rag.summary_agent.SUMMARY_PATH",
                Path(temporary_directory.name) / "missing-summary.md",
            ),
        ):
            signals = _new_p1_signals()
        self.assertEqual(40, len(signals))
        self.assertEqual("top-40", signals[0]["id"])
        self.assertNotIn("top-00", {signal["id"] for signal in signals})

    def test_graph_stops_without_new_p1_signals(self) -> None:
        with patch("rag.summary_agent._new_p1_signals", return_value=[]):
            result = _build_graph().invoke({})
        self.assertEqual([], result["signals"])
        self.assertNotIn("document", result)

    def test_report_is_written_with_one_global_retrieval_and_one_generation(
        self,
    ) -> None:
        signals = [
            {
                "id": "1",
                "title": "Signal A",
                "source": "Source",
                "url": "https://example.com/a",
                "summary": "Résumé A",
            },
            {
                "id": "2",
                "title": "Signal B",
                "source": "Source",
                "url": "https://example.com/b",
                "summary": "Résumé B",
            },
        ]
        model = Mock()
        model.invoke.return_value.content = "Analyse globale."
        with (
            patch("rag.summary_agent.retrieve", return_value=[]) as retrieve,
            patch("rag.summary_agent.chat_model", return_value=model),
            patch("rag.summary_agent.load_prompt", return_value="instruction"),
        ):
            result = _draft_node({"signals": signals})
        retrieve.assert_called_once()
        model.invoke.assert_called_once_with("instruction")
        self.assertEqual("Points clés", result["drafts"][0]["title"])

    def test_summary_runs_only_after_successful_indexing(self) -> None:
        errors = []
        with (
            patch("rag.indexing.sync_index", side_effect=RuntimeError("Nyx down")),
            patch("rag.summary_agent.generate_summary") as generate,
            patch("rag.summarizer.generate_telegram_summary") as summarize,
            patch("system.telegram.send_summary_if_pending") as send,
        ):
            _index, summary, summarizer, telegram = _refresh_ai_outputs(errors)
        self.assertIsNone(summary)
        self.assertIsNone(summarizer)
        self.assertIsNone(telegram)
        generate.assert_not_called()
        summarize.assert_not_called()
        send.assert_not_called()
        self.assertIn("Index RAG: Nyx down", errors)

        expected = {"generated": True, "signals": 2, "sections": 1}
        with (
            patch("rag.indexing.sync_index", return_value={"indexed": 2}),
            patch("rag.summary_agent.generate_summary", return_value=expected),
            patch(
                "rag.summarizer.generate_telegram_summary",
                return_value={"generated": True, "chars": 3000},
            ) as summarize,
            patch("system.telegram.telegram_message_limit", return_value=3900),
            patch(
                "system.telegram.send_summary_if_pending",
                return_value={"sent": True, "messages": 1},
            ) as send,
        ):
            _index, summary, summarizer, telegram = _refresh_ai_outputs([])
        self.assertEqual(expected, summary)
        self.assertTrue(summarizer["generated"])
        self.assertTrue(telegram["sent"])
        summarize.assert_called_once_with(3900, progress=ANY)
        send.assert_called_once()

    def test_summarizer_failure_prevents_raw_report_delivery(self) -> None:
        errors = []
        with (
            patch("rag.indexing.sync_index", return_value={"indexed": 2}),
            patch(
                "rag.summary_agent.generate_summary", return_value={"generated": True}
            ),
            patch(
                "rag.summarizer.generate_telegram_summary",
                side_effect=RuntimeError("résumé trop long"),
            ),
            patch("system.telegram.send_summary_if_pending") as send,
        ):
            _index, _summary, summarizer, telegram = _refresh_ai_outputs(errors)

        self.assertIsNone(summarizer)
        self.assertIsNone(telegram)
        send.assert_not_called()
        self.assertIn("Summarizer: résumé trop long", errors)


if __name__ == "__main__":
    unittest.main()
