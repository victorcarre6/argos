from collections import Counter
from pathlib import Path
import re
import unittest

import yaml

from feeds.collection import _source_tags

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

    def test_every_source_inherits_controlled_tags(self) -> None:
        taxonomy = set(self.config["tags"])
        for source in self.sources:
            with self.subTest(source=source["name"]):
                tags = _source_tags(source)
                self.assertTrue(tags)
                self.assertLessEqual(set(tags), taxonomy)

    def test_storage_and_collection_windows(self) -> None:
        self.assertGreater(self.config["storage"]["retention_days"], 0)
        self.assertGreater(self.config["collection"]["max_age_days"], 0)

    def test_tags_use_one_global_controlled_taxonomy(self) -> None:
        self.assertEqual(19, len(self.config["tags"]))
        self.assertEqual(
            ["release", "releases", "changelog"], self.config["tags"]["releases"]
        )
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
        self.assertEqual(126, len(self.sources))
        self.assertEqual(
            126,
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
            "https://eurohpc-ju.europa.eu/node/205/rss_en",
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

    def test_funding_sources_use_the_eight_validated_official_feeds(self) -> None:
        category = next(
            category
            for category in self.config["categories"]
            if category["name"] == "Appels à projets et financements"
        )
        expected = {
            "ANR": "https://anr.fr/rss/?aap",
            "European Innovation Council": "https://eic.ec.europa.eu/node/2/rss_en",
            "HaDEA": "https://hadea.ec.europa.eu/node/2/rss_en",
            "European Research Executive Agency": "https://rea.ec.europa.eu/node/2/rss_en",
            "Commission européenne — Recherche et innovation": "https://research-and-innovation.ec.europa.eu/node/2/rss_en",
            "EuroHPC JU": "https://eurohpc-ju.europa.eu/node/205/rss_en",
            "UK Research and Innovation": "https://www.ukri.org/opportunity/feed/",
            "US NSF — Funding opportunities": "https://www.nsf.gov/rss/rss_www_funding_pgm_annc_inf.xml",
        }
        self.assertEqual(
            expected,
            {source["name"]: source["url"] for source in category["sources"]},
        )
        self.assertTrue(
            all(
                source.get("enabled", True) is not False
                for source in category["sources"]
            )
        )


if __name__ == "__main__":
    unittest.main()
