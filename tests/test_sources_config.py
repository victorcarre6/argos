from collections import Counter
from pathlib import Path
import re
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

    def test_storage_and_collection_windows(self) -> None:
        self.assertGreater(self.config["storage"]["retention_days"], 0)
        self.assertGreater(self.config["collection"]["max_age_days"], 0)

    def test_tags_use_one_global_controlled_taxonomy(self) -> None:
        self.assertEqual(18, len(self.config["tags"]))
        self.assertTrue(all(self.config["tags"].values()))
        self.assertTrue(
            all(re.fullmatch(r"[a-z][a-z0-9_]*", tag) for tag in self.config["tags"])
        )
        self.assertTrue(
            all("keywords" not in category for category in self.config["categories"])
        )

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
                "Aggrégateurs",
                "Institutions publiques et politiques",
                "Frameworks et SDK",
                "Ops, Cloud et plateformes",
                "Sécurité, guardrails et évaluation",
                "Appels à projets et financements",
            }
            <= category_names
        )

    def test_merged_catalog_shape(self) -> None:
        self.assertEqual(8, len(self.config["categories"]))
        self.assertEqual(
            [
                "Aggrégateurs",
                "Laboratoires et providers",
                "Frameworks et SDK",
                "HPC",
                "Ops, Cloud et plateformes",
                "Sécurité, guardrails et évaluation",
                "Appels à projets et financements",
                "Institutions publiques et politiques",
            ],
            [category["name"] for category in self.config["categories"]],
        )
        self.assertEqual(134, len(self.sources))
        self.assertEqual(
            125,
            sum(source.get("enabled", True) is not False for source in self.sources),
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
            "https://github.com/OWASP/www-project-top-10-for-large-language-model-applications/releases.atom",
            "https://cyber.gouv.fr/actualites/rss/",
            "https://www.cert.ssi.gouv.fr/feed/",
            "https://www.cnil.fr/fr/rss.xml",
            "https://www.enisa.europa.eu/news/enisa-news/RSS",
            "https://eurohpc-ju.europa.eu/node/1/rss_en",
            "https://www.nsf.gov/rss/rss_www_funding_pgm_annc_inf.xml",
        }
        self.assertLessEqual(expected, source_urls)

    def test_repaired_sources_are_active_or_explicitly_disabled(self) -> None:
        by_name = {source["name"]: source for source in self.sources}
        repaired = {
            "AMD Blog": "https://gpuopen.com/feed.xml",
            "AMD ROCm Blog": "https://rocm.blogs.amd.com/blog/atom.xml",
            "Allen Institute for AI": "https://github.com/allenai/OLMo/releases.atom",
            "Arize AI Blog": "https://github.com/Arize-ai/phoenix/releases.atom",
            "Ben's Bites": "https://www.bensbites.com/feed",
            "BentoML Blog": "https://github.com/bentoml/BentoML/releases.atom",
            "Confluent Blog": "https://github.com/confluentinc/confluent-kafka-python/releases.atom",
            "Databricks Blog": "https://www.databricks.com/feed",
            "EleutherAI Blog": "https://github.com/EleutherAI/gpt-neox/releases.atom",
            "Haystack Blog": "https://github.com/deepset-ai/haystack/releases.atom",
            "KServe Blog": "https://github.com/kserve/kserve/releases.atom",
            "Keras Blog": "https://github.com/keras-team/keras/releases.atom",
            "Meta AI": "https://engineering.fb.com/feed/",
            "Milvus Blog": "https://github.com/milvus-io/milvus/releases.atom",
            "Mistral AI": "https://github.com/mistralai/client-python/releases.atom",
            "OWASP GenAI Security Project": "https://github.com/OWASP/www-project-top-10-for-large-language-model-applications/releases.atom",
            "OpenShift AI": "https://github.com/opendatahub-io/opendatahub-operator/releases.atom",
            "Qdrant Blog": "https://github.com/qdrant/qdrant/releases.atom",
            "Snowflake Blog": "https://github.com/snowflakedb/snowpark-python/releases.atom",
            "US NIST Artificial Intelligence": "https://www.nist.gov/news-events/artificial-intelligence/rss.xml",
            "Unstructured Blog": "https://github.com/Unstructured-IO/unstructured/releases.atom",
        }
        for name, url in repaired.items():
            self.assertEqual(url, by_name[name]["url"])
            self.assertIsNot(False, by_name[name].get("enabled", True))
        for name in {"ENISA News", "EuroHPC JU", "HaDEA", "OECD AI"}:
            self.assertIs(False, by_name[name].get("enabled"))


if __name__ == "__main__":
    unittest.main()
