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

    def test_report_is_split_sent_once_and_marked_as_delivered(self) -> None:
        response = Mock(ok=True, status_code=200)
        with patch("system.telegram.requests.post", return_value=response) as post:
            result = telegram.send_summary_if_pending()
            second = telegram.send_summary_if_pending()

        self.assertTrue(result["sent"])
        self.assertGreater(result["messages"], 1)
        self.assertEqual("already_sent", second["reason"])
        self.assertEqual(result["messages"], post.call_count)
        self.assertTrue(telegram._delivery_path().exists())
        self.assertTrue(
            all(len(call.kwargs["json"]["text"]) <= 500 for call in post.call_args_list)
        )

    def test_failed_delivery_remains_pending_and_does_not_leak_token(self) -> None:
        response = Mock(ok=False, status_code=500)
        response.json.return_value = {"description": "temporary failure"}
        with patch("system.telegram.requests.post", return_value=response):
            with self.assertRaises(RuntimeError) as raised:
                telegram.send_summary_if_pending()

        self.assertNotIn("secret-token", str(raised.exception))
        self.assertTrue(telegram.telegram_status()["report_pending"])
        self.assertFalse(telegram._delivery_path().exists())


if __name__ == "__main__":
    unittest.main()
