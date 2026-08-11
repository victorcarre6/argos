from collections import Counter
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_KEYS = {
    "recherche",
    "LLM",
    "IA Agentique",
    "Orchestration",
    "RAG",
    "Cloud",
    "HPC",
    "Deep Learning",
    "Ops",
    "Monitoring",
    "Politique",
    "Newsletter",
    "Cybersécurité",
    "Appels à projets",
}


class SourcesConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(
            (ROOT / "config/sources.yml").read_text(encoding="utf-8")
        )
        cls.sources = [
            source
            for category in cls.config["categories"]
            for source in category["sources"]
        ]

    def test_every_source_has_valid_keys(self) -> None:
        for source in self.sources:
            with self.subTest(source=source["name"]):
                self.assertTrue(source.get("keys"))
                self.assertLessEqual(set(source["keys"]), ALLOWED_KEYS)

    def test_every_source_has_valid_priority(self) -> None:
        for source in self.sources:
            with self.subTest(source=source["name"]):
                self.assertIn(source.get("priorité"), {1, 2, 3})

    def test_names_and_urls_are_unique(self) -> None:
        for field in ("name", "url"):
            duplicates = [
                value
                for value, count in Counter(
                    source[field] for source in self.sources
                ).items()
                if count > 1
            ]
            self.assertEqual([], duplicates, f"{field} dupliqué(s): {duplicates}")

    def test_requested_families_and_sources_are_present(self) -> None:
        category_names = {category["name"] for category in self.config["categories"]}
        self.assertTrue(
            {
                "Agrégateurs & publications",
                "Institutions publiques et politiques",
                "Frameworks agentiques & orchestration",
                "Sécurité, guardrails & évaluation IA",
                "Appels à projets & financements",
            }
            <= category_names
        )
        source_urls = {source["url"] for source in self.sources}
        expected = {
            "https://github.com/openai/openai-agents-python/releases.atom",
            "https://github.com/google/adk-python/releases.atom",
            "https://github.com/huggingface/smolagents/releases.atom",
            "https://github.com/stanfordnlp/dspy/releases.atom",
            "https://github.com/Azure/PyRIT/releases.atom",
            "https://github.com/NVIDIA/garak/releases.atom",
            "https://github.com/UKGovernmentBEIS/inspect_ai/releases.atom",
            "https://github.com/OWASP/Top10-for-Large-Language-Model-Applications/releases.atom",
            "https://cyber.gouv.fr/actualites/rss/",
            "https://www.cert.ssi.gouv.fr/feed/",
            "https://www.cnil.fr/fr/rss.xml",
            "https://www.enisa.europa.eu/news/enisa-news/RSS",
            "https://eurohpc-ju.europa.eu/node/1/rss_en",
            "https://www.nsf.gov/rss/rss_www_funding_pgm_annc_inf.xml",
        }
        self.assertLessEqual(expected, source_urls)


if __name__ == "__main__":
    unittest.main()
