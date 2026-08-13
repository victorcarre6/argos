import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("APP_ROOT", str(ROOT))

from rag.summary_agent import _closing_sentence, _compose_node, _save_node  # noqa: E402
from system.reports import (  # noqa: E402
    latest_report_path,
    report_generated_at,
    report_path,
)


class ReportHistoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.summary_path = Path(self.temporary_directory.name) / "summary.md"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_latest_report_uses_dated_name_and_ignores_other_files(self) -> None:
        directory = self.summary_path.parent / "reports"
        directory.mkdir()
        (directory / "report_260811_1800.md").write_text("ancien", encoding="utf-8")
        latest = directory / "report_260812_1000.md"
        latest.write_text("récent", encoding="utf-8")
        (directory / "notes.md").write_text("à ignorer", encoding="utf-8")

        self.assertEqual(latest, latest_report_path(self.summary_path))

    def test_legacy_summary_is_used_until_an_archive_exists(self) -> None:
        self.summary_path.write_text("rapport existant", encoding="utf-8")

        self.assertEqual(self.summary_path, latest_report_path(self.summary_path))

    def test_save_archives_report_and_updates_compatibility_copy(self) -> None:
        state = {
            "document": "# Rapport daté\n",
            "menu": "1. Sujet\nRésumé\n\n5. Autre\nAucun autre signal.",
            "drafts": [
                {"number": 1, "title": "Sujet", "content": "Texte"},
                {"number": 5, "title": "Autre", "content": "Aucun autre signal."},
            ],
            "generated_at": "2026-08-12T14:05:37+00:00",
        }
        with patch("rag.summary_agent.SUMMARY_PATH", self.summary_path):
            _save_node(state)

        archive = self.summary_path.parent / "reports" / "report_260812_1605.md"
        self.assertEqual(state["document"], archive.read_text(encoding="utf-8"))
        self.assertEqual(
            state["document"], self.summary_path.read_text(encoding="utf-8")
        )

    def test_compose_adds_date_to_title(self) -> None:
        result = _compose_node(
            {
                "drafts": [
                    {
                        "number": 1,
                        "title": "Sujet",
                        "overview": "Résumé",
                        "content": "Texte",
                    },
                    {
                        "number": 5,
                        "title": "Autre",
                        "overview": "Aucun autre signal.",
                        "content": "Aucun autre signal.",
                    },
                ],
                "signals": [{}],
            }
        )

        self.assertRegex(
            result["document"],
            r"^# Synthèse IA — \d{2}/\d{2}/\d{4} \d{2}:\d{2} CEST",
        )
        self.assertIn("generated_at", result)
        self.assertIn("5. Autre", result["menu"])
        self.assertIn("Réponds le numéro de la partie", result["menu"])
        self.assertTrue(result["menu"].endswith("télécharger le rapport complet."))

    def test_closing_sentence_uses_random_index(self) -> None:
        sentences = self.summary_path.parent / "sentences.yaml"
        sentences.write_text(
            'sentences:\n  - "Phrase A"\n  - "Phrase B"\n  - "Phrase C"\n',
            encoding="utf-8",
        )
        with (
            patch("rag.summary_agent.SENTENCES_PATH", sentences),
            patch("rag.summary_agent.randint", return_value=1) as randint,
        ):
            selected = _closing_sentence()

        self.assertEqual("Phrase B", selected)
        randint.assert_called_once_with(0, 2)

    def test_missing_sentence_file_omits_variable_phrase(self) -> None:
        missing = self.summary_path.parent / "missing-sentences.yaml"
        with patch("rag.summary_agent.SENTENCES_PATH", missing):
            selected = _closing_sentence()
            result = _compose_node(
                {
                    "drafts": [
                        {
                            "number": 5,
                            "title": "Autre",
                            "overview": "Aucun autre signal.",
                            "content": "Aucun autre signal.",
                        }
                    ],
                    "signals": [],
                }
            )

        self.assertEqual("", selected)
        self.assertIn("\n\nRéponds le numéro", result["menu"])

    def test_report_path_uses_requested_format(self) -> None:
        generated_at = datetime(2026, 8, 12, 14, 5, tzinfo=timezone.utc)

        self.assertEqual(
            "report_260812_1605.md", report_path(self.summary_path, generated_at).name
        )

    def test_legacy_utc_report_content_is_converted_to_paris_time(self) -> None:
        report = self.summary_path.parent / "report_260812_0848.md"
        report.write_text(
            "# Synthèse\n\n> Générée le 2026-08-12T08:48:00+00:00 à partir de 3 signaux.",
            encoding="utf-8",
        )

        generated_at = report_generated_at(report)

        self.assertEqual("2026-08-12T10:48:00+02:00", generated_at.isoformat())


if __name__ == "__main__":
    unittest.main()
