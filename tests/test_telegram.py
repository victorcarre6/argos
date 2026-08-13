import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("APP_ROOT", str(ROOT))

from system import telegram  # noqa: E402


class TelegramDeliveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        directory = Path(self.temporary_directory.name)
        self.summary_path = directory / "summary.md"
        self.config_path = directory / "telegram.yaml"
        self.config_path.write_text(
            'enabled: true\nbot_token_env: TEST_TELEGRAM_TOKEN\nchat_id: "42"\n'
            "max_message_chars: 500\n",
            encoding="utf-8",
        )
        self.summary_path.write_text(
            "# Rapport\n\n" + "signal " * 200, encoding="utf-8"
        )
        self.telegram_path = self.summary_path.with_suffix(".telegram.txt")
        self.telegram_path.write_text(
            "Rapport 12-08 10:00\n\nUne évolution importante.", encoding="utf-8"
        )
        self.summary_path.with_suffix(".telegram_part_1.txt").write_text(
            "1. Sujet\n\nRapport thématique.", encoding="utf-8"
        )
        self.paths = (
            patch.object(telegram, "SUMMARY_PATH", self.summary_path),
            patch.object(telegram, "TELEGRAM_PATH", self.config_path),
            patch.dict(os.environ, {"TEST_TELEGRAM_TOKEN": "secret-token"}),
        )
        for context in self.paths:
            context.start()

    def tearDown(self) -> None:
        for context in reversed(self.paths):
            context.stop()
        self.temporary_directory.cleanup()

    def test_summary_is_sent_as_one_message_and_marked_as_delivered(self) -> None:
        response = Mock(ok=True, status_code=200)
        with patch("system.telegram.requests.post", return_value=response) as post:
            result = telegram.send_summary_if_pending()
            second = telegram.send_summary_if_pending()

        self.assertTrue(result["sent"])
        self.assertEqual(1, result["messages"])
        self.assertEqual("already_sent", second["reason"])
        self.assertEqual(1, post.call_count)
        self.assertTrue(telegram._delivery_path().exists())
        self.assertEqual(
            self.telegram_path.read_text(encoding="utf-8"),
            post.call_args.kwargs["json"]["text"],
        )

    def test_help_and_multiple_part_requests_use_latest_report(self) -> None:
        response = Mock(ok=True, status_code=200)
        updates = [
            {"message": {"chat": {"id": 42}, "text": "/help"}},
            {"message": {"chat": {"id": 42}, "text": "1"}},
            {"message": {"chat": {"id": 42}, "text": "1"}},
        ]

        with patch("system.telegram.requests.post", return_value=response) as post:
            for update in updates:
                telegram.handle_update(update)

        self.assertEqual(3, post.call_count)
        self.assertIn(
            "plusieurs parties", post.call_args_list[0].kwargs["json"]["text"]
        )
        self.assertEqual(
            "1. Sujet\n\nRapport thématique.",
            post.call_args_list[1].kwargs["json"]["text"],
        )

    def test_update_from_unconfigured_chat_is_ignored(self) -> None:
        with patch("system.telegram.requests.post") as post:
            telegram.handle_update({"message": {"chat": {"id": 99}, "text": "1"}})

        post.assert_not_called()

    def test_download_sends_latest_markdown_report_as_document(self) -> None:
        report = self.summary_path.parent / "reports" / "report_260813_1800.md"
        report.parent.mkdir()
        report.write_text("# Rapport complet\n", encoding="utf-8")
        response = Mock(ok=True, status_code=200)

        with patch("system.telegram.requests.post", return_value=response) as post:
            telegram.handle_update(
                {"message": {"chat": {"id": 42}, "text": "/download"}}
            )

        self.assertTrue(post.call_args.args[0].endswith("/sendDocument"))
        self.assertEqual({"chat_id": "42"}, post.call_args.kwargs["data"])
        self.assertEqual(
            "report_260813_1800.md",
            post.call_args.kwargs["files"]["document"][0],
        )
        self.assertEqual("text/markdown", post.call_args.kwargs["files"]["document"][2])

    def test_failed_delivery_remains_pending_and_does_not_leak_token(self) -> None:
        response = Mock(ok=False, status_code=500)
        response.json.return_value = {"description": "temporary failure"}
        with patch("system.telegram.requests.post", return_value=response):
            with self.assertRaises(RuntimeError) as raised:
                telegram.send_summary_if_pending()

        self.assertNotIn("secret-token", str(raised.exception))
        self.assertTrue(telegram.telegram_status()["report_pending"])
        self.assertFalse(telegram._delivery_path().exists())

    def test_summary_is_sent_to_each_configured_recipient(self) -> None:
        self.config_path.write_text(
            "enabled: true\n"
            "bot_token_env: TEST_TELEGRAM_TOKEN\n"
            "chat_ids:\n"
            '  user1: "42"\n'
            '  user2: "84"\n'
            "max_message_chars: 500\n",
            encoding="utf-8",
        )
        response = Mock(ok=True, status_code=200)

        with patch("system.telegram.requests.post", return_value=response) as post:
            result = telegram.send_summary_if_pending()

        self.assertEqual(2, result["messages"])
        self.assertEqual(
            ["42", "84"],
            [call.kwargs["json"]["chat_id"] for call in post.call_args_list],
        )
        self.assertEqual(2, telegram.telegram_status()["recipient_count"])
        self.assertTrue(telegram._delivery_path().exists())


if __name__ == "__main__":
    unittest.main()
