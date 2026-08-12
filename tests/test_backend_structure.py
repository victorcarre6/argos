import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

temporary_directory = tempfile.TemporaryDirectory()
os.environ["APP_ROOT"] = str(ROOT)
os.environ["DATABASE_PATH"] = str(Path(temporary_directory.name) / "monitoring.db")

from app import app  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from feeds.collection import (  # noqa: E402
    _finish_run,
    _pipeline_progress,
    _refresh_scores,
    _start_run,
)
from feeds.database import connect, initialize  # noqa: E402
from system import health as health_module  # noqa: E402
from system.settings import load_sources_config  # noqa: E402
from system.state import collection_state  # noqa: E402


class BackendStructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        initialize()
        cls.client = app.test_client()

    def test_health_route(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_pipeline_progress_maps_each_stage_to_its_weighted_range(self) -> None:
        _pipeline_progress("fetch", "Flux 1", 1, 2)
        self.assertEqual(22.5, collection_state["progress"]["percent"])
        _pipeline_progress("summary", "Rédaction", 1, 2)
        self.assertEqual(83.5, collection_state["progress"]["percent"])
        self.assertEqual("Rédaction", collection_state["progress"]["label"])
        _pipeline_progress("summarizer", "Condensation", 1, 2)
        self.assertEqual(94.5, collection_state["progress"]["percent"])

    def test_app_health_exposes_safe_telegram_status(self) -> None:
        health = self.client.get("/api/health/app").get_json()
        payload = health["telegram"]
        self.assertIn("ready", payload)
        self.assertIn("token_configured", payload)
        self.assertNotIn("token", payload)
        self.assertNotIn("chat_id", payload)
        self.assertIn("storage_bytes", health)
        self.assertIn("signals_total", health)
        self.assertIn("signals_p1", health)

    def test_automation_status_is_read_from_the_systemd_timer(self) -> None:
        timer_path = Path(temporary_directory.name) / "argos-collect.timer"
        timer_path.write_text(
            "[Timer]\nOnCalendar=*-*-* 09,13:30:00\nPersistent=true\n",
            encoding="utf-8",
        )
        original = health_module.TIMER_PATH
        health_module.TIMER_PATH = timer_path
        try:
            payload = health_module.automation_status()
        finally:
            health_module.TIMER_PATH = original
        self.assertEqual(["09:30", "13:30"], payload["times"])
        self.assertTrue(payload["persistent"])

    def test_summary_reads_the_fixed_markdown_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary_path = Path(directory) / "summary.md"
            summary_path.write_text("# Synthèse\n\nSignal important.", encoding="utf-8")
            original = health_module.SUMMARY_PATH
            health_module.SUMMARY_PATH = summary_path
            try:
                response = self.client.get("/api/summary")
            finally:
                health_module.SUMMARY_PATH = original
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            "# Synthèse\n\nSignal important.", response.get_json()["content"]
        )
        self.assertEqual("summary.md", response.get_json()["filename"])
        self.assertIsNotNone(response.get_json()["updated_at"])
        self.assertEqual("no-store", response.headers["Cache-Control"])

    def test_latest_summary_can_be_downloaded_with_its_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary_path = Path(directory) / "summary.md"
            reports = summary_path.parent / "reports"
            reports.mkdir()
            report = reports / "report_260812_1405.md"
            report.write_text("# Rapport téléchargeable", encoding="utf-8")
            original = health_module.SUMMARY_PATH
            health_module.SUMMARY_PATH = summary_path
            try:
                response = self.client.get("/api/summary/download")
                self.assertEqual(200, response.status_code)
                self.assertEqual(
                    b"# Rapport t\xc3\xa9l\xc3\xa9chargeable", response.get_data()
                )
                self.assertIn(
                    "report_260812_1405.md", response.headers["Content-Disposition"]
                )
                response.close()
            finally:
                health_module.SUMMARY_PATH = original

    def test_stats_use_the_active_source_catalog(self) -> None:
        config = load_sources_config()
        expected = sum(
            source.get("enabled", True) is not False
            for category in config["categories"]
            for source in category["sources"]
        )
        payload = self.client.get("/api/stats").get_json()
        self.assertEqual(expected, payload["sources"])
        self.assertIn("collected_sources", payload)
        self.assertIn("new_signals", payload)
        self.assertIn("priority_one_recent", payload)
        self.assertIn("last_collection_successful_sources", payload)

    def test_initialize_backfills_historical_first_seen_dates(self) -> None:
        with connect() as connection:
            connection.execute("""INSERT OR REPLACE INTO articles
                (id,title,url,source,category,collected_at,first_seen_at,score,tags)
                VALUES ('historical','Historical','https://history.example','Test',
                'Test','2026-08-10T08:00:00+00:00',NULL,1,'')""")
        initialize()
        with connect() as connection:
            first_seen = connection.execute(
                "SELECT first_seen_at FROM articles WHERE id='historical'"
            ).fetchone()[0]
        self.assertEqual("2026-08-10T08:00:00+00:00", first_seen)

    def test_collection_history_exposes_trigger_and_result(self) -> None:
        run_id = _start_run("systemd")
        _finish_run(
            run_id,
            "completed",
            {"sources": 2, "articles": 3, "errors": []},
        )
        payload = self.client.get("/api/collection/runs?limit=1").get_json()
        self.assertEqual("systemd", payload["runs"][0]["trigger"])
        self.assertEqual(3, payload["runs"][0]["result"]["articles"])

    def test_source_health_lists_failures_first(self) -> None:
        with connect() as connection:
            connection.execute("""INSERT OR REPLACE INTO source_health
                (source,category,url,last_error) VALUES
                ('AMD ROCm Blog','HPC','https://healthy.example',NULL),
                ('AMD Blog','HPC','https://failing.example','HTTP 404')""")
        sources = self.client.get("/api/health/sources").get_json()["sources"]
        self.assertEqual("AMD Blog", sources[0]["source"])

    def test_all_stored_scores_are_refreshed_from_current_configuration(self) -> None:
        collected_at = "2026-08-11T10:00:00+00:00"
        with connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO articles
                (id,title,url,source,category,summary,published_at,collected_at,
                score,tags) VALUES
                ('score-test','Agent release','https://score.example','Score Source',
                'Old category','',?, ?,0,'')""",
                (collected_at, collected_at),
            )
        config = {
            "collection": {"max_age_days": 14},
            "tags": {"Agents": ["agent"]},
            "categories": [
                {
                    "name": "Current category",
                    "sources": [{"name": "Score Source", "priorité": 1}],
                }
            ],
        }
        _refresh_scores(config, datetime(2026, 8, 11, 10, tzinfo=timezone.utc))
        with connect() as connection:
            row = connection.execute(
                "SELECT score,tags,category FROM articles WHERE id='score-test'"
            ).fetchone()
        self.assertEqual(60, row["score"])
        self.assertEqual("Agents", row["tags"])
        self.assertEqual("Current category", row["category"])

    def test_all_public_routes_are_registered(self) -> None:
        routes = {rule.rule for rule in app.url_map.iter_rules()}
        expected = {
            "/api/health",
            "/api/health/app",
            "/api/summary",
            "/api/health/sources",
            "/api/health/sources/test",
            "/api/sources",
            "/api/config/<name>",
            "/api/storage/sqlite",
            "/api/storage/chroma",
            "/api/articles",
            "/api/articles/favorites",
            "/api/articles/<article_id>/view",
            "/api/articles/<article_id>/feedback",
            "/api/stats",
            "/api/refresh",
            "/api/collection/runs",
            "/api/rag/index/status",
            "/api/assistant",
            "/api/assistant/session/<session_id>",
        }
        self.assertTrue(expected.issubset(routes))
        self.assertTrue(
            {
                "/api/collect",
                "/api/sources.yml",
                "/api/sources/yaml",
                "/api/assistant/status",
                "/api/clusters",
                "/api/clusters/<cluster_id>",
                "/api/viz/heatmap",
                "/api/viz/semantic-map",
            }.isdisjoint(routes)
        )

    def test_assistant_session_can_be_explicitly_cleared(self) -> None:
        with patch("rag.routes.clear_session") as clear_session:
            response = self.client.delete("/api/assistant/session/conversation-1")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "deleted"}, response.get_json())
        clear_session.assert_called_once_with("conversation-1")

    def test_article_can_be_hidden_without_being_deleted(self) -> None:
        with connect() as connection:
            connection.execute("""INSERT OR REPLACE INTO articles
                (id,title,url,source,category,collected_at,score,tags,view)
                VALUES ('hide-test','Hidden','https://hidden.example','Test',
                'Test','2026-08-11T10:00:00+00:00',10,'',1)""")
        response = self.client.patch(
            "/api/articles/hide-test/view", json={"view": False}
        )
        self.assertEqual(200, response.status_code)
        with connect() as connection:
            row = connection.execute(
                "SELECT view FROM articles WHERE id='hide-test'"
            ).fetchone()
        self.assertEqual(0, row["view"])
        with connect() as connection:
            feedback = connection.execute(
                """SELECT candidate,snapshot_json FROM signal_feedback
                WHERE article_id='hide-test'"""
            ).fetchone()
        self.assertEqual("bad", feedback["candidate"])
        self.assertIn('"title": "Hidden"', feedback["snapshot_json"])
        visible_ids = {
            article["id"]
            for article in self.client.get("/api/articles").get_json()["articles"]
        }
        self.assertNotIn("hide-test", visible_ids)

    def test_article_can_be_saved_as_a_good_candidate(self) -> None:
        with connect() as connection:
            connection.execute("""INSERT OR REPLACE INTO articles
                (id,title,url,source,category,collected_at,score,tags,view)
                VALUES ('favorite-test','Favorite','https://favorite.example',
                'Test','Test','2026-08-11T10:00:00+00:00',80,'agent',1)""")
        response = self.client.patch(
            "/api/articles/favorite-test/feedback", json={"candidate": "good"}
        )
        self.assertEqual(200, response.status_code)
        articles = self.client.get("/api/articles?limit=500").get_json()["articles"]
        favorite = next(item for item in articles if item["id"] == "favorite-test")
        self.assertEqual("good", favorite["candidate"])

    def test_favorites_are_durable_limited_and_sorted_by_collection_date(self) -> None:
        with connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO signal_feedback
                (article_id,candidate,snapshot_json,created_at,updated_at)
                VALUES ('older','good',?, 'now','now'),
                       ('newer','good',?, 'now','now')""",
                (
                    '{"id":"older","collected_at":"2099-08-10T10:00:00+00:00"}',
                    '{"id":"newer","collected_at":"2099-08-11T10:00:00+00:00"}',
                ),
            )
        payload = self.client.get("/api/articles/favorites?limit=1").get_json()
        self.assertEqual(1, len(payload["articles"]))
        self.assertEqual("newer", payload["articles"][0]["id"])


if __name__ == "__main__":
    unittest.main()
