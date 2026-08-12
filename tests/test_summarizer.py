import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("APP_ROOT", str(ROOT))

from rag import summarizer  # noqa: E402


class TelegramSummarizerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        directory = Path(self.temporary_directory.name)
        self.summary_path = directory / "summary.md"
        reports = directory / "reports"
        reports.mkdir()
        self.report_path = reports / "report_260812_1405.md"
        self.example = (ROOT / "data_example" / "report.md").read_text(encoding="utf-8")
        self.report_path.write_text(self.example, encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_large_report_becomes_plain_single_message(self) -> None:
        model = Mock()
        model.invoke.return_value.content = (
            "## Tendance\n\nLes agents progressent [1, 2].\n\n"
            "- L'inférence locale devient plus efficace."
        )
        with (
            patch.object(summarizer, "SUMMARY_PATH", self.summary_path),
            patch("rag.summarizer.chat_model", return_value=model),
            patch(
                "rag.summarizer.load_prompt",
                side_effect=lambda _section, _name, **values: values["report"],
            ),
        ):
            result = summarizer._build_graph().invoke({"max_chars": 500})

        content = result["content"]
        self.assertTrue(content.startswith("Rapport 12-08 14:05\n\n"))
        self.assertNotIn("##", content)
        self.assertNotIn("[1, 2]", content)
        self.assertNotIn("\n- ", content)
        self.assertLessEqual(len(content), 500)
        self.assertEqual(self.example, model.invoke.call_args.args[0])
        self.assertEqual(content, result["output_path"].read_text(encoding="utf-8"))

    def test_oversized_summary_is_rejected_instead_of_split(self) -> None:
        model = Mock()
        model.invoke.return_value.content = "x" * 600
        with (
            patch.object(summarizer, "SUMMARY_PATH", self.summary_path),
            patch("rag.summarizer.chat_model", return_value=model),
            patch("rag.summarizer.load_prompt", return_value="instruction"),
        ):
            with self.assertRaisesRegex(RuntimeError, "dépasse la limite"):
                summarizer._build_graph().invoke({"max_chars": 500})


if __name__ == "__main__":
    unittest.main()
