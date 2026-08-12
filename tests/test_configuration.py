import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import system.configuration as configuration
import system.settings as settings
from app import app
from feeds.database import connect, initialize


class ConfigurationTest(unittest.TestCase):
    def setUp(self) -> None:
        initialize()
        self.client = app.test_client()

    def test_yaml_configuration_is_read_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ai.yaml"
            path.write_text("assistant:\n  model: test\n", encoding="utf-8")
            with patch.dict(configuration.CONFIG_FILES, {"ai": path}):
                response = self.client.get("/api/config/ai")
                self.assertEqual(200, response.status_code)
                self.assertIn("model: test", response.get_json()["content"])

                invalid = self.client.put(
                    "/api/config/ai", json={"content": "assistant: ["}
                )
                self.assertEqual(400, invalid.status_code)
                self.assertEqual(
                    "assistant:\n  model: test\n", path.read_text(encoding="utf-8")
                )

    def test_partial_ai_sections_receive_missing_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ai.yaml"
            path.write_text("assistant:\n  model: custom\n", encoding="utf-8")
            with patch.object(settings, "AI_CONFIG_PATH", path):
                config = settings.load_ai_config()
        self.assertEqual("custom", config["assistant"]["model"])
        self.assertEqual(180, config["assistant"]["timeout_seconds"])
        self.assertEqual(24, config["rag"]["candidate_k"])
        self.assertEqual(24, config["assistant"]["rag"]["candidate_k"])
        self.assertEqual(12, config["assistant"]["rag"]["session_message_limit"])
        self.assertEqual(800, config["summarizer"]["max_output_tokens"])
        self.assertFalse(config["summarizer"]["reasoning"])

    def test_assistant_rag_settings_are_independent_from_report_rag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ai.yaml"
            path.write_text(
                "rag:\n  candidate_k: 10\n  final_k: 4\n"
                "assistant:\n  rag:\n    candidate_k: 30\n    final_k: 8\n",
                encoding="utf-8",
            )
            with patch.object(settings, "AI_CONFIG_PATH", path):
                config = settings.load_ai_config()
        self.assertEqual(10, config["rag"]["candidate_k"])
        self.assertEqual(4, config["rag"]["final_k"])
        self.assertEqual(30, config["assistant"]["rag"]["candidate_k"])
        self.assertEqual(8, config["assistant"]["rag"]["final_k"])

    def test_invalid_prompt_configuration_is_not_saved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prompt.yaml"
            original = "assistant:\n  system: '{context}'\n"
            path.write_text(original, encoding="utf-8")
            with patch.dict(configuration.CONFIG_FILES, {"prompt": path}):
                response = self.client.put(
                    "/api/config/prompt",
                    json={"content": "assistant:\n  system: sans-variable"},
                )
            self.assertEqual(400, response.status_code)
            self.assertEqual(original, path.read_text(encoding="utf-8"))

    def test_sqlite_flush_preserves_durable_feedback(self) -> None:
        with connect() as connection:
            connection.execute(
                """INSERT INTO articles
                (id,title,url,source,category,collected_at,score,tags)
                VALUES ('test','Test','https://example.com','Test','Test','now',1,'')"""
            )
            connection.execute("""INSERT OR REPLACE INTO signal_feedback
                (article_id,candidate,snapshot_json,created_at,updated_at)
                VALUES ('durable','good','{}','now','now')""")
        response = self.client.delete("/api/storage/sqlite")
        self.assertEqual(200, response.status_code)
        with connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            feedback = connection.execute(
                "SELECT candidate FROM signal_feedback WHERE article_id='durable'"
            ).fetchone()
        self.assertEqual(0, count)
        self.assertEqual("good", feedback["candidate"])

    def test_chroma_flush_removes_only_the_configured_data_index(self) -> None:
        chroma_path = configuration.DATABASE_PATH.parent / "chroma"
        chroma_path.mkdir()
        (chroma_path / "index").write_text("test", encoding="utf-8")
        with patch.object(
            configuration,
            "load_ai_config",
            return_value={"rag": {"chroma_path": str(chroma_path)}},
        ):
            response = self.client.delete("/api/storage/chroma")
        self.assertEqual(200, response.status_code)
        self.assertFalse(chroma_path.exists())


if __name__ == "__main__":
    unittest.main()
